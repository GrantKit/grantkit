"""Tests for grantkit share functionality."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from grantkit.sync import GrantKitSync, SyncConfig


class TestShareGrant:
    """Tests for sharing grants with collaborators."""

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

    def test_share_grant_adds_collaborator(self, mock_supabase, sync_config):
        """share() should add a collaborator to the grant_collaborators table."""
        # Mock successful user lookup
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": "user-uuid-123",
            "email": "daphne@policyengine.org",
        }
        # Mock successful insert
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="daphne@policyengine.org",
            role="editor",
        )

        assert result["success"] is True
        assert result["email"] == "daphne@policyengine.org"
        assert result["role"] == "editor"

    def test_share_grant_invalid_email(self, mock_supabase, sync_config):
        """share() should return error for non-existent user."""
        # Mock user not found
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
            None
        )

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="nonexistent@example.com",
            role="editor",
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_share_grant_default_role_is_viewer(
        self, mock_supabase, sync_config
    ):
        """share() should default to 'viewer' role if not specified."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": "user-uuid-123",
            "email": "viewer@example.com",
        }
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="viewer@example.com",
        )

        assert result["success"] is True
        assert result["role"] == "viewer"

        # Verify insert was called with viewer role
        insert_call = mock_supabase.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["role"] == "viewer"

    def test_share_grant_already_shared(self, mock_supabase, sync_config):
        """share() should handle already-shared grants gracefully."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": "user-uuid-123",
            "email": "daphne@policyengine.org",
        }
        # Mock duplicate key error
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
            "duplicate key value violates unique constraint"
        )

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="daphne@policyengine.org",
        )

        assert result["success"] is False
        assert "already" in result["error"].lower()


class TestUnshareGrant:
    """Tests for removing collaborators from grants."""

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

    def test_unshare_grant_removes_collaborator(
        self, mock_supabase, sync_config
    ):
        """unshare() should remove a collaborator from grant_collaborators."""
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = (
            MagicMock()
        )

        sync = GrantKitSync(sync_config)
        result = sync.unshare(
            grant_id="test-grant",
            email="daphne@policyengine.org",
        )

        assert result["success"] is True


class TestListCollaborators:
    """Tests for listing grant collaborators."""

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

    def test_list_collaborators_returns_all(self, mock_supabase, sync_config):
        """list_collaborators() should return all collaborators for a grant."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "user_email": "daphne@policyengine.org",
                "role": "editor",
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "user_email": "max@policyengine.org",
                "role": "owner",
                "created_at": "2024-12-01T00:00:00Z",
            },
        ]

        sync = GrantKitSync(sync_config)
        collaborators = sync.list_collaborators(grant_id="test-grant")

        assert len(collaborators) == 2
        assert collaborators[0]["user_email"] == "daphne@policyengine.org"
        assert collaborators[0]["role"] == "editor"

    def test_list_collaborators_empty(self, mock_supabase, sync_config):
        """list_collaborators() should return empty list for unshared grants."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        sync = GrantKitSync(sync_config)
        collaborators = sync.list_collaborators(grant_id="test-grant")

        assert collaborators == []
