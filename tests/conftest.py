"""Shared fixtures for the GrantKit engine tests."""

from pathlib import Path

import pytest
import yaml


def _write_grant(root: Path, config: dict, responses: dict) -> Path:
    """Write a grant.yaml plus response files under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "grant.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    for rel, content in responses.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def make_grant(tmp_path):
    """Return a factory that writes a grant project and returns its root.

    Usage::

        root = make_grant(config={...}, responses={"responses/x.md": "..."})
    """
    counter = {"n": 0}

    def _factory(config: dict, responses: dict | None = None) -> Path:
        counter["n"] += 1
        root = tmp_path / f"grant{counter['n']}"
        return _write_grant(root, config, responses or {})

    return _factory


@pytest.fixture
def simple_config():
    """A minimal, markdown-friendly grant config with two sections."""
    return {
        "title": "Test Grant",
        "funder": "Test Foundation",
        "program": "Test Program",
        "deadline": "2099-12-31",
        "accepts_markdown": True,
        "locale": "en-US",
        "sections": [
            {
                "id": "summary",
                "title": "Summary",
                "word_limit": 100,
                "required": True,
                "file": "responses/summary.md",
            },
            {
                "id": "narrative",
                "title": "Narrative",
                "word_limit": 50,
                "required": True,
                "file": "responses/narrative.md",
            },
        ],
    }
