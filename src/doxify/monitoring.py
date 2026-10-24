from __future__ import annotations

import importlib.metadata
import logging
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sentry_sdk
import sentry_sdk.logger as sentry_logger
from sentry_sdk import crons
from sentry_sdk.consts import OP, SPANDATA
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.tracing import Span, Transaction

from .redaction import (
    SAFE_DATA_COLLECTION,
    SAFE_LOG_FIELDS,
    redact_text,
    redact_value,
    safe_url,
    sanitize_breadcrumb,
    sanitize_event,
    sanitize_log,
    sanitize_transaction,
)

DEFAULT_MONITOR_SLUG = "doxify-nightly"
DEFAULT_TRACES_SAMPLE_RATE = 0.2
MONITOR_CONFIG = {
    "schedule": {"type": "crontab", "value": "0 3 * * *"},
    "checkin_margin": 10,
    "max_runtime": 15,
    "timezone": "UTC",
    "failure_issue_threshold": 2,
    "recovery_threshold": 1,
}

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_initialized = False
_current_transaction: ContextVar[Transaction | Span | None] = ContextVar(
    "doxify_transaction", default=None
)
_current_stage: ContextVar[Span | None] = ContextVar("doxify_stage", default=None)


@dataclass(frozen=True)
class MonitoringStatus:
    enabled: bool = False
    initialized: bool = False
    dsn_configured: bool = False
    environment: str = "development"
    release: str | None = None
    traces_sample_rate: float = DEFAULT_TRACES_SAMPLE_RATE
    logs_enabled: bool = False
    error: str | None = None


_status = MonitoringStatus()


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _env_float(name: str, *, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return min(max(value, 0.0), 1.0)


def _release() -> str:
    configured = os.environ.get("SENTRY_RELEASE")
    if configured:
        return configured
    try:
        version = importlib.metadata.version("doxify")
    except importlib.metadata.PackageNotFoundError:
        version = "0.1.0"
    return f"doxify@{version}"


def _environment() -> str:
    return os.environ.get("SENTRY_ENVIRONMENT", "development")


def _dsn() -> str | None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return None
    if not _env_bool("DOXIFY_SENTRY", default=True):
        return None
    return dsn


def _monitor_slug() -> str | None:
    return os.environ.get("SENTRY_MONITOR_SLUG")


def init_monitoring() -> bool:
    """Initialize Sentry only when an explicit DSN is configured.

    Initialization failures are non-fatal: the CLI continues without telemetry.
    """
    global _initialized, _status

    with _lock:
        if _initialized:
            return _status.enabled

        dsn = _dsn()
        traces_sample_rate = _env_float(
            "SENTRY_TRACES_SAMPLE_RATE", default=DEFAULT_TRACES_SAMPLE_RATE
        )
        logs_enabled = _env_bool("SENTRY_SEND_LOGS", default=True)
        status = MonitoringStatus(
            enabled=False,
            initialized=True,
            dsn_configured=dsn is not None,
            environment=_environment(),
            release=_release(),
            traces_sample_rate=traces_sample_rate,
            logs_enabled=logs_enabled,
        )

        if dsn is None:
            _status = status
            _initialized = True
            return False

        try:
            sentry_sdk.init(
                dsn=dsn,
                release=status.release,
                environment=status.environment,
                traces_sample_rate=traces_sample_rate,
                profiles_sample_rate=0.0,
                data_collection=SAFE_DATA_COLLECTION,
                default_integrations=False,
                auto_enabling_integrations=False,
                integrations=[DedupeIntegration()],
                before_send=sanitize_event,
                before_breadcrumb=sanitize_breadcrumb,
                before_send_transaction=sanitize_transaction,
                before_send_log=sanitize_log,
                enable_logs=logs_enabled,
                max_breadcrumbs=20,
                max_value_length=1024,
                server_name="doxify-cli",
                project_root=str(Path(__file__).resolve().parents[1]),
                debug=_env_bool("SENTRY_DEBUG", default=False),
                attach_stacktrace=False,
                auto_session_tracking=False,
            )
        except Exception as exc:
            _status = MonitoringStatus(
                enabled=False,
                initialized=True,
                dsn_configured=True,
                environment=status.environment,
                release=status.release,
                traces_sample_rate=traces_sample_rate,
                logs_enabled=logs_enabled,
                error=redact_text(exc),
            )
            _initialized = True
            _log.warning("Sentry initialization failed; continuing without monitoring.")
            return False

        _status = MonitoringStatus(
            enabled=True,
            initialized=True,
            dsn_configured=True,
            environment=status.environment,
            release=status.release,
            traces_sample_rate=traces_sample_rate,
            logs_enabled=logs_enabled,
        )
        _initialized = True
        _log.warning(
            "Sentry monitoring enabled: errors and timings only. "
            "Disable with DOXIFY_SENTRY=0 or an empty SENTRY_DSN."
        )
        return True


def reset_monitoring() -> None:
    """Reset module state. Intended for tests."""
    global _initialized, _status
    _initialized = False
    _status = MonitoringStatus()
    _current_transaction.set(None)
    _current_stage.set(None)


def monitoring_status() -> MonitoringStatus:
    return _status


def is_monitoring_enabled() -> bool:
    return _status.enabled


def report_exception(
    exc: BaseException,
    *,
    command: str | None = None,
    stage: str | None = None,
) -> None:
    if not _status.enabled:
        return
    try:
        with sentry_sdk.new_scope() as scope:
            if command:
                scope.set_tag("command", command)
            if stage:
                scope.set_tag("stage", stage)
            scope.set_context(
                "doxify",
                {
                    "command": command or "unknown",
                    "stage": stage or "unknown",
                    "provider": "unknown",
                },
            )
            sentry_sdk.capture_exception(exc)
    except Exception:
        _log.debug("Failed to report exception to Sentry.", exc_info=True)


def flush_monitoring(timeout: float = 2.0) -> None:
    if not _status.enabled:
        return
    try:
        sentry_sdk.flush(timeout=timeout)
    except Exception:
        _log.debug("Failed to flush Sentry events.", exc_info=True)


def capture_log(level: str, event: str, fields: dict[str, Any]) -> None:
    if not _status.enabled or not _status.logs_enabled:
        return
    attributes = {
        key: redact_value(value)
        for key, value in fields.items()
        if key in SAFE_LOG_FIELDS and isinstance(value, (str, int, float, bool))
    }
    attributes["doxify.event"] = redact_text(event)
    try:
        level_name = {"critical": "fatal"}.get(level, level)
        logger = getattr(sentry_logger, level_name, sentry_logger.info)
        logger(event, attributes=attributes)
    except Exception:
        _log.debug("Failed to send structured log to Sentry.", exc_info=True)


def set_measurement(name: str, value: float, unit: str = "") -> None:
    if not _status.enabled:
        return
    transaction = _current_transaction.get()
    if transaction is None:
        return
    try:
        transaction.set_measurement(name, float(value), unit)
    except (TypeError, ValueError):
        return


def set_tag(name: str, value: str) -> None:
    if not _status.enabled:
        return
    transaction = _current_transaction.get()
    if transaction is None:
        return
    transaction.set_tag(name, value)


def begin_stage(name: str) -> None:
    if not _status.enabled:
        return
    end_stage()
    transaction = _current_transaction.get()
    if transaction is None:
        return
    span = transaction.start_child(op="doxify.stage", name=name)
    span.set_data("doxify.stage", name)
    _current_stage.set(span)


def end_stage(status: str = "ok") -> None:
    if not _status.enabled:
        return
    span = _current_stage.get()
    if span is None:
        return
    try:
        span.set_status(status)
        span.finish()
    finally:
        _current_stage.set(None)


@contextmanager
def command_transaction(command: str) -> Iterator[None]:
    if not _status.enabled:
        yield
        return

    started = time.perf_counter()
    transaction = sentry_sdk.start_transaction(
        name=f"doxify.{command}",
        op="cli.command",
    )
    transaction.set_tag("command", command)
    transaction.set_data("doxify.command", command)
    token = _current_transaction.set(transaction)
    failed = False
    exit_code = 0

    try:
        with transaction:
            try:
                yield
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1
                transaction.set_tag("exit_code", str(exit_code))
                transaction.set_tag(
                    "outcome", "ok" if exit_code == 0 else "user_error"
                )
                transaction.set_status(
                    "ok" if exit_code == 0 else "invalid_argument"
                )
                failed = exit_code != 0
                raise
            except KeyboardInterrupt:
                transaction.set_tag("outcome", "cancelled")
                transaction.set_status("cancelled")
                failed = True
                raise
            except BaseException as exc:
                failed = True
                transaction.set_tag("outcome", "error")
                transaction.set_status("internal_error")
                report_exception(exc, command=command)
                raise
            else:
                transaction.set_tag("outcome", "ok")
                transaction.set_status("ok")
            finally:
                end_stage("error" if failed else "ok")
                transaction.set_measurement(
                    "doxify.command.duration_ms",
                    (time.perf_counter() - started) * 1000,
                    "millisecond",
                )
    finally:
        _current_transaction.reset(token)


@contextmanager
def span(name: str, *, op: str = "doxify.operation") -> Iterator[Span | None]:
    if not _status.enabled:
        yield None
        return
    with sentry_sdk.start_span(op=op, name=name) as current:
        yield current


@contextmanager
def model_span(
    *,
    provider: str,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Iterator[Span | None]:
    if not _status.enabled:
        yield None
        return
    with sentry_sdk.start_span(op=OP.GEN_AI_CHAT, name="model.chat") as current:
        current.set_data(SPANDATA.GEN_AI_SYSTEM, "ollama")
        current.set_data(SPANDATA.GEN_AI_PROVIDER_NAME, provider)
        current.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model)
        if temperature is not None:
            current.set_data(SPANDATA.GEN_AI_REQUEST_TEMPERATURE, temperature)
        if max_tokens is not None:
            current.set_data(SPANDATA.GEN_AI_REQUEST_MAX_TOKENS, max_tokens)
        yield current


def record_model_usage(
    span: Span | None,
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    duration_ms: float | None = None,
) -> None:
    if span is None:
        return
    if prompt_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, prompt_tokens)
    if completion_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS, completion_tokens)
    if total_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_TOTAL_TOKENS, total_tokens)
    if duration_ms is not None:
        span.set_measurement("doxify.model.duration_ms", duration_ms, "millisecond")


@contextmanager
def http_span(label: str, url: str) -> Iterator[Span | None]:
    if not _status.enabled:
        yield None
        return
    with sentry_sdk.start_span(op=OP.HTTP_CLIENT, name=label) as current:
        current.set_data("http.method", "GET")
        current.set_data("http.url", safe_url(url))
        yield current


@contextmanager
def cron_monitor(
    monitor_slug: str | None = None,
    monitor_config: dict[str, Any] | None = None,
) -> Iterator[None]:
    if not _status.enabled:
        yield
        return
    slug = monitor_slug or _monitor_slug()
    if not slug:
        yield
        return
    with crons.monitor(
        monitor_slug=slug,
        monitor_config=monitor_config or MONITOR_CONFIG,
    ):
        yield
