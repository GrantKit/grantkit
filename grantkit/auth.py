"""OAuth device flow authentication for GrantKit CLI."""

import json
import logging
import os
import secrets
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from supabase import Client, create_client

logger = logging.getLogger(__name__)

# Constants
DEFAULT_SUPABASE_URL = "https://jgrvjvqhrngcdmtrojlk.supabase.co"
APP_URL = "https://app.grantkit.io"
CREDENTIALS_FILE = Path.home() / ".grantkit" / "credentials.json"


@dataclass
class Credentials:
    """Stored credentials for CLI authentication."""

    access_token: str
    refresh_token: str
    expires_at: float  # Unix timestamp
    user_email: str

    def is_expired(self) -> bool:
        """Check if access token is expired (with 5 min buffer)."""
        return time.time() > (self.expires_at - 300)

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "user_email": self.user_email,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Credentials":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            user_email=data["user_email"],
        )


def save_credentials(creds: Credentials) -> None:
    """Save credentials to disk."""
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(creds.to_dict(), indent=2))
    # Secure permissions (owner read/write only)
    os.chmod(CREDENTIALS_FILE, 0o600)
    logger.info(f"Credentials saved to {CREDENTIALS_FILE}")


def load_credentials() -> Optional[Credentials]:
    """Load credentials from disk."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIALS_FILE.read_text())
        return Credentials.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load credentials: {e}")
        return None


def clear_credentials() -> None:
    """Remove stored credentials."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
        logger.info("Credentials cleared")


def refresh_access_token(creds: Credentials) -> Optional[Credentials]:
    """Refresh an expired access token using the refresh token."""
    supabase_url = os.environ.get("GRANTKIT_SUPABASE_URL", DEFAULT_SUPABASE_URL)
    # Use anon key for refresh - Supabase handles the refresh token validation
    supabase_key = os.environ.get(
        "GRANTKIT_SUPABASE_ANON_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpncnZqdnFocm5nY2RtdHJvamxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQwNTU4MTIsImV4cCI6MjA3OTYzMTgxMn0.hbUgodUx4lAzV7nsRRqDoyvSyOOnoPxBVLzIj0AlOss",
    )

    try:
        client: Client = create_client(supabase_url, supabase_key)
        response = client.auth.refresh_session(creds.refresh_token)

        if response.session:
            new_creds = Credentials(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_at=response.session.expires_at,
                user_email=creds.user_email,
            )
            save_credentials(new_creds)
            logger.info("Access token refreshed")
            return new_creds
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")

    return None


def get_authenticated_client() -> Optional[Client]:
    """
    Get a Supabase client authenticated with the user's credentials.

    Returns None if not logged in or credentials are invalid.
    """
    creds = load_credentials()
    if not creds:
        return None

    # Refresh if expired
    if creds.is_expired():
        creds = refresh_access_token(creds)
        if not creds:
            return None

    supabase_url = os.environ.get("GRANTKIT_SUPABASE_URL", DEFAULT_SUPABASE_URL)
    # Use anon key for initial client creation
    supabase_key = os.environ.get(
        "GRANTKIT_SUPABASE_ANON_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpncnZqdnFocm5nY2RtdHJvamxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQwNTU4MTIsImV4cCI6MjA3OTYzMTgxMn0.hbUgodUx4lAzV7nsRRqDoyvSyOOnoPxBVLzIj0AlOss",
    )

    try:
        client: Client = create_client(supabase_url, supabase_key)
        # Set the session with our stored tokens
        client.auth.set_session(creds.access_token, creds.refresh_token)
        return client
    except Exception as e:
        logger.error(f"Failed to create authenticated client: {e}")
        return None


def device_login(timeout: int = 300) -> Optional[Credentials]:
    """
    Perform OAuth device flow login.

    1. Generate a device code
    2. Open browser to authorization URL
    3. Poll Supabase for completion
    4. Store and return credentials

    Args:
        timeout: Maximum time to wait for user to complete auth (seconds)

    Returns:
        Credentials if successful, None otherwise
    """
    supabase_url = os.environ.get("GRANTKIT_SUPABASE_URL", DEFAULT_SUPABASE_URL)
    supabase_key = os.environ.get(
        "GRANTKIT_SUPABASE_ANON_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpncnZqdnFocm5nY2RtdHJvamxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQwNTU4MTIsImV4cCI6MjA3OTYzMTgxMn0.hbUgodUx4lAzV7nsRRqDoyvSyOOnoPxBVLzIj0AlOss",
    )

    # Generate a unique device code
    device_code = secrets.token_urlsafe(32)

    # Build authorization URL
    auth_url = f"{APP_URL}/auth/device?code={device_code}"

    print(f"\nOpening browser to complete authentication...")
    print(f"If browser doesn't open, visit: {auth_url}\n")

    # Open browser
    webbrowser.open(auth_url)

    # Create Supabase client for polling
    client: Client = create_client(supabase_url, supabase_key)

    # Create the pending device code in the database
    # This allows the web app to find and complete it
    try:
        client.table("device_codes").insert(
            {"code": device_code, "status": "pending"}
        ).execute()
    except Exception as e:
        logger.error(f"Failed to create device code: {e}")
        print(f"\nFailed to initiate login. Please try again.")
        return None

    print("Waiting for authentication...")

    # Poll for completion
    poll_interval = 2  # seconds
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Query the device_codes table
            result = (
                client.table("device_codes")
                .select("*")
                .eq("code", device_code)
                .single()
                .execute()
            )

            if result.data:
                data = result.data
                if data.get("status") == "complete":
                    creds = Credentials(
                        access_token=data["access_token"],
                        refresh_token=data["refresh_token"],
                        expires_at=float(data["expires_at"]),
                        user_email=data["user_email"],
                    )
                    save_credentials(creds)
                    return creds
                elif data.get("status") == "expired":
                    print("\nDevice code expired. Please try again.")
                    return None
                # status == 'pending' - keep polling

        except Exception as e:
            # Unexpected error - log and continue polling
            logger.debug(f"Poll error: {e}")

        time.sleep(poll_interval)

    print("\nAuthentication timed out. Please try again.")
    return None


def get_current_user() -> Optional[str]:
    """Get the email of the currently logged in user."""
    creds = load_credentials()
    if creds:
        return creds.user_email
    return None


def is_logged_in() -> bool:
    """Check if user is logged in with valid credentials."""
    creds = load_credentials()
    if not creds:
        return False

    # Check if expired and try to refresh
    if creds.is_expired():
        refreshed = refresh_access_token(creds)
        return refreshed is not None

    return True
