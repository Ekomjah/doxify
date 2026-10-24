from __future__ import annotations

import pytest

from doxify import monitoring


@pytest.fixture(autouse=True)
def disable_sentry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "")
    monkeypatch.delenv("DOXIFY_SENTRY", raising=False)
    monitoring.reset_monitoring()
    yield
    monitoring.reset_monitoring()
