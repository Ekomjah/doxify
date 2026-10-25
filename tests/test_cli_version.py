from __future__ import annotations

import re

from typer.testing import CliRunner

from doxify.cli import app


def test_version_flag_prints_installed_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert re.fullmatch(r"\d+\.\d+\.\d+", result.output.strip())
