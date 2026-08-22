"""AWS transport setup for this project.

Windows Python 3.14 ships with an empty default CA bundle, so every script
that makes outbound HTTPS calls to AWS must inject a working cert store
*before* importing ``boto3`` or ``requests``. This module does that once,
and also unsets ``SSL_CERT_FILE`` so botocore picks up the injected bundle
instead of trying (and failing) to read a non-existent file path.

Call ``ensure_aws_ssl()`` at the top of any script that uses AWS SDKs.
"""

from __future__ import annotations

import os
import sys


def ensure_aws_ssl() -> None:
    """Inject system / OS CA certs into Python's TLS stack.

    Safe to call multiple times (idempotent). Catches the case where
    ``truststore`` is not installed and falls back to doing nothing —
    callers should handle the resulting SSL errors themselves.
    """
    # Clear any user-set cert-file env vars so botocore / urllib3 use the
    # injected OS-native store instead of an explicit file path.
    for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        os.environ.pop(key, None)

    try:
        import truststore  # noqa: PLC0415 (local import)
        truststore.inject_into_ssl()
    except ImportError:
        # Fallback: point SSL_CERT_FILE at certifi if available.
        try:
            import certifi  # noqa: PLC0415
            os.environ["SSL_CERT_FILE"] = certifi.where()
        except ImportError:
            pass  # will fail at connection time with a clear SSLError


__all__ = ["ensure_aws_ssl"]
