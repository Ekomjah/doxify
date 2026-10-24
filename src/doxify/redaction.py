from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MAX_TEXT_LENGTH = 2048
FILTERED = "[Filtered]"
REDACTED_PATH = "<path>"

SAFE_DATA_COLLECTION: dict[str, Any] = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "off"}},
    "http_bodies": [],
    "url_query_params": {"mode": "off"},
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": False,
    "frame_context_lines": 0,
}

SAFE_TAGS = frozenset(
    {
        "command",
        "environment",
        "exit_code",
        "model",
        "outcome",
        "provider",
        "release",
        "status",
    }
)
SAFE_EXTRA_KEYS = frozenset(
    {
        "command",
        "duration_ms",
        "exit_code",
        "model",
        "provider",
        "stage",
        "status",
    }
)
SAFE_LOG_FIELDS = frozenset(
    {
        "command",
        "completion_tokens",
        "duration_ms",
        "ecosystem",
        "event",
        "exit_code",
        "fallback_changes",
        "matches",
        "model",
        "prompt_tokens",
        "provider",
        "replay_score",
        "stage",
        "status",
        "total_tokens",
        "touching",
    }
)
SAFE_SPAN_DATA_KEYS = frozenset(
    {
        "doxify.stage",
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.request.max_tokens",
        "gen_ai.request.model",
        "gen_ai.request.temperature",
        "gen_ai.response.model",
        "gen_ai.system",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.total_tokens",
        "http.method",
        "http.status_code",
    }
)

_SENSITIVE_KEY_TERMS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "github_token",
    "ollama_api_key",
    "password",
    "passwd",
    "private_key",
    "secret",
    "serpapi",
    "session",
    "token",
)
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)((?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|token|"
        r"secret|password|passwd|authorization)\s*[=:]\s*)([^\s&,'\"]+)"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
_ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![\w.-])/(?:home|Users)/[^\s\"']+"),
    re.compile(r"\b[A-Za-z]:\\Users\\[^\s\"']+"),
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.casefold()
    return any(term in lowered for term in _SENSITIVE_KEY_TERMS)


def _known_paths(paths: tuple[str | Path, ...]) -> list[str]:
    values: set[str] = set()
    for path in (*paths, Path.cwd()):
        try:
            text = str(Path(path).expanduser())
        except (TypeError, ValueError):
            continue
        if text:
            values.add(text)
    return sorted(values, key=len, reverse=True)


def redact_text(value: Any, *, paths: tuple[str | Path, ...] = ()) -> str:
    text = str(value)
    for pattern in _ABSOLUTE_PATH_PATTERNS:
        text = pattern.sub(REDACTED_PATH, text)
    for path in _known_paths(paths):
        text = text.replace(path, REDACTED_PATH)
    text = _SECRET_PATTERNS[0].sub(r"\1" + FILTERED, text)
    text = _SECRET_PATTERNS[1].sub("Bearer " + FILTERED, text)
    for pattern in _SECRET_PATTERNS[2:]:
        text = pattern.sub(FILTERED, text)
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "...[truncated]"
    return text


def redact_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[Truncated]"
    if isinstance(value, dict):
        return {
            redact_text(key): (
                FILTERED if _is_sensitive_key(str(key)) else redact_value(item, depth=depth + 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item, depth=depth + 1) for item in value]
    if isinstance(value, bytes):
        return "[Binary]"
    if isinstance(value, str):
        return redact_text(value)
    return value


def safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return redact_text(value)
    if not parsed.scheme or not parsed.netloc:
        return redact_text(value)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _safe_path(value: Any) -> str:
    text = str(value or "")
    if not text:
        return text
    if text.startswith("/") or re.match(r"^[A-Za-z]:\\", text):
        return REDACTED_PATH
    return Path(text).name or REDACTED_PATH


def _sanitize_extra(extra: Any) -> dict[str, Any]:
    if not isinstance(extra, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in extra.items():
        key_text = str(key)
        if key_text in SAFE_EXTRA_KEYS or key_text.startswith("doxify."):
            safe[key_text] = redact_value(value)
    return safe


def _sanitize_tags(tags: Any) -> dict[str, str]:
    if not isinstance(tags, dict):
        return {}
    return {
        str(key): redact_text(value)
        for key, value in tags.items()
        if str(key) in SAFE_TAGS
    }


def _sanitize_frames(exception: dict[str, Any]) -> None:
    stacktrace = exception.get("stacktrace")
    if not isinstance(stacktrace, dict):
        return
    frames = stacktrace.get("frames")
    if not isinstance(frames, list):
        return
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for key in ("vars", "pre_context", "context_line", "post_context", "abs_path"):
            frame.pop(key, None)
        if "filename" in frame:
            frame["filename"] = _safe_path(frame["filename"])


def sanitize_breadcrumb(crumb: dict[str, Any], _hint: Any = None) -> dict[str, Any] | None:
    if not isinstance(crumb, dict):
        return None
    category = str(crumb.get("category") or "")
    if category not in {"doxify", "doxify.stage", "cli"}:
        return None
    safe = copy.deepcopy(crumb)
    if "message" in safe:
        safe["message"] = redact_text(safe["message"])
    safe["data"] = _sanitize_extra(safe.get("data"))
    return safe


def _sanitize_common(event: dict[str, Any]) -> None:
    event.pop("user", None)
    event.pop("request", None)
    event.pop("modules", None)
    event.pop("device", None)
    event["server_name"] = "doxify-cli"
    event["tags"] = _sanitize_tags(event.get("tags"))
    event["extra"] = _sanitize_extra(event.get("extra"))

    contexts = event.get("contexts")
    if isinstance(contexts, dict):
        event["contexts"] = {
            key: redact_value(value)
            for key, value in contexts.items()
            if key in {"doxify", "runtime", "trace"}
        }

    if "culprit" in event:
        event["culprit"] = redact_text(event["culprit"])
    if "transaction" in event:
        event["transaction"] = redact_text(event["transaction"])

    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            if key in logentry:
                logentry[key] = redact_text(logentry[key])
        params = logentry.get("params")
        if params is not None:
            logentry["params"] = redact_value(params)

    exception = event.get("exception")
    exceptions = exception.get("values", []) if isinstance(exception, dict) else []
    if isinstance(exceptions, list):
        for exception in exceptions:
            if not isinstance(exception, dict):
                continue
            if "value" in exception:
                exception["value"] = redact_text(exception["value"])
            _sanitize_frames(exception)

    breadcrumbs = event.get("breadcrumbs")
    breadcrumbs = breadcrumbs.get("values", []) if isinstance(breadcrumbs, dict) else []
    if isinstance(breadcrumbs, list):
        cleaned = [
            crumb
            for item in breadcrumbs
            if (crumb := sanitize_breadcrumb(item)) is not None
        ]
        event["breadcrumbs"] = {"values": cleaned}


def sanitize_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    safe = copy.deepcopy(event)
    _sanitize_common(safe)
    return safe


def sanitize_transaction(event: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    safe = sanitize_event(event, _hint)
    spans = safe.get("spans")
    if isinstance(spans, list):
        for span in spans:
            if not isinstance(span, dict):
                continue
            if "description" in span:
                span["description"] = redact_text(span["description"])
            span["tags"] = _sanitize_tags(span.get("tags"))
            data = span.get("data")
            if isinstance(data, dict):
                span["data"] = {
                    str(key): redact_value(value)
                    for key, value in data.items()
                    if str(key) in SAFE_SPAN_DATA_KEYS or str(key).startswith("doxify.")
                }

    measurements = safe.get("measurements")
    if isinstance(measurements, dict):
        safe["measurements"] = {
            str(key): value
            for key, value in measurements.items()
            if str(key).startswith("doxify.") and isinstance(value, (int, float))
        }
    return safe


def sanitize_log(log: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    safe = copy.deepcopy(log)
    if "body" in safe:
        safe["body"] = redact_text(safe["body"])
    attributes = safe.get("attributes")
    if isinstance(attributes, dict):
        safe["attributes"] = {
            str(key): redact_value(value)
            for key, value in attributes.items()
            if str(key) in SAFE_LOG_FIELDS or str(key).startswith("doxify.")
        }
    return safe
