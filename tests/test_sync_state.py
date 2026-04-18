"""Tests for sync state, plan computation, and conflict detection."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from grantkit.sync import GrantKitSync, SyncConfig, SyncConflictError
from grantkit.sync_plan import ChangeKind, build_grant_plan
from grantkit.sync_state import (
    EntityState,
    GrantState,
    SyncState,
    content_hash,
    load_state,
    save_state,
)

# ---------------------------------------------------------------------------
# sync_state (pure, no Supabase needed)
# ---------------------------------------------------------------------------


class TestSyncState:
    def test_load_missing_returns_empty(self, tmp_path):
        state = load_state(tmp_path)
        assert state.grants == {}

    def test_roundtrip_preserves_everything(self, tmp_path):
        state = SyncState()
        gs = GrantState(
            grant=EntityState(
                updated_at="2026-01-01T00:00:00Z", content_hash="abc"
            )
        )
        gs.responses["abstract"] = EntityState(
            updated_at="2026-01-02T00:00:00Z", content_hash="def"
        )
        gs.bibliography_entries["citekey"] = EntityState(
            updated_at="2026-01-03T00:00:00Z", content_hash="ghi"
        )
        state.set_grant("grant1", gs)
        save_state(tmp_path, state)

        reloaded = load_state(tmp_path)
        assert reloaded.grants["grant1"].grant.content_hash == "abc"
        assert (
            reloaded.grants["grant1"].responses["abstract"].updated_at
            == "2026-01-02T00:00:00Z"
        )
        assert (
            reloaded.grants["grant1"]
            .bibliography_entries["citekey"]
            .content_hash
            == "ghi"
        )

    def test_corrupt_state_file_is_tolerated(self, tmp_path):
        state_path = tmp_path / ".grantkit" / "state.json"
        state_path.parent.mkdir()
        state_path.write_text("not valid json")
        state = load_state(tmp_path)
        assert state.grants == {}


# ---------------------------------------------------------------------------
# sync_plan (pure classification logic)
# ---------------------------------------------------------------------------


class TestPlanClassification:
    def _plan(self, **kwargs):
        defaults = dict(
            grant_id="g",
            local_grant_hash=None,
            cloud_grant_updated_at=None,
            local_response_hashes={},
            cloud_response_updated_at={},
            local_bib_hashes={},
            cloud_bib_updated_at={},
            state=GrantState(),
        )
        defaults.update(kwargs)
        return build_grant_plan(**defaults)

    def test_local_only_new_grant_is_added(self):
        plan = self._plan(local_grant_hash="h1")
        grant_changes = [c for c in plan.changes if c.entity_type == "grant"]
        assert len(grant_changes) == 1
        assert grant_changes[0].kind == ChangeKind.LOCAL_ONLY_ADDED

    def test_local_unchanged_against_baseline_is_not_reported(self):
        state = GrantState(
            grant=EntityState(updated_at="t1", content_hash="h1")
        )
        plan = self._plan(
            local_grant_hash="h1",
            cloud_grant_updated_at="t1",
            state=state,
        )
        # No change should be emitted when everything matches.
        assert plan.changes == []

    def test_local_modified_only(self):
        state = GrantState(
            grant=EntityState(updated_at="t1", content_hash="h1")
        )
        plan = self._plan(
            local_grant_hash="h2",  # local changed
            cloud_grant_updated_at="t1",  # cloud unchanged
            state=state,
        )
        assert plan.changes[0].kind == ChangeKind.LOCAL_ONLY_MODIFIED

    def test_cloud_modified_only(self):
        state = GrantState(
            grant=EntityState(updated_at="t1", content_hash="h1")
        )
        plan = self._plan(
            local_grant_hash="h1",
            cloud_grant_updated_at="t2",  # cloud moved
            state=state,
        )
        assert plan.changes[0].kind == ChangeKind.CLOUD_ONLY_MODIFIED

    def test_conflict_when_both_sides_moved(self):
        state = GrantState(
            grant=EntityState(updated_at="t1", content_hash="h1")
        )
        plan = self._plan(
            local_grant_hash="h2",
            cloud_grant_updated_at="t2",
            state=state,
        )
        assert plan.has_conflicts
        assert plan.changes[0].kind == ChangeKind.CONFLICT

    def test_conflict_when_no_baseline_but_both_exist(self):
        plan = self._plan(
            local_grant_hash="h1",
            cloud_grant_updated_at="t1",
            state=GrantState(),
        )
        assert plan.has_conflicts

    def test_response_level_conflict_surfaces_in_plan(self):
        state = GrantState()
        state.responses["abstract"] = EntityState(
            updated_at="t1", content_hash="h1"
        )
        plan = self._plan(
            local_response_hashes={"abstract": "h2"},
            cloud_response_updated_at={"abstract": "t2"},
            state=state,
        )
        resp = [c for c in plan.changes if c.entity_type == "response"]
        assert resp and resp[0].kind == ChangeKind.CONFLICT

    def test_push_candidates_filters_to_local_changes(self):
        state = GrantState()
        state.responses["keep"] = EntityState(updated_at="t", content_hash="h")
        plan = self._plan(
            local_response_hashes={
                "keep": "h",  # unchanged
                "new": "h-new",  # added locally
                "edited": "h-edited",  # modified locally
            },
            cloud_response_updated_at={"keep": "t"},
            state=GrantState(
                responses={
                    "keep": EntityState(updated_at="t", content_hash="h"),
                    "edited": EntityState(
                        updated_at="t-edited", content_hash="h-was"
                    ),
                }
            ),
        )
        kinds = {c.entity_id: c.kind for c in plan.push_candidates()}
        assert kinds == {
            "new": ChangeKind.LOCAL_ONLY_ADDED,
            "edited": ChangeKind.LOCAL_ONLY_MODIFIED,
        }


# ---------------------------------------------------------------------------
# Push-with-conflict-detection (using the existing mock pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_supabase():
    with patch("grantkit.sync.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def sync_config(tmp_path):
    return SyncConfig(
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        grants_dir=tmp_path,
    )


def _write_grant(grant_dir: Path, grant_id: str) -> None:
    grant_dir.mkdir(parents=True, exist_ok=True)
    (grant_dir / "grant.yaml").write_text(
        yaml.dump({"id": grant_id, "name": "G", "foundation": "F"}),
        encoding="utf-8",
    )


def _write_response(grant_dir: Path, key: str, body: str) -> None:
    responses_dir = grant_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    (responses_dir / f"{key}.md").write_text(
        f"---\ntitle: {key}\nkey: {key}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def _set_select_empty(mock_client: MagicMock) -> None:
    """Return empty cloud state from every select().eq() chain."""
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
        []
    )
    # A two-filter chain (.eq().eq()) also needs to resolve to empty data.
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        []
    )


class TestPushConflictDetection:
    def test_dry_run_does_not_upsert(self, mock_supabase, sync_config):
        grant_dir = sync_config.grants_dir / "g1"
        _write_grant(grant_dir, "g1")
        _write_response(grant_dir, "abstract", "body")
        _set_select_empty(mock_supabase)

        sync = GrantKitSync(sync_config)
        stats = sync.push(grant_id="g1", dry_run=True)

        assert "plan" in stats
        mock_supabase.table.return_value.upsert.assert_not_called()
        assert stats["push_candidates"] >= 1

    def test_push_updates_state_file(self, mock_supabase, sync_config):
        grant_dir = sync_config.grants_dir / "g1"
        _write_grant(grant_dir, "g1")
        _write_response(grant_dir, "abstract", "body")
        _set_select_empty(mock_supabase)

        # Make upsert return a plausible "updated_at".
        upsert_result = MagicMock()
        upsert_result.data = [
            {"id": "g1", "updated_at": "2026-01-01T00:00:00Z"}
        ]
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            upsert_result
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="g1")

        state = load_state(sync_config.grants_dir)
        assert "g1" in state.grants
        assert state.grants["g1"].grant.updated_at == "2026-01-01T00:00:00Z"
        assert state.grants["g1"].grant.content_hash  # non-empty

    def test_push_raises_on_cloud_drift(self, mock_supabase, sync_config):
        grant_dir = sync_config.grants_dir / "g1"
        _write_grant(grant_dir, "g1")
        _write_response(grant_dir, "abstract", "local edit")

        # Seed state as if we pulled at t1 with a known hash.
        state = SyncState()
        gs = GrantState(
            grant=EntityState(updated_at="t1", content_hash="stale")
        )
        state.set_grant("g1", gs)
        save_state(sync_config.grants_dir, state)

        # Cloud has moved on to t2.
        def select_side_effect(columns):
            select_mock = MagicMock()
            eq_mock = MagicMock()
            eq_mock.execute.return_value.data = [
                {"id": "g1", "updated_at": "t2"}
            ]
            select_mock.eq.return_value = eq_mock
            return select_mock

        mock_supabase.table.return_value.select.side_effect = (
            select_side_effect
        )

        sync = GrantKitSync(sync_config)
        with pytest.raises(SyncConflictError):
            sync.push(grant_id="g1")

    def test_force_bypasses_conflict(self, mock_supabase, sync_config):
        grant_dir = sync_config.grants_dir / "g1"
        _write_grant(grant_dir, "g1")
        _write_response(grant_dir, "abstract", "local edit")

        state = SyncState()
        gs = GrantState(
            grant=EntityState(updated_at="t1", content_hash="stale")
        )
        state.set_grant("g1", gs)
        save_state(sync_config.grants_dir, state)

        # Cloud drifted, but force=True should ignore the conflict.
        def select_side_effect(columns):
            select_mock = MagicMock()
            eq_mock = MagicMock()
            eq_mock.execute.return_value.data = [
                {"id": "g1", "updated_at": "t2"}
            ]
            select_mock.eq.return_value = eq_mock
            return select_mock

        mock_supabase.table.return_value.select.side_effect = (
            select_side_effect
        )
        upsert_result = MagicMock()
        upsert_result.data = [{"id": "g1", "updated_at": "t3"}]
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            upsert_result
        )

        sync = GrantKitSync(sync_config)
        stats = sync.push(grant_id="g1", force=True)
        assert stats["grants"] == 1


# ---------------------------------------------------------------------------
# Pull records baseline
# ---------------------------------------------------------------------------


class TestPullRecordsBaseline:
    def test_pull_saves_state(self, mock_supabase, sync_config):
        # First select (grants) returns one row, subsequent selects return [].
        grant_row = {
            "id": "g1",
            "name": "Test Grant",
            "foundation": "F",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        resp_row = {
            "key": "abstract",
            "title": "Abstract",
            "content": "body",
            "updated_at": "2026-01-02T00:00:00Z",
        }

        mock_supabase.table.return_value.select.return_value.execute.return_value.data = [
            grant_row
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            resp_row
        ]

        sync = GrantKitSync(sync_config)
        sync.pull()

        state = load_state(sync_config.grants_dir)
        assert state.grants["g1"].grant.updated_at == "2026-01-01T00:00:00Z"
        assert state.grants["g1"].grant.content_hash
        assert (
            state.grants["g1"].responses["abstract"].updated_at
            == "2026-01-02T00:00:00Z"
        )

    def test_pull_dry_run_does_not_write_files(
        self, mock_supabase, sync_config
    ):
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = (
            []
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        sync = GrantKitSync(sync_config)
        stats = sync.pull(dry_run=True)

        assert "plan" in stats
        # Nothing on disk.
        assert not (
            sync_config.grants_dir / ".grantkit" / "state.json"
        ).exists()


# ---------------------------------------------------------------------------
# compute_plan
# ---------------------------------------------------------------------------


class TestComputePlan:
    def test_empty_project_has_empty_plan(self, mock_supabase, sync_config):
        sync = GrantKitSync(sync_config)
        plan = sync.compute_plan(include_cloud=False)
        assert plan.changes == []

    def test_offline_plan_only_uses_baseline(self, mock_supabase, sync_config):
        grant_dir = sync_config.grants_dir / "g1"
        _write_grant(grant_dir, "g1")
        _write_response(grant_dir, "abstract", "body")

        sync = GrantKitSync(sync_config)
        plan = sync.compute_plan(include_cloud=False)
        # With no baseline, both grant and response are "local added".
        kinds = {(c.entity_type, c.entity_id): c.kind for c in plan.changes}
        assert kinds[("grant", "g1")] == ChangeKind.LOCAL_ONLY_ADDED
        assert kinds[("response", "abstract")] == ChangeKind.LOCAL_ONLY_ADDED


# ---------------------------------------------------------------------------
# Bibliography auto-regen is not silent anymore
# ---------------------------------------------------------------------------


class TestBibliographyRegenWarning:
    def test_existing_file_is_not_silently_overwritten(
        self, mock_supabase, sync_config, tmp_path
    ):
        grant_dir = sync_config.grants_dir / "g1"
        grant_dir.mkdir()

        # Grant with auto_generate bibliography config.
        (grant_dir / "grant.yaml").write_text(
            yaml.dump(
                {
                    "id": "g1",
                    "name": "G",
                    "foundation": "F",
                    "sections": [
                        {
                            "type": "bibliography",
                            "file": "responses/references.md",
                            "auto_generate": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        responses_dir = grant_dir / "responses"
        responses_dir.mkdir()
        user_written = "Hand-written bibliography that must be preserved"
        (responses_dir / "references.md").write_text(
            user_written, encoding="utf-8"
        )

        _set_select_empty(mock_supabase)
        upsert_result = MagicMock()
        upsert_result.data = [
            {"id": "g1", "updated_at": "2026-01-01T00:00:00Z"}
        ]
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            upsert_result
        )

        sync = GrantKitSync(sync_config)
        stats = sync.push(grant_id="g1")

        # File content preserved.
        assert (responses_dir / "references.md").read_text(
            encoding="utf-8"
        ) == user_written
        # Stats surface the skip.
        assert stats.get("bibliography_skipped") == ["g1"]


# ---------------------------------------------------------------------------
# Content hash is stable
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_same_input_same_hash(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different_input_different_hash(self):
        assert content_hash("hello") != content_hash("world")
