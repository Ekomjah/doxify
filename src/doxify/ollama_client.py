from __future__ import annotations

import logging
import os
import time
from typing import Any, Literal

from ollama import Client, RequestError, ResponseError

from .errors import ModelError
from .log import log_event
from .monitoring import model_span, record_model_usage

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:1b"
DEFAULT_CLOUD_HOST = "https://ollama.com"
DEFAULT_CLOUD_MODEL = "gemma4:31b"

Provider = Literal["local", "cloud"]


def _resolve_provider(value: str | None) -> Provider:
    normalized = (value or "local").strip().lower()
    if normalized in {"local", "ollama", "ollama-local"}:
        return "local"
    if normalized in {"cloud", "ollama-cloud"}:
        return "cloud"
    raise ModelError(f"Unknown provider {value!r}. Use 'local' or 'cloud'.")


class OllamaClient:
    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        *,
        provider: str | None = None,
        api_key: str | None = None,
    ) -> None:
        resolved_provider = _resolve_provider(
            provider or os.environ.get("DOXIFY_PROVIDER")
        )
        configured_host = (
            host
            or os.environ.get("DOXIFY_OLLAMA_HOST")
            or (DEFAULT_CLOUD_HOST if resolved_provider == "cloud" else DEFAULT_HOST)
        )
        if "://" not in configured_host:
            configured_host = f"http://{configured_host}"
        self.host = configured_host.rstrip("/")
        self.is_cloud = resolved_provider == "cloud" or "ollama.com" in self.host
        self.provider = "cloud" if self.is_cloud else "local"
        self.model = (
            model
            or os.environ.get("DOXIFY_MODEL")
            or (DEFAULT_CLOUD_MODEL if self.is_cloud else DEFAULT_MODEL)
        )
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY")
        headers = (
            {"Authorization": f"Bearer {self.api_key}"}
            if self.api_key
            else None
        )
        self._client = Client(host=self.host, headers=headers)

    @property
    def label(self) -> str:
        return "Ollama Cloud" if self.is_cloud else "Ollama"

    def health(self) -> tuple[bool, str]:
        if self.is_cloud and not self.api_key:
            return False, (
                "Ollama Cloud requires an API key. Create one at "
                "https://ollama.com/settings/keys and run: "
                "export OLLAMA_API_KEY=..."
            )
        try:
            models = self.list_models()
        except ModelError as exc:
            return False, str(exc)
        if self.model in models:
            return True, f"{self.label} is reachable and {self.model} is available."
        if self.is_cloud:
            return False, (
                f"{self.model} is not available on Ollama Cloud. "
                "Choose another model with --model or see "
                "https://ollama.com/library?c=cloud"
            )
        return False, (
            f"Ollama is reachable, but {self.model} is not installed. "
            f"Run: ollama pull {self.model}"
        )

    def list_models(self) -> list[str]:
        try:
            response = self._client.list()
        except ResponseError as exc:
            raise ModelError(self._response_error(exc)) from exc
        except (RequestError, ConnectionError, OSError) as exc:
            raise ModelError(self._connection_error()) from exc
        return [
            item.model
            for item in response.models
            if getattr(item, "model", None)
        ]

    def ensure_ready(self) -> None:
        healthy, detail = self.health()
        if not healthy:
            raise ModelError(detail)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        num_predict: int = 400,
    ) -> str:
        options: dict[str, Any] = {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": 8192 if self.is_cloud else 4096,
            "num_predict": num_predict,
            "repeat_penalty": 1.1,
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if not self.is_cloud:
            payload["keep_alive"] = "10m"
        started = time.perf_counter()
        try:
            with model_span(
                provider=self.provider,
                model=self.model,
                temperature=temperature,
                max_tokens=num_predict,
            ) as span:
                response = self._client.chat(**payload)
                duration_ms = (time.perf_counter() - started) * 1000
                prompt_tokens = getattr(response, "prompt_eval_count", None)
                completion_tokens = getattr(response, "eval_count", None)
                total_tokens = (
                    (prompt_tokens or 0) + (completion_tokens or 0)
                    if prompt_tokens is not None or completion_tokens is not None
                    else None
                )
                record_model_usage(
                    span,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    duration_ms=duration_ms,
                )
        except ResponseError as exc:
            log_event(
                logging.WARNING,
                "model.error",
                provider=self.provider,
                model=self.model,
                status="response_error",
            )
            raise ModelError(self._response_error(exc)) from exc
        except (RequestError, ConnectionError, OSError) as exc:
            log_event(
                logging.WARNING,
                "model.error",
                provider=self.provider,
                model=self.model,
                status="connection_error",
            )
            raise ModelError(self._connection_error()) from exc

        content = response.message.content
        if not content or not content.strip():
            raise ModelError(f"{self.label} returned an empty response.")
        log_event(
            logging.INFO,
            "model.response",
            provider=self.provider,
            model=self.model,
            duration_ms=round(duration_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        return content.strip()

    def _connection_error(self) -> str:
        if self.is_cloud:
            return (
                f"Could not reach Ollama Cloud at {self.host}. "
                "Check your network connection and OLLAMA_API_KEY."
            )
        return f"Could not connect to Ollama at {self.host}. Run: ollama serve"

    def _response_error(self, exc: ResponseError) -> str:
        if exc.status_code in {401, 403}:
            if self.is_cloud:
                return "Ollama Cloud rejected the API key. Check OLLAMA_API_KEY."
            return f"{self.label} rejected the request: {exc}"
        if exc.status_code == 404:
            return (
                f"Model {self.model} is not available on {self.label}. "
                "Pass a different model with --model."
            )
        if exc.status_code == 429:
            return (
                f"{self.label} rate limit reached. Wait a moment and retry, "
                "or choose a different model."
            )
        if exc.status_code >= 500:
            return f"{self.label} is temporarily unavailable: {exc}"
        return f"{self.label} rejected the request: {exc}"
