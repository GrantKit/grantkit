"""End-to-end CLI tests via Click's CliRunner."""

import json

from click.testing import CliRunner

from grantkit.cli import main


def _init(runner, path, funder="nuffield-rda"):
    return runner.invoke(main, ["init", "--funder", funder, str(path)])


def test_five_verbs_registered():
    assert set(main.commands) == {
        "init",
        "check",
        "build",
        "review",
        "status",
    }


def test_init_and_status(tmp_path):
    runner = CliRunner()
    result = _init(runner, tmp_path)
    assert result.exit_code == 0
    assert (tmp_path / "grant.yaml").exists()

    result = runner.invoke(main, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert "complete" in result.output


def test_check_exit_codes(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)

    # Fresh scaffold: placeholder warnings only -> exit 0.
    result = runner.invoke(main, ["check", str(tmp_path)])
    assert result.exit_code == 0

    # --strict makes the warnings fail.
    result = runner.invoke(main, ["check", "--strict", str(tmp_path)])
    assert result.exit_code == 1

    # Introduce an error (a table survives plain-text conversion).
    (tmp_path / "responses" / "project_summary.md").write_text(
        "| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8"
    )
    result = runner.invoke(main, ["check", str(tmp_path)])
    assert result.exit_code == 1


def test_check_json_is_valid(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    result = runner.invoke(main, ["check", "--json", str(tmp_path)])
    payload = json.loads(result.output)
    assert set(payload) == {"errors", "warnings", "items"}


def test_status_json_writes_file(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    result = runner.invoke(main, ["status", "--json", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "status.json").exists()
    payload = json.loads(result.output)
    assert payload["grantkit_version"] == "0.2.0"


def test_build_share_via_cli(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    result = runner.invoke(
        main, ["build", "--format", "md", "--share", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert (tmp_path / "assembled.html").exists()
    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "proposal.md").exists()


def test_review_outputs_packet(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    result = runner.invoke(main, ["review", str(tmp_path)])
    assert result.exit_code == 0
    packet = json.loads(result.output)
    assert "rubric" in packet
    assert "sections" in packet
    assert "checks" in packet
    assert "pack" not in packet  # only with --pack


def test_review_pack_flag(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    result = runner.invoke(main, ["review", "--pack", str(tmp_path)])
    packet = json.loads(result.output)
    assert "pack" in packet


def test_missing_grant_yaml_exits_2(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["check", str(tmp_path)])
    assert result.exit_code == 2
