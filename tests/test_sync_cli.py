"""CliRunner tests for grantkit sync commands.

The library-level tests exercise ``GrantKitSync`` directly. These
cover the CLI surface: option parsing, exit codes, and the plan
rendering an agent would see.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from grantkit.cli import main
from grantkit.sync_state import EntityState, GrantState, SyncState, save_state


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_sync_client():
    """Patch get_sync_client where the CLI imports it (lazy, in-function)."""
    with patch("grantkit.sync.get_sync_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


def _write_grant(project_root: Path, grant_id: str) -> None:
    grant_dir = project_root / grant_id
    grant_dir.mkdir(parents=True, exist_ok=True)
    (grant_dir / "grant.yaml").write_text(
        yaml.dump({"id": grant_id, "name": "G", "foundation": "F"}),
        encoding="utf-8",
    )


class TestSyncStatusCommand:
    def test_status_with_no_changes_prints_all_good(
        self, runner, mock_sync_client, tmp_path
    ):
        from grantkit.sync_plan import SyncPlan

        mock_sync_client.compute_plan.return_value = SyncPlan(changes=[])

        result = runner.invoke(
            main,
            ["--project-root", str(tmp_path), "sync", "status"],
        )
        assert result.exit_code == 0
        assert "Nothing to sync" in result.output

    def test_status_with_conflict_exits_2(
        self, runner, mock_sync_client, tmp_path
    ):
        from grantkit.sync_plan import ChangeKind, EntityChange, SyncPlan

        plan = SyncPlan(
            changes=[
                EntityChange(
                    entity_type="response",
                    grant_id="g1",
                    entity_id="abstract",
                    kind=ChangeKind.CONFLICT,
                )
            ]
        )
        mock_sync_client.compute_plan.return_value = plan

        result = runner.invoke(
            main,
            ["--project-root", str(tmp_path), "sync", "status"],
        )
        assert result.exit_code == 2
        assert "abstract" in result.output

    def test_status_offline_skips_cloud_probe(
        self, runner, mock_sync_client, tmp_path
    ):
        from grantkit.sync_plan import SyncPlan

        mock_sync_client.compute_plan.return_value = SyncPlan(changes=[])

        runner.invoke(
            main,
            ["--project-root", str(tmp_path), "sync", "status", "--offline"],
        )
        _, kwargs = mock_sync_client.compute_plan.call_args
        assert kwargs.get("include_cloud") is False


class TestSyncPushCommand:
    def test_push_dry_run_renders_plan(
        self, runner, mock_sync_client, tmp_path
    ):
        from grantkit.sync_plan import ChangeKind, EntityChange, SyncPlan

        plan = SyncPlan(
            changes=[
                EntityChange(
                    entity_type="response",
                    grant_id="g1",
                    entity_id="abstract",
                    kind=ChangeKind.LOCAL_ONLY_ADDED,
                )
            ]
        )
        mock_sync_client.push.return_value = {
            "grants": 0,
            "responses": 0,
            "deleted": 0,
            "errors": [],
            "plan": plan,
            "push_candidates": 1,
            "delete_candidates": 0,
            "conflicts": 0,
        }

        result = runner.invoke(
            main,
            [
                "--project-root",
                str(tmp_path),
                "sync",
                "push",
                "--dry-run",
                "--no-validate",
            ],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "abstract" in result.output

    def test_push_conflict_exits_1_with_hint(
        self, runner, mock_sync_client, tmp_path
    ):
        from grantkit.sync import SyncConflictError
        from grantkit.sync_plan import ChangeKind, EntityChange, SyncPlan

        plan = SyncPlan(
            changes=[
                EntityChange(
                    entity_type="response",
                    grant_id="g1",
                    entity_id="abstract",
                    kind=ChangeKind.CONFLICT,
                )
            ]
        )
        mock_sync_client.push.side_effect = SyncConflictError(plan)

        result = runner.invoke(
            main,
            [
                "--project-root",
                str(tmp_path),
                "sync",
                "push",
                "--no-validate",
            ],
        )
        assert result.exit_code == 1
        assert "Conflict" in result.output
        assert "--force" in result.output

    def test_push_forwards_flags_to_client(
        self, runner, mock_sync_client, tmp_path
    ):
        mock_sync_client.push.return_value = {
            "grants": 0,
            "responses": 0,
            "deleted": 0,
            "errors": [],
        }
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(tmp_path),
                "sync",
                "push",
                "--force",
                "--with-deletes",
                "--no-validate",
            ],
        )
        assert result.exit_code == 0
        _, kwargs = mock_sync_client.push.call_args
        assert kwargs["force"] is True
        assert kwargs["with_deletes"] is True
        assert kwargs["dry_run"] is False


class TestSyncPullCommand:
    def test_pull_with_skipped_local_edits_surfaces_them(
        self, runner, mock_sync_client, tmp_path
    ):
        mock_sync_client.pull.return_value = {
            "grants": 1,
            "responses": 0,
            "files_written": 1,
            "skipped_local_edits": ["g1/responses/abstract.md"],
        }

        result = runner.invoke(
            main,
            ["--project-root", str(tmp_path), "sync", "pull"],
        )
        assert result.exit_code == 0
        assert "abstract.md" in result.output
        assert "Kept local changes" in result.output

    def test_pull_conflict_exits_1(self, runner, mock_sync_client, tmp_path):
        from grantkit.sync import SyncConflictError
        from grantkit.sync_plan import ChangeKind, EntityChange, SyncPlan

        plan = SyncPlan(
            changes=[
                EntityChange(
                    entity_type="grant",
                    grant_id="g1",
                    entity_id="g1",
                    kind=ChangeKind.CONFLICT,
                )
            ]
        )
        mock_sync_client.pull.side_effect = SyncConflictError(plan)

        result = runner.invoke(
            main,
            ["--project-root", str(tmp_path), "sync", "pull"],
        )
        assert result.exit_code == 1
        assert "Conflict" in result.output
        assert "--force" in result.output


class TestSyncIntegration:
    """Check the CLI wires through to a real in-memory SyncState."""

    def test_status_reads_baseline_from_state_file(
        self, runner, mock_sync_client, tmp_path
    ):
        # Seed a state file so compute_plan semantics would normally
        # see "no local edits" — but since we mock compute_plan we
        # just check the CLI dispatches without error even when a
        # state file already exists.
        _write_grant(tmp_path, "g1")
        state = SyncState()
        state.set_grant(
            "g1",
            GrantState(grant=EntityState(updated_at="t1", content_hash="h1")),
        )
        save_state(tmp_path, state)

        from grantkit.sync_plan import SyncPlan

        mock_sync_client.compute_plan.return_value = SyncPlan(changes=[])

        result = runner.invoke(
            main,
            ["--project-root", str(tmp_path), "sync", "status"],
        )
        assert result.exit_code == 0
