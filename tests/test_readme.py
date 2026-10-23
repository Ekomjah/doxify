from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import doxify.cli as cli
import doxify.pipeline as pipeline
from doxify.models import (
    Claim,
    ClaimStatus,
    CompileResult,
    CompileSummary,
    EvidenceCard,
    EvidenceKind,
    EvidenceStrength,
    RepoSummary,
    SessionManifest,
)
from doxify.readme import (
    GENERATED_MARKER,
    ReadmeResult,
    build_readme,
    resolve_readme_target,
)


def _card(
    card_id: str,
    kind: EvidenceKind,
    title: str,
    text: str,
    *,
    meta: dict[str, object] | None = None,
    strength: EvidenceStrength = EvidenceStrength.DETERMINISTIC,
) -> EvidenceCard:
    return EvidenceCard(
        id=card_id,
        kind=kind,
        title=title,
        text=text,
        strength=strength,
        meta=meta or {},
    )


def _result(repo_root: Path) -> CompileResult:
    repo = RepoSummary(
        path=str(repo_root),
        name="demo",
        commit_count=4,
        first_commit_date="2026-01-01",
        last_commit_date="2026-01-04",
        tracked_file_count=12,
        languages={"Python": 8, "Markdown": 1},
        manifests=["package.json"],
        test_files=["tests/test_app.py"],
        deploy_files=[],
    )
    evidence = [
        _card(
            "E1",
            EvidenceKind.METRIC,
            "Commit timeline",
            "demo has 4 commits between 2026-01-01 and 2026-01-04.",
        ),
        _card(
            "E2",
            EvidenceKind.METRIC,
            "Repository size and languages",
            "The repository tracks 12 files, with languages Python (8), Markdown (1).",
        ),
        _card(
            "E3",
            EvidenceKind.METRIC,
            "No README",
            "No README file was found among the tracked files.",
        ),
        _card(
            "E4",
            EvidenceKind.STACK,
            "Declared dependencies",
            "The project declares runtime dependencies including fastapi, pytest.",
            meta={"dependencies": ["fastapi", "pytest"]},
        ),
        _card(
            "E5",
            EvidenceKind.STACK,
            "Project scripts",
            "The project defines scripts named build, smoke, test.",
            meta={"scripts": ["build", "smoke", "test"]},
        ),
        _card(
            "E6",
            EvidenceKind.FILE,
            "Top-level structure",
            "The repository is organized into src and tests.",
            meta={"top_level": {"src": 7, "tests": 2, "package.json": 1}},
        ),
        _card(
            "E7",
            EvidenceKind.CODE,
            "2 registered tools",
            "src/tools.py registers 2 tools: search, save.",
            meta={"tool_names": ["search", "save"]},
            strength=EvidenceStrength.CODE,
        ),
        _card(
            "E8",
            EvidenceKind.CODE,
            "1 database models",
            "The repository defines 1 data model: Item.",
            meta={"model_names": ["Item"]},
            strength=EvidenceStrength.CODE,
        ),
        _card(
            "E9",
            EvidenceKind.CODE,
            "1 HTTP routes",
            "The repository declares 1 HTTP route including /health.",
            strength=EvidenceStrength.CODE,
        ),
        _card(
            "E10",
            EvidenceKind.METRIC,
            "3 records in data/items.json",
            "data/items.json contains 3 JSON records.",
            meta={"record_count": 3},
        ),
        _card(
            "E11",
            EvidenceKind.TEST,
            "1 test-related files",
            "The repository contains test-related files: tests/test_app.py.",
            meta={"test_files": ["tests/test_app.py"]},
        ),
    ]
    claims = [
        Claim(
            id="C1",
            text="The repository has no README. [E3]",
            section_id="snapshot",
            evidence_ids=["E3"],
            status=ClaimStatus.VERIFIED,
        ),
        Claim(
            id="C2",
            text="Unsupported claim that must stay out.",
            section_id="approach",
            status=ClaimStatus.NEEDS_EVIDENCE,
            gap_question="What evidence supports this?",
        ),
        Claim(
            id="C3",
            text="The author used this in production. [E7]",
            section_id="reflection",
            evidence_ids=["E7"],
            status=ClaimStatus.ATTESTED,
            user_answer="I used it in a small production workflow.",
        ),
    ]
    summary = CompileSummary(
        verified=1,
        attested=1,
        needs_evidence=1,
        rejected=0,
        sections=3,
        evidence_cards=len(evidence),
    )
    manifest = SessionManifest(
        created_at="2026-01-04T00:00:00+00:00",
        updated_at="2026-01-04T00:00:00+00:00",
        repo=repo,
        model="test-model",
        status="done",
    )
    return CompileResult(
        manifest=manifest,
        evidence=evidence,
        claims=claims,
        summary=summary,
    )


def test_build_readme_uses_evidence_and_hides_unresolved(tmp_path: Path) -> None:
    result = _result(tmp_path / "repo")
    content = build_readme(result, session_dir=tmp_path / "session")

    assert content.startswith(GENERATED_MARKER)
    assert "# demo" in content
    assert "## Overview" in content
    assert "search" in content
    assert "npm run smoke" in content
    assert "<!-- doxify-evidence: E1 E2 -->" in content
    assert "The author used this in production." in content
    assert "No README file was found" not in content
    assert "Unsupported claim that must stay out" not in content
    assert "[E1]" not in content
    assert "[needs evidence]" not in content
    assert "[GAP]" not in content
    assert "doxify-unresolved: 1 claim(s) need evidence" in content


def test_resolve_readme_target_defaults_to_repo_root(tmp_path: Path) -> None:
    target = resolve_readme_target(tmp_path, None)
    assert target == (tmp_path / "README.md").resolve()


def test_resolve_readme_target_refuses_existing_readme(tmp_path: Path) -> None:
    existing = tmp_path / "README.md"
    existing.write_text("keep me", encoding="utf-8")

    with pytest.raises(Exception, match="already exists"):
        resolve_readme_target(tmp_path, None)
    assert resolve_readme_target(tmp_path, None, force=True) == existing.resolve()


def test_resolve_readme_target_accepts_directory_and_file(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    assert resolve_readme_target(tmp_path, docs) == (docs / "README.md").resolve()

    custom = tmp_path / "CUSTOM.md"
    assert resolve_readme_target(tmp_path, custom) == custom.resolve()


def test_readme_repo_writes_only_readme_and_keeps_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _result(tmp_path / "repo")
    output = tmp_path / "out" / "README.md"

    def fake_compile(*_args: object, **_kwargs: object) -> CompileResult:
        session = Path(_args[1])
        (session / "evidence.json").write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(pipeline, "compile_repo", fake_compile)

    readme = pipeline.readme_repo(
        tmp_path / "repo",
        client=object(),  # type: ignore[arg-type]
        model="test-model",
        output=output,
    )

    assert readme.path == output.resolve()
    assert output.read_text(encoding="utf-8").startswith(GENERATED_MARKER)
    assert [path.name for path in output.parent.iterdir()] == ["README.md"]
    assert (readme.session_dir / "evidence.json").exists()
    assert readme.omitted_claims[0].id == "C2"
    assert readme.session_cleaned is False


def test_readme_repo_cleans_session_only_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _result(tmp_path / "repo")
    output = tmp_path / "out" / "README.md"

    def fake_compile(*_args: object, **_kwargs: object) -> CompileResult:
        return result

    monkeypatch.setattr(pipeline, "compile_repo", fake_compile)

    readme = pipeline.readme_repo(
        tmp_path / "repo",
        client=object(),  # type: ignore[arg-type]
        model="test-model",
        output=output,
        cleanup=True,
    )

    assert output.exists()
    assert not readme.session_dir.exists()
    assert readme.session_cleaned is True


def test_readme_repo_backs_up_existing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "README.md"
    target.write_text("old readme", encoding="utf-8")
    result = _result(repo)

    def fake_compile(*_args: object, **_kwargs: object) -> CompileResult:
        return result

    monkeypatch.setattr(pipeline, "compile_repo", fake_compile)

    readme = pipeline.readme_repo(
        repo,
        client=object(),  # type: ignore[arg-type]
        model="test-model",
        force=True,
    )

    assert target.read_text(encoding="utf-8").startswith(GENERATED_MARKER)
    assert readme.backup_path is not None
    assert readme.backup_path.read_text(encoding="utf-8") == "old readme"


def test_readme_cli_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = _result(repo)
    path = tmp_path / "README.md"
    readme = ReadmeResult(
        path=path,
        session_dir=tmp_path / "session",
        content=build_readme(result),
        compile_result=result,
        omitted_claims=[],
        warnings=[],
    )

    def fake_readme(*_args: object, **_kwargs: object) -> ReadmeResult:
        return readme

    monkeypatch.setattr(cli, "readme_repo", fake_readme)
    runner = CliRunner()
    response = runner.invoke(cli.app, ["readme", str(repo), "--output", str(path)])

    assert response.exit_code == 0, response.output
    assert "README complete" in response.output
