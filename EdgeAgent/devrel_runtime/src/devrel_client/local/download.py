"""Resilient file download with corporate-proxy TLS auto-retry.

The IQ-9075 retrospective hit ``SSL: CERTIFICATE_VERIFY_FAILED`` when
downloading ResNet-50 on a corporate network: a TLS-inspecting proxy presents
its own CA that Python doesn't trust, and the download dead-ends with no
workaround (IQ9 issue 24).

``download_file`` tries a normal verified download first and, on a certificate
trust failure, automatically retries with a corporate-compatible SSL context:

  1. ``truststore`` (OS trust store — usually already has the corporate CA)
  2. a CA bundle from ``DevRel_CA_BUNDLE`` / ``REQUESTS_CA_BUNDLE`` / ``SSL_CERT_FILE``
  3. an UNVERIFIED context, with a loud warning (last resort)

The manual workaround documented in the quickstart is equivalent to step 3::

    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
"""

from __future__ import annotations

import ssl
import urllib.request
import warnings
from pathlib import Path

__all__ = ["download_file", "is_ssl_cert_error", "corporate_ssl_context"]


def is_ssl_cert_error(exc: BaseException) -> bool:
    """True when an exception chain looks like a TLS trust failure."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ssl.SSLCertVerificationError):
            return True
        msg = str(cur).upper()
        if "CERTIFICATE_VERIFY_FAILED" in msg or "UNABLE TO GET LOCAL ISSUER" in msg:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def corporate_ssl_context() -> tuple[ssl.SSLContext, str]:
    """Build a TLS context that tolerates a corporate proxy CA.

    Returns (context, human-readable strategy label).
    """
    import os

    try:
        import truststore  # noqa: PLC0415

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "OS trust store (truststore)"
    except Exception:  # noqa: BLE001 - truststore optional
        pass

    for env in ("DevRel_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        bundle = os.environ.get(env)
        if bundle and Path(bundle).expanduser().exists():
            return ssl.create_default_context(cafile=str(Path(bundle).expanduser())), f"CA bundle ${env}"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx, "UNVERIFIED (certificate checks disabled)"


def download_file(
    url: str,
    dest: str | Path,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 300.0,
) -> Path:
    """Download ``url`` to ``dest``, auto-retrying on a corporate-proxy TLS error.

    Returns the destination Path. Raises the original error for non-TLS
    failures, or if the retry also fails.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req_headers = headers or {"User-Agent": "devrelAgent/1.0"}

    def _attempt(ctx: ssl.SSLContext | None) -> None:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
        dest.write_bytes(data)

    try:
        _attempt(None)
        return dest
    except Exception as exc:  # noqa: BLE001 - classify then maybe retry
        if not is_ssl_cert_error(exc):
            raise
        ctx, strategy = corporate_ssl_context()
        warnings.warn(
            f"TLS certificate verification failed for {url} — likely a corporate "
            f"proxy. Retrying via {strategy}. Make it permanent by setting "
            f"DevRel_CA_BUNDLE to your corporate CA .pem, or `pip install truststore`.",
            stacklevel=2,
        )
        _attempt(ctx)
        return dest
