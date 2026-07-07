"""Discovery and loading of funder rule packs.

Packs live as ``*.yaml`` files under ``grantkit/data/funders/``. The stem of
each filename is the pack id (e.g. ``nsf-pappg.yaml`` -> ``nsf-pappg``).
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Optional

import yaml

from .schema import FunderPack, validate_pack


def _funders_dir() -> Path:
    """Return the directory that holds packaged funder rule packs."""
    return Path(str(files("grantkit"))) / "data" / "funders"


def pack_path(pack_id: str) -> Path:
    """Return the filesystem path for a pack id (may not exist)."""
    return _funders_dir() / f"{pack_id}.yaml"


def list_pack_ids() -> list[str]:
    """Return sorted ids of all available funder rule packs."""
    directory = _funders_dir()
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def load_pack_dict(pack_id: str) -> dict:
    """Load the raw dict for a pack id.

    Raises:
        KeyError: if no pack with that id exists.
    """
    path = pack_path(pack_id)
    if not path.exists():
        raise KeyError(
            f"Unknown funder pack '{pack_id}'. Available: {', '.join(list_pack_ids()) or '(none)'}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_pack(pack_id: str) -> FunderPack:
    """Load and parse a funder pack by id.

    Raises:
        KeyError: if no pack with that id exists.
        ValueError: if the pack fails schema validation.
    """
    data = load_pack_dict(pack_id)
    errors = validate_pack(data)
    if errors:
        joined = "\n  - ".join(errors)
        raise ValueError(f"Invalid funder pack '{pack_id}':\n  - {joined}")
    return FunderPack.from_dict(data)


def resolve_pack(funder: Optional[str]) -> Optional[FunderPack]:
    """Resolve a pack from a funder id or free-text funder name.

    Tries, in order:
      1. exact pack-id match,
      2. case-insensitive match against each pack's ``name`` or ``program``,
      3. substring match against pack id / name.

    Returns None if nothing matches (or ``funder`` is falsy).
    """
    if not funder:
        return None

    key = funder.strip()
    ids = list_pack_ids()

    # 1. Exact id match.
    if key in ids:
        return load_pack(key)

    key_lower = key.lower()

    # 2/3. Scan packs for a name/program/id match.
    best: Optional[FunderPack] = None
    for pack_id in ids:
        try:
            pack = load_pack(pack_id)
        except (ValueError, KeyError):
            continue
        candidates = [
            pack.id.lower(),
            (pack.name or "").lower(),
            (pack.program or "").lower(),
        ]
        if key_lower in candidates:
            return pack
        if best is None and any(
            key_lower in c or (c and c in key_lower) for c in candidates if c
        ):
            best = pack
    return best
