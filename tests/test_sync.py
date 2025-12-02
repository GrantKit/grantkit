"""Tests for grantkit sync functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from grantkit.sync import (
    GrantKitSync,
    SyncConfig,
    get_sync_client,
)


class TestSyncConfig:
    """Tests for SyncConfig class."""

    def test_from_env_missing_key(self):
        """Should raise ValueError when GRANTKIT_SUPABASE_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("GRANTKIT_SUPABASE_KEY", None)
            with pytest.raises(ValueError, match="GRANTKIT_SUPABASE_KEY"):
                SyncConfig.from_env(Path("/tmp"))

    def test_from_env_with_key(self):
        """Should create config when key is provided."""
        with patch.dict(
            os.environ, {"GRANTKIT_SUPABASE_KEY": "test-key"}, clear=True
        ):
            config = SyncConfig.from_env(Path("/tmp"))
            assert config.supabase_key == "test-key"
            assert (
                config.supabase_url
                == "https://jgrvjvqhrngcdmtrojlk.supabase.co"
            )
            assert config.grants_dir == Path("/tmp")

    def test_from_env_custom_url(self):
        """Should use custom URL from environment."""
        with patch.dict(
            os.environ,
            {
                "GRANTKIT_SUPABASE_KEY": "test-key",
                "GRANTKIT_SUPABASE_URL": "https://custom.supabase.co",
            },
            clear=True,
        ):
            config = SyncConfig.from_env(Path("/tmp"))
            assert config.supabase_url == "https://custom.supabase.co"

    def test_from_file(self):
        """Should create config from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "grantkit.yaml"
            config_data = {
                "sync": {
                    "supabase_url": "https://test.supabase.co",
                    "supabase_key": "file-key",
                    "grant_id": "test-grant",
                }
            }
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            config = SyncConfig.from_file(config_path, Path(tmpdir))
            assert config.supabase_url == "https://test.supabase.co"
            assert config.supabase_key == "file-key"
            assert config.grant_id == "test-grant"


class TestGrantKitSync:
    """Tests for GrantKitSync class."""

    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        with patch("grantkit.sync.create_client") as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def sync_config(self, tmp_path):
        """Create a test config."""
        return SyncConfig(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            grants_dir=tmp_path,
        )

    def test_pull_creates_directories(self, mock_supabase, sync_config):
        """Pull should create grant directories."""
        # Mock grants response
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = [
            {
                "id": "test-grant",
                "name": "Test Grant",
                "foundation": "Test Foundation",
                "status": "draft",
            }
        ]
        # Mock responses response (empty)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        sync = GrantKitSync(sync_config)
        stats = sync.pull()

        assert stats["grants"] == 1
        assert (sync_config.grants_dir / "test-grant").exists()
        assert (sync_config.grants_dir / "test-grant" / "grant.yaml").exists()

    def test_pull_writes_grant_yaml(self, mock_supabase, sync_config):
        """Pull should write grant metadata to YAML."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = [
            {
                "id": "test-grant",
                "name": "Test Grant",
                "foundation": "Test Foundation",
                "amount_requested": 100000,
                "status": "draft",
            }
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        sync = GrantKitSync(sync_config)
        sync.pull()

        grant_yaml = sync_config.grants_dir / "test-grant" / "grant.yaml"
        with open(grant_yaml) as f:
            data = yaml.safe_load(f)

        assert data["id"] == "test-grant"
        assert data["name"] == "Test Grant"
        assert data["amount_requested"] == 100000

    def test_pull_writes_responses(self, mock_supabase, sync_config):
        """Pull should write responses as markdown with frontmatter."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = [
            {"id": "test-grant", "name": "Test Grant", "foundation": "Test"}
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "key": "abstract",
                "title": "Project Abstract",
                "content": "This is the abstract.",
                "status": "draft",
                "word_limit": 250,
            }
        ]

        sync = GrantKitSync(sync_config)
        sync.pull()

        response_file = (
            sync_config.grants_dir / "test-grant" / "responses" / "abstract.md"
        )
        assert response_file.exists()

        content = response_file.read_text()
        assert "---" in content  # Has frontmatter
        assert "title: Project Abstract" in content
        assert "word_limit: 250" in content
        assert "This is the abstract." in content

    def test_push_reads_grant_yaml(self, mock_supabase, sync_config):
        """Push should read and upsert grant from YAML."""
        # Create grant directory and YAML
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)
        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "Test",
                },
                f,
            )

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        stats = sync.push(grant_id="test-grant")

        assert stats["grants"] == 1
        # Verify upsert was called
        mock_supabase.table.assert_called()

    def test_push_reads_response_markdown(self, mock_supabase, sync_config):
        """Push should parse response markdown with frontmatter."""
        # Create grant and response
        grant_dir = sync_config.grants_dir / "test-grant"
        responses_dir = grant_dir / "responses"
        responses_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump({"id": "test-grant", "name": "Test"}, f)

        response_content = """---
title: Project Abstract
key: abstract
word_limit: 250
status: draft
---

This is the abstract content.
"""
        with open(responses_dir / "abstract.md", "w") as f:
            f.write(response_content)

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        stats = sync.push(grant_id="test-grant")

        assert stats["responses"] == 1

    def test_parse_response_file(self, sync_config, mock_supabase):
        """_parse_response_file should correctly parse frontmatter."""
        # Create a response file
        responses_dir = sync_config.grants_dir / "responses"
        responses_dir.mkdir(parents=True)

        response_content = """---
title: Test Section
key: test_section
word_limit: 500
question: What is your approach?
---

The response content here.
With multiple lines.
"""
        response_file = responses_dir / "test_section.md"
        with open(response_file, "w") as f:
            f.write(response_content)

        sync = GrantKitSync(sync_config)
        result = sync._parse_response_file(response_file, "grant-123")

        assert result["grant_id"] == "grant-123"
        assert result["key"] == "test_section"
        assert result["title"] == "Test Section"
        assert result["word_limit"] == 500
        assert result["question"] == "What is your approach?"
        assert "The response content here." in result["content"]
        assert "With multiple lines." in result["content"]

    def test_parse_response_file_no_frontmatter(
        self, sync_config, mock_supabase
    ):
        """Should handle files without frontmatter."""
        responses_dir = sync_config.grants_dir / "responses"
        responses_dir.mkdir(parents=True)

        response_file = responses_dir / "simple.md"
        with open(response_file, "w") as f:
            f.write("Just plain content.")

        sync = GrantKitSync(sync_config)
        result = sync._parse_response_file(response_file, "grant-123")

        assert result["key"] == "simple"
        assert result["content"] == "Just plain content."


class TestGetSyncClient:
    """Tests for get_sync_client function."""

    def test_uses_env_when_no_config_file(self, tmp_path):
        """Should use environment variables when no config file exists."""
        with patch.dict(
            os.environ, {"GRANTKIT_SUPABASE_KEY": "env-key"}, clear=True
        ):
            with patch("grantkit.sync.create_client") as mock_create:
                mock_create.return_value = MagicMock()
                client = get_sync_client(tmp_path)
                assert client.config.supabase_key == "env-key"

    def test_uses_config_file_when_exists(self, tmp_path):
        """Should use config file when it exists."""
        config_path = tmp_path / "grantkit.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"sync": {"supabase_key": "file-key"}}, f)

        with patch("grantkit.sync.create_client") as mock_create:
            mock_create.return_value = MagicMock()
            client = get_sync_client(tmp_path)
            assert client.config.supabase_key == "file-key"


class TestBudgetSync:
    """Tests for budget sync functionality - ensuring budget.yaml is source of truth."""

    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        with patch("grantkit.sync.create_client") as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def sync_config(self, tmp_path):
        """Create a test config."""
        return SyncConfig(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            grants_dir=tmp_path,
        )

    def test_push_syncs_budget_to_grant_yaml(self, mock_supabase, sync_config):
        """Push should sync budget.yaml totals to grant.yaml before pushing."""
        # Create grant directory with grant.yaml (has old amount_requested)
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "Test Foundation",
                    "amount_requested": 100000,  # Old value - should be updated
                },
                f,
            )

        # Create budget.yaml that calculates to $150,000
        with open(grant_dir / "budget.yaml", "w") as f:
            yaml.dump(
                {
                    "years_in_budget": 1,
                    "personnel": {
                        "senior_key": [
                            {
                                "name": "Test PI",
                                "role": "PI",
                                "base_salary": 100000,
                                "year_1": 100000,
                            }
                        ]
                    },
                    "fringe_benefits": {"rate": 0.30, "base": "salaries"},
                    "travel": {"domestic": [], "foreign": []},
                    "other_direct_costs": [],
                    "indirect_costs": {"rate": 0.10, "base": "mtdc"},
                },
                f,
            )

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="test-grant")

        # Verify grant.yaml was updated with calculated budget total
        with open(grant_dir / "grant.yaml") as f:
            updated_grant = yaml.safe_load(f)

        # Budget: $100k salary + $30k fringe = $130k direct
        # Indirect: 10% of $130k MTDC = $13k
        # Total: $143,000
        assert updated_grant["amount_requested"] == 143000

    def test_push_sends_calculated_amount_to_supabase(
        self, mock_supabase, sync_config
    ):
        """Push should send the calculated amount_requested to Supabase."""
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "Test Foundation",
                    "amount_requested": 50000,  # Will be overwritten
                },
                f,
            )

        # Budget that calculates to different amount
        with open(grant_dir / "budget.yaml", "w") as f:
            yaml.dump(
                {
                    "years_in_budget": 1,
                    "personnel": {
                        "senior_key": [
                            {
                                "name": "Test PI",
                                "role": "PI",
                                "base_salary": 80000,
                                "year_1": 80000,
                            }
                        ]
                    },
                    "fringe_benefits": {"rate": 0.30, "base": "salaries"},
                    "travel": {"domestic": [], "foreign": []},
                    "other_direct_costs": [],
                    "indirect_costs": {"rate": 0.10, "base": "mtdc"},
                },
                f,
            )

        # Mock select to return empty (grant doesn't exist) so insert is called
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="test-grant")

        # Verify the inserted data has calculated amount
        # Budget: $80k salary + $24k fringe = $104k direct
        # Indirect: 10% of $104k = $10,400
        # Total: $114,400
        insert_call = mock_supabase.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["amount_requested"] == 114400

    def test_push_includes_budget_data_in_jsonb(
        self, mock_supabase, sync_config
    ):
        """Push should include calculated budget summary in budget JSONB column."""
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "Test Foundation",
                },
                f,
            )

        with open(grant_dir / "budget.yaml", "w") as f:
            yaml.dump(
                {
                    "years_in_budget": 2,
                    "personnel": {
                        "senior_key": [
                            {
                                "name": "Test PI",
                                "role": "PI",
                                "base_salary": 100000,
                                "year_1": 50000,
                                "year_2": 50000,
                            }
                        ]
                    },
                    "fringe_benefits": {"rate": 0.30, "base": "salaries"},
                    "travel": {"domestic": [], "foreign": []},
                    "other_direct_costs": [],
                    "indirect_costs": {"rate": 0.10, "base": "mtdc"},
                },
                f,
            )

        # Mock select to return empty (grant doesn't exist) so insert is called
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="test-grant")

        insert_call = mock_supabase.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]

        # Should have budget JSONB with full budget.yaml + summary
        assert "budget" in inserted_data
        # Full budget.yaml content preserved
        assert "years_in_budget" in inserted_data["budget"]
        assert "personnel" in inserted_data["budget"]
        # Summary formatted for app
        assert "summary" in inserted_data["budget"]
        assert "total" in inserted_data["budget"]["summary"]
        assert "total" in inserted_data["budget"]["summary"]["total"]
        assert "year_1" in inserted_data["budget"]["summary"]

    def test_push_without_budget_yaml_uses_grant_yaml_amount(
        self, mock_supabase, sync_config
    ):
        """Push without budget.yaml should use amount_requested from grant.yaml."""
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "Test Foundation",
                    "amount_requested": 75000,
                },
                f,
            )

        # No budget.yaml file

        # Mock select to return empty (grant doesn't exist) so insert is called
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="test-grant")

        insert_call = mock_supabase.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["amount_requested"] == 75000

    def test_push_updates_research_gov_total(self, mock_supabase, sync_config):
        """Push should update research_gov.total_requested when present."""
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "NSF",
                    "amount_requested": 100000,
                    "research_gov": {
                        "total_requested": 100000,  # Should be updated
                        "pi_name": "Test PI",
                    },
                },
                f,
            )

        with open(grant_dir / "budget.yaml", "w") as f:
            yaml.dump(
                {
                    "years_in_budget": 1,
                    "personnel": {
                        "senior_key": [
                            {
                                "name": "Test PI",
                                "role": "PI",
                                "base_salary": 100000,
                                "year_1": 100000,
                            }
                        ]
                    },
                    "fringe_benefits": {"rate": 0.30, "base": "salaries"},
                    "travel": {"domestic": [], "foreign": []},
                    "other_direct_costs": [],
                    "indirect_costs": {"rate": 0.10, "base": "mtdc"},
                },
                f,
            )

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="test-grant")

        # Verify grant.yaml research_gov.total_requested was updated
        with open(grant_dir / "grant.yaml") as f:
            updated_grant = yaml.safe_load(f)

        assert updated_grant["research_gov"]["total_requested"] == 143000

    def test_push_preserves_personnel_year_funds_for_app(
        self, mock_supabase, sync_config
    ):
        """Push should preserve personnel year_1, year_2, year_3 funds for app display."""
        grant_dir = sync_config.grants_dir / "test-grant"
        grant_dir.mkdir(parents=True)

        with open(grant_dir / "grant.yaml", "w") as f:
            yaml.dump(
                {
                    "id": "test-grant",
                    "name": "Test Grant",
                    "foundation": "Test Foundation",
                },
                f,
            )

        # Budget with variable year funds like the real NSF budget
        with open(grant_dir / "budget.yaml", "w") as f:
            yaml.dump(
                {
                    "years_in_budget": 3,
                    "personnel": {
                        "senior_key": [
                            {
                                "name": "Max Ghenis",
                                "role": "PI",
                                "base_salary": 180000,
                                "year_1_months": 2.0,
                                "year_2_months": 1.5,
                                "year_3_months": 1.0,
                                "year_1": 30000,
                                "year_2": 22500,
                                "year_3": 15000,
                            },
                            {
                                "name": "Nikhil Woodruff",
                                "role": "Senior Personnel",
                                "base_salary": 150000,
                                "year_1_months": 3.0,
                                "year_2_months": 1.5,
                                "year_3_months": 1.0,
                                "year_1": 37500,
                                "year_2": 18750,
                                "year_3": 12500,
                            },
                        ],
                        "other": [
                            {
                                "category": "Other Professionals",
                                "title": "Research Software Engineer",
                                "base_salary": 140000,
                                "year_1_fte": 0.37,
                                "year_2_fte": 0.56,
                                "year_3_fte": 0.65,
                                "year_1": 51800,
                                "year_2": 78400,
                                "year_3": 91000,
                            }
                        ],
                    },
                    "fringe_benefits": {"rate": 0.30, "base": "salaries"},
                    "travel": {"domestic": [], "foreign": []},
                    "other_direct_costs": [],
                    "indirect_costs": {"rate": 0.10, "base": "mtdc"},
                },
                f,
            )

        # Mock select to return empty (grant doesn't exist) so insert is called
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        sync.push(grant_id="test-grant")

        insert_call = mock_supabase.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]

        # Budget JSONB must preserve personnel with year_1, year_2, year_3 funds
        budget = inserted_data["budget"]
        assert "personnel" in budget

        # Senior/key personnel must have year funds
        senior_key = budget["personnel"]["senior_key"]
        assert len(senior_key) == 2

        # Max Ghenis (PI)
        max_data = senior_key[0]
        assert max_data["name"] == "Max Ghenis"
        assert max_data["year_1"] == 30000
        assert max_data["year_2"] == 22500
        assert max_data["year_3"] == 15000
        assert max_data["year_1_months"] == 2.0

        # Nikhil Woodruff
        nikhil_data = senior_key[1]
        assert nikhil_data["year_1"] == 37500
        assert nikhil_data["year_2"] == 18750
        assert nikhil_data["year_3"] == 12500

        # Other personnel must have year funds
        other = budget["personnel"]["other"]
        assert len(other) == 1
        engineer = other[0]
        assert engineer["year_1"] == 51800
        assert engineer["year_2"] == 78400
        assert engineer["year_3"] == 91000
        assert engineer["year_1_fte"] == 0.37
