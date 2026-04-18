"""Supabase sync functionality for GrantKit."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from supabase import Client, create_client

from .auth import get_authenticated_client, get_current_user_id, is_logged_in
from .budget.calculator import BudgetCalculator
from .references.bibtex_manager import BibTeXManager
from .sync_plan import SyncPlan, build_grant_plan, merge_plans
from .sync_state import (
    EntityState,
    GrantState,
    content_hash,
    load_state,
    save_state,
)

logger = logging.getLogger(__name__)

# Default Supabase config (can be overridden via env vars or config file)
DEFAULT_SUPABASE_URL = "https://bmfssahcufqykfagvgtm.supabase.co"


class SyncConflictError(RuntimeError):
    """Raised when push would overwrite concurrent cloud changes.

    The CLI catches this and shows the plan so AI agents can decide
    whether to pull, merge, or force-push.
    """

    def __init__(self, plan: SyncPlan):
        super().__init__(
            "Push blocked: cloud has changes not present locally. "
            "Run `grantkit sync status` to see what differs, pull to "
            "adopt cloud changes, or re-run push with --force to "
            "overwrite the cloud."
        )
        self.plan = plan


@dataclass
class SyncConfig:
    """Configuration for Supabase sync."""

    supabase_url: str
    supabase_key: str
    grants_dir: Path
    grant_id: Optional[str] = None  # If set, only sync this grant

    @classmethod
    def from_env(cls, grants_dir: Path) -> "SyncConfig":
        """Create config from environment variables."""
        url = os.environ.get("GRANTKIT_SUPABASE_URL", DEFAULT_SUPABASE_URL)
        key = os.environ.get("GRANTKIT_SUPABASE_KEY")

        if not key:
            raise ValueError(
                "GRANTKIT_SUPABASE_KEY environment variable is required. "
                "Get your key from https://supabase.com/dashboard/project/_/settings/api"
            )

        return cls(supabase_url=url, supabase_key=key, grants_dir=grants_dir)

    @classmethod
    def from_file(cls, config_path: Path, grants_dir: Path) -> "SyncConfig":
        """Create config from a YAML config file."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except OSError as e:
            raise ValueError(
                f"Could not read config file {config_path}: {e}"
            ) from e
        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML in config file {config_path}: {e}"
            ) from e

        sync_config = config.get("sync", {})
        url = sync_config.get(
            "supabase_url",
            os.environ.get("GRANTKIT_SUPABASE_URL", DEFAULT_SUPABASE_URL),
        )
        key = sync_config.get(
            "supabase_key", os.environ.get("GRANTKIT_SUPABASE_KEY")
        )

        if not key:
            raise ValueError(
                "Supabase key not found in config or environment. "
                "Set GRANTKIT_SUPABASE_KEY or add to grantkit.yaml"
            )

        return cls(
            supabase_url=url,
            supabase_key=key,
            grants_dir=grants_dir,
            grant_id=sync_config.get("grant_id"),
        )


class GrantKitSync:
    """Handles syncing between local files and Supabase."""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.client: Client = create_client(
            config.supabase_url, config.supabase_key
        )

    def pull(
        self,
        grant_id: Optional[str] = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Pull grants and responses from Supabase to local files.

        Args:
            grant_id: Optional specific grant to pull. If None, pulls all.
            dry_run: If True, compute and return the plan but don't
                write any files or update the sync baseline.
            force: Overwrite local files that have unsaved changes
                (LOCAL_ONLY_MODIFIED) or conflicts. Default False so we
                never lose an agent's in-progress edits by accident.

        Returns:
            Dict with stats about what was pulled. When ``dry_run`` is
            True the dict also includes ``"plan"`` (a ``SyncPlan``).

        Raises:
            SyncConflictError: if any entity is in CONFLICT and
                ``force`` is False.
        """
        stats: Dict[str, Any] = {
            "grants": 0,
            "responses": 0,
            "files_written": 0,
            "skipped_local_edits": [],
        }

        if dry_run:
            plan = self.compute_plan(grant_id=grant_id, include_cloud=True)
            stats["plan"] = plan
            stats["pull_candidates"] = len(plan.pull_candidates())
            stats["conflicts"] = len(
                [c for c in plan.changes if c.kind.name == "CONFLICT"]
            )
            return stats

        state = load_state(self.config.grants_dir)

        # Pre-flight: check for conflicts and local changes so a pull
        # cannot silently overwrite in-progress work.
        plan = self.compute_plan(grant_id=grant_id, include_cloud=True)
        if plan.has_conflicts and not force:
            raise SyncConflictError(plan)

        # Entities with local-only changes are kept as-is; we skip them
        # below and surface the list so the user can push them.
        local_edited: set = {
            (c.entity_type, c.grant_id, c.entity_id)
            for c in plan.changes
            if c.kind.name
            in ("LOCAL_ONLY_MODIFIED", "LOCAL_ONLY_ADDED", "LOCAL_DELETED")
        }
        if force:
            local_edited = set()

        # Fetch grants
        query = self.client.table("grants").select("*")
        if grant_id:
            query = query.eq("id", grant_id)
        elif self.config.grant_id:
            query = query.eq("id", self.config.grant_id)

        result = query.execute()
        grants = result.data

        for grant in grants:
            grant_dir = self.config.grants_dir / grant["id"]
            grant_dir.mkdir(parents=True, exist_ok=True)

            existing_grant_state = state.get_grant(grant["id"])
            grant_key = ("grant", grant["id"], grant["id"])
            if grant_key in local_edited:
                stats["skipped_local_edits"].append(f"grant {grant['id']}")
                # Keep the current baseline entry; we didn't write.
                grant_state = GrantState(
                    grant=existing_grant_state.grant,
                )
            else:
                grant_yaml_bytes = self._write_grant_yaml(grant_dir, grant)
                stats["files_written"] += 1
                stats["grants"] += 1
                grant_state = GrantState(
                    grant=EntityState(
                        updated_at=grant.get("updated_at"),
                        content_hash=content_hash(grant_yaml_bytes),
                    ),
                )

            # Fetch responses for this grant
            responses_result = (
                self.client.table("responses")
                .select("*")
                .eq("grant_id", grant["id"])
                .execute()
            )
            responses = responses_result.data

            # Create responses directory
            responses_dir = grant_dir / "responses"
            responses_dir.mkdir(exist_ok=True)

            for response in responses:
                resp_key = ("response", grant["id"], response["key"])
                if resp_key in local_edited:
                    stats["skipped_local_edits"].append(
                        f"{grant['id']}/responses/{response['key']}.md"
                    )
                    # Preserve existing baseline so subsequent pushes
                    # still detect the local edit against it.
                    existing = existing_grant_state.responses.get(
                        response["key"]
                    )
                    if existing:
                        grant_state.responses[response["key"]] = existing
                    continue
                filepath, body_bytes = self._write_response_file(
                    responses_dir, response
                )
                grant_state.responses[response["key"]] = EntityState(
                    updated_at=response.get("updated_at"),
                    content_hash=content_hash(body_bytes),
                )
                stats["files_written"] += 1
                stats["responses"] += 1

            # Pull bibliography entries into state so push can detect drift.
            try:
                bib_result = (
                    self.client.table("bibliography_entries")
                    .select("citation_key, raw_bibtex, updated_at")
                    .eq("grant_id", grant["id"])
                    .execute()
                )
                for entry in bib_result.data or []:
                    grant_state.bibliography_entries[entry["citation_key"]] = (
                        EntityState(
                            updated_at=entry.get("updated_at"),
                            content_hash=content_hash(
                                entry.get("raw_bibtex") or ""
                            ),
                        )
                    )
            except Exception as e:
                logger.debug(
                    "bibliography_entries not available on pull: %s", e
                )

            state.set_grant(grant["id"], grant_state)

            logger.info(
                f"Pulled grant '{grant['name']}' with "
                f"{len(responses)} responses"
            )

        save_state(self.config.grants_dir, state)

        return stats

    @staticmethod
    def _write_grant_yaml(grant_dir: Path, grant: Dict[str, Any]) -> str:
        """Serialize the grant to ``grant.yaml`` and return what we wrote."""
        grant_meta = {
            "id": grant["id"],
            "name": grant["name"],
            "foundation": grant["foundation"],
            "program": grant.get("program"),
            "deadline": grant.get("deadline"),
            "status": grant.get("status"),
            "amount_requested": grant.get("amount_requested"),
            "duration_years": grant.get("duration_years"),
            "solicitation_url": grant.get("solicitation_url"),
            "repo_url": grant.get("repo_url"),
        }
        text = yaml.dump(grant_meta, default_flow_style=False)
        (grant_dir / "grant.yaml").write_text(text, encoding="utf-8")
        return text

    @staticmethod
    def _write_response_file(
        responses_dir: Path, response: Dict[str, Any]
    ) -> Tuple[Path, str]:
        """Serialize a response to ``<key>.md`` and return (path, text)."""
        filename = f"{response['key']}.md"
        filepath = responses_dir / filename

        frontmatter = {
            "title": response.get("title", response["key"]),
            "key": response["key"],
            "status": response.get("status", "draft"),
            "word_limit": response.get("word_limit"),
            "char_limit": response.get("char_limit"),
            "question": response.get("question"),
        }
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}

        content = response.get("content", "")
        text = (
            "---\n"
            + yaml.dump(frontmatter, default_flow_style=False)
            + "---\n\n"
            + content
        )
        filepath.write_text(text, encoding="utf-8")
        return filepath, text

    # Known database columns for the grants table
    KNOWN_DB_COLUMNS = {
        "id",
        "name",
        "foundation",
        "program",
        "deadline",
        "status",
        "amount_requested",
        "duration_years",
        "solicitation_url",
        "repo_url",
        "fiscal_sponsor",
        "pi_name",
        "pi_email",
        "co_pi_name",
        "metadata",
        "project",
        "contact",
        "nsf_config",
        "scope",
        "impact",
        "advisors",
        "sustainability",
        "budget",
        "user_id",
        "accepts_markdown",
    }

    def _normalize_grant_yaml(
        self, grant_meta: Dict[str, Any], grant_dir_name: str
    ) -> Dict[str, Any]:
        """
        Normalize grant.yaml to database schema.

        Handles both flat format (simple) and nested format (PolicyEngine-style).
        Nested format has keys like 'metadata', 'project', 'contact', etc.
        """
        # Detect if this is nested format (has 'metadata' key)
        is_nested = "metadata" in grant_meta

        if is_nested:
            # Extract from nested structure
            metadata = grant_meta.get("metadata", {})
            project = grant_meta.get("project", {})
            contact = grant_meta.get("contact", {})
            status_info = grant_meta.get("status", {})

            db_record = {
                # Core flat fields from nested structure
                "id": metadata.get("grant_id", grant_dir_name),
                "name": metadata.get("name", grant_dir_name),
                "foundation": metadata.get("foundation"),
                "program": metadata.get("program"),
                "deadline": status_info.get("deadline"),
                "status": status_info.get("stage", "draft"),
                "amount_requested": project.get("total_budget"),
                "duration_years": project.get("duration_years"),
                "solicitation_url": metadata.get("solicitation_url"),
                "fiscal_sponsor": metadata.get("fiscal_sponsor"),
                # Contact fields
                "pi_name": contact.get("pi_name"),
                "pi_email": contact.get("pi_email"),
                "co_pi_name": contact.get("co_pi_name"),
                # JSONB columns for complex nested data
                "metadata": metadata,
                "project": project,
                "contact": contact,
                "nsf_config": grant_meta.get("nsf"),
                "scope": grant_meta.get("scope"),
                "impact": grant_meta.get("impact"),
                "advisors": grant_meta.get("advisors"),
                "sustainability": grant_meta.get("sustainability"),
                "budget": grant_meta.get("budget"),
            }
        else:
            # Flat format - filter to known DB columns only
            db_record = {
                k: v
                for k, v in grant_meta.items()
                if k in self.KNOWN_DB_COLUMNS
            }
            if "id" not in db_record:
                db_record["id"] = grant_dir_name

        # Remove None values to avoid overwriting with nulls
        db_record = {k: v for k, v in db_record.items() if v is not None}

        return db_record

    def _sync_budget_to_grant(
        self, grant_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """
        Sync budget.yaml to grant.yaml, updating amount_requested.

        Args:
            grant_dir: Path to grant directory

        Returns:
            Budget summary dict if budget.yaml exists, None otherwise
        """
        budget_yaml = grant_dir / "budget.yaml"
        grant_yaml = grant_dir / "grant.yaml"

        if not budget_yaml.exists():
            return None

        # Read budget.yaml first to check format
        with open(budget_yaml) as f:
            budget_data = yaml.safe_load(f)

        # Check if this is a simple format with pre-calculated totals
        # (e.g., Nuffield-style) vs NSF format with line items
        if "totals" in budget_data and "grand_total" in budget_data["totals"]:
            # Use pre-calculated total from budget.yaml
            total = budget_data["totals"]["grand_total"]
            summary = budget_data.get("totals", {})
        else:
            # Calculate budget totals using NSF-style calculator
            calculator = BudgetCalculator(budget_yaml)
            summary = calculator.get_summary()
            total = summary["grand_total"]

        # Read current grant.yaml
        with open(grant_yaml) as f:
            grant_meta = yaml.safe_load(f) or {}

        # Update amount_requested
        grant_meta["amount_requested"] = total

        # Also update research_gov.total_requested if present
        if "research_gov" in grant_meta:
            grant_meta["research_gov"]["total_requested"] = total

        # Write back to grant.yaml
        with open(grant_yaml, "w") as f:
            yaml.dump(grant_meta, f, default_flow_style=False, sort_keys=False)

        # Add calculated summary to budget data for JSONB storage
        budget_data["summary"] = summary

        return budget_data

    def _auto_generate_bibliography(
        self, grant_dir: Path, grant_meta: Dict[str, Any]
    ) -> bool:
        """
        Auto-generate bibliography section from used citations.

        Scans all response files for [@key] citations, looks up entries
        in references.bib, and generates the bibliography file.

        Args:
            grant_dir: Path to grant directory
            grant_meta: Parsed grant.yaml metadata

        Returns:
            True if bibliography was generated, False otherwise
        """
        import re

        # Find bibliography section with auto_generate: true
        sections = grant_meta.get("full_application", {}).get(
            "sections", grant_meta.get("sections", [])
        )

        bib_section = None
        for section in sections:
            if (
                section.get("auto_generate")
                and section.get("type") == "bibliography"
            ):
                bib_section = section
                break

        if not bib_section:
            return False

        # Load bibtex
        bib_manager = BibTeXManager(grant_dir)
        bib_manager.load_bibliography()

        if not bib_manager.entries:
            logger.warning("No bibliography entries found for auto-generation")
            return False

        # Find all response files
        response_dirs = [
            grant_dir / "responses" / "full",
            grant_dir / "responses",
            grant_dir / "docs" / "responses",
        ]

        responses_dir = None
        for d in response_dirs:
            if d.exists():
                responses_dir = d
                break

        if not responses_dir:
            return False

        # Scan for citations
        used_keys = set()
        citation_pattern = re.compile(r"\[@([^\]]+)\]")

        bib_file_path = grant_dir / bib_section.get("file", "")

        for md_file in responses_dir.glob("*.md"):
            # Skip the bibliography file itself
            if md_file.resolve() == bib_file_path.resolve():
                continue

            content = md_file.read_text(encoding="utf-8")
            for match in citation_pattern.finditer(content):
                citation_text = match.group(1)
                # Handle multiple citations: [@key1; @key2]
                keys = [
                    k.strip().lstrip("@")
                    for k in re.split(r"[;,]", citation_text)
                ]
                used_keys.update(k for k in keys if k)

        if not used_keys:
            logger.info("No citations found in response files")
            return False

        # Sort entries alphabetically by first author
        def get_sort_key(key):
            entry = bib_manager.get_entry(key)
            if entry and entry.authors:
                first_author = entry.authors[0]
                if "," in first_author:
                    return first_author.split(",")[0].lower()
                parts = first_author.split()
                return parts[-1].lower() if parts else key.lower()
            return key.lower()

        sorted_keys = sorted(used_keys, key=get_sort_key)

        # Group entries by category (based on bibtex comments)
        # For now, generate a flat list
        bib_lines = []

        for key in sorted_keys:
            entry = bib_manager.get_entry(key)
            if not entry:
                logger.warning(
                    f"Citation key '{key}' not found in bibliography"
                )
                continue

            # Format entry
            formatted = self._format_bibliography_entry(entry)
            bib_lines.append(formatted)

        # Write bibliography file
        output_path = grant_dir / bib_section["file"]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content = "\n\n".join(bib_lines)
        output_path.write_text(content, encoding="utf-8")

        logger.info(
            f"Generated bibliography with {len(bib_lines)} entries at {output_path}"
        )
        return True

    def _format_bibliography_entry(self, entry) -> str:
        """Format a BibEntry as a plain-text citation for bibliography."""
        # Format authors
        if entry.authors:
            if len(entry.authors) == 1:
                authors_str = entry.authors[0]
            elif len(entry.authors) == 2:
                authors_str = f"{entry.authors[0]} & {entry.authors[1]}"
            else:
                authors_str = (
                    ", ".join(entry.authors[:-1]) + f", & {entry.authors[-1]}"
                )
        else:
            authors_str = "Unknown"

        year = entry.year or "n.d."
        title = entry.title or "Untitled"
        entry_type = entry.entry_type.lower()

        # Build citation based on entry type
        if entry_type == "article":
            journal = entry.journal or ""
            volume = entry.volume or ""
            pages = entry.pages or ""

            citation = f"{authors_str} ({year}). {title}."
            if journal:
                citation += f" {journal}"
                if volume:
                    citation += f", {volume}"
                if pages:
                    citation += f", {pages}"
                citation += "."
        elif entry_type in ("book", "incollection"):
            publisher = entry.raw_entry.get("publisher", "")
            citation = f"{authors_str} ({year}). {title}."
            if publisher:
                citation += f" {publisher}."
        elif entry_type in ("techreport", "misc"):
            institution = entry.raw_entry.get("institution", "")
            url = entry.url or ""
            citation = f"{authors_str} ({year}). {title}."
            if institution:
                citation += f" {institution}."
            if url:
                citation += f" Retrieved from {url}"
        else:
            citation = f"{authors_str} ({year}). {title}."
            if entry.url:
                citation += f" Retrieved from {entry.url}"

        return citation

    def push(
        self,
        grant_id: Optional[str] = None,
        force: bool = False,
        dry_run: bool = False,
        regenerate_bibliography: Optional[bool] = None,
        with_deletes: bool = False,
    ) -> Dict[str, Any]:
        """
        Push local files to Supabase.

        Args:
            grant_id: Optional specific grant to push. If None, pushes all.
            force: Skip the "cloud has moved on" check and overwrite.
            dry_run: Compute the plan and return it without pushing.
            regenerate_bibliography: None = auto-regen when configured,
                but skip (with a warning) if the bibliography file has
                diverged from the last-regen hash. True = always
                regenerate. False = never regenerate.
            with_deletes: If True, delete cloud rows for response or
                bibliography entries that were in the sync baseline but
                are no longer on disk. Default False to avoid
                destructive surprises. Deletions for entities that
                changed on cloud since the last pull are still blocked
                (conflict), matching the existing modify semantics.

        Returns:
            Stats dict. In dry-run mode it also contains ``"plan"``.

        Raises:
            SyncConflictError: if the cloud has moved on for any
                entity with local changes and ``force`` is False.
        """
        stats: Dict[str, Any] = {
            "grants": 0,
            "responses": 0,
            "deleted": 0,
            "errors": [],
        }

        grant_dirs = self._resolve_grant_dirs(grant_id)
        state = load_state(self.config.grants_dir)

        # --- Phase 1: prepare (apply implicit mutations with warnings,
        # compute local hashes, fetch cloud timestamps, build plan). ---
        prepared: List[Dict[str, Any]] = []
        per_grant_plans: List[SyncPlan] = []
        for grant_dir in grant_dirs:
            prep = self._prepare_push_for_grant(
                grant_dir, regenerate_bibliography, stats
            )
            if prep is None:
                continue
            cloud = self._fetch_cloud_updated_at(prep["grant_id"])
            prep["cloud"] = cloud
            plan = build_grant_plan(
                grant_id=prep["grant_id"],
                local_grant_hash=prep["grant_hash"],
                cloud_grant_updated_at=cloud["grant_updated_at"],
                local_response_hashes=prep["response_hashes"],
                cloud_response_updated_at=cloud["responses"],
                local_bib_hashes=prep["bib_hashes"],
                cloud_bib_updated_at=cloud["bib"],
                state=state.get_grant(prep["grant_id"]),
            )
            prep["plan"] = plan
            per_grant_plans.append(plan)
            prepared.append(prep)

        plan = merge_plans(per_grant_plans)
        stats["plan"] = plan

        if dry_run:
            stats["push_candidates"] = len(plan.push_candidates())
            stats["delete_candidates"] = len(plan.delete_candidates())
            stats["conflicts"] = len(
                [c for c in plan.changes if c.kind.name == "CONFLICT"]
            )
            return stats

        if plan.has_conflicts and not force:
            raise SyncConflictError(plan)

        # --- Phase 2: execute pushes and record new baseline. ---
        user_id = get_current_user_id()
        for prep in prepared:
            grant_state = state.get_grant(prep["grant_id"])
            self._execute_push_for_grant(prep, user_id, stats, grant_state)
            if with_deletes:
                self._execute_deletes_for_grant(
                    prep["plan"], stats, grant_state
                )
            state.set_grant(prep["grant_id"], grant_state)

        # Surface skipped deletions so agents realize nothing happened
        # for those entries (they need to pass --with-deletes).
        skipped = plan.delete_candidates()
        if skipped and not with_deletes:
            stats["deletions_skipped"] = [
                {"grant_id": c.grant_id, "entity": c.entity_id}
                for c in skipped
            ]

        save_state(self.config.grants_dir, state)
        return stats

    # ------------------------------------------------------------------
    # Push pipeline helpers
    # ------------------------------------------------------------------

    def _resolve_grant_dirs(self, grant_id: Optional[str]) -> List[Path]:
        if grant_id:
            return [self.config.grants_dir / grant_id]
        if self.config.grant_id:
            return [self.config.grants_dir / self.config.grant_id]
        return [
            d
            for d in self.config.grants_dir.iterdir()
            if d.is_dir() and (d / "grant.yaml").exists()
        ]

    def _prepare_push_for_grant(
        self,
        grant_dir: Path,
        regenerate_bibliography: Optional[bool],
        stats: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Apply implicit mutations (with warnings) and compute hashes.

        Returns a dict with everything ``_execute_push_for_grant`` needs,
        or None if the directory should be skipped.
        """
        grant_yaml = grant_dir / "grant.yaml"
        if not grant_yaml.exists():
            logger.warning(f"No grant.yaml in {grant_dir}, skipping")
            return None

        # Implicit mutation: budget.yaml -> grant.yaml. We warn so agents
        # can see that their grant.yaml may have been rewritten in place.
        budget_data = self._sync_budget_to_grant_with_notice(grant_dir, stats)

        with open(grant_yaml) as f:
            grant_meta = yaml.safe_load(f)

        # Implicit mutation: auto-regenerate bibliography markdown from
        # citations in responses. Skip when the user has manually edited
        # the file, unless they explicitly opt in.
        bib_generated = self._maybe_regenerate_bibliography(
            grant_dir,
            grant_meta,
            regenerate_bibliography,
            stats,
        )
        if bib_generated:
            stats["bibliography_generated"] = True

        # Normalize to DB schema and compute local hashes for conflict
        # detection.
        db_record = self._normalize_grant_yaml(grant_meta, grant_dir.name)
        if budget_data:
            db_record["budget"] = budget_data

        grant_hash = content_hash(grant_yaml.read_text(encoding="utf-8"))

        # Locate responses directory (multi-layout support).
        responses_dir = next(
            (
                d
                for d in [
                    grant_dir / "responses" / "full",
                    grant_dir / "responses",
                    grant_dir / "docs" / "responses",
                ]
                if d.exists()
            ),
            None,
        )
        response_hashes: Dict[str, str] = {}
        response_files: Dict[str, Path] = {}
        if responses_dir:
            for md_file in responses_dir.glob("*.md"):
                response_data = self._parse_response_file(
                    md_file, db_record["id"]
                )
                key = response_data["key"]
                response_hashes[key] = content_hash(
                    md_file.read_text(encoding="utf-8")
                )
                response_files[key] = md_file

        # Compute bibliography entry hashes from references.bib.
        bib_hashes: Dict[str, str] = {}
        bib_file = self._locate_bib_file(grant_dir)
        if bib_file:
            bib_manager = BibTeXManager(grant_dir)
            bib_manager.load_bibliography(bib_file)
            for key, entry in bib_manager.entries.items():
                bib_hashes[key] = content_hash(self._entry_to_bibtex(entry))

        return {
            "grant_dir": grant_dir,
            "grant_id": db_record["id"],
            "grant_meta": grant_meta,
            "db_record": db_record,
            "budget_data": budget_data,
            "grant_hash": grant_hash,
            "response_hashes": response_hashes,
            "response_files": response_files,
            "responses_dir": responses_dir,
            "bib_hashes": bib_hashes,
            "bib_file": bib_file,
        }

    def _execute_push_for_grant(
        self,
        prep: Dict[str, Any],
        user_id: Optional[str],
        stats: Dict[str, Any],
        grant_state: GrantState,
    ) -> None:
        db_record = dict(prep["db_record"])
        if user_id:
            db_record["user_id"] = user_id

        # Upsert grant
        try:
            result = (
                self.client.table("grants")
                .upsert(db_record, on_conflict="id")
                .execute()
            )
            stats["grants"] += 1
            logger.info(
                f"Pushed grant '{db_record.get('name', prep['grant_id'])}'"
            )
            updated_at = self._extract_updated_at(result)
            grant_state.grant = EntityState(
                updated_at=updated_at,
                content_hash=prep["grant_hash"],
            )
        except Exception as e:
            stats["errors"].append(f"Grant {prep['grant_id']}: {e}")
            logger.error(f"Failed to push grant {prep['grant_id']}: {e}")
            logger.debug("Supabase upsert error details", exc_info=True)
            return

        # Build section lookup (word_limit/char_limit/sort_order).
        sections = (
            prep["grant_meta"]
            .get("full_application", {})
            .get("sections", prep["grant_meta"].get("sections", []))
        )
        section_by_file: Dict[str, Dict[str, Any]] = {}
        for idx, section in enumerate(sections):
            if section.get("file"):
                section_by_file[section["file"]] = {
                    **section,
                    "_sort_order": idx,
                }

        # Push responses and update per-response baseline.
        if prep["responses_dir"]:
            sort_order_supported = True
            for key, md_file in prep["response_files"].items():
                response_data = self._parse_response_file(
                    md_file, prep["grant_id"]
                )
                relative_path = md_file.relative_to(prep["grant_dir"])
                section_meta = section_by_file.get(str(relative_path), {})
                for field_name in ("word_limit", "char_limit", "question"):
                    if section_meta.get(field_name) and not response_data.get(
                        field_name
                    ):
                        response_data[field_name] = section_meta[field_name]
                if "_sort_order" in section_meta and sort_order_supported:
                    response_data["sort_order"] = section_meta["_sort_order"]

                success, sort_order_supported, updated_at = (
                    self._upsert_response(
                        response_data,
                        md_file.name,
                        stats,
                        sort_order_supported,
                    )
                )
                if success:
                    grant_state.responses[key] = EntityState(
                        updated_at=updated_at,
                        content_hash=prep["response_hashes"][key],
                    )

        # Push bibliography entries.
        bib_stats = self._sync_bibliography(
            prep["grant_dir"],
            prep["grant_id"],
            grant_state=grant_state,
            local_hashes=prep["bib_hashes"],
        )
        if bib_stats:
            stats["bibliography_entries"] = (
                stats.get("bibliography_entries", 0) + bib_stats["entries"]
            )

    def _execute_deletes_for_grant(
        self,
        plan: SyncPlan,
        stats: Dict[str, Any],
        grant_state: GrantState,
    ) -> None:
        """Issue DELETEs for LOCAL_DELETED entities under this grant.

        Conflicts (cloud moved after last pull) are never deleted here —
        they would have blocked the push in the conflict check above
        unless ``force=True`` was set, in which case the agent has
        explicitly opted in to overwriting.
        """
        for change in plan.delete_candidates():
            if change.entity_type == "response":
                try:
                    self.client.table("responses").delete().eq(
                        "grant_id", change.grant_id
                    ).eq("key", change.entity_id).execute()
                    grant_state.responses.pop(change.entity_id, None)
                    stats["deleted"] = stats.get("deleted", 0) + 1
                except Exception as e:
                    stats["errors"].append(
                        f"Delete response {change.entity_id}: {e}"
                    )
                    logger.error(
                        "Failed to delete response %s: %s",
                        change.entity_id,
                        e,
                    )
            elif change.entity_type == "bibliography_entry":
                try:
                    self.client.table("bibliography_entries").delete().eq(
                        "grant_id", change.grant_id
                    ).eq("citation_key", change.entity_id).execute()
                    grant_state.bibliography_entries.pop(
                        change.entity_id, None
                    )
                    stats["deleted"] = stats.get("deleted", 0) + 1
                except Exception as e:
                    stats["errors"].append(
                        f"Delete bib entry {change.entity_id}: {e}"
                    )
                    logger.error(
                        "Failed to delete bib entry %s: %s",
                        change.entity_id,
                        e,
                    )
            # Grants themselves are never deleted via push; users remove
            # grants through explicit `grantkit archive` flows.

    # ------------------------------------------------------------------
    # Cloud timestamp probe (for plan computation)
    # ------------------------------------------------------------------

    def _fetch_cloud_updated_at(self, grant_id: str) -> Dict[str, Any]:
        """Fetch just the ``updated_at`` columns for conflict detection.

        Resilient to malformed responses: any value that isn't a real
        list-of-dicts (e.g. from a mocked client in tests) is treated
        as "cloud row does not exist".
        """
        result: Dict[str, Any] = {
            "grant_updated_at": None,
            "responses": {},
            "bib": {},
        }
        rows = self._safe_select(
            "grants",
            "id, updated_at",
            {"id": grant_id},
            context=f"grant {grant_id}",
        )
        if rows:
            result["grant_updated_at"] = rows[0].get("updated_at")

        for row in self._safe_select(
            "responses",
            "key, updated_at",
            {"grant_id": grant_id},
            context=f"responses for {grant_id}",
        ):
            key = row.get("key")
            if key:
                result["responses"][key] = row.get("updated_at")

        for row in self._safe_select(
            "bibliography_entries",
            "citation_key, updated_at",
            {"grant_id": grant_id},
            context=f"bibliography for {grant_id}",
        ):
            key = row.get("citation_key")
            if key:
                result["bib"][key] = row.get("updated_at")

        return result

    def _safe_select(
        self,
        table: str,
        columns: str,
        filters: Dict[str, Any],
        context: str,
    ) -> List[Dict[str, Any]]:
        """Run a select and return a list of dicts, or [] on any error.

        This is the one place we centralize "cloud may not have this
        table / row / shape" handling so plan computation never raises.
        """
        try:
            query = self.client.table(table).select(columns)
            for col, val in filters.items():
                query = query.eq(col, val)
            response = query.execute()
        except Exception as e:
            logger.debug("Cloud select failed for %s: %s", context, e)
            return []
        data = getattr(response, "data", None)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    @staticmethod
    def _extract_updated_at(result: Any) -> Optional[str]:
        """Extract ``updated_at`` from an upsert response, if available."""
        data = getattr(result, "data", None)
        if not data:
            return None
        if isinstance(data, list) and data:
            return data[0].get("updated_at")
        if isinstance(data, dict):
            return data.get("updated_at")
        return None

    @staticmethod
    def _locate_bib_file(grant_dir: Path) -> Optional[Path]:
        for candidate in (
            grant_dir / "references.bib",
            grant_dir / "bibliography.bib",
            grant_dir / "refs.bib",
        ):
            if candidate.exists():
                return candidate
        return None

    # ------------------------------------------------------------------
    # Implicit-mutation wrappers
    # ------------------------------------------------------------------

    def _sync_budget_to_grant_with_notice(
        self, grant_dir: Path, stats: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Wrap ``_sync_budget_to_grant`` so agents see that grant.yaml
        may have been rewritten in place.
        """
        grant_yaml = grant_dir / "grant.yaml"
        before_hash: Optional[str] = None
        if grant_yaml.exists():
            before_hash = content_hash(grant_yaml.read_text(encoding="utf-8"))

        budget_data = self._sync_budget_to_grant(grant_dir)

        if budget_data is not None and before_hash is not None:
            after_hash = content_hash(grant_yaml.read_text(encoding="utf-8"))
            if before_hash != after_hash:
                logger.warning(
                    "%s: budget.yaml updated grant.yaml "
                    "amount_requested; commit this change",
                    grant_dir.name,
                )
                stats.setdefault("grant_yaml_updated_from_budget", []).append(
                    grant_dir.name
                )

        return budget_data

    def _maybe_regenerate_bibliography(
        self,
        grant_dir: Path,
        grant_meta: Dict[str, Any],
        regenerate: Optional[bool],
        stats: Dict[str, Any],
    ) -> bool:
        """Decide whether to auto-regenerate the bibliography file.

        Auto-regen would silently overwrite manual edits, which is a
        nasty surprise for an AI agent. We regenerate only when:

        * ``regenerate`` is explicitly True, or
        * ``regenerate`` is None and the bibliography file either does
          not exist yet or matches the last regen output exactly.

        Manual edits are detected by hashing the current file and
        comparing to the hash we produced the last time we wrote it,
        stored in a sidecar ``.grantkit/state.json`` baseline under the
        bibliography entity (the file itself isn't tracked there, so we
        take a conservative approach: if the file exists and
        ``regenerate`` is None, skip with a warning).
        """
        if regenerate is False:
            return False

        sections = grant_meta.get("full_application", {}).get(
            "sections", grant_meta.get("sections", [])
        )
        bib_section = next(
            (
                s
                for s in sections
                if s.get("auto_generate") and s.get("type") == "bibliography"
            ),
            None,
        )
        if not bib_section:
            return False

        output_path = grant_dir / bib_section.get("file", "")
        if regenerate is True or not output_path.exists():
            return self._auto_generate_bibliography(grant_dir, grant_meta)

        # Conservative default: don't silently rewrite a file that
        # already exists. Surface the skip so agents can pass
        # --regenerate-bibliography when they actually want it.
        logger.warning(
            "%s: skipping bibliography regen to avoid overwriting "
            "%s; pass --regenerate-bibliography to force.",
            grant_dir.name,
            output_path.relative_to(grant_dir),
        )
        stats.setdefault("bibliography_skipped", []).append(grant_dir.name)
        return False

    # ------------------------------------------------------------------
    # Plan computation (used by status, diff, and dry-run)
    # ------------------------------------------------------------------

    def compute_plan(
        self,
        grant_id: Optional[str] = None,
        include_cloud: bool = True,
    ) -> SyncPlan:
        """Return what a sync would do, without performing it.

        ``include_cloud=False`` is a fast path for offline "what have I
        changed locally?" queries.
        """
        state = load_state(self.config.grants_dir)
        grant_dirs = self._resolve_grant_dirs(grant_id)

        plans: List[SyncPlan] = []
        for grant_dir in grant_dirs:
            grant_yaml = grant_dir / "grant.yaml"
            if not grant_yaml.exists():
                continue

            gid = grant_dir.name
            # Best-effort grant id extraction (matches push normalization).
            try:
                with open(grant_yaml) as f:
                    grant_meta = yaml.safe_load(f) or {}
                gid = (
                    grant_meta.get("id")
                    or grant_meta.get("metadata", {}).get("grant_id")
                    or grant_dir.name
                )
            except Exception:
                grant_meta = {}

            grant_hash: Optional[str] = content_hash(
                grant_yaml.read_text(encoding="utf-8")
            )
            response_hashes: Dict[str, str] = {}
            responses_dir = next(
                (
                    d
                    for d in [
                        grant_dir / "responses" / "full",
                        grant_dir / "responses",
                        grant_dir / "docs" / "responses",
                    ]
                    if d.exists()
                ),
                None,
            )
            if responses_dir:
                for md_file in responses_dir.glob("*.md"):
                    key = self._parse_response_file(md_file, gid)["key"]
                    response_hashes[key] = content_hash(
                        md_file.read_text(encoding="utf-8")
                    )

            bib_hashes: Dict[str, str] = {}
            bib_file = self._locate_bib_file(grant_dir)
            if bib_file:
                bib_manager = BibTeXManager(grant_dir)
                bib_manager.load_bibliography(bib_file)
                for k, entry in bib_manager.entries.items():
                    bib_hashes[k] = content_hash(self._entry_to_bibtex(entry))

            if include_cloud:
                cloud = self._fetch_cloud_updated_at(gid)
            else:
                cloud = {
                    "grant_updated_at": state.get_grant(gid).grant.updated_at,
                    "responses": {
                        k: v.updated_at
                        for k, v in state.get_grant(gid).responses.items()
                    },
                    "bib": {
                        k: v.updated_at
                        for k, v in state.get_grant(
                            gid
                        ).bibliography_entries.items()
                    },
                }

            plans.append(
                build_grant_plan(
                    grant_id=gid,
                    local_grant_hash=grant_hash,
                    cloud_grant_updated_at=cloud["grant_updated_at"],
                    local_response_hashes=response_hashes,
                    cloud_response_updated_at=cloud["responses"],
                    local_bib_hashes=bib_hashes,
                    cloud_bib_updated_at=cloud["bib"],
                    state=state.get_grant(gid),
                )
            )

        return merge_plans(plans)

    def _upsert_response(
        self,
        response_data: Dict[str, Any],
        filename: str,
        stats: Dict[str, Any],
        sort_order_supported: bool,
    ) -> Tuple[bool, bool, Optional[str]]:
        """
        Upsert a response to the database, handling sort_order column gracefully.

        Returns:
            Tuple of (success, sort_order_supported, updated_at). The
            third element is the cloud's ``updated_at`` timestamp after
            the write, used to refresh the sync baseline.
        """
        try:
            result = (
                self.client.table("responses")
                .upsert(response_data, on_conflict="grant_id,key")
                .execute()
            )
            stats["responses"] += 1
            return True, sort_order_supported, self._extract_updated_at(result)
        except Exception as e:
            error_str = str(e)
            # Check if sort_order column doesn't exist
            if "sort_order" in error_str and (
                "PGRST204" in error_str
                or "could not find" in error_str.lower()
            ):
                response_data.pop("sort_order", None)
                try:
                    result = (
                        self.client.table("responses")
                        .upsert(response_data, on_conflict="grant_id,key")
                        .execute()
                    )
                    stats["responses"] += 1
                    logger.debug(
                        "sort_order column not found, syncing without it. "
                        "Run migration to enable response ordering."
                    )
                    return True, False, self._extract_updated_at(result)
                except Exception as retry_e:
                    stats["errors"].append(f"Response {filename}: {retry_e}")
                    logger.error(
                        f"Failed to push response {filename}: {retry_e}"
                    )
                    logger.debug(
                        "Response upsert retry error details", exc_info=True
                    )
                    return False, False, None
            else:
                stats["errors"].append(f"Response {filename}: {e}")
                logger.error(f"Failed to push response {filename}: {e}")
                logger.debug("Response upsert error details", exc_info=True)
                return False, sort_order_supported, None

    def _sync_bibliography(
        self,
        grant_dir: Path,
        grant_id: str,
        grant_state: Optional[GrantState] = None,
        local_hashes: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, int]]:
        """
        Sync references.bib to bibliography_entries table.

        Args:
            grant_dir: Path to grant directory
            grant_id: Grant ID for database
            grant_state: Optional grant state to update with per-entry
                baselines after successful pushes.
            local_hashes: Optional precomputed per-entry hashes so the
                caller and this method agree on what "baseline" means.

        Returns:
            Dict with sync stats, or None if no .bib file found or table doesn't exist
        """
        # Look for .bib files in common locations
        bib_locations = [
            grant_dir / "references.bib",
            grant_dir / "bibliography.bib",
            grant_dir / "refs.bib",
        ]

        bib_file = next((loc for loc in bib_locations if loc.exists()), None)
        if not bib_file:
            return None

        try:
            # Parse bibtex using existing manager
            bib_manager = BibTeXManager(grant_dir)
            bib_manager.load_bibliography(bib_file)

            if not bib_manager.entries:
                logger.info(f"No entries found in {bib_file.name}")
                return {"entries": 0}

            # Calculate display_year with letter suffixes for disambiguation
            display_years = self._calculate_display_years(bib_manager.entries)

            entries_synced = 0
            display_year_supported = (
                True  # Assume supported until proven otherwise
            )

            for key, entry in bib_manager.entries.items():
                db_entry = {
                    "grant_id": grant_id,
                    "citation_key": key,
                    "entry_type": entry.entry_type,
                    "title": entry.title or "Untitled",
                    "authors": entry.authors or None,
                    "year": entry.year,
                    "journal": entry.journal or None,
                    "volume": entry.volume,
                    "pages": entry.pages,
                    "publisher": entry.raw_entry.get("publisher"),
                    "institution": entry.raw_entry.get("institution"),
                    "url": entry.url,
                    "doi": entry.doi,
                    "raw_bibtex": self._entry_to_bibtex(entry),
                }

                # Add display_year if column exists
                if display_year_supported:
                    db_entry["display_year"] = display_years.get(
                        key, entry.year
                    )

                # Remove None values
                db_entry = {k: v for k, v in db_entry.items() if v is not None}

                try:
                    result = (
                        self.client.table("bibliography_entries")
                        .upsert(db_entry, on_conflict="grant_id,citation_key")
                        .execute()
                    )
                    entries_synced += 1
                    self._record_bib_baseline(
                        grant_state, local_hashes, key, result
                    )
                except Exception as e:
                    error_str = str(e)
                    # Table doesn't exist - log once and return early
                    if (
                        "404" in error_str
                        or "does not exist" in error_str.lower()
                    ):
                        logger.debug(
                            "bibliography_entries table not found, skipping sync. "
                            "Run migration to enable this feature."
                        )
                        return None
                    # display_year column doesn't exist - retry without it
                    if "display_year" in error_str and "PGRST204" in error_str:
                        display_year_supported = False
                        db_entry.pop("display_year", None)
                        try:
                            result = (
                                self.client.table("bibliography_entries")
                                .upsert(
                                    db_entry,
                                    on_conflict="grant_id,citation_key",
                                )
                                .execute()
                            )
                            entries_synced += 1
                            self._record_bib_baseline(
                                grant_state, local_hashes, key, result
                            )
                            continue
                        except Exception as retry_e:
                            logger.error(
                                f"Failed to sync bibliography entry {key}: {retry_e}"
                            )
                            logger.debug(
                                "Bibliography upsert retry error",
                                exc_info=True,
                            )
                            continue
                    logger.error(
                        f"Failed to sync bibliography entry {key}: {e}"
                    )
                    logger.debug(
                        "Bibliography upsert error details", exc_info=True
                    )

            if entries_synced > 0:
                logger.info(
                    f"Synced {entries_synced} bibliography entries from {bib_file.name}"
                )
            return {"entries": entries_synced}

        except Exception as e:
            logger.error(f"Failed to sync bibliography from {bib_file}: {e}")
            logger.debug("Bibliography sync error details", exc_info=True)
            return None

    def _record_bib_baseline(
        self,
        grant_state: Optional[GrantState],
        local_hashes: Optional[Dict[str, str]],
        key: str,
        result: Any,
    ) -> None:
        """Persist the post-push baseline for a single bibliography entry."""
        if grant_state is None or local_hashes is None:
            return
        hash_value = local_hashes.get(key)
        if not hash_value:
            return
        grant_state.bibliography_entries[key] = EntityState(
            updated_at=self._extract_updated_at(result),
            content_hash=hash_value,
        )

    def _calculate_display_years(
        self, entries: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Calculate display years with letter suffixes for disambiguation.

        When multiple entries share the same first author and year,
        adds letter suffixes (a, b, c...) to distinguish them.

        Args:
            entries: Dict of citation_key -> BibEntry

        Returns:
            Dict of citation_key -> display_year (e.g., "2025a")
        """
        from collections import defaultdict

        # Group entries by (first_author, year)
        author_year_groups = defaultdict(list)
        for key, entry in entries.items():
            # Get first author (normalized for grouping)
            first_author = ""
            if entry.authors:
                first_author = entry.authors[0].lower().strip()
                # Handle corporate authors - use full name
                # Handle "Last, First" format - extract last name
                if "," in first_author:
                    first_author = first_author.split(",")[0].strip()

            year = entry.year or ""
            author_year_groups[(first_author, year)].append(key)

        # Build display_year dict
        display_years = {}
        for (first_author, year), keys in author_year_groups.items():
            if len(keys) <= 1:
                # No disambiguation needed
                for key in keys:
                    display_years[key] = year
            else:
                # Sort keys for consistent ordering (alphabetically by citation key)
                sorted_keys = sorted(keys)
                for i, key in enumerate(sorted_keys):
                    letter = chr(ord("a") + i)  # a, b, c, ...
                    display_years[key] = f"{year}{letter}"

        return display_years

    def _entry_to_bibtex(self, entry) -> str:
        """Convert a BibEntry back to bibtex format for storage."""
        lines = [f"@{entry.entry_type}{{{entry.key},"]
        if entry.title:
            lines.append(f"  title = {{{entry.title}}},")
        if entry.authors:
            lines.append(f"  author = {{{' and '.join(entry.authors)}}},")
        if entry.year:
            lines.append(f"  year = {{{entry.year}}},")
        if entry.journal:
            lines.append(f"  journal = {{{entry.journal}}},")
        if entry.volume:
            lines.append(f"  volume = {{{entry.volume}}},")
        if entry.pages:
            lines.append(f"  pages = {{{entry.pages}}},")
        if entry.doi:
            lines.append(f"  doi = {{{entry.doi}}},")
        if entry.url:
            lines.append(f"  url = {{{entry.url}}},")
        lines.append("}")
        return "\n".join(lines)

    def _parse_response_file(
        self, filepath: Path, grant_id: str
    ) -> Dict[str, Any]:
        """Parse a markdown response file with YAML frontmatter."""
        try:
            with open(filepath) as f:
                content = f.read()
        except OSError as e:
            logger.error(f"Could not read response file {filepath}: {e}")
            raise

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                except yaml.YAMLError as e:
                    logger.warning(
                        f"Invalid YAML frontmatter in {filepath.name}: {e}"
                    )
                    frontmatter = {}
                body = parts[2].strip()
            else:
                frontmatter = {}
                body = content
        else:
            frontmatter = {}
            body = content

        # Build response data
        key = frontmatter.get("key", filepath.stem)
        return {
            "grant_id": grant_id,
            "key": key,
            "title": frontmatter.get("title", key.replace("_", " ").title()),
            "content": body,
            "status": frontmatter.get("status", "draft" if body else "empty"),
            "word_limit": frontmatter.get("word_limit"),
            "char_limit": frontmatter.get("char_limit"),
            "question": frontmatter.get("question"),
        }

    def watch(
        self, callback: Optional[callable] = None, poll_interval: float = 1.0
    ):
        """
        Watch for file changes and auto-sync.

        Args:
            callback: Optional callback function called after each sync.
            poll_interval: How often to check for changes (seconds).
        """
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        sync_instance = self

        class SyncHandler(FileSystemEventHandler):
            def __init__(self):
                self.last_sync: Dict[Path, float] = {}
                # Grant IDs we've hit a conflict on. We stop auto-syncing
                # those until the user explicitly pulls / force-pushes.
                # Otherwise watch would spam the same conflict error on
                # every keystroke.
                self.paused: Dict[str, str] = {}

            def on_modified(self, event):
                if event.is_directory:
                    return

                filepath = Path(event.src_path)

                # Only sync markdown files in responses dirs or grant.yaml
                if not (
                    filepath.name == "grant.yaml"
                    or (
                        filepath.suffix == ".md"
                        and "responses" in filepath.parts
                    )
                ):
                    return

                # Debounce - don't sync same file within 1 second
                now = datetime.now().timestamp()
                if (
                    filepath in self.last_sync
                    and now - self.last_sync[filepath] < 1.0
                ):
                    return
                self.last_sync[filepath] = now

                # Find grant_id from path
                grant_id = None
                for part in filepath.parts:
                    if (sync_instance.config.grants_dir / part).is_dir():
                        grant_id = part
                        break

                if not grant_id:
                    return

                if grant_id in self.paused:
                    logger.warning(
                        "Watch is paused for grant '%s' (%s). Run "
                        "`grantkit sync status` then pull or push "
                        "--force to resume.",
                        grant_id,
                        self.paused[grant_id],
                    )
                    return

                logger.info(f"File changed: {filepath.name}, syncing...")
                try:
                    stats = sync_instance.push(grant_id)
                    logger.info(f"Synced: {stats['responses']} responses")
                    if callback:
                        callback(stats)
                except SyncConflictError as e:
                    # Pause this grant until the user intervenes. Keep
                    # watching other grants normally.
                    self.paused[grant_id] = "cloud drifted since last pull"
                    logger.error("Conflict for grant '%s': %s", grant_id, e)
                except Exception as e:
                    logger.error(f"Sync failed: {e}")

        observer = Observer()
        observer.schedule(
            SyncHandler(), str(self.config.grants_dir), recursive=True
        )
        observer.start()

        logger.info(
            f"Watching {self.config.grants_dir} for changes. Press Ctrl+C to stop."
        )

        try:
            import time

            while True:
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            observer.stop()
            logger.info("Watch stopped.")

        observer.join()

    def share(
        self, grant_id: str, email: str, role: str = "editor"
    ) -> Dict[str, Any]:
        """
        Share a grant with another user.

        Args:
            grant_id: The grant ID to share.
            email: The collaborator's email address.
            role: Permission level ('viewer' or 'editor').

        Returns:
            Dict with 'success' and optional 'error' message.
        """
        try:
            # First verify the grant exists and current user owns it
            grant_result = (
                self.client.table("grants")
                .select("id, user_id")
                .eq("id", grant_id)
                .execute()
            )

            if not grant_result.data:
                return {
                    "success": False,
                    "error": f"Grant '{grant_id}' not found",
                }

            # Look up user by email in profiles table
            # Note: email might be stored differently, try both exact and ilike match
            user_lookup = (
                self.client.table("profiles")
                .select("id, email")
                .ilike("email", email)
                .execute()
            )

            if not user_lookup.data:
                return {
                    "success": False,
                    "error": f"User with email '{email}' not found. "
                    "They must create an account first.",
                }

            target_user = user_lookup.data[0]
            target_user_id = target_user["id"]

            # Check if already a collaborator
            existing = (
                self.client.table("grant_collaborators")
                .select("id, role")
                .eq("grant_id", grant_id)
                .eq("user_id", target_user_id)
                .execute()
            )

            if existing.data:
                # Update existing collaboration
                self.client.table("grant_collaborators").update(
                    {"role": role}
                ).eq("grant_id", grant_id).eq(
                    "user_id", target_user_id
                ).execute()
                return {
                    "success": True,
                    "message": f"Updated {email}'s role to {role}",
                }

            # Insert new collaborator
            self.client.table("grant_collaborators").insert(
                {
                    "grant_id": grant_id,
                    "user_id": target_user_id,
                    "user_email": email,
                    "role": role,
                }
            ).execute()

            logger.info(f"Shared grant '{grant_id}' with {email} as {role}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to share grant: {e}")
            logger.debug("Share grant error details", exc_info=True)
            return {"success": False, "error": str(e)}

    def unshare(self, grant_id: str, email: str) -> Dict[str, Any]:
        """
        Remove a collaborator from a grant.

        Args:
            grant_id: The grant ID.
            email: The collaborator's email to remove.

        Returns:
            Dict with 'success' and optional 'error' message.
        """
        try:
            # Look up user by email
            user_lookup = self.client.rpc(
                "get_user_id_by_email", {"lookup_email": email}
            ).execute()

            if not user_lookup.data:
                return {
                    "success": False,
                    "error": f"User with email '{email}' not found",
                }

            target_user_id = user_lookup.data[0]["user_id"]

            # Delete the collaboration
            result = (
                self.client.table("grant_collaborators")
                .delete()
                .eq("grant_id", grant_id)
                .eq("user_id", target_user_id)
                .execute()
            )

            if not result.data:
                return {
                    "success": False,
                    "error": f"{email} is not a collaborator on '{grant_id}'",
                }

            logger.info(f"Removed {email} from grant '{grant_id}'")
            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to unshare grant: {e}")
            logger.debug("Unshare grant error details", exc_info=True)
            return {"success": False, "error": str(e)}

    def list_collaborators(self, grant_id: str) -> Dict[str, Any]:
        """
        List all collaborators for a grant.

        Args:
            grant_id: The grant ID.

        Returns:
            Dict with 'success', 'collaborators' list, and optional 'error'.
        """
        try:
            result = (
                self.client.table("grant_collaborators")
                .select("user_email, role, created_at")
                .eq("grant_id", grant_id)
                .execute()
            )

            return {
                "success": True,
                "collaborators": result.data or [],
            }

        except Exception as e:
            logger.error(f"Failed to list collaborators: {e}")
            logger.debug("List collaborators error details", exc_info=True)
            return {"success": False, "error": str(e), "collaborators": []}


def get_sync_client(grants_dir: Path) -> GrantKitSync:
    """
    Get a configured sync client.

    Looks for auth/config in this order:
    1. Logged in user credentials (via `grantkit auth login`)
    2. grantkit.yaml in grants_dir
    3. Environment variables
    """
    # First, try to use authenticated client from OAuth login
    if is_logged_in():
        auth_client = get_authenticated_client()
        if auth_client:
            logger.info("Using authenticated session")
            # Create a config with dummy key (client is already authenticated)
            config = SyncConfig(
                supabase_url=DEFAULT_SUPABASE_URL,
                supabase_key="authenticated",  # Not used - client is pre-authenticated
                grants_dir=grants_dir,
            )
            sync = GrantKitSync.__new__(GrantKitSync)
            sync.config = config
            sync.client = auth_client
            return sync

    # Fall back to config file or env vars
    config_file = grants_dir / "grantkit.yaml"

    if config_file.exists():
        config = SyncConfig.from_file(config_file, grants_dir)
    else:
        config = SyncConfig.from_env(grants_dir)

    return GrantKitSync(config)
