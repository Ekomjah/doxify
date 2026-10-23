from __future__ import annotations

import json
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath

from .git_repo import RepoContext
from .models import EvidenceCard, EvidenceKind, EvidenceRef, EvidenceStrength
from .paths import is_manifest, is_readme, is_secret, is_skippable, read_text_limited
from .text import compact_whitespace, keywords_for

JS_SYMBOL_RE = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
PY_SYMBOL_RE = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE)
TOOL_NAME_RE = re.compile(r"^\s*name:\s*[\"']([^\"']+)[\"']", re.MULTILINE)
MONGOOSE_MODEL_RE = re.compile(r"mongoose\.model\(\s*[\"']([^\"']+)[\"']")
ROUTE_RE = re.compile(
    r"\b(?:router|app)\.(?:get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']"
)

KEY_SOURCE_NAMES = {
    "index.js",
    "index.ts",
    "main.py",
    "app.py",
    "app.js",
    "app.ts",
    "server.js",
    "server.ts",
    "cli.py",
    "match.js",
    "match.ts",
    "filter.js",
    "filter.ts",
    "tools.js",
    "tools.ts",
    "prompt.js",
    "prompt.ts",
    "resource.js",
    "resource.ts",
    "models.py",
    "db.js",
    "db.ts",
}


@dataclass
class _SourceFile:
    relative: str
    text: str
    lines: list[str]


class _Factory:
    def __init__(self, max_cards: int) -> None:
        self.max_cards = max_cards
        self.cards: list[EvidenceCard] = []

    def add(
        self,
        *,
        kind: EvidenceKind,
        title: str,
        text: str,
        strength: EvidenceStrength,
        refs: list[EvidenceRef] | None = None,
        quote: str | None = None,
        keywords: list[str] | None = None,
        meta: dict[str, object] | None = None,
    ) -> None:
        if len(self.cards) >= self.max_cards:
            return
        card = EvidenceCard(
            id=f"E{len(self.cards) + 1}",
            kind=kind,
            title=title,
            text=compact_whitespace(text),
            quote=compact_whitespace(quote) if quote else None,
            refs=refs or [],
            strength=strength,
            keywords=keywords or keywords_for(f"{title} {text} {quote or ''}"),
            meta=meta or {},
        )
        self.cards.append(card)


def build_evidence(
    context: RepoContext,
    *,
    max_cards: int = 60,
    max_file_bytes: int = 120_000,
) -> list[EvidenceCard]:
    factory = _Factory(max_cards)

    _identity_cards(factory, context)
    _readme_card(factory, context, max_file_bytes)
    _manifest_cards(factory, context, max_file_bytes)
    _directory_card(factory, context)

    sources = _read_sources(context, max_file_bytes)
    _tool_card(factory, sources)
    _model_card(factory, sources)
    _route_card(factory, sources)
    _data_cards(factory, context, max_file_bytes)
    _test_card(factory, context)
    _deploy_card(factory, context)
    _commit_cards(factory, context)
    _source_excerpt_cards(factory, sources)

    return factory.cards


def _identity_cards(factory: _Factory, context: RepoContext) -> None:
    summary = context.summary
    refs = [EvidenceRef(commit=summary.head_sha)] if summary.head_sha else []
    timeline = (
        f"{summary.name} has {summary.commit_count} commits"
        f" between {summary.first_commit_date} and {summary.last_commit_date}."
        if summary.first_commit_date and summary.last_commit_date
        else f"{summary.name} has {summary.commit_count} commits."
    )
    factory.add(
        kind=EvidenceKind.METRIC,
        title="Commit timeline",
        text=timeline,
        refs=refs,
        strength=EvidenceStrength.DETERMINISTIC,
        keywords=["commits", "timeline", "history", "dates"],
        meta={
            "commit_count": summary.commit_count,
            "first_commit_date": summary.first_commit_date,
            "last_commit_date": summary.last_commit_date,
        },
    )

    languages = ", ".join(
        f"{name} ({count})" for name, count in list(summary.languages.items())[:5]
    )
    language_text = (
        f"The repository tracks {summary.tracked_file_count} files"
        + (f", with languages {languages}." if languages else ".")
    )
    factory.add(
        kind=EvidenceKind.METRIC,
        title="Repository size and languages",
        text=language_text,
        strength=EvidenceStrength.DETERMINISTIC,
        keywords=["files", "languages", "repository", "size"],
        meta={"tracked_file_count": summary.tracked_file_count},
    )


def _readme_card(factory: _Factory, context: RepoContext, max_file_bytes: int) -> None:
    readme = context.summary.readme_path
    if not readme:
        factory.add(
            kind=EvidenceKind.METRIC,
            title="No README",
            text="No README file was found among the tracked files.",
            strength=EvidenceStrength.DETERMINISTIC,
            keywords=["readme", "documentation", "missing"],
        )
        return

    source = _read_source(context, readme, max_file_bytes)
    if not source:
        factory.add(
            kind=EvidenceKind.README,
            title="README present",
            text=f"The repository contains a README at {readme}.",
            refs=[EvidenceRef(path=readme)],
            strength=EvidenceStrength.README,
            keywords=["readme", "documentation"],
        )
        return

    quote = "\n".join(source.lines[:18])
    factory.add(
        kind=EvidenceKind.README,
        title="README present",
        text=f"The repository contains a README at {readme}.",
        refs=[EvidenceRef(path=readme, lines="1-18")],
        quote=quote,
        strength=EvidenceStrength.README,
        meta={"path": readme},
    )


def _manifest_cards(factory: _Factory, context: RepoContext, max_file_bytes: int) -> None:
    manifests = context.summary.manifests
    if not manifests:
        return

    dependencies: list[str] = []
    scripts: list[str] = []
    for relative in manifests:
        source = _read_source(context, relative, max_file_bytes)
        if not source:
            continue
        if relative.endswith("package.json"):
            try:
                data = json.loads(source.text)
            except json.JSONDecodeError:
                continue
            dependencies.extend(sorted((data.get("dependencies") or {}).keys()))
            scripts.extend(sorted((data.get("scripts") or {}).keys()))
        elif relative.endswith("pyproject.toml"):
            try:
                data = tomllib.loads(source.text)
            except tomllib.TOMLDecodeError:
                continue
            project = data.get("project") or {}
            dependencies.extend(list(project.get("dependencies") or []))
        elif relative.endswith("requirements.txt"):
            dependencies.extend(
                line.split("==")[0].strip()
                for line in source.text.splitlines()
                if line.strip() and not line.startswith("#")
            )

    unique_dependencies = sorted({dep.split("[")[0].split(">=")[0].strip() for dep in dependencies})
    if unique_dependencies:
        displayed = ", ".join(unique_dependencies[:12])
        factory.add(
            kind=EvidenceKind.STACK,
            title="Declared dependencies",
            text=f"The project declares runtime dependencies including {displayed}.",
            refs=[EvidenceRef(path=path) for path in manifests],
            strength=EvidenceStrength.DETERMINISTIC,
            keywords=keywords_for(" ".join(unique_dependencies)),
            meta={"dependencies": unique_dependencies},
        )

    if scripts:
        factory.add(
            kind=EvidenceKind.STACK,
            title="Project scripts",
            text=f"The project defines scripts named {', '.join(scripts)}.",
            refs=[EvidenceRef(path=path) for path in manifests if path.endswith("package.json")],
            strength=EvidenceStrength.DETERMINISTIC,
            keywords=["scripts", "commands", "test", "build", *scripts],
            meta={"scripts": scripts},
        )


def _directory_card(factory: _Factory, context: RepoContext) -> None:
    counts: dict[str, int] = {}
    for raw in context.tracked_files:
        relative = PurePosixPath(raw)
        if not relative.parts:
            continue
        top = relative.parts[0]
        counts[top] = counts.get(top, 0) + 1
    if not counts:
        return
    top_dirs = ", ".join(
        f"{name} ({count})" for name, count in sorted(counts.items(), key=lambda item: -item[1])[:8]
    )
    factory.add(
        kind=EvidenceKind.FILE,
        title="Top-level structure",
        text=f"The repository is organized into these top-level paths: {top_dirs}.",
        strength=EvidenceStrength.DETERMINISTIC,
        keywords=["architecture", "directories", "structure", "modules"],
        meta={"top_level": counts},
    )


def _read_sources(context: RepoContext, max_file_bytes: int) -> list[_SourceFile]:
    sources: list[_SourceFile] = []
    for relative in context.tracked_files:
        pure = PurePosixPath(relative)
        if is_readme(pure) or is_manifest(pure) or is_secret(pure) or is_skippable(pure):
            continue
        if pure.suffix.lower() not in {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"}:
            continue
        source = _read_source(context, relative, max_file_bytes)
        if source:
            sources.append(source)
        if len(sources) >= 180:
            break
    return sources


def _tool_card(factory: _Factory, sources: list[_SourceFile]) -> None:
    best: tuple[_SourceFile, list[re.Match[str]]] | None = None
    for source in sources:
        matches = list(TOOL_NAME_RE.finditer(source.text))
        if (
            len(matches) >= 2
            and ("TOOLS" in source.text or "tool" in source.relative.lower())
            and (best is None or len(matches) > len(best[1]))
        ):
            best = (source, matches)
    if best is None:
        return

    source, matches = best
    names = [match.group(1) for match in matches]
    start_line = _line_number(source.text, matches[0].start())
    end_line = _line_number(source.text, matches[-1].end())
    quote = "\n".join(source.lines[start_line - 1 : min(end_line, start_line + 24)])
    factory.add(
        kind=EvidenceKind.CODE,
        title=f"{len(names)} registered tools",
        text=(
            f"{source.relative} registers {len(names)} tools: "
            f"{', '.join(names)}."
        ),
        refs=[EvidenceRef(path=source.relative, lines=f"{start_line}-{end_line}")],
        quote=quote,
        strength=EvidenceStrength.CODE,
        keywords=["tools", "mcp", "commands", *names],
        meta={"tool_count": len(names), "tool_names": names},
    )


def _model_card(factory: _Factory, sources: list[_SourceFile]) -> None:
    found: list[tuple[str, str, int]] = []
    for source in sources:
        for match in MONGOOSE_MODEL_RE.finditer(source.text):
            found.append((source.relative, match.group(1), _line_number(source.text, match.start())))
    if not found:
        return

    names = [name for _, name, _ in found]
    refs = _dedupe_refs(
        [EvidenceRef(path=path, lines=str(line)) for path, _, line in found]
    )
    factory.add(
        kind=EvidenceKind.CODE,
        title=f"{len(names)} database models",
        text=f"The repository defines {len(names)} Mongoose models: {', '.join(names)}.",
        refs=refs,
        strength=EvidenceStrength.CODE,
        keywords=["models", "database", "mongoose", "schema", *names],
        meta={"model_count": len(names), "model_names": names},
    )


def _route_card(factory: _Factory, sources: list[_SourceFile]) -> None:
    routes: list[str] = []
    for source in sources:
        routes.extend(match.group(1) for match in ROUTE_RE.finditer(source.text))
    if not routes:
        return
    unique = list(dict.fromkeys(routes))
    factory.add(
        kind=EvidenceKind.CODE,
        title=f"{len(unique)} HTTP routes",
        text=f"The repository declares {len(unique)} HTTP routes including {', '.join(unique[:10])}.",
        strength=EvidenceStrength.CODE,
        keywords=["routes", "http", "api", "endpoints", *unique[:10]],
        meta={"route_count": len(unique)},
    )


def _data_cards(factory: _Factory, context: RepoContext, max_file_bytes: int) -> None:
    for relative in context.tracked_files:
        pure = PurePosixPath(relative)
        if pure.suffix.lower() != ".json" or is_manifest(pure):
            continue
        lower = relative.lower()
        if not any(part in lower for part in ("data/", "seed", "catalog", "fixture")):
            continue
        source = _read_source(context, relative, max_file_bytes)
        if not source:
            continue
        try:
            data = json.loads(source.text)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list):
            continue
        factory.add(
            kind=EvidenceKind.METRIC,
            title=f"{len(data)} records in {relative}",
            text=f"{relative} contains {len(data)} JSON records.",
            refs=[EvidenceRef(path=relative)],
            strength=EvidenceStrength.DETERMINISTIC,
            keywords=["records", "data", "seed", "catalog", relative],
            meta={"record_count": len(data), "data_path": relative},
        )


def _test_card(factory: _Factory, context: RepoContext) -> None:
    tests = context.summary.test_files
    if not tests:
        return
    factory.add(
        kind=EvidenceKind.TEST,
        title=f"{len(tests)} test-related files",
        text=f"The repository contains test-related files: {', '.join(tests[:12])}.",
        refs=[EvidenceRef(path=path) for path in tests[:12]],
        strength=EvidenceStrength.CODE,
        keywords=["tests", "testing", "smoke", "verification", *tests[:8]],
        meta={"test_count": len(tests), "test_files": tests},
    )


def _deploy_card(factory: _Factory, context: RepoContext) -> None:
    deploys = context.summary.deploy_files
    if not deploys:
        return
    factory.add(
        kind=EvidenceKind.DEPLOY,
        title="Deployment configuration",
        text=f"The repository contains deployment or CI files: {', '.join(deploys[:12])}.",
        refs=[EvidenceRef(path=path) for path in deploys[:12]],
        strength=EvidenceStrength.CODE,
        keywords=["deployment", "docker", "ci", "deploy", *deploys[:8]],
        meta={"deploy_files": deploys},
    )


def _commit_cards(factory: _Factory, context: RepoContext) -> None:
    for commit in context.commits[:10]:
        factory.add(
            kind=EvidenceKind.COMMIT,
            title=f"Commit on {commit.date}",
            text=f'Commit {commit.hexsha} on {commit.date} has subject "{commit.subject}".',
            refs=[EvidenceRef(commit=commit.hexsha)],
            quote=commit.subject,
            strength=EvidenceStrength.COMMIT,
            keywords=keywords_for(commit.subject),
            meta={"commit": commit.hexsha, "date": commit.date, "subject": commit.subject},
        )


def _source_excerpt_cards(factory: _Factory, sources: list[_SourceFile]) -> None:
    selected: list[_SourceFile] = []
    for source in sources:
        if PurePosixPath(source.relative).name in KEY_SOURCE_NAMES:
            selected.append(source)
    for source in sources:
        if source not in selected and len(selected) < 14:
            selected.append(source)
        if len(selected) >= 14:
            break

    for source in selected[:14]:
        symbols = _symbols(source)
        quote, start, end = _excerpt(source, symbols)
        if not quote:
            continue
        label = f"defines {', '.join(symbols[:6])}" if symbols else f"contains {len(source.lines)} lines"
        factory.add(
            kind=EvidenceKind.CODE,
            title=f"Source: {source.relative}",
            text=f"{source.relative} {label}.",
            refs=[EvidenceRef(path=source.relative, lines=f"{start}-{end}")],
            quote=quote,
            strength=EvidenceStrength.CODE,
            keywords=keywords_for(f"{source.relative} {' '.join(symbols)}"),
            meta={"path": source.relative, "symbols": symbols, "line_start": start, "line_end": end},
        )


def _symbols(source: _SourceFile) -> list[str]:
    matches = [
        *JS_SYMBOL_RE.finditer(source.text),
        *PY_SYMBOL_RE.finditer(source.text),
    ]
    return list(dict.fromkeys(match.group(1) for match in matches))[:10]


def _excerpt(source: _SourceFile, symbols: list[str]) -> tuple[str, int, int]:
    text = source.text
    start = 1
    if symbols:
        match = re.search(rf"\b{re.escape(symbols[0])}\b", text)
        if match:
            start = max(1, _line_number(text, match.start()) - 2)
    end = min(len(source.lines), start + 18)
    quote = "\n".join(source.lines[start - 1 : end])
    return quote[:1500], start, end


def _read_source(context: RepoContext, relative: str, max_file_bytes: int) -> _SourceFile | None:
    path = context.root / relative
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(context.root):
        return None
    text = read_text_limited(resolved, max_file_bytes)
    if text is None:
        return None
    return _SourceFile(relative=relative, text=text, lines=text.splitlines())


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _dedupe_refs(refs: list[EvidenceRef]) -> list[EvidenceRef]:
    seen: set[tuple[str | None, str | None, str | None]] = set()
    result: list[EvidenceRef] = []
    for ref in refs:
        key = (ref.path, ref.lines, ref.commit)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result
