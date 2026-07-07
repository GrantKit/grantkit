"""Unified grant project model.

``GrantProject`` reads a single ``grant.yaml`` (the 0.2.0 unified schema where
each section carries ``id``/``title``/``word_limit``/``char_limit``/
``page_limit``/``required``/``file``) and exposes the section content, word/char
counts, and per-section status that the linter, builder, status report, and
review packet all consume.

For backwards compatibility it also reads sections from legacy layouts used by
existing grants (``full_application.sections``, ``outline.sections``, and
funder-nested ``<funder>.sections`` such as ``nsf.sections``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from ..packs import FunderPack, resolve_pack
from ..utils.text import count_words

# Words-per-page used only for advisory page-limit estimates (page limits cannot
# be measured exactly from markdown). Kept deliberately generous for dense,
# single-spaced NSF-style text.
DEFAULT_WORDS_PER_PAGE = 500

# Placeholder / stub markers that indicate an unfinished section.
PLACEHOLDER_PATTERNS: list[re.Pattern] = [
    re.compile(r"\[\s*to\s+be\s+completed\s*\]", re.IGNORECASE),
    re.compile(r"\[\s*write\s+your\s+content\s+here", re.IGNORECASE),
    re.compile(r"\[\s*(your|insert|add)\b[^\]]*\]", re.IGNORECASE),
    re.compile(r"\blorem\s+ipsum\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z])TODO(?![A-Za-z])"),
    re.compile(r"(?<![A-Za-z])TBD(?![A-Za-z])"),
    re.compile(r"(?<![A-Za-z])FIXME(?![A-Za-z])"),
    re.compile(r"(?<![A-Za-z])XXX(?![A-Za-z])"),
]

# Legacy funder keys whose nested `sections` we still understand.
_LEGACY_FUNDER_KEYS = ["nsf", "arnold", "pritzker", "gitlab", "neo", "nuffield"]


def find_placeholders(text: str) -> list[str]:
    """Return the distinct placeholder snippets found in ``text``."""
    found: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(text):
            snippet = match.group(0).strip()
            if snippet not in found:
                found.append(snippet)
    return found


def strip_frontmatter(content: str) -> str:
    """Strip a leading YAML frontmatter block (``--- ... ---``) if present."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content


@dataclass
class SectionState:
    """Computed state for a single grant section."""

    id: str
    title: str
    file: Optional[str] = None
    path: Optional[Path] = None
    required: bool = True
    word_limit: Optional[int] = None
    char_limit: Optional[int] = None
    page_limit: Optional[int] = None
    exists: bool = False
    body: str = ""
    words: int = 0
    chars: int = 0
    pages: float = 0.0
    placeholders: list[str] = field(default_factory=list)
    status: str = "empty"
    issues: list[str] = field(default_factory=list)

    @property
    def over_word_limit(self) -> bool:
        return bool(self.word_limit) and self.words > self.word_limit

    @property
    def over_char_limit(self) -> bool:
        return bool(self.char_limit) and self.chars > self.char_limit

    @property
    def over_page_limit(self) -> bool:
        return bool(self.page_limit) and self.pages > self.page_limit


class GrantProject:
    """A grant directory with a ``grant.yaml`` and section response files."""

    def __init__(
        self,
        root: Path,
        words_per_page: int = DEFAULT_WORDS_PER_PAGE,
    ):
        self.root = Path(root).resolve()
        self.words_per_page = words_per_page
        self.grant_yaml_path = self.root / "grant.yaml"
        self.config: dict[str, Any] = {}
        self._pack: Optional[FunderPack] = None
        self._pack_resolved = False
        self.sections: list[SectionState] = []
        self._load()

    # -- loading ---------------------------------------------------------

    def _load(self) -> None:
        if self.grant_yaml_path.exists():
            with open(self.grant_yaml_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        self._load_sections()

    def _grant_block(self) -> dict[str, Any]:
        block = self.config.get("grant")
        return block if isinstance(block, dict) else {}

    def _get(self, *keys: str) -> Any:
        """Return the first present value across top-level and ``grant:`` block."""
        grant_block = self._grant_block()
        for key in keys:
            if key in self.config and self.config[key] is not None:
                return self.config[key]
            if key in grant_block and grant_block[key] is not None:
                return grant_block[key]
        return None

    def _raw_sections(self) -> list[dict[str, Any]]:
        """Locate the section list across the unified and legacy layouts."""
        sections = self.config.get("sections")
        if sections:
            return sections

        # Legacy: full application / outline blocks (Nuffield-style).
        for block_key in ("full_application", "outline"):
            block = self.config.get(block_key, {})
            if isinstance(block, dict) and block.get("sections"):
                return block["sections"]

        # Legacy: funder-nested sections (e.g. nsf.sections in old examples).
        for funder_key in _LEGACY_FUNDER_KEYS:
            block = self.config.get(funder_key, {})
            if isinstance(block, dict) and block.get("sections"):
                return block["sections"]

        return []

    def _resolve_section_path(self, file_rel: Optional[str], sid: str) -> Path:
        """Resolve a section file to an absolute path, trying common bases."""
        candidates: list[Path] = []
        if file_rel:
            candidates.append(self.root / file_rel)
            for base in ("responses", "responses/full", "sections", "docs"):
                candidates.append(self.root / base / file_rel)
        # Fallbacks by id.
        for base in ("responses", "responses/full", "sections"):
            candidates.append(self.root / base / f"{sid}.md")

        for candidate in candidates:
            if candidate.exists():
                return candidate
        # Default (may not exist): grant-relative file or responses/<id>.md.
        if file_rel:
            return self.root / file_rel
        return self.root / "responses" / f"{sid}.md"

    def _load_sections(self) -> None:
        self.sections = []
        for raw in self._raw_sections():
            sid = raw.get("id", "")
            title = raw.get("title") or sid.replace("_", " ").title()
            file_rel = raw.get("file")
            path = self._resolve_section_path(file_rel, sid)
            section = SectionState(
                id=sid,
                title=title,
                file=file_rel or (str(path.relative_to(self.root)) if path.exists() and self._is_within_root(path) else None),
                path=path,
                required=bool(raw.get("required", True)),
                word_limit=raw.get("word_limit"),
                char_limit=raw.get("char_limit"),
                page_limit=raw.get("page_limit"),
            )
            self._compute_section(section)
            self.sections.append(section)

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    def _compute_section(self, section: SectionState) -> None:
        path = section.path
        if not path or not path.exists():
            section.exists = False
            section.status = "empty"
            return

        section.exists = True
        raw_content = path.read_text(encoding="utf-8")
        body = strip_frontmatter(raw_content)
        section.body = body
        section.words = count_words(body)
        section.chars = len(body.strip())
        section.pages = (
            section.words / self.words_per_page if self.words_per_page else 0.0
        )
        section.placeholders = find_placeholders(body)

        # Status precedence: empty -> over_limit -> partial -> complete.
        if section.words == 0:
            section.status = "empty"
        elif section.over_word_limit or section.over_char_limit:
            section.status = "over_limit"
        elif section.placeholders:
            section.status = "partial"
        else:
            section.status = "complete"

        # Per-section issue strings (surfaced in status.json).
        if section.over_word_limit:
            section.issues.append(
                f"{section.words} words exceeds limit of {section.word_limit}"
            )
        if section.over_char_limit:
            section.issues.append(
                f"{section.chars} characters exceeds limit of {section.char_limit}"
            )
        if section.over_page_limit:
            section.issues.append(
                f"~{section.pages:.1f} pages exceeds limit of {section.page_limit} "
                f"(estimate at {self.words_per_page} words/page)"
            )
        if section.placeholders:
            section.issues.append(
                "contains placeholder text: " + ", ".join(section.placeholders)
            )

    # -- metadata --------------------------------------------------------

    @property
    def pack(self) -> Optional[FunderPack]:
        """The resolved funder rule pack, if any (cached)."""
        if not self._pack_resolved:
            explicit = self._get("pack")
            funder = self._get("funder", "foundation")
            self._pack = resolve_pack(explicit) or resolve_pack(funder)
            self._pack_resolved = True
        return self._pack

    @property
    def title(self) -> str:
        return self._get("title", "name") or ""

    @property
    def funder(self) -> str:
        value = self._get("funder", "foundation")
        if value:
            return str(value)
        return self.pack.name if self.pack else ""

    @property
    def program(self) -> str:
        value = self._get("program")
        if value:
            return str(value)
        return self.pack.program if self.pack else ""

    @property
    def deadline(self) -> Optional[str]:
        value = self._get("deadline")
        return str(value) if value else None

    @property
    def accepts_markdown(self) -> bool:
        value = self._get("accepts_markdown")
        if value is not None:
            return bool(value)
        full_app = self.config.get("full_application", {})
        if isinstance(full_app, dict) and "accepts_markdown" in full_app:
            return bool(full_app["accepts_markdown"])
        if self.pack:
            return self.pack.accepts_markdown
        return True

    @property
    def locale(self) -> str:
        value = self._get("locale")
        if value:
            return str(value)
        return self.pack.locale if self.pack else "en-US"

    @property
    def references_path(self) -> Optional[Path]:
        """Locate a references.bib, if one exists."""
        explicit = self._get("references")
        if explicit:
            candidate = self.root / explicit
            if candidate.exists():
                return candidate
        for candidate in (
            self.root / "references.bib",
            self.root / "references" / "references.bib",
        ):
            if candidate.exists():
                return candidate
        # Any .bib in the root.
        bibs = sorted(self.root.glob("*.bib"))
        return bibs[0] if bibs else None

    @property
    def budget_path(self) -> Optional[Path]:
        """Locate a budget.yaml, if one exists."""
        explicit = self._get("budget")
        if isinstance(explicit, str):
            candidate = self.root / explicit
            if candidate.exists():
                return candidate
        for candidate in (
            self.root / "budget.yaml",
            self.root / "budget" / "budget.yaml",
        ):
            if candidate.exists():
                return candidate
        return None

    # -- aggregate stats -------------------------------------------------

    @property
    def total_words(self) -> int:
        return sum(s.words for s in self.sections)

    @property
    def sections_total(self) -> int:
        return len(self.sections)

    @property
    def sections_complete(self) -> int:
        return sum(1 for s in self.sections if s.status == "complete")

    @property
    def completion_percent(self) -> float:
        if not self.sections:
            return 0.0
        return round(self.sections_complete / len(self.sections) * 100, 1)

    def get_section(self, section_id: str) -> Optional[SectionState]:
        for section in self.sections:
            if section.id == section_id:
                return section
        return None
