from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import SessionError
from .models import (
    Claim,
    ClaimStatus,
    CompileResult,
    EvidenceCard,
    EvidenceKind,
    RepoSummary,
)
from .text import compact_whitespace

GENERATED_MARKER = "<!-- doxify-generated -->"
CITATION_RE = re.compile(r"\s*\[E\d+\]")
MARKER_RE = re.compile(
    r"\s*\[(?:GAP|needs evidence|attested|rejected)\]",
    re.IGNORECASE,
)
README_FILENAME = "README.md"


@dataclass
class ReadmeResult:
    path: Path
    session_dir: Path
    content: str
    compile_result: CompileResult
    omitted_claims: list[Claim]
    warnings: list[str]
    backup_path: Path | None = None
    session_cleaned: bool = False


def build_readme(
    result: CompileResult,
    *,
    session_dir: Path | None = None,
) -> str:
    repo = result.manifest.repo
    evidence = [card for card in result.evidence if _usable_card(card) is not None]
    claims = result.claims
    lines: list[str] = [GENERATED_MARKER]
    if session_dir is not None:
        lines.append(f"<!-- doxify-compile-session: {session_dir} -->")
    lines.extend(
        [
            f"<!-- doxify-summary: {_summary_text(result)} -->",
            "",
            f"# {repo.name}",
            "",
        ]
    )

    _overview(lines, repo, evidence)
    _what_it_does(lines, evidence)
    _tech_stack(lines, repo, evidence)
    _project_layout(lines, evidence)
    _getting_started(lines, repo, evidence)
    _testing(lines, repo, evidence)
    _limitations(lines, repo)
    _project_notes(lines, claims)

    omitted = [
        claim
        for claim in claims
        if claim.status not in {ClaimStatus.VERIFIED, ClaimStatus.ATTESTED}
    ]
    if omitted:
        lines.extend(
            [
                (
                    f"<!-- doxify-unresolved: {len(omitted)} claim(s) need evidence; "
                    "see claims.json in the compile session. -->"
                ),
                "",
            ]
        )
    lines.append(
        "<!-- doxify-note: Add a LICENSE file and license section if applicable. -->"
    )
    return "\n".join(lines).rstrip() + "\n"


def resolve_readme_target(
    repo_root: Path,
    output: Path | None,
    *,
    force: bool = False,
) -> Path:
    root = repo_root.expanduser().resolve()
    if output is None:
        target = root / README_FILENAME
    else:
        candidate = output.expanduser()
        if candidate.exists() and candidate.is_dir():
            target = candidate / README_FILENAME
        elif candidate.is_file() or candidate.suffix.lower() in {".md", ".markdown"}:
            target = candidate
        else:
            target = candidate / README_FILENAME
        target = target.resolve()

    if target.exists() and target.is_dir():
        raise SessionError(f"README target is a directory: {target}")
    if target.exists() and not force:
        raise SessionError(
            f"README target already exists: {target}. "
            "Pass --force to overwrite it, or use --output to write elsewhere."
        )
    return target


def backup_readme(target: Path, session_dir: Path) -> Path:
    backup_dir = session_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / target.name
    backup.write_bytes(target.read_bytes())
    return backup


def citation_free(text: str) -> str:
    cleaned = CITATION_RE.sub("", text)
    cleaned = MARKER_RE.sub("", cleaned)
    return compact_whitespace(cleaned)


def _overview(lines: list[str], repo: RepoSummary, evidence: list[EvidenceCard]) -> None:
    cards = [
        card
        for card in evidence
        if card.kind == EvidenceKind.METRIC
        and card.title in {"Commit timeline", "Repository size and languages"}
    ]
    body = [card.text for card in cards]
    if not body:
        body = [
            f"{repo.name} contains {repo.tracked_file_count} tracked files"
            + _timeline_suffix(repo)
            + "."
        ]
    _section(lines, "Overview", body, cards)


def _what_it_does(lines: list[str], evidence: list[EvidenceCard]) -> None:
    body: list[str] = []
    ids: list[str] = []

    tools = _first_card(evidence, "registered tools")
    if tools is not None:
        names = _meta_list(tools, "tool_names")
        body.append(tools.text)
        if names:
            body.extend(["", *[f"- `{name}`" for name in names]])
        ids.append(tools.id)

    models = _first_card(evidence, "database models")
    if models is not None:
        names = _meta_list(models, "model_names")
        body.extend(["", models.text])
        if names:
            body.extend(["", *[f"- `{name}`" for name in names]])
        ids.append(models.id)

    routes = _first_card(evidence, "HTTP routes")
    if routes is not None:
        body.extend(["", routes.text])
        ids.append(routes.id)

    data = _first_card(evidence, "records in")
    if data is not None:
        body.extend(["", data.text])
        ids.append(data.id)

    if not body:
        return
    _section(lines, "What it does", body, _cards_by_ids(evidence, ids))


def _tech_stack(lines: list[str], repo: RepoSummary, evidence: list[EvidenceCard]) -> None:
    body: list[str] = []
    ids: list[str] = []

    if repo.languages:
        languages = ", ".join(
            f"{name} ({count})" for name, count in list(repo.languages.items())[:8]
        )
        body.append(f"Languages detected: {languages}.")
        language_card = _first_card(evidence, "Repository size and languages")
        if language_card is not None:
            ids.append(language_card.id)

    dependencies = _first_card(evidence, "Declared dependencies")
    if dependencies is not None:
        names = _meta_list(dependencies, "dependencies")
        if names:
            body.extend(
                [
                    "",
                    "Declared runtime dependencies:",
                    *[f"- `{name}`" for name in names],
                ]
            )
        else:
            body.extend(["", dependencies.text])
        ids.append(dependencies.id)

    if repo.manifests:
        body.extend(["", f"Manifests: {', '.join(repo.manifests)}."])

    if not body:
        return
    _section(lines, "Tech stack", body, _cards_by_ids(evidence, ids))


def _project_layout(lines: list[str], evidence: list[EvidenceCard]) -> None:
    layout = _first_card(evidence, "Top-level structure")
    if layout is None:
        return
    top_level = layout.meta.get("top_level")
    if not isinstance(top_level, dict) or not top_level:
        return

    entries = sorted(
        ((str(name), int(count)) for name, count in top_level.items()),
        key=lambda item: (-item[1], item[0]),
    )
    body = [
        "Top-level paths detected in the repository:",
        "",
        "```text",
        *[f"{name}/ ({count} files)" if count > 1 else f"{name} ({count} file)" for name, count in entries],
        "```",
    ]
    _section(lines, "Project layout", body, [layout])


def _getting_started(
    lines: list[str],
    repo: RepoSummary,
    evidence: list[EvidenceCard],
) -> None:
    scripts = _first_card(evidence, "Project scripts")
    if scripts is None:
        _hidden_note(
            lines,
            "No setup scripts were detected. Add install and run instructions manually.",
        )
        return

    names = _meta_list(scripts, "scripts")
    if not names:
        return

    use_npm = any(path.endswith("package.json") for path in repo.manifests)
    body = ["The project defines these scripts:", "", "```bash"]
    if use_npm:
        body.extend(f"npm run {name}" for name in names)
    else:
        body.extend(names)
    body.extend(["```"])
    _section(lines, "Getting started", body, [scripts])
    _hidden_note(
        lines,
        "Add install, environment, and database setup steps where the repository requires them.",
    )


def _testing(lines: list[str], repo: RepoSummary, evidence: list[EvidenceCard]) -> None:
    test_card = _first_card(evidence, "test-related files")
    test_files = _meta_list(test_card, "test_files") if test_card else repo.test_files
    if not test_files:
        return

    body = [
        "Test files detected:",
        *[f"- `{path}`" for path in test_files],
    ]
    scripts = _first_card(evidence, "Project scripts")
    script_names = _meta_list(scripts, "scripts") if scripts else []
    test_scripts = [name for name in script_names if "test" in name.lower() or "smoke" in name.lower()]
    if test_scripts:
        body.extend(
            [
                "",
                "Test-related scripts: "
                + ", ".join(f"`{name}`" for name in test_scripts),
            ]
        )
    ids = [card.id for card in (test_card, scripts) if card is not None]
    _section(lines, "Testing", body, _cards_by_ids(evidence, ids))
    _hidden_note(
        lines,
        "Add the exact test command and current test status after running it.",
    )


def _limitations(lines: list[str], repo: RepoSummary) -> None:
    body: list[str] = []
    if not repo.deploy_files:
        body.append(
            "Doxify did not detect deployment configuration in the tracked files."
        )
    if repo.test_files:
        body.append(
            "Test files are listed above; this README does not claim that the tests pass."
        )
    body.append(
        "Add installation, environment, deployment, and licensing details that are not "
        "visible in the repository."
    )
    _section(lines, "Limitations and next steps", body, [])


def _project_notes(lines: list[str], claims: list[Claim]) -> None:
    attested = [
        claim
        for claim in claims
        if claim.status == ClaimStatus.ATTESTED and citation_free(claim.text)
    ]
    if not attested:
        return
    body = [f"- {citation_free(claim.text)}" for claim in attested]
    lines.extend(["## Project notes", ""])
    lines.extend(body)
    lines.extend(["", f"<!-- doxify-attested: {' '.join(claim.id for claim in attested)} -->", ""])


def _section(
    lines: list[str],
    title: str,
    body: list[str],
    cards: list[EvidenceCard],
) -> None:
    lines.extend([f"## {title}", ""])
    lines.extend(body)
    ids = " ".join(dict.fromkeys(card.id for card in cards))
    if ids:
        lines.extend(["", f"<!-- doxify-evidence: {ids} -->"])
    lines.append("")


def _hidden_note(lines: list[str], text: str) -> None:
    lines.extend([f"<!-- doxify-note: {text} -->", ""])


def _usable_card(card: EvidenceCard) -> EvidenceCard | None:
    title = card.title.lower()
    if title == "no readme" or "no readme file" in card.text.lower():
        return None
    if not card.text.strip():
        return None
    return card


def _first_card(evidence: list[EvidenceCard], title_fragment: str) -> EvidenceCard | None:
    fragment = title_fragment.lower()
    return next((card for card in evidence if fragment in card.title.lower()), None)


def _cards_by_ids(evidence: list[EvidenceCard], ids: list[str]) -> list[EvidenceCard]:
    wanted = set(ids)
    return [card for card in evidence if card.id in wanted]


def _meta_list(card: EvidenceCard | None, key: str) -> list[str]:
    if card is None:
        return []
    value: Any = card.meta.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _timeline_suffix(repo: RepoSummary) -> str:
    if repo.first_commit_date and repo.last_commit_date:
        return (
            f" across {repo.commit_count} commits between "
            f"{repo.first_commit_date} and {repo.last_commit_date}"
        )
    return f" across {repo.commit_count} commits"


def _summary_text(result: CompileResult) -> str:
    summary = result.summary
    return (
        f"{summary.verified} verified, {summary.attested} attested, "
        f"{summary.needs_evidence} needing evidence, {summary.rejected} rejected"
    )
