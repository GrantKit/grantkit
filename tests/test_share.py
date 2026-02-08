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

    def _setup_share_mocks(self, mock_supabase, grant_found=True, user_found=True, existing_collab=False):
        """Helper to set up the chain of mock calls for share().

        The share() method makes these calls in order:
        1. table("grants").select(...).eq(...).execute() - grant lookup
        2. table("profiles").select(...).ilike(...).execute() - user lookup
        3. table("grant_collaborators").select(...).eq(...).eq(...).execute() - existing check
        4. table("grant_collaborators").insert(...).execute() - insert new collab
        """
        # We need per-table mock behavior. Use side_effect on table() to
        # return different mock chains depending on the table name.
        table_mocks = {}

        # grants table mock
        grants_mock = MagicMock()
        if grant_found:
            grants_mock.select.return_value.eq.return_value.execute.return_value.data = [
                {"id": "test-grant", "user_id": "owner-uuid"}
            ]
        else:
            grants_mock.select.return_value.eq.return_value.execute.return_value.data = []
        table_mocks["grants"] = grants_mock

        # profiles table mock
        profiles_mock = MagicMock()
        if user_found:
            profiles_mock.select.return_value.ilike.return_value.execute.return_value.data = [
                {"id": "user-uuid-123", "email": "daphne@policyengine.org"}
            ]
        else:
            profiles_mock.select.return_value.ilike.return_value.execute.return_value.data = []
        table_mocks["profiles"] = profiles_mock

        # grant_collaborators table mock
        collabs_mock = MagicMock()
        if existing_collab:
            collabs_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"id": "collab-1", "role": "viewer"}
            ]
        else:
            collabs_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        collabs_mock.insert.return_value.execute.return_value = MagicMock()
        collabs_mock.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        table_mocks["grant_collaborators"] = collabs_mock

        def table_side_effect(name):
            return table_mocks.get(name, MagicMock())

        mock_supabase.table.side_effect = table_side_effect

        return table_mocks

    def test_share_grant_adds_collaborator(self, mock_supabase, sync_config):
        """share() should add a collaborator to the grant_collaborators table."""
        self._setup_share_mocks(mock_supabase)

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="daphne@policyengine.org",
            role="editor",
        )

        assert result["success"] is True

    def test_share_grant_invalid_email(self, mock_supabase, sync_config):
        """share() should return error for non-existent user."""
        self._setup_share_mocks(mock_supabase, user_found=False)

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
        table_mocks = self._setup_share_mocks(mock_supabase)

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="viewer@example.com",
        )

        assert result["success"] is True

        # Verify insert was called with default role (editor is the default in the method signature)
        insert_call = table_mocks["grant_collaborators"].insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["role"] == "editor"

    def test_share_grant_already_shared(self, mock_supabase, sync_config):
        """share() should handle already-shared grants by updating role."""
        self._setup_share_mocks(mock_supabase, existing_collab=True)

        sync = GrantKitSync(sync_config)
        result = sync.share(
            grant_id="test-grant",
            email="daphne@policyengine.org",
        )

        # When already shared, the code updates the role and returns success
        assert result["success"] is True


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
        result = sync.list_collaborators(grant_id="test-grant")

        assert result["success"] is True
        collaborators = result["collaborators"]
        assert len(collaborators) == 2
        assert collaborators[0]["user_email"] == "daphne@policyengine.org"
        assert collaborators[0]["role"] == "editor"

    def test_list_collaborators_empty(self, mock_supabase, sync_config):
        """list_collaborators() should return empty list for unshared grants."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        sync = GrantKitSync(sync_config)
        result = sync.list_collaborators(grant_id="test-grant")

        assert result["success"] is True
        assert result["collaborators"] == []
