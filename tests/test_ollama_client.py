from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ollama import ResponseError
from typer.testing import CliRunner

import doxify.cli as cli
import doxify.ollama_client as ollama_client
from doxify.errors import DoxifyError, ModelError
from doxify.ollama_client import OllamaClient


def _use_temp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DOXIFY_PROVIDER",
        "DOXIFY_MODEL",
        "DOXIFY_OLLAMA_HOST",
        "OLLAMA_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    models: list[str] | Exception = (),
    chat_response: Any = None,
) -> type:
    class FakeClient:
        last: FakeClient

        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            FakeClient.last = self

        def list(self) -> SimpleNamespace:
            if isinstance(models, Exception):
                raise models
            return SimpleNamespace(
                models=[SimpleNamespace(model=name) for name in models]
            )

        def chat(self, **kwargs: Any) -> Any:
            self.chat_kwargs = kwargs
            if isinstance(chat_response, Exception):
                raise chat_response
            return chat_response

    monkeypatch.setattr(ollama_client, "Client", FakeClient)
    return FakeClient


def test_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    fake = _install_fake_client(monkeypatch)

    client = OllamaClient()

    assert client.provider == "local"
    assert client.is_cloud is False
    assert client.model == "gemma3:1b"
    assert client.host == "http://127.0.0.1:11434"
    assert client.api_key is None
    assert fake.last.kwargs["headers"] is None


def test_cloud_defaults_and_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    fake = _install_fake_client(monkeypatch)

    client = OllamaClient(provider="cloud")

    assert client.provider == "cloud"
    assert client.is_cloud is True
    assert client.model == "gemma4:31b"
    assert client.host == "https://ollama.com"
    assert fake.last.kwargs["headers"] == {"Authorization": "Bearer secret"}


def test_cloud_without_key_reports_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_temp_env(monkeypatch)
    _install_fake_client(monkeypatch)

    client = OllamaClient(provider="cloud")

    healthy, detail = client.health()
    assert healthy is False
    assert "OLLAMA_API_KEY" in detail
    with pytest.raises(ModelError, match="OLLAMA_API_KEY"):
        client.ensure_ready()


def test_cloud_model_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    _install_fake_client(monkeypatch, models=["gemma4:31b"])

    healthy, detail = OllamaClient(provider="cloud").health()

    assert healthy is True
    assert "gemma4:31b" in detail


def test_cloud_reports_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    _install_fake_client(monkeypatch, models=["other:1b"])

    healthy, detail = OllamaClient(provider="cloud").health()

    assert healthy is False
    assert "gemma4:31b" in detail
    assert "https://ollama.com/library?c=cloud" in detail


def test_cloud_auth_error_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    _install_fake_client(
        monkeypatch,
        chat_response=ResponseError("Unauthorized", 401),
    )

    client = OllamaClient(provider="cloud", api_key="bad")

    with pytest.raises(ModelError, match="rejected the API key"):
        client.chat([{"role": "user", "content": "hello"}])


def test_cloud_chat_omits_local_keep_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    fake = _install_fake_client(
        monkeypatch,
        chat_response=SimpleNamespace(message=SimpleNamespace(content="ok")),
    )

    client = OllamaClient(provider="cloud", api_key="secret")
    assert client.chat([{"role": "user", "content": "hello"}]) == "ok"
    assert "keep_alive" not in fake.last.chat_kwargs
    assert fake.last.chat_kwargs["model"] == "gemma4:31b"


def test_env_overrides_provider_model_and_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    monkeypatch.setenv("DOXIFY_PROVIDER", "cloud")
    monkeypatch.setenv("DOXIFY_MODEL", "custom:1b")
    monkeypatch.setenv("DOXIFY_OLLAMA_HOST", "https://example.test")
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    _install_fake_client(monkeypatch)

    client = OllamaClient()

    assert client.provider == "cloud"
    assert client.model == "custom:1b"
    assert client.host == "https://example.test"


def test_ollama_com_host_infers_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    _install_fake_client(monkeypatch)

    client = OllamaClient(host="https://ollama.com")

    assert client.is_cloud is True
    assert client.model == "gemma4:31b"


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_temp_env(monkeypatch)
    _install_fake_client(monkeypatch)

    with pytest.raises(ModelError, match="Unknown provider"):
        OllamaClient(provider="mainframe")


def test_doctor_cloud_without_key_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_temp_env(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(cli.app, ["doctor", "--provider", "cloud"])

    assert result.exit_code == 1
    assert "OLLAMA_API_KEY" in result.output


def test_compile_uses_resolved_cloud_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        model = "gemma4:31b"
        provider = "cloud"
        host = "https://ollama.com"
        is_cloud = True
        api_key = "secret"

    def fake_compile(*_args: object, **kwargs: object) -> None:
        captured.update(kwargs)
        raise DoxifyError("stop")

    monkeypatch.setattr(cli, "OllamaClient", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(cli, "compile_repo", fake_compile)
    runner = CliRunner()

    result = runner.invoke(
        cli.app,
        ["compile", str(tmp_path), "--provider", "cloud"],
    )

    assert result.exit_code == 1
    assert captured["model"] == "gemma4:31b"
    assert "Cloud mode" in result.output
