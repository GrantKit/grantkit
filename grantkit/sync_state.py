"""Sync state tracking for conflict detection.

GrantKit's sync model makes AI agents confident that pushing their
local edits will not silently overwrite concurrent cloud changes.
To do that we need a baseline: what did the cloud look like the last
time we synced, and what did local look like then?

The baseline lives at ``.grantkit/state.json`` inside the project root.
For every grant (and its responses and bibliography entries) we track:

* ``updated_at`` — the ``updated_at`` timestamp the cloud returned at
  the time of the last successful pull or push. We use this to detect
  whether the cloud has moved on since we last saw it.
* ``content_hash`` — a sha256 of the serialized content we wrote to
  disk (on pull) or pushed to the cloud (on push). We use this to
  detect local edits, regardless of whitespace or reordering in the
  frontmatter/yaml that ``yaml.dump`` can introduce.

Three-way logic:

* local_changed and not cloud_changed → safe to push.
* cloud_changed and not local_changed → need to pull first.
* both changed → conflict; user must resolve (or ``--force``).
* neither changed → no-op.

The file is human-inspectable JSON, has a ``version`` for forward
compatibility, and is safe to delete — if it's missing we fall back
to "pull creates baseline" and warn that conflict detection is off.

The state is per-machine metadata (it describes when **this** client
last saw the cloud) and should be gitignored. Merging two teammates'
baselines would produce a file that doesn't match either teammate's
actual sync history.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STATE_VERSION = 1
STATE_DIR_NAME = ".grantkit"
STATE_FILE_NAME = "state.json"


def state_file_path(project_root: Path) -> Path:
    """Return the canonical path to the sync state file."""
    return project_root / STATE_DIR_NAME / STATE_FILE_NAME


def content_hash(content: str) -> str:
    """Return a deterministic sha256 of a string.

    Used to detect local edits independent of cosmetic yaml churn.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class EntityState:
    """Per-entity sync baseline."""

    updated_at: Optional[str] = None
    content_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "EntityState":
        if not data:
            return cls()
        return cls(
            updated_at=data.get("updated_at"),
            content_hash=data.get("content_hash"),
        )


@dataclass
class GrantState:
    """Baseline for a grant and all its child entities."""

    grant: EntityState = field(default_factory=EntityState)
    responses: Dict[str, EntityState] = field(default_factory=dict)
    bibliography_entries: Dict[str, EntityState] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grant": self.grant.to_dict(),
            "responses": {k: v.to_dict() for k, v in self.responses.items()},
            "bibliography_entries": {
                k: v.to_dict() for k, v in self.bibliography_entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "GrantState":
        if not data:
            return cls()
        return cls(
            grant=EntityState.from_dict(data.get("grant")),
            responses={
                k: EntityState.from_dict(v)
                for k, v in (data.get("responses") or {}).items()
            },
            bibliography_entries={
                k: EntityState.from_dict(v)
                for k, v in (data.get("bibliography_entries") or {}).items()
            },
        )


@dataclass
class SyncState:
    """The complete local view of what cloud looked like at last sync."""

    grants: Dict[str, GrantState] = field(default_factory=dict)
    version: int = STATE_VERSION

    def get_grant(self, grant_id: str) -> GrantState:
        return self.grants.get(grant_id, GrantState())

    def set_grant(self, grant_id: str, state: GrantState) -> None:
        self.grants[grant_id] = state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "grants": {gid: g.to_dict() for gid, g in self.grants.items()},
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SyncState":
        if not data:
            return cls()
        return cls(
            version=data.get("version", STATE_VERSION),
            grants={
                gid: GrantState.from_dict(g)
                for gid, g in (data.get("grants") or {}).items()
            },
        )


def load_state(project_root: Path) -> SyncState:
    """Load the state file, returning an empty state if it doesn't exist."""
    path = state_file_path(project_root)
    if not path.exists():
        return SyncState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            "Could not read sync state file %s: %s. "
            "Conflict detection will be disabled until next pull.",
            path,
            e,
        )
        return SyncState()
    return SyncState.from_dict(data)


def save_state(project_root: Path, state: SyncState) -> None:
    """Write the state file atomically."""
    path = state_file_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
