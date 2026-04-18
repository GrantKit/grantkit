"""Compute what a sync operation would do, without performing it.

This module is the shared core behind ``grantkit sync status``,
``grantkit sync diff``, and the ``--dry-run`` flags on push/pull.
It never touches the network on its own — it takes data that has
already been fetched (or skips cloud-side comparison entirely for
local-only status) and returns a structured plan.

Plan terminology (borrowed from git):

* **added** — entity exists on one side but not the other
* **modified** — entity exists on both sides but content differs
  from the baseline we last observed
* **conflict** — both local and cloud have moved away from the
  baseline; the user must resolve
* **unchanged** — everything matches the baseline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .sync_state import EntityState, GrantState


class ChangeKind(str, Enum):
    UNCHANGED = "unchanged"
    LOCAL_ONLY_ADDED = "local_added"
    LOCAL_ONLY_MODIFIED = "local_modified"
    CLOUD_ONLY_ADDED = "cloud_added"
    CLOUD_ONLY_MODIFIED = "cloud_modified"
    CONFLICT = "conflict"


@dataclass
class EntityChange:
    """One entity's place in the sync plan."""

    entity_type: str  # "grant" | "response" | "bibliography_entry"
    grant_id: str
    entity_id: str  # response key, citation key, or grant_id again
    kind: ChangeKind
    local_hash: Optional[str] = None
    cloud_updated_at: Optional[str] = None
    baseline_updated_at: Optional[str] = None
    baseline_hash: Optional[str] = None


@dataclass
class SyncPlan:
    """The full set of changes that status/diff/push/pull care about."""

    changes: List[EntityChange] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return any(c.kind == ChangeKind.CONFLICT for c in self.changes)

    def by_kind(self, kind: ChangeKind) -> List[EntityChange]:
        return [c for c in self.changes if c.kind == kind]

    def push_candidates(self) -> List[EntityChange]:
        """Changes that `push` would attempt to send."""
        return [
            c
            for c in self.changes
            if c.kind
            in (ChangeKind.LOCAL_ONLY_ADDED, ChangeKind.LOCAL_ONLY_MODIFIED)
        ]

    def pull_candidates(self) -> List[EntityChange]:
        """Changes that `pull` would bring down from the cloud."""
        return [
            c
            for c in self.changes
            if c.kind
            in (ChangeKind.CLOUD_ONLY_ADDED, ChangeKind.CLOUD_ONLY_MODIFIED)
        ]


def _classify(
    local_hash: Optional[str],
    cloud_updated_at: Optional[str],
    baseline: EntityState,
) -> ChangeKind:
    """Three-way compare: local content, cloud timestamp, and baseline."""
    local_exists = local_hash is not None
    cloud_exists = cloud_updated_at is not None
    baseline_exists = baseline.content_hash is not None

    local_changed = (
        local_exists
        and baseline.content_hash is not None
        and local_hash != baseline.content_hash
    )
    cloud_changed = (
        cloud_exists
        and baseline.updated_at is not None
        and cloud_updated_at != baseline.updated_at
    )

    # Neither baseline nor either side: treat as unchanged (nothing to do).
    if not local_exists and not cloud_exists:
        return ChangeKind.UNCHANGED

    # New on one side only (no baseline either).
    if not baseline_exists:
        if local_exists and not cloud_exists:
            return ChangeKind.LOCAL_ONLY_ADDED
        if cloud_exists and not local_exists:
            return ChangeKind.CLOUD_ONLY_ADDED
        # Both exist with no baseline: cannot know who's newer without
        # hashing cloud content. Conservative: flag as conflict so the
        # user pulls fresh (to establish baseline) or force-pushes.
        return ChangeKind.CONFLICT

    # Baseline exists; compare each side.
    if local_changed and cloud_changed:
        return ChangeKind.CONFLICT
    if local_changed:
        return ChangeKind.LOCAL_ONLY_MODIFIED
    if cloud_changed:
        return ChangeKind.CLOUD_ONLY_MODIFIED
    return ChangeKind.UNCHANGED


def build_grant_plan(
    grant_id: str,
    local_grant_hash: Optional[str],
    cloud_grant_updated_at: Optional[str],
    local_response_hashes: Dict[str, str],
    cloud_response_updated_at: Dict[str, str],
    local_bib_hashes: Dict[str, str],
    cloud_bib_updated_at: Dict[str, str],
    state: GrantState,
) -> SyncPlan:
    """Build a plan for a single grant.

    All "cloud" inputs are dictionaries of the ``updated_at`` timestamps
    the caller already fetched from Supabase (or ``{}`` for status runs
    that skip the cloud). The function performs no I/O.
    """
    changes: List[EntityChange] = []

    # Grant itself - only surface if it actually differs from baseline.
    grant_kind = _classify(
        local_grant_hash, cloud_grant_updated_at, state.grant
    )
    if grant_kind != ChangeKind.UNCHANGED:
        changes.append(
            EntityChange(
                entity_type="grant",
                grant_id=grant_id,
                entity_id=grant_id,
                kind=grant_kind,
                local_hash=local_grant_hash,
                cloud_updated_at=cloud_grant_updated_at,
                baseline_updated_at=state.grant.updated_at,
                baseline_hash=state.grant.content_hash,
            )
        )

    # Responses
    keys = (
        set(local_response_hashes)
        | set(cloud_response_updated_at)
        | set(state.responses)
    )
    for key in sorted(keys):
        baseline = state.responses.get(key, EntityState())
        kind = _classify(
            local_response_hashes.get(key),
            cloud_response_updated_at.get(key),
            baseline,
        )
        if kind == ChangeKind.UNCHANGED:
            continue
        changes.append(
            EntityChange(
                entity_type="response",
                grant_id=grant_id,
                entity_id=key,
                kind=kind,
                local_hash=local_response_hashes.get(key),
                cloud_updated_at=cloud_response_updated_at.get(key),
                baseline_updated_at=baseline.updated_at,
                baseline_hash=baseline.content_hash,
            )
        )

    # Bibliography entries
    bib_keys = (
        set(local_bib_hashes)
        | set(cloud_bib_updated_at)
        | set(state.bibliography_entries)
    )
    for key in sorted(bib_keys):
        baseline = state.bibliography_entries.get(key, EntityState())
        kind = _classify(
            local_bib_hashes.get(key),
            cloud_bib_updated_at.get(key),
            baseline,
        )
        if kind == ChangeKind.UNCHANGED:
            continue
        changes.append(
            EntityChange(
                entity_type="bibliography_entry",
                grant_id=grant_id,
                entity_id=key,
                kind=kind,
                local_hash=local_bib_hashes.get(key),
                cloud_updated_at=cloud_bib_updated_at.get(key),
                baseline_updated_at=baseline.updated_at,
                baseline_hash=baseline.content_hash,
            )
        )

    return SyncPlan(changes=changes)


def merge_plans(plans: List[SyncPlan]) -> SyncPlan:
    """Merge per-grant plans into a single plan for display."""
    out = SyncPlan()
    for p in plans:
        out.changes.extend(p.changes)
    return out


def summarize(plan: SyncPlan) -> Dict[ChangeKind, int]:
    """Count changes by kind for compact status output."""
    counts: Dict[ChangeKind, int] = {k: 0 for k in ChangeKind}
    for c in plan.changes:
        counts[c.kind] = counts.get(c.kind, 0) + 1
    return counts


__all__ = [
    "ChangeKind",
    "EntityChange",
    "SyncPlan",
    "build_grant_plan",
    "merge_plans",
    "summarize",
]
