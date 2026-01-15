"""Supabase sync functionality for GrantKit."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from supabase import Client, create_client

from .auth import get_authenticated_client, get_current_user_id, is_logged_in
from .budget.calculator import BudgetCalculator

logger = logging.getLogger(__name__)

# Default Supabase config (can be overridden via env vars or config file)
DEFAULT_SUPABASE_URL = "https://bmfssahcufqykfagvgtm.supabase.co"


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
        with open(config_path) as f:
            config = yaml.safe_load(f)

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

    def pull(self, grant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Pull grants and responses from Supabase to local files.

        Args:
            grant_id: Optional specific grant to pull. If None, pulls all.

        Returns:
            Dict with stats about what was pulled.
        """
        stats = {"grants": 0, "responses": 0, "files_written": 0}

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

            # Write grant metadata
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
            with open(grant_dir / "grant.yaml", "w") as f:
                yaml.dump(grant_meta, f, default_flow_style=False)
            stats["files_written"] += 1
            stats["grants"] += 1

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
                # Write response as markdown
                filename = f"{response['key']}.md"
                filepath = responses_dir / filename

                # Add frontmatter with metadata
                frontmatter = {
                    "title": response.get("title", response["key"]),
                    "key": response["key"],
                    "status": response.get("status", "draft"),
                    "word_limit": response.get("word_limit"),
                    "char_limit": response.get("char_limit"),
                    "question": response.get("question"),
                }
                # Remove None values
                frontmatter = {
                    k: v for k, v in frontmatter.items() if v is not None
                }

                content = response.get("content", "")
                with open(filepath, "w") as f:
                    f.write("---\n")
                    yaml.dump(frontmatter, f, default_flow_style=False)
                    f.write("---\n\n")
                    f.write(content)

                stats["files_written"] += 1
                stats["responses"] += 1

            logger.info(
                f"Pulled grant '{grant['name']}' with "
                f"{len(responses)} responses"
            )

        return stats

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

        # Calculate budget totals
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

        # Read full budget.yaml for JSONB storage
        with open(budget_yaml) as f:
            budget_data = yaml.safe_load(f)

        # Add calculated summary to budget data
        budget_data["summary"] = summary

        return budget_data

    def push(self, grant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Push local files to Supabase.

        Args:
            grant_id: Optional specific grant to push. If None, pushes all.

        Returns:
            Dict with stats about what was pushed.
        """
        stats = {"grants": 0, "responses": 0, "errors": []}

        # Find grant directories
        if grant_id:
            grant_dirs = [self.config.grants_dir / grant_id]
        elif self.config.grant_id:
            grant_dirs = [self.config.grants_dir / self.config.grant_id]
        else:
            grant_dirs = [
                d
                for d in self.config.grants_dir.iterdir()
                if d.is_dir() and (d / "grant.yaml").exists()
            ]

        for grant_dir in grant_dirs:
            grant_yaml = grant_dir / "grant.yaml"
            if not grant_yaml.exists():
                logger.warning(f"No grant.yaml in {grant_dir}, skipping")
                continue

            # Sync budget.yaml to grant.yaml if it exists
            budget_data = self._sync_budget_to_grant(grant_dir)

            # Read grant metadata (now with updated amount_requested)
            with open(grant_yaml) as f:
                grant_meta = yaml.safe_load(f)

            # Normalize to database schema (handles nested and flat formats)
            db_record = self._normalize_grant_yaml(grant_meta, grant_dir.name)

            # Add budget JSONB if we have budget data
            if budget_data:
                db_record["budget"] = budget_data

            # Set user_id if authenticated (required by RLS policy)
            user_id = get_current_user_id()
            if user_id:
                db_record["user_id"] = user_id

            # Upsert grant
            try:
                self.client.table("grants").upsert(
                    db_record, on_conflict="id"
                ).execute()
                stats["grants"] += 1
                logger.info(
                    f"Pushed grant '{db_record.get('name', grant_dir.name)}'"
                )
            except Exception as e:
                stats["errors"].append(f"Grant {grant_dir.name}: {e}")
                logger.error(f"Failed to push grant {grant_dir.name}: {e}")
                continue

            # Push responses - check multiple possible locations
            response_dirs_to_check = [
                grant_dir / "responses" / "full",  # Nuffield-style: responses/full/
                grant_dir / "responses",  # Simple layout: responses/
                grant_dir / "docs" / "responses",  # PolicyEngine-style: docs/responses/
            ]

            for responses_dir in response_dirs_to_check:
                if responses_dir.exists():
                    for md_file in responses_dir.glob("*.md"):
                        try:
                            response_data = self._parse_response_file(
                                md_file, db_record["id"]
                            )
                            self.client.table("responses").upsert(
                                response_data, on_conflict="grant_id,key"
                            ).execute()
                            stats["responses"] += 1
                        except Exception as e:
                            stats["errors"].append(f"Response {md_file.name}: {e}")
                            logger.error(
                                f"Failed to push response {md_file.name}: {e}"
                            )
                    break  # Stop after finding first valid responses dir

        return stats

    def _parse_response_file(
        self, filepath: Path, grant_id: str
    ) -> Dict[str, Any]:
        """Parse a markdown response file with YAML frontmatter."""
        with open(filepath) as f:
            content = f.read()

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
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
                self.last_sync = {}

            def on_modified(self, event):
                if event.is_directory:
                    return

                filepath = Path(event.src_path)

                # Only sync markdown files in responses dirs or grant.yaml
                if filepath.name == "grant.yaml" or (
                    filepath.suffix == ".md" and "responses" in filepath.parts
                ):
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

                    if grant_id:
                        logger.info(
                            f"File changed: {filepath.name}, syncing..."
                        )
                        try:
                            stats = sync_instance.push(grant_id)
                            logger.info(
                                f"Synced: {stats['responses']} responses"
                            )
                            if callback:
                                callback(stats)
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
                return {"success": False, "error": f"Grant '{grant_id}' not found"}

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
                ).eq("grant_id", grant_id).eq("user_id", target_user_id).execute()
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
