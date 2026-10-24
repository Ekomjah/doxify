from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

import doxify.cli as cli
from doxify.exporter import write_evidence_json
from doxify.models import (
    EvidenceCard,
    EvidenceKind,
    EvidenceStrength,
    RepoSummary,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_STUDY = ROOT / "output" / "next-dashboard" / "case-study"


def _card() -> EvidenceCard:
    return EvidenceCard(
        id="E1",
        kind=EvidenceKind.METRIC,
        title="Repository facts",
        text="Demo has 3 files.",
        strength=EvidenceStrength.DETERMINISTIC,
    )


def _evidence_file(tmp_path: Path) -> Path:
    repo = RepoSummary(
        path=".",
        name="demo",
        tracked_file_count=3,
    )
    return write_evidence_json(tmp_path, repo, [_card()])


def test_verify_artifact_passes_with_evidence_marker(tmp_path: Path) -> None:
    evidence = _evidence_file(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

<!-- doxify-attested: title -->

## Facts

Demo has 3 files.

<!-- doxify-evidence: E1 -->
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "verify",
            "--artifact",
            str(readme),
            "--evidence",
            str(evidence),
            "--fail-on",
            "needs_evidence,rejected",
            "--check",
        ],
    )

    assert result.exit_code == 0, result.output


def test_verify_artifact_fails_on_unsupported_claim(tmp_path: Path) -> None:
    evidence = _evidence_file(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

<!-- doxify-attested: title -->

## Facts

Demo has 99 users.

<!-- doxify-evidence: E1 -->
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "verify",
            "--artifact",
            str(readme),
            "--evidence",
            str(evidence),
            "--fail-on",
            "needs_evidence,rejected",
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "Verification failed" in result.output


def test_verify_artifact_requires_evidence_without_session(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Demo\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["verify", "--artifact", str(readme), "--check"],
    )

    assert result.exit_code != 0


def test_verify_check_does_not_rewrite_session(tmp_path: Path) -> None:
    session = tmp_path / "case-study"
    shutil.copytree(CASE_STUDY, session)
    before = {
        path.name: path.read_bytes()
        for path in session.iterdir()
        if path.is_file()
    }

    result = CliRunner().invoke(
        cli.app,
        ["verify", str(session), "--check", "--fail-on", "none"],
    )

    assert result.exit_code == 0, result.output
    after = {
        path.name: path.read_bytes()
        for path in session.iterdir()
        if path.is_file()
    }
    assert after == before


def test_verify_session_fails_on_unresolved_claims(tmp_path: Path) -> None:
    session = tmp_path / "case-study"
    shutil.copytree(CASE_STUDY, session)

    result = CliRunner().invoke(
        cli.app,
        [
            "verify",
            str(session),
            "--check",
            "--fail-on",
            "needs_evidence,rejected",
        ],
    )

    assert result.exit_code == 1
    assert "Verification failed" in result.output
