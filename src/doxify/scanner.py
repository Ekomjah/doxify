from __future__ import annotations

from pathlib import Path

from .evidence import build_evidence
from .git_repo import RepoContext, collect_repo_context, open_repo
from .models import ScanResult


def scan_repository(
    path: Path,
    *,
    max_commits: int = 100,
    max_cards: int = 60,
    max_file_bytes: int = 120_000,
) -> tuple[RepoContext, ScanResult]:
    repo = open_repo(path)
    context = collect_repo_context(repo, max_commits=max_commits)
    cards = build_evidence(
        context,
        max_cards=max_cards,
        max_file_bytes=max_file_bytes,
    )
    return context, ScanResult(repo=context.summary, evidence=cards)
