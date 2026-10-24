from __future__ import annotations

from pathlib import Path

from doxify.audit import audit_artifact
from doxify.evidence import build_evidence
from doxify.git_repo import collect_repo_context, open_repo

ROOT = Path(__file__).resolve().parents[1]


def test_doxify_readme_verifies_against_current_repository() -> None:
    repo = open_repo(ROOT, allow_tool_root=True)
    context = collect_repo_context(repo)
    evidence = build_evidence(context)

    report = audit_artifact(ROOT / "README.md", evidence)

    assert report.unmarked_sections == []
    assert report.summary.needs_evidence == 0
    assert report.summary.rejected == 0
    assert report.summary.verified == 5
    assert report.summary.attested == 8
