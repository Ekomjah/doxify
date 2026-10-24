from __future__ import annotations

import os

import sentry_sdk

DSN = "https://cfb2154aff4c5c1639a7a8b2c6a9a4b6@o4512310108094464.ingest.us.sentry.io/4512310172123136"

_client = None


def init_monitoring() -> bool:
    """Initialize Sentry error monitoring and tracing.

    The DSN may be overridden with SENTRY_DSN. Returns True when monitoring
    is active.
    """
    global _client
    dsn = os.environ.get("SENTRY_DSN", DSN)
    if not dsn:
        return False
    _client = sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=1.0,
        release=_guess_release(),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return _client is not None


def report_exception(exc: BaseException) -> None:
    """Capture an exception if monitoring is active. Safe to call always."""
    if _client is not None:
        sentry_sdk.capture_exception(exc)


def _guess_release() -> str | None:
    release = os.environ.get("SENTRY_RELEASE")
    if release:
        return release
    try:
        from git import Repo

        repo = Repo(__file__, search_parent_directories=True)
        return repo.head.commit.hexsha[:12]
    except Exception:
        return None
