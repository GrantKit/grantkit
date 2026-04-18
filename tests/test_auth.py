"""Tests for GrantKit authentication helpers."""

from unittest.mock import MagicMock

from grantkit import auth


def test_device_login_creates_pending_code_before_opening_browser(
    tmp_path, monkeypatch
):
    """device_login should insert the pending device code before opening."""

    events = []
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    monkeypatch.setattr(auth, "CREDENTIALS_FILE", tmp_path / "credentials.json")
    monkeypatch.setattr(auth.secrets, "token_urlsafe", lambda _: "device-code")
    monkeypatch.setattr(auth.time, "sleep", lambda _: None)
    monkeypatch.setattr(auth, "create_client", lambda *_: mock_client)

    def insert_execute():
        events.append("insert")
        return MagicMock()

    def poll_execute():
        events.append("poll")
        return MagicMock(
            data={
                "status": "complete",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_at": 9999999999,
                "user_email": "max@example.com",
            }
        )

    def open_browser(url):
        events.append("open")
        assert url == "https://app.grantkit.io/auth/device?code=device-code"
        return True

    mock_table.insert.return_value.execute.side_effect = insert_execute
    (
        mock_table.select.return_value.eq.return_value.single.return_value.execute
    ).side_effect = poll_execute
    monkeypatch.setattr(auth.webbrowser, "open", open_browser)

    creds = auth.device_login(timeout=1)

    assert creds is not None
    assert creds.user_email == "max@example.com"
    assert events == ["insert", "open", "poll"]


def test_device_login_does_not_open_browser_if_code_creation_fails(
    monkeypatch,
):
    """device_login should stop before browser launch on insert failure."""

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    monkeypatch.setattr(auth.secrets, "token_urlsafe", lambda _: "device-code")
    monkeypatch.setattr(auth, "create_client", lambda *_: mock_client)

    opened = []

    def fail_insert():
        raise RuntimeError("insert failed")

    def open_browser(_url):
        opened.append(True)
        return True

    mock_table.insert.return_value.execute.side_effect = fail_insert
    monkeypatch.setattr(auth.webbrowser, "open", open_browser)

    creds = auth.device_login(timeout=1)

    assert creds is None
    assert opened == []
