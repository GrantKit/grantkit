"""Core document assembly functionality for NSF grant proposals."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader

from ..utils.io import ensure_directory, load_text_file
from ..utils.text import count_words

logger = logging.getLogger(__name__)


@dataclass
class SectionInfo:
    """Information about a proposal section."""

    id: str
    title: str
    file_path: Optional[Path] = None
    page_limit: Optional[int] = None
    word_limit: Optional[int] = None
    required: bool = True
    content: str = ""
    word_count: int = 0
    is_complete: bool = False


@dataclass
class AssemblyResult:
    """Result of document assembly operation."""

    success: bool
    output_path: Optional[Path] = None
    total_words: int = 0
    total_pages: Optional[int] = None
    sections: List[SectionInfo] = None
    warnings: List[str] = None
    errors: List[str] = None

    def __post_init__(self) -> None:
        if self.sections is None:
            self.sections = []
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


class GrantAssembler:
    """Main class for assembling NSF grant proposals from component sections."""

    def __init__(
        self, project_root: Path, templates_dir: Optional[Path] = None
    ):
        """Initialize the assembler.

        Args:
            project_root: Root directory of the grant project
            templates_dir: Optional custom templates directory
        """
        self.project_root = Path(project_root).resolve()
        self.sections: List[SectionInfo] = []
        self.config: Dict[str, Any] = {}

        # Set up templates
        if templates_dir and templates_dir.exists():
            self.templates_dir = templates_dir
        else:
            self.templates_dir = Path(__file__).parent.parent / "templates"

        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Load configuration if available
        self._load_config()

    def _load_config(self) -> None:
        """Load project configuration from YAML file."""
        config_paths = [
            self.project_root / "nsf_config.yaml",
            self.project_root / "config.yaml",
            self.project_root / "grant.yaml",
            # Support existing POSE format
            self.project_root / "docs" / "pose" / "pose_questions.yaml",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        self.config = yaml.safe_load(f) or {}
                    logger.info(f"Loaded configuration from {config_path}")
                    break
                except Exception as e:
                    logger.warning(
                        f"Failed to load config from {config_path}: {e}"
                    )

    def load_sections_from_config(self) -> None:
        """Load section definitions from configuration."""
        # Look for sections in multiple places to support different config formats
        sections_config = self.config.get("sections", [])

        # Support funder-specific nested sections (e.g., nsf.sections, arnold.sections)
        if not sections_config:
            for funder_key in ["nsf", "arnold", "pritzker", "gitlab", "neo"]:
                funder_config = self.config.get(funder_key, {})
                if (
                    isinstance(funder_config, dict)
                    and "sections" in funder_config
                ):
                    sections_config = funder_config["sections"]
                    break

        self.sections = []

        for section_def in sections_config:
            section = SectionInfo(
                id=section_def.get("id", ""),
                title=section_def.get("title", "Untitled"),
                page_limit=section_def.get("page_limit"),
                word_limit=section_def.get("word_limit"),
                required=section_def.get("required", True),
            )

            # Resolve file path
            file_rel = section_def.get("file", "")
            if file_rel:
                # Try multiple base directories
                base_dirs = [
                    self.project_root,
                    self.project_root / "docs",
                    self.project_root / "src",
                    self.project_root / "sections",
                    self.project_root / "responses",
                ]

                for base_dir in base_dirs:
                    potential_path = base_dir / file_rel
                    if potential_path.exists():
                        section.file_path = potential_path
                        break

            self.sections.append(section)

    def load_section_content(self, section: SectionInfo) -> None:
        """Load content for a single section."""
        if not section.file_path or not section.file_path.exists():
            section.content = ""
            section.word_count = 0
            section.is_complete = False
            return

        try:
            section.content = load_text_file(section.file_path)
            section.word_count = count_words(section.content)
            section.is_complete = len(section.content.strip()) > 0

            # Check word limit compliance
            if section.word_limit and section.word_count > section.word_limit:
                logger.warning(
                    f"Section '{section.title}' exceeds word limit: "
                    f"{section.word_count} > {section.word_limit}"
                )

        except Exception as e:
            logger.error(
                f"Failed to load content for section '{section.title}': {e}"
            )
            section.content = ""
            section.word_count = 0
            section.is_complete = False

    def load_all_content(self) -> None:
        """Load content for all sections."""
        if not self.sections:
            self.load_sections_from_config()

        for section in self.sections:
            self.load_section_content(section)

    def generate_table_of_contents(self) -> str:
        """Generate a table of contents for the proposal."""
        toc_lines = ["# Table of Contents\n"]

        page_num = 1
        for section in self.sections:
            if section.is_complete:
                # Estimate pages (very rough: 250 words per page)
                section_pages = max(1, (section.word_count + 249) // 250)
                toc_lines.append(f"{page_num}. {section.title}")
                page_num += section_pages

        return "\n".join(toc_lines)

    def assemble_document(
        self,
        output_path: Optional[Path] = None,
        template_name: str = "proposal_template.md",
        include_toc: bool = True,
        include_metadata: bool = True,
    ) -> AssemblyResult:
        """Assemble the complete proposal document.

        Args:
            output_path: Where to write the assembled document
            template_name: Jinja2 template to use for assembly
            include_toc: Whether to include table of contents
            include_metadata: Whether to include metadata header

        Returns:
            AssemblyResult with success status and details
        """
        result = AssemblyResult(success=False)

        try:
            # Load all content
            self.load_all_content()

            # Calculate totals
            total_words = sum(
                s.word_count for s in self.sections if s.is_complete
            )
            complete_sections = [s for s in self.sections if s.is_complete]
            incomplete_sections = [
                s for s in self.sections if not s.is_complete and s.required
            ]

            # Check for missing required sections
            if incomplete_sections:
                for section in incomplete_sections:
                    result.errors.append(
                        f"Required section missing: {section.title}"
                    )

            # Generate content
            content_parts = []

            # Metadata header
            if include_metadata:
                metadata = self._generate_metadata()
                content_parts.append(metadata)

            # Table of contents
            if include_toc:
                toc = self.generate_table_of_contents()
                content_parts.append(toc)
                content_parts.append("\n---\n")

            # Section content
            for section in self.sections:
                if section.is_complete:
                    content_parts.append(f"\n# {section.title}\n")
                    content_parts.append(section.content)
                    content_parts.append("\n---\n")
                elif section.required:
                    content_parts.append(f"\n# {section.title}\n")
                    content_parts.append("❌ SECTION MISSING - REQUIRED\n")
                    content_parts.append("---\n")

            # Try to use template if available
            try:
                template = self.jinja_env.get_template(template_name)
                final_content = template.render(
                    config=self.config,
                    sections=self.sections,
                    complete_sections=complete_sections,
                    total_words=total_words,
                    generated_date=datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    content="\n".join(content_parts),
                )
            except Exception as e:
                logger.warning(
                    f"Template rendering failed, using basic assembly: {e}"
                )
                final_content = "\n".join(content_parts)

            # Write output
            if not output_path:
                output_path = self.project_root / "assembled_proposal.md"

            ensure_directory(output_path.parent)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_content)

            # Populate result
            result.success = True
            result.output_path = output_path
            result.total_words = total_words
            result.sections = self.sections.copy()

            # Add warnings
            over_limit_sections = [
                s
                for s in self.sections
                if s.word_limit and s.word_count > s.word_limit
            ]
            for section in over_limit_sections:
                result.warnings.append(
                    f"Section '{section.title}' exceeds word limit: "
                    f"{section.word_count} > {section.word_limit}"
                )

            logger.info(f"Successfully assembled proposal to {output_path}")
            logger.info(f"Total words: {total_words}")
            logger.info(
                f"Complete sections: {len(complete_sections)}/{len(self.sections)}"
            )

        except Exception as e:
            result.errors.append(f"Assembly failed: {str(e)}")
            logger.error(f"Assembly failed: {e}", exc_info=True)

        return result

    def _generate_metadata(self) -> str:
        """Generate document metadata header."""
        basic_info = self.config.get("basic_info", {})

        metadata_lines = []
        metadata_lines.append("---")
        metadata_lines.append("# NSF Grant Proposal - Generated Document")

        if basic_info.get("program"):
            metadata_lines.append(f"**Program:** {basic_info['program']}")
        if basic_info.get("project_title"):
            metadata_lines.append(f"**Title:** {basic_info['project_title']}")
        if basic_info.get("organization_name"):
            metadata_lines.append(
                f"**Organization:** {basic_info['organization_name']}"
            )
        if basic_info.get("deadline"):
            metadata_lines.append(f"**Deadline:** {basic_info['deadline']}")

        metadata_lines.append(
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        metadata_lines.append("---\n")

        return "\n".join(metadata_lines)

    def get_completion_status(self) -> Dict[str, Any]:
        """Get detailed completion status."""
        if not self.sections:
            self.load_all_content()

        complete = [s for s in self.sections if s.is_complete]
        incomplete = [s for s in self.sections if not s.is_complete]
        required_incomplete = [s for s in incomplete if s.required]

        total_words = sum(s.word_count for s in complete)

        return {
            "total_sections": len(self.sections),
            "complete_sections": len(complete),
            "incomplete_sections": len(incomplete),
            "required_incomplete": len(required_incomplete),
            "total_words": total_words,
            "completion_percentage": (
                len(complete) / len(self.sections) * 100
                if self.sections
                else 0
            ),
            "sections": [
                {
                    "title": s.title,
                    "complete": s.is_complete,
                    "required": s.required,
                    "word_count": s.word_count,
                    "word_limit": s.word_limit,
                    "over_limit": s.word_limit and s.word_count > s.word_limit,
                }
                for s in self.sections
            ],
        }

    def validate_proposal(self) -> List[str]:
        """Run basic validation checks on the proposal."""
        issues = []

        if not self.sections:
            self.load_all_content()

        # Check for missing required sections
        for section in self.sections:
            if section.required and not section.is_complete:
                issues.append(f"Required section missing: {section.title}")

        # Check word limits
        for section in self.sections:
            if section.word_limit and section.word_count > section.word_limit:
                issues.append(
                    f"Section '{section.title}' exceeds word limit: "
                    f"{section.word_count} > {section.word_limit}"
                )

        # Check for empty sections that have content files
        for section in self.sections:
            if (
                section.file_path
                and section.file_path.exists()
                and not section.is_complete
            ):
                issues.append(
                    f"Section '{section.title}' has file but no content"
                )

        return issues
