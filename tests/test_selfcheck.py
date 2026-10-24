from __future__ import annotations

import json

from typer.testing import CliRunner

import doxify.cli as cli
from doxify.selfcheck import Check, SelfCheckResult, run_self_check


class FakeClient:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    def health(self) -> tuple[bool, str]:
        return self.healthy, "ok" if self.healthy else "model missing"


def test_self_check_passes_without_model() -> None:
    result = run_self_check()

    assert result.ok is True
    assert {check.name for check in result.checks} == {
        "python",
        "git",
        "package",
        "tempdir",
    }


def test_self_check_reports_model_failure() -> None:
    result = run_self_check(client=FakeClient(healthy=False))

    model = next(check for check in result.checks if check.name == "model")
    assert result.ok is False
    assert model.ok is False
    assert model.detail == "model missing"


def test_self_check_cli_json() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ["self-check", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert {check["name"] for check in payload["checks"]} == {
        "python",
        "git",
        "package",
        "tempdir",
    }


def test_self_check_cli_fails_on_failed_check(monkeypatch) -> None:
    def fake_check(**_kwargs: object) -> SelfCheckResult:
        return SelfCheckResult(
            checks=[Check(name="git", ok=False, detail="missing")]
        )

    monkeypatch.setattr(cli, "run_self_check", fake_check)
    runner = CliRunner()
    result = runner.invoke(cli.app, ["self-check", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["checks"][0]["name"] == "git"
