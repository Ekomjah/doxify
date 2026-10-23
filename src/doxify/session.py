from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .errors import SessionError
from .models import SessionManifest

T = TypeVar("T", bound=BaseModel)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def prepare_output_dir(path: Path, *, force: bool = False) -> Path:
    output = path.expanduser().resolve()
    if output.exists() and not output.is_dir():
        raise SessionError(f"Output path is not a directory: {output}")
    if output.exists() and any(output.iterdir()) and not force:
        raise SessionError(
            f"Output directory is not empty: {output}. Pass --force to reuse it."
        )
    output.mkdir(parents=True, exist_ok=True)
    return output


def write_json(path: Path, value: BaseModel | dict[str, Any] | list[Any]) -> None:
    if isinstance(value, BaseModel):
        payload = value.model_dump_json(indent=2)
    else:
        payload = json.dumps(value, indent=2, ensure_ascii=False)
    _atomic_write(path, payload + "\n")


def read_model(path: Path, model_type: type[T]) -> T:
    if not path.exists():
        raise SessionError(f"Missing session artifact: {path}")
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SessionError(f"Could not read {path.name}: {exc}") from exc


def write_text(path: Path, text: str) -> None:
    _atomic_write(path, text.rstrip() + "\n")


def write_manifest(path: Path, manifest: SessionManifest, artifacts: list[str]) -> None:
    manifest.updated_at = utc_now()
    manifest.artifacts = sorted(set(artifacts))
    write_json(path, manifest)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
