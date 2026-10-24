from __future__ import annotations

from typing import Any

import pytest

import doxify.monitoring as monitoring
from doxify.redaction import SAFE_DATA_COLLECTION


class FakeSpan:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.data: dict[str, Any] = {}
        self.measurements: dict[str, Any] = {}
        self.tags: dict[str, str] = {}
        self.status: str | None = None
        self.finished = False
        self.entered = False
        self.children: list[FakeSpan] = []

    def set_data(self, key: str, value: Any) -> None:
        self.data[key] = value

    def set_measurement(self, name: str, value: float, unit: str = "") -> None:
        self.measurements[name] = (value, unit)

    def set_tag(self, key: str, value: str) -> None:
        self.tags[key] = value

    def set_status(self, value: str) -> None:
        self.status = value

    def start_child(self, **kwargs: Any) -> FakeSpan:
        child = FakeSpan(**kwargs)
        self.children.append(child)
        return child

    def finish(self) -> None:
        self.finished = True

    def __enter__(self) -> FakeSpan:
        self.entered = True
        return self

    def __exit__(self, *_args: object) -> None:
        self.finish()


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        monitoring,
        "_status",
        monitoring.MonitoringStatus(
            enabled=True,
            initialized=True,
            dsn_configured=True,
            environment="test",
            release="doxify@test",
            logs_enabled=True,
        ),
    )


def test_monitoring_is_disabled_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "")
    assert monitoring.init_monitoring() is False
    assert monitoring.monitoring_status().enabled is False


def test_monitoring_can_be_explicitly_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.test/1")
    monkeypatch.setenv("DOXIFY_SENTRY", "0")
    assert monitoring.init_monitoring() is False


def test_init_uses_safe_data_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_init(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("SENTRY_DSN", "https://public@example.test/1")
    monkeypatch.setattr(monitoring.sentry_sdk, "init", fake_init)

    assert monitoring.init_monitoring() is True
    assert captured["data_collection"] == SAFE_DATA_COLLECTION
    assert captured["server_name"] == "doxify-cli"
    assert captured["default_integrations"] is False
    assert captured["auto_enabling_integrations"] is False
    assert captured["traces_sample_rate"] == 0.2
    assert captured["enable_logs"] is True
    assert "send_default_pii" not in captured


def test_init_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_init(**_kwargs: Any) -> object:
        raise RuntimeError("bad dsn")

    monkeypatch.setenv("SENTRY_DSN", "https://public@example.test/1")
    monkeypatch.setattr(monitoring.sentry_sdk, "init", fake_init)

    assert monitoring.init_monitoring() is False
    assert monitoring.monitoring_status().error == "bad dsn"


def test_report_exception_is_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("capture should not be called")

    monkeypatch.setattr(monitoring.sentry_sdk, "capture_exception", fail)
    monitoring.report_exception(RuntimeError("ignored"))


def test_command_transaction_records_stage_and_measurements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    transaction = FakeSpan(name="doxify.compile", op="cli.command")
    monkeypatch.setattr(
        monitoring.sentry_sdk, "start_transaction", lambda **_kwargs: transaction
    )

    with monitoring.command_transaction("compile"):
        monitoring.begin_stage("scan")
        monitoring.end_stage()

    assert transaction.tags["command"] == "compile"
    assert transaction.tags["outcome"] == "ok"
    assert transaction.status == "ok"
    assert "doxify.command.duration_ms" in transaction.measurements
    assert transaction.children[0].status == "ok"
    assert transaction.children[0].finished is True
    assert transaction.entered is True
    assert transaction.finished is True
    assert monitoring._current_transaction.get() is None


def test_command_transaction_reports_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    transaction = FakeSpan(name="doxify.compile", op="cli.command")
    captured: list[BaseException] = []
    monkeypatch.setattr(
        monitoring.sentry_sdk, "start_transaction", lambda **_kwargs: transaction
    )
    monkeypatch.setattr(
        monitoring,
        "report_exception",
        lambda exc, **_kwargs: captured.append(exc),
    )

    with pytest.raises(RuntimeError, match="boom"), monitoring.command_transaction("compile"):
        raise RuntimeError("boom")

    assert transaction.status == "internal_error"
    assert transaction.tags["outcome"] == "error"
    assert len(captured) == 1


def test_command_transaction_marks_user_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    transaction = FakeSpan(name="doxify.compile", op="cli.command")
    monkeypatch.setattr(
        monitoring.sentry_sdk, "start_transaction", lambda **_kwargs: transaction
    )

    with pytest.raises(SystemExit), monitoring.command_transaction("compile"):
        raise SystemExit(1)

    assert transaction.status == "invalid_argument"
    assert transaction.tags["outcome"] == "user_error"
    assert transaction.tags["exit_code"] == "1"


def test_capture_log_sends_safe_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_warning(event: str, **kwargs: Any) -> None:
        captured["event"] = event
        captured.update(kwargs)

    monkeypatch.setattr(monitoring.sentry_logger, "warning", fake_warning)
    monitoring.capture_log(
        "warning",
        "model.error",
        {"model": "gemma3:1b", "prompt": "secret", "status": "connection_error"},
    )

    assert captured["event"] == "model.error"
    assert captured["attributes"]["model"] == "gemma3:1b"
    assert captured["attributes"]["status"] == "connection_error"
    assert "prompt" not in captured["attributes"]


def test_model_span_records_metadata_without_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    span = FakeSpan()
    monkeypatch.setattr(monitoring.sentry_sdk, "start_span", lambda **_kwargs: span)

    with monitoring.model_span(
        provider="local",
        model="gemma3:1b",
        temperature=0.2,
        max_tokens=400,
    ) as current:
        monitoring.record_model_usage(
            current,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            duration_ms=123.0,
        )

    assert span.data["gen_ai.provider.name"] == "local"
    assert span.data["gen_ai.request.model"] == "gemma3:1b"
    assert span.data["gen_ai.usage.total_tokens"] == 15
    assert "gen_ai.input.messages" not in span.data
    assert span.measurements["doxify.model.duration_ms"][0] == 123.0
