"""I/O utilities for file handling."""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_text_file(file_path: Path, encoding: str = "utf-8") -> str:
    """Load text content from a file with error handling."""
    try:
        return file_path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        # Try with different encodings
        for alt_encoding in ["latin-1", "utf-16", "ascii"]:
            try:
                logger.warning(
                    f"Retrying {file_path} with {alt_encoding} encoding"
                )
                return file_path.read_text(encoding=alt_encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(
            f"Cannot decode file {file_path} with any common encoding"
        )
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        raise


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)


def find_project_root(
    start_path: Path, markers: Optional[list] = None
) -> Optional[Path]:
    """Find project root by looking for marker files.

    Args:
        start_path: Path to start searching from
        markers: List of marker filenames to look for

    Returns:
        Path to project root or None if not found
    """
    if markers is None:
        markers = [
            "nsf_config.yaml",
            "config.yaml",
            "grant.yaml",
            "pyproject.toml",
            "setup.py",
            ".git",
        ]

    current = Path(start_path).resolve()

    while current != current.parent:  # Not at filesystem root
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    return None


def safe_filename(name: str) -> str:
    """Convert string to safe filename."""
    # Replace problematic characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("_")


def backup_file(file_path: Path) -> Path:
    """Create a backup of an existing file."""
    if not file_path.exists():
        return file_path

    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    counter = 1

    while backup_path.exists():
        backup_path = file_path.with_suffix(
            f"{file_path.suffix}.bak.{counter}"
        )
        counter += 1

    try:
        backup_path.write_bytes(file_path.read_bytes())
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup of {file_path}: {e}")
        raise
