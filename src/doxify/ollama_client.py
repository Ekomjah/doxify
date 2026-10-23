from __future__ import annotations

import os
from typing import Any

from ollama import Client, RequestError, ResponseError

from .errors import ModelError

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:1b"


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL, host: str | None = None) -> None:
        configured_host = host or os.environ.get("DOXIFY_OLLAMA_HOST") or DEFAULT_HOST
        if "://" not in configured_host:
            configured_host = f"http://{configured_host}"
        self.model = model or os.environ.get("DOXIFY_MODEL") or DEFAULT_MODEL
        self.host = configured_host.rstrip("/")
        self._client = Client(host=self.host)

    def health(self) -> tuple[bool, str]:
        try:
            models = self.list_models()
        except ModelError as exc:
            return False, str(exc)
        if self.model in models:
            return True, f"Ollama is reachable and {self.model} is installed."
        return False, (
            f"Ollama is reachable, but {self.model} is not installed. "
            f"Run: ollama pull {self.model}"
        )

    def list_models(self) -> list[str]:
        try:
            response = self._client.list()
        except (RequestError, ResponseError, ConnectionError, OSError) as exc:
            raise ModelError(
                f"Could not connect to Ollama at {self.host}. Run: ollama serve"
            ) from exc
        return [
            item.model
            for item in response.models
            if getattr(item, "model", None)
        ]

    def ensure_ready(self) -> None:
        models = self.list_models()
        if self.model not in models:
            raise ModelError(
                f"Model {self.model} is not installed. Run: ollama pull {self.model}"
            )

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
            "num_ctx": 4096,
            "num_predict": num_predict,
            "repeat_penalty": 1.1,
        }
        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                stream=False,
                keep_alive="10m",
                options=options,
            )
        except ResponseError as exc:
            raise ModelError(f"Ollama rejected the request: {exc}") from exc
        except (RequestError, ConnectionError, OSError) as exc:
            raise ModelError(
                f"Ollama is unavailable at {self.host}. Run: ollama serve"
            ) from exc

        content = response.message.content
        if not content or not content.strip():
            raise ModelError("Ollama returned an empty response.")
        return content.strip()
