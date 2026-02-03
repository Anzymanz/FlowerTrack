from __future__ import annotations

import ssl


def make_ssl_context() -> ssl.SSLContext:
    """Return an SSL context using certifi if available."""
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()
