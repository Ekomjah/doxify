from __future__ import annotations

from doxify.redaction import (
    FILTERED,
    REDACTED_PATH,
    redact_text,
    safe_url,
    sanitize_event,
    sanitize_log,
    sanitize_transaction,
)


def test_redacts_tokens_and_absolute_paths() -> None:
    text = (
        "Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz123456 "
        "repo=/home/alice/private/repo file=/Users/alice/secret.py"
    )

    redacted = redact_text(text)

    assert "ghp_" not in redacted
    assert "/home/alice" not in redacted
    assert "/Users/alice" not in redacted
    assert FILTERED in redacted
    assert REDACTED_PATH in redacted


def test_redacts_query_parameters() -> None:
    redacted = redact_text("https://example.test/search?api_key=secret&q=react")

    assert "secret" not in redacted
    assert "api_key=[Filtered]" in redacted
    assert "q=react" in redacted


def test_safe_url_drops_query_and_fragment() -> None:
    assert safe_url("https://api.github.com/repos/x/y?token=secret#frag") == (
        "https://api.github.com/repos/x/y"
    )


def test_sanitize_event_removes_pii_and_locals() -> None:
    event = {
        "server_name": "laptop",
        "user": {"id": 1},
        "request": {"headers": {"Authorization": "Bearer secret"}},
        "extra": {
            "OLLAMA_API_KEY": "secret",
            "doxify.command": "compile",
            "unrelated": "value",
        },
        "tags": {"command": "compile", "repo": "/home/alice/repo"},
        "exception": {
            "values": [
                {
                    "value": "failed at /home/alice/repo/file.py?token=secret",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "/home/alice/repo/file.py",
                                "vars": {"token": "secret"},
                                "context_line": "secret = True",
                            }
                        ]
                    },
                }
            ]
        },
        "breadcrumbs": {
            "values": [
                {"category": "httpx", "message": "token=secret"},
                {"category": "doxify", "message": "stage=/home/alice/repo"},
            ]
        },
    }

    safe = sanitize_event(event)

    assert safe["server_name"] == "doxify-cli"
    assert "user" not in safe
    assert "request" not in safe
    assert safe["extra"] == {"doxify.command": "compile"}
    assert safe["tags"] == {"command": "compile"}
    frame = safe["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert "vars" not in frame
    assert "context_line" not in frame
    assert frame["filename"] == REDACTED_PATH
    assert [crumb["category"] for crumb in safe["breadcrumbs"]["values"]] == ["doxify"]


def test_sanitize_transaction_filters_span_data() -> None:
    event = {
        "spans": [
            {
                "description": "GET /home/alice/repo?token=secret",
                "data": {
                    "http.url": "https://example.test?api_key=secret",
                    "gen_ai.request.model": "gemma3:1b",
                    "unrelated": "value",
                },
                "tags": {"model": "gemma3:1b", "repo": "/home/alice/repo"},
            }
        ],
        "measurements": {
            "doxify.model.duration_ms": 1.2,
            "unrelated": 2.0,
        },
        "extra": {},
    }

    safe = sanitize_transaction(event)

    span = safe["spans"][0]
    assert "http.url" not in span["data"]
    assert span["data"] == {"gen_ai.request.model": "gemma3:1b"}
    assert span["tags"] == {"model": "gemma3:1b"}
    assert safe["measurements"] == {"doxify.model.duration_ms": 1.2}


def test_sanitize_log_drops_message_parameters() -> None:
    safe = sanitize_log(
        {
            "body": "token=secret /home/alice/repo",
            "attributes": {
                "doxify.event": "model.error",
                "doxify.model": "gemma3:1b",
                "sentry.message.parameter.0": "secret",
            },
        }
    )

    assert "secret" not in safe["body"]
    assert safe["attributes"] == {
        "doxify.event": "model.error",
        "doxify.model": "gemma3:1b",
    }
