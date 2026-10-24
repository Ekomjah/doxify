from __future__ import annotations

import json
import logging

import pytest

from doxify.log import configure_logging, log_event, reset_logging


@pytest.fixture(autouse=True)
def clean_logging() -> None:
    reset_logging()
    yield
    reset_logging()


def test_json_logging_redacts_and_filters_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DOXIFY_LOG_FORMAT", "json")
    monkeypatch.setenv("DOXIFY_LOG_LEVEL", "INFO")
    configure_logging()

    log_event(
        logging.INFO,
        "model.response",
        model="gemma3:1b",
        duration_ms=12.5,
        prompt="do not log this",
    )

    line = capsys.readouterr().err.strip()
    payload = json.loads(line)
    assert payload["event"] == "model.response"
    assert payload["level"] == "info"
    assert payload["model"] == "gemma3:1b"
    assert payload["duration_ms"] == 12.5
    assert "prompt" not in payload
    assert "do not log this" not in line


def test_json_logging_redacts_secret_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DOXIFY_LOG_FORMAT", "json")
    monkeypatch.setenv("DOXIFY_LOG_LEVEL", "INFO")
    configure_logging()

    log_event(
        logging.INFO,
        "stage.start",
        stage="validate",
        status="token=secret /home/alice/repo",
    )

    line = capsys.readouterr().err.strip()
    assert "secret" not in line
    assert "/home/alice" not in line
    assert json.loads(line)["stage"] == "validate"
