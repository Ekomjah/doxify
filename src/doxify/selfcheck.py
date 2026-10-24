from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ollama_client import OllamaClient


class SelfCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class SelfCheckResult:
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in self.checks
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True)


def run_self_check(*, client: OllamaClient | None = None) -> SelfCheckResult:
    checks: list[Check] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        Check(
            "python",
            python_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}",
        )
    )

    git_path = shutil.which("git")
    checks.append(Check("git", bool(git_path), git_path or "missing"))

    try:
        version = importlib.metadata.version("doxify")
    except importlib.metadata.PackageNotFoundError:
        version = "not installed"
    checks.append(Check("package", version != "not installed", version))

    try:
        with tempfile.TemporaryDirectory(prefix="doxify-self-check-") as directory:
            probe = Path(directory) / "probe"
            probe.write_text("ok", encoding="utf-8")
            readable = probe.read_text(encoding="utf-8") == "ok"
        checks.append(Check("tempdir", readable, "read/write ok"))
    except OSError as exc:
        checks.append(Check("tempdir", False, str(exc)))

    if client is not None:
        healthy, detail = client.health()
        checks.append(Check("model", healthy, detail))

    return SelfCheckResult(checks=checks)
