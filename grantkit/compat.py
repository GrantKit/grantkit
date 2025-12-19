"""Compatibility fixes for Python 3.14 and other environments."""

import ssl
import sys


def patch_certifi():
    """
    Patch certifi module if certifi.where() is missing.

    This can happen on Python 3.14 with homebrew where certifi
    is installed but broken. We fall back to system SSL certs.
    """
    try:
        import certifi
        # Test if where() exists and works
        certifi.where()
    except (ImportError, AttributeError):
        # certifi is missing or broken - create a shim
        import types

        # Get system CA bundle path
        ssl_context = ssl.create_default_context()
        # On macOS, use the system cert bundle
        if sys.platform == "darwin":
            ca_path = "/etc/ssl/cert.pem"
        else:
            # Linux typically uses this
            ca_path = "/etc/ssl/certs/ca-certificates.crt"

        # Create a fake certifi module
        certifi_shim = types.ModuleType("certifi")
        certifi_shim.where = lambda: ca_path
        certifi_shim.__version__ = "0.0.0"

        # Replace in sys.modules
        sys.modules["certifi"] = certifi_shim


# Apply patch on import
patch_certifi()
