from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from git import InvalidGitRepositoryError, NoSuchPathError, Repo

from .errors import RepoError
from .models import CommitInfo, RepoSummary
from .paths import (
    is_deploy,
    is_manifest,
    is_readme,
    is_skippable,
    is_test,
    language_for,
)

TOOL_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RepoContext:
    repo: Repo
    root: Path
    summary: RepoSummary
    commits: list[CommitInfo]
    tracked_files: list[str]


def open_repo(path: Path) -> Repo:
    try:
        root = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise RepoError(f"Repository path does not exist: {path}") from exc

    if not root.is_dir():
        raise RepoError(f"Repository path is not a directory: {root}")
    if root == Path(root.anchor):
        raise RepoError("Refusing to scan the filesystem root.")
    if root == Path.home():
        raise RepoError("Refusing to scan the home directory.")
    if root == TOOL_ROOT:
        raise RepoError("Refusing to scan Doxify's own repository.")

    try:
        repo = Repo(str(root), search_parent_directories=False)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise RepoError(f"Not a git repository: {root}") from exc

    if repo.bare:
        raise RepoError("Bare repositories are not supported.")
    if not repo.working_tree_dir:
        raise RepoError("Repository has no working tree.")
    return repo


def collect_repo_context(repo: Repo, max_commits: int = 100) -> RepoContext:
    root = Path(repo.working_tree_dir or ".").resolve()
    all_files = _tracked_files(repo)
    tracked_files: list[str] = []
    languages: dict[str, int] = {}
    readme_path: str | None = None
    manifests: list[str] = []
    tests: list[str] = []
    deploys: list[str] = []

    for raw in all_files:
        relative = PurePosixPath(raw)
        if is_skippable(relative):
            continue
        tracked_files.append(raw)
        language = language_for(relative)
        if language:
            languages[language] = languages.get(language, 0) + 1
        if relative.suffix or is_readme(relative):
            if is_readme(relative) and readme_path is None:
                readme_path = raw
            if is_manifest(relative):
                manifests.append(raw)
            if is_test(relative):
                tests.append(raw)
            if is_deploy(relative):
                deploys.append(raw)

    commits = _recent_commits(repo, max_commits)
    head_sha, branch = _head_info(repo)
    commit_count, first_date, last_date = _history_summary(repo, commits)

    summary = RepoSummary(
        path=str(root),
        name=root.name,
        head_sha=head_sha,
        branch=branch,
        commit_count=commit_count,
        first_commit_date=first_date,
        last_commit_date=last_date,
        tracked_file_count=len(all_files),
        languages=dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        readme_path=readme_path,
        manifests=manifests,
        test_files=tests,
        deploy_files=deploys,
    )
    return RepoContext(
        repo=repo,
        root=root,
        summary=summary,
        commits=commits,
        tracked_files=tracked_files,
    )


def _tracked_files(repo: Repo) -> list[str]:
    try:
        output = repo.git.ls_files()
    except Exception:
        return []
    return [line for line in output.splitlines() if line.strip()]


def _recent_commits(repo: Repo, max_commits: int) -> list[CommitInfo]:
    try:
        iterator = repo.iter_commits(max_count=max(1, max_commits))
    except Exception:
        return []

    commits: list[CommitInfo] = []
    for commit in iterator:
        message = commit.message or ""
        subject = message.strip().splitlines()[0] if message.strip() else "(no message)"
        date = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc).date().isoformat()
        commits.append(CommitInfo(hexsha=commit.hexsha[:12], date=date, subject=subject))
    return commits


def _head_info(repo: Repo) -> tuple[str | None, str | None]:
    try:
        if not repo.head.is_valid():
            return None, None
        head_sha = repo.head.commit.hexsha
    except Exception:
        return None, None

    try:
        branch = repo.active_branch.name
    except Exception:
        branch = None
    return head_sha, branch


def _history_summary(
    repo: Repo, commits: list[CommitInfo]
) -> tuple[int, str | None, str | None]:
    try:
        count = int(repo.git.rev_list("--count", "HEAD"))
    except Exception:
        count = len(commits)

    try:
        root_shas = repo.git.rev_list("--max-parents=0", "HEAD").splitlines()
        root_dates = [
            datetime.fromtimestamp(repo.commit(sha).committed_date, tz=timezone.utc)
            .date()
            .isoformat()
            for sha in root_shas
            if sha.strip()
        ]
        first_date = min(root_dates) if root_dates else ""
        last_date = (
            datetime.fromtimestamp(
                repo.head.commit.committed_date, tz=timezone.utc
            )
            .date()
            .isoformat()
        )
    except Exception:
        dates = sorted(commit.date for commit in commits)
        first_date = dates[0] if dates else ""
        last_date = dates[-1] if dates else ""

    return count, first_date or None, last_date or None
