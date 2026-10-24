from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import ModelError, ScoutError
from .git_repo import RepoContext, collect_repo_context, open_repo
from .models import (
    BreakingChange,
    CodeMatch,
    ReleaseNote,
    RepoSummary,
    ScoutReport,
    ScoutScore,
    ScoutSource,
    ScoutSummary,
    SessionManifest,
)
from .ollama_client import OllamaClient
from .paths import is_secret, is_skippable, read_text_limited
from .prompts import scout_batch_messages
from .session import (
    prepare_output_dir,
    utc_now,
    write_json,
    write_manifest,
    write_text,
)

GITHUB_API = "https://api.github.com/repos/{repo}/releases"
SERPAPI_URL = "https://serpapi.com/search.json"
USER_AGENT = "doxify-scout/0.2"
MAX_HTTP_BYTES = 2_000_000
MAX_FILE_BYTES = 250_000
MAX_RELEASES = 12
MAX_CHUNKS_PER_RELEASE = 3
MAX_MODEL_CALLS = 6
MAX_MATCHES = 300
MAX_CHUNK_CHARS = 7_000
MAX_BATCH_CHARS = 9_000

SCOUT_MD = "scout.md"
SCOUT_JSON = "scout.json"
RELEASE_NOTES_JSON = "release-notes.json"

GENERIC_APIS = {
    "api",
    "browser",
    "client",
    "component",
    "components",
    "function",
    "hook",
    "javascript",
    "method",
    "module",
    "node",
    "package",
    "props",
    "react",
    "react-dom",
    "server",
    "state",
    "typescript",
}

ECOSYSTEMS: dict[str, str] = {
    "@angular/core": "angular/angular",
    "@prisma/client": "prisma/prisma",
    "@sveltejs/kit": "sveltejs/svelte",
    "angular": "angular/angular",
    "django": "django/django",
    "express": "expressjs/express",
    "fastapi": "fastapi/fastapi",
    "fastify": "fastify/fastify",
    "flask": "pallets/flask",
    "go": "golang/go",
    "next": "vercel/next.js",
    "next.js": "vercel/next.js",
    "node": "nodejs/node",
    "nodejs": "nodejs/node",
    "nuxt": "nuxt/nuxt",
    "numpy": "numpy/numpy",
    "pandas": "pandas-dev/pandas",
    "prisma": "prisma/prisma",
    "pydantic": "pydantic/pydantic",
    "pytest": "pytest-dev/pytest",
    "pytorch": "pytorch/pytorch",
    "react": "facebook/react",
    "react-dom": "facebook/react",
    "requests": "psf/requests",
    "rust": "rust-lang/rust",
    "sqlalchemy": "sqlalchemy/sqlalchemy",
    "svelte": "sveltejs/svelte",
    "tailwindcss": "tailwindlabs/tailwindcss",
    "torch": "pytorch/pytorch",
    "typescript": "microsoft/TypeScript",
    "vite": "vitejs/vite",
    "vue": "vuejs/core",
    "webpack": "webpack/webpack",
}

SEARCHABLE_SUFFIXES = {
    ".astro",
    ".c",
    ".cjs",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}

_SEMVER_RE = re.compile(
    r"(?<![A-Za-z0-9_.])v?(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:[-.]([0-9A-Za-z][0-9A-Za-z.-]*))?",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$")
_BREAKING_RE = re.compile(
    r"breaking|deprecat|remov|migrat|upgrade|no longer|renamed|dropped|replaced",
    re.IGNORECASE,
)
_API_RE = re.compile(r"[^A-Za-z0-9_$@./:<>-]+")
_UNQUALIFIED_STOP = {"act", "hydrate", "mount", "render", "unmount", "update", "use"}


def _api_aliases(api: str) -> list[str]:
    aliases = [api]
    if "." in api or "::" in api:
        last = re.split(r"\.|::", api)[-1]
        if len(last) >= 8 and last.casefold() not in _UNQUALIFIED_STOP:
            aliases.append(last)
    return aliases


def _api_match_keys(api: str) -> set[str]:
    return {alias.casefold() for alias in _api_aliases(api)}


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    precision: int
    prerelease: bool
    raw: str


@dataclass
class ScoutResult:
    report: ScoutReport
    output_dir: Path
    markdown_path: Path
    json_path: Path
    notes_path: Path
    manifest_path: Path


class _RawChange:
    def __init__(
        self,
        *,
        title: str,
        quote: str,
        release: str | None,
        apis: list[str],
        migration: str | None,
        severity: str,
    ) -> None:
        self.title = title
        self.quote = quote
        self.release = release
        self.apis = apis
        self.migration = migration
        self.severity = severity


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "pre", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "pre", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape("".join(self.parts))
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", value)).strip()


def parse_version(value: str) -> Version | None:
    match = _SEMVER_RE.search(value.strip())
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    precision = 3 if match.group(3) is not None else 2 if match.group(2) is not None else 1
    suffix = match.group(4) or ""
    prerelease = bool(suffix) and not suffix[0].isdigit()
    return Version(major, minor, patch, precision, prerelease, value.strip())


def _version_key(version: Version) -> tuple[int, int, int, int]:
    return (version.major, version.minor, version.patch, 0 if version.prerelease else 1)


def version_in_range(version: Version, start: Version, end: Version) -> bool:
    if _version_key(version) <= _version_key(start):
        return False
    if end.precision == 1:
        return version.major <= end.major
    if end.precision == 2:
        return (version.major, version.minor) <= (end.major, end.minor)
    return _version_key(version) <= _version_key(end)


def _tag_matches_package(tag: str, package: str) -> bool:
    if "@" not in tag or tag.startswith("v"):
        return True
    prefix = tag.rsplit("@", 1)[0].lstrip("@").lower()
    return prefix == package.lstrip("@").lower()


def select_releases(
    notes: list[ReleaseNote],
    package: str,
    from_version: str,
    to_version: str,
    *,
    max_releases: int = MAX_RELEASES,
) -> tuple[list[ReleaseNote], int]:
    start = parse_version(from_version)
    end = parse_version(to_version)
    if start is None or end is None:
        raise ScoutError("Versions must look like 18, 18.2.0, or v19.0.0.")
    if _version_key(end) <= _version_key(start):
        raise ScoutError("The target version must be newer than the starting version.")

    candidates: list[ReleaseNote] = []
    seen: set[str] = set()
    for note in notes:
        if note.version in seen or not _tag_matches_package(note.version, package):
            continue
        parsed = parse_version(note.version)
        if parsed is None or not version_in_range(parsed, start, end):
            continue
        seen.add(note.version)
        candidates.append(note)

    candidates.sort(key=lambda note: _version_key(parse_version(note.version) or start))
    if len(candidates) <= max_releases:
        return candidates, 0

    by_major: dict[int, list[ReleaseNote]] = {}
    by_minor: dict[tuple[int, int], list[ReleaseNote]] = {}
    for note in candidates:
        parsed = parse_version(note.version)
        if parsed is None:
            continue
        by_major.setdefault(parsed.major, []).append(note)
        by_minor.setdefault((parsed.major, parsed.minor), []).append(note)

    prioritized: list[ReleaseNote] = []
    prioritized_versions: set[str] = set()

    def add(note: ReleaseNote) -> None:
        if note.version not in prioritized_versions and len(prioritized) < max_releases:
            prioritized_versions.add(note.version)
            prioritized.append(note)

    for group in by_major.values():
        add(group[0])
    add(candidates[-1])

    for group in by_minor.values():
        add(group[0])
    for group in by_minor.values():
        add(group[-1])
    for note in candidates:
        if _BREAKING_RE.search(note.body):
            add(note)
    for note in reversed(candidates):
        add(note)

    selected = sorted(
        prioritized,
        key=lambda note: _version_key(parse_version(note.version) or start),
    )
    return selected, len(candidates) - len(selected)


def _http_get(
    url: str,
    *,
    label: str,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
    max_bytes: int = MAX_HTTP_BYTES,
    truncate: bool = False,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise ScoutError(f"{label} returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ScoutError(f"Could not reach {label}: {exc.reason}.") from exc
    except OSError as exc:
        raise ScoutError(f"Could not reach {label}: {exc}.") from exc
    if len(data) > max_bytes:
        if not truncate:
            raise ScoutError(f"{label} returned too much data.")
        data = data[:max_bytes]
    return data


def _http_json(url: str, *, label: str, headers: dict[str, str] | None = None) -> Any:
    raw = _http_get(url, label=label, headers=headers)
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ScoutError(f"{label} returned invalid JSON.") from exc


def fetch_github_releases(
    package: str,
    github_repo: str,
    from_version: str,
    to_version: str,
    *,
    token: str | None = None,
    max_pages: int = 3,
    max_releases: int = MAX_RELEASES,
) -> tuple[list[ReleaseNote], int]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    raw_notes: list[ReleaseNote] = []
    for page in range(1, max_pages + 1):
        url = f"{GITHUB_API.format(repo=github_repo)}?per_page=100&page={page}"
        data = _http_json(url, label=f"GitHub releases for {github_repo}", headers=headers)
        if not isinstance(data, list):
            raise ScoutError(f"GitHub releases for {github_repo} returned an invalid response.")
        for item in data:
            if not isinstance(item, dict) or item.get("draft"):
                continue
            tag = str(item.get("tag_name") or "").strip()
            body = str(item.get("body") or "").strip()
            if not tag or not body:
                continue
            raw_notes.append(
                ReleaseNote(
                    version=tag,
                    title=str(item.get("name") or tag),
                    url=str(item.get("html_url") or ""),
                    body=body,
                    source="github",
                    published_at=str(item.get("published_at") or "") or None,
                )
            )
        if len(data) < 100:
            break

    selected, dropped = select_releases(
        raw_notes,
        package,
        from_version,
        to_version,
        max_releases=max_releases,
    )
    if not selected:
        raise ScoutError(
            f"No GitHub releases with notes were found for {package} "
            f"between {from_version} and {to_version}."
        )
    return selected, dropped


def _fetch_html_text(url: str) -> str:
    raw = _http_get(url, label="release note page", max_bytes=200_000, truncate=True)
    parser = _HTMLTextExtractor()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return parser.text()


def fetch_serpapi_notes(
    package: str,
    from_version: str,
    to_version: str,
    *,
    api_key: str,
    max_results: int = 3,
) -> list[ReleaseNote]:
    query = f"{package} {from_version} to {to_version} release notes breaking changes"
    url = SERPAPI_URL + "?" + urlencode(
        {"engine": "google", "q": query, "api_key": api_key, "num": max_results}
    )
    data = _http_json(url, label="SerpApi")
    if not isinstance(data, dict):
        raise ScoutError("SerpApi returned an invalid response.")
    if data.get("error"):
        raise ScoutError(f"SerpApi rejected the request: {data['error']}")
    results = data.get("organic_results") or []
    if not isinstance(results, list) or not results:
        raise ScoutError("SerpApi returned no release-note results.")

    notes: list[ReleaseNote] = []
    for result in results[:max_results]:
        if not isinstance(result, dict):
            continue
        link = str(result.get("link") or "").strip()
        title = str(result.get("title") or package).strip()
        snippet = str(result.get("snippet") or "").strip()
        if not link.startswith(("http://", "https://")):
            continue
        page_text = ""
        try:
            page_text = _fetch_html_text(link)[:12_000]
        except ScoutError:
            page_text = ""
        body = "\n\n".join(part for part in (title, snippet, page_text) if part).strip()
        if len(body) < 40:
            continue
        notes.append(
            ReleaseNote(
                version=f"{from_version}..{to_version}",
                title=title,
                url=link,
                body=body,
                source="serpapi",
            )
        )
    if not notes:
        raise ScoutError("SerpApi returned no usable release notes.")
    return notes


def fetch_release_notes(
    package: str,
    github_repo: str | None,
    from_version: str,
    to_version: str,
    *,
    notes_file: Path | None = None,
    github_token: str | None = None,
    serpapi_key: str | None = None,
    max_releases: int = MAX_RELEASES,
) -> tuple[list[ReleaseNote], list[str]]:
    warnings: list[str] = []
    if notes_file is not None:
        try:
            body = notes_file.expanduser().resolve().read_text(encoding="utf-8")
        except OSError as exc:
            raise ScoutError(f"Could not read release notes file: {exc}") from exc
        if not body.strip():
            raise ScoutError(f"Release notes file is empty: {notes_file}")
        return [
            ReleaseNote(
                version=f"{from_version}..{to_version}",
                title=notes_file.name,
                url=notes_file.expanduser().resolve().as_uri(),
                body=body,
                source="file",
            )
        ], warnings

    github_error: ScoutError | None = None
    if github_repo:
        try:
            notes, dropped = fetch_github_releases(
                package,
                github_repo,
                from_version,
                to_version,
                token=github_token or os.environ.get("GITHUB_TOKEN"),
                max_releases=max_releases,
            )
            if dropped:
                warnings.append(
                    f"Kept the newest {max_releases} releases and skipped {dropped} older ones."
                )
            return notes, warnings
        except ScoutError as exc:
            github_error = exc
            warnings.append(f"GitHub release fetch failed: {exc}")

    key = serpapi_key or os.environ.get("SERPAPI_API_KEY")
    if key:
        try:
            notes = fetch_serpapi_notes(package, from_version, to_version, api_key=key)
            warnings.append("Used SerpApi because GitHub release notes were unavailable.")
            return notes, warnings
        except ScoutError as exc:
            warnings.append(f"SerpApi fallback failed: {exc}")

    detail = f" {github_error}" if github_error else ""
    raise ScoutError(
        "Could not fetch release notes."
        f"{detail} Set GITHUB_TOKEN for a higher GitHub rate limit, "
        "set SERPAPI_API_KEY for the SerpApi fallback, or pass --notes FILE."
    )


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        return []
    levels = [len(match.group(1)) for match in headings]
    for level in (2, 1, 3, 4):
        if level in levels:
            split_level = level
            break
    else:
        split_level = min(levels)

    selected = [m for m in headings if len(m.group(1)) == split_level]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(selected):
        end = selected[index + 1].start() if index + 1 < len(selected) else len(text)
        sections.append((match.group(2).strip(), text[match.start() : end]))
    return sections


def _chunk_text(text: str, max_chars: int, max_chunks: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            parts = [paragraph[i : i + max_chars] for i in range(0, len(paragraph), max_chars)]
        else:
            parts = [paragraph]
        for part in parts:
            candidate = f"{current}\n\n{part}".strip() if current else part
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = part
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks[:max_chunks]


def release_chunks(
    note: ReleaseNote,
    *,
    max_chars: int = MAX_CHUNK_CHARS,
    max_chunks: int = MAX_CHUNKS_PER_RELEASE,
) -> list[str]:
    text = note.body.strip()
    if not text:
        return []

    sections = _markdown_sections(text)
    selected = [body for heading, body in sections if _BREAKING_RE.search(heading)]
    if selected:
        excerpt = "\n\n".join(selected)
    else:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        hits = [part for part in paragraphs if _BREAKING_RE.search(part)]
        excerpt = "\n\n".join(hits) if hits else text
    return _chunk_text(excerpt, max_chars, max_chunks)


def _normalize_quote(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[`*_~#>]", "", value)
    value = re.sub(r"\s+", " ", value)
    return html.unescape(value).strip().casefold()


def quote_in_notes(quote: str, body: str) -> bool:
    normalized = _normalize_quote(quote)
    return len(normalized) >= 12 and normalized in _normalize_quote(body)


def normalize_api_tokens(values: Any) -> list[str]:
    if isinstance(values, str):
        raw_values: list[Any] = [values]
    elif isinstance(values, list):
        raw_values = values
    else:
        return []

    tokens: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not isinstance(raw, str):
            continue
        for piece in re.split(r"[,;]\s*", raw):
            token = piece.strip().strip("`'\"")
            token = token.replace("`", "")
            token = re.sub(r"\(.*\)$", "", token)
            token = re.sub(r"<.*>$", "", token)
            token = token.strip(".,:;()[]{}")
            token = _API_RE.sub("", token)
            if not token or len(token) > 100 or " " in token:
                continue
            if "://" in token or token.startswith("www."):
                continue
            if "/" in token and "." in token.split("/", 1)[0]:
                continue
            if token.casefold() in GENERIC_APIS:
                continue
            if not re.search(r"[A-Za-z_$]", token):
                continue
            key = token.casefold()
            if key in seen:
                continue
            seen.add(key)
            tokens.append(token)
    return tokens


_API_SEGMENT = r"[A-Za-z_$][A-Za-z0-9_$-]*"
_MULTIPART_API_RE = re.compile(
    rf"(?<![A-Za-z0-9_$])({_API_SEGMENT}(?:(?:\.|::|/){_API_SEGMENT})+)(?![A-Za-z0-9_$])"
)
_SIMPLE_CODE_RE = re.compile(r"`([A-Za-z_$][A-Za-z0-9_$]*)`")


def extract_apis_from_quote(quote: str) -> list[str]:
    normalized = re.sub(r"https?://\S+", " ", quote).replace("`", "")
    tokens = [
        match.group(1)
        for match in _MULTIPART_API_RE.finditer(normalized)
        if all(len(part) >= 2 for part in re.split(r"\.|::|/", match.group(1)))
    ]
    token_parts = {
        part
        for token in tokens
        for part in re.split(r"\.|::|/", token)
    }
    tokens.extend(
        span
        for span in _SIMPLE_CODE_RE.findall(quote)
        if span not in token_parts
    )
    return normalize_api_tokens(tokens)


def _declared_api_text(quote: str) -> str:
    text = quote.strip()
    if text.startswith(("* ", "- ")):
        text = text[2:].strip()
    match = re.match(
        r"^(?:removed|deprecated|breaking(?: change)?|no longer|renamed|dropped|required)\s*:\s*",
        text,
        re.IGNORECASE,
    )
    if not match:
        return text
    rest = text[match.end() :]
    head = rest.split(":", 1)[0].strip()
    if not head:
        return rest
    head = re.split(
        r"\s+(?:in favor of|instead of|use|using|replace(?:d)? with|can be replaced by)\s+",
        head,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return head.strip()


def _coerce_raw_change(item: Any) -> _RawChange | None:
    if isinstance(item, str):
        quote = item.strip()
        apis = extract_apis_from_quote(_declared_api_text(quote))
        if not quote or not apis:
            return None
        title = re.sub(r"^(removed|deprecated|changed|breaking)\s*:\s*", "", quote, flags=re.I)
        severity = "high" if re.search(r"\bremoved\b", quote, re.I) else "medium"
        return _RawChange(
            title=(title[:80].replace("`", "").strip() or "Breaking change"),
            quote=quote,
            release=None,
            apis=apis,
            migration=None,
            severity=severity,
        )
    if not isinstance(item, dict):
        return None
    quote = str(item.get("quote") or item.get("evidence") or item.get("excerpt") or "").strip()
    apis = normalize_api_tokens(
        item.get("apis") or item.get("api") or item.get("affected_apis") or []
    )
    if not apis:
        apis = extract_apis_from_quote(_declared_api_text(quote))
    title = str(item.get("title") or item.get("change") or item.get("summary") or "").strip()
    if not title:
        title = quote[:80].strip() or "Breaking change"
    if not quote or not apis:
        return None
    severity = str(item.get("severity") or "medium").strip().lower()
    if severity not in {"high", "medium", "low"}:
        severity = "medium"
    migration = item.get("migration") or item.get("fix")
    return _RawChange(
        title=title,
        quote=quote,
        release=str(item.get("release") or item.get("version") or "").strip() or None,
        apis=apis,
        migration=str(migration).strip() if migration else None,
        severity=severity,
    )


def parse_changes_response(text: str) -> list[_RawChange]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    starts = sorted(
        {index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0}
    )
    if not starts:
        raise ScoutError("The model did not return JSON.")
    payload: Any = None
    last_error: json.JSONDecodeError | None = None
    for start in starts:
        try:
            payload, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            break
        except json.JSONDecodeError as exc:
            last_error = exc
    if payload is None:
        raise ScoutError("The model returned invalid JSON.") from last_error

    if isinstance(payload, dict):
        raw_changes = payload.get("changes") or payload.get("breaking_changes") or []
    elif isinstance(payload, list):
        raw_changes = payload
    else:
        raw_changes = []
    if not isinstance(raw_changes, list):
        raise ScoutError("The model returned an unexpected JSON shape.")

    changes: list[_RawChange] = []
    for item in raw_changes:
        change = _coerce_raw_change(item)
        if change is not None:
            changes.append(change)
    return changes


def focus_notes(
    notes: list[ReleaseNote],
    from_version: str,
    to_version: str,
) -> list[ReleaseNote]:
    if not notes:
        return []
    start = parse_version(from_version)
    end = parse_version(to_version)
    if start is None or end is None:
        return notes[:1]

    pool = notes
    if end.major > start.major:
        target = [
            note
            for note in notes
            if (parse_version(note.version) or start).major == end.major
        ]
        if target:
            pool = target
    for note in pool:
        if _BREAKING_RE.search(note.body):
            return [note]
    return pool[:1]


def build_batches(
    notes: list[ReleaseNote],
    *,
    max_chars: int = MAX_BATCH_CHARS,
) -> list[tuple[str, list[ReleaseNote]]]:
    entries: list[tuple[ReleaseNote, str]] = []
    for note in notes:
        chunks = release_chunks(note)
        if not chunks:
            continue
        if len(note.body) < 500 and not _BREAKING_RE.search(note.body):
            continue
        for chunk in chunks:
            header = f"## Release {note.version}\nSource: {note.url}\n\n"
            entries.append((note, header + chunk))

    batches: list[tuple[str, list[ReleaseNote]]] = []
    current = ""
    current_notes: list[ReleaseNote] = []
    for note, entry in entries:
        if current and len(current) + len(entry) + 2 > max_chars:
            batches.append((current.strip(), current_notes))
            current = ""
            current_notes = []
        current = f"{current}\n\n{entry}".strip() if current else entry
        if note not in current_notes:
            current_notes.append(note)
    if current:
        batches.append((current.strip(), current_notes))
    return batches


def deterministic_changes(note: ReleaseNote) -> list[_RawChange]:
    found: list[_RawChange] = []
    for chunk in release_chunks(note):
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if line.startswith(("* ", "- ")):
                line = line[2:].strip()
            if len(line) < 20 and not line.lower().startswith(("removed:", "deprecated:")):
                continue
            if not re.match(
                r"^(removed|deprecated|breaking|no longer|renamed|dropped|required)\b",
                line,
                re.IGNORECASE,
            ):
                continue
            apis = extract_apis_from_quote(_declared_api_text(line))
            if not apis:
                continue
            severity = "high" if re.search(r"\bremoved\b", line, re.IGNORECASE) else "medium"
            action = re.match(
                r"^(removed|deprecated|breaking(?: change)?|no longer|renamed|dropped|required)\b",
                line,
                re.IGNORECASE,
            )
            declared = _declared_api_text(line).replace("`", "").strip()
            title = (
                f"{action.group(1).capitalize()}: {declared}"[:100]
                if action and declared
                else declared[:100] or "Breaking change"
            )
            found.append(
                _RawChange(
                    title=title,
                    quote=line,
                    release=note.version,
                    apis=apis,
                    migration=None,
                    severity=severity,
                )
            )
    return found


def _attribute_note(raw: _RawChange, notes: list[ReleaseNote]) -> ReleaseNote | None:
    if raw.release:
        raw_version = parse_version(raw.release)
        for note in notes:
            note_version = parse_version(note.version)
            version_matches = raw.release == note.version or (
                raw_version is not None
                and note_version is not None
                and _version_key(raw_version) == _version_key(note_version)
            )
            if version_matches and quote_in_notes(raw.quote, note.body):
                return note
    for note in notes:
        if quote_in_notes(raw.quote, note.body):
            return note
    return None


def extract_breaking_changes(
    client: OllamaClient,
    notes: list[ReleaseNote],
    package: str,
    from_version: str,
    to_version: str,
    *,
    max_model_calls: int = MAX_MODEL_CALLS,
) -> tuple[list[BreakingChange], list[str]]:
    changes: list[BreakingChange] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    calls = 0
    successful_calls = 0
    stop = False
    batches = build_batches(notes)
    if not batches:
        warnings.append("No release notes contained breaking-change sections.")

    for batch_text, batch_notes in batches:
        if calls >= max_model_calls:
            warnings.append(
                f"Stopped after {max_model_calls} model calls; later release chunks were skipped."
            )
            break
        calls += 1
        try:
            response = client.chat(
                scout_batch_messages(package, from_version, to_version, batch_text),
                temperature=0.0,
                num_predict=500,
            )
        except ModelError as exc:
            raise ScoutError(f"The model could not analyze the release notes: {exc}") from exc

        try:
            raw_changes = parse_changes_response(response)
            successful_calls += 1
        except ScoutError:
            warnings.append("The model returned an unparseable response for one batch.")
            raw_changes = []

        for raw in raw_changes:
            note = _attribute_note(raw, batch_notes)
            if note is None:
                warnings.append(
                    "Dropped a change because its quote was not found in the release notes."
                )
                continue
            key = (note.version, _normalize_quote(raw.quote))
            if key in seen:
                continue
            seen.add(key)
            changes.append(
                BreakingChange(
                    id=f"BC{len(changes) + 1}",
                    package=package,
                    release_version=note.version,
                    title=raw.title,
                    quote=raw.quote,
                    apis=raw.apis,
                    migration=raw.migration,
                    severity=raw.severity,
                    source_title=note.title,
                    source_url=note.url,
                    source_kind=note.source,
                    method="model",
                )
            )
            if len(changes) >= 80:
                warnings.append("Stopped after 80 extracted breaking changes.")
                stop = True
                break

        for note in batch_notes:
            for raw in deterministic_changes(note):
                key = (note.version, _normalize_quote(raw.quote))
                if key in seen:
                    continue
                normalized = _normalize_quote(raw.quote)
                raw_apis = {api.casefold() for api in raw.apis}
                if any(
                    change.release_version == note.version
                    and _normalize_quote(change.quote) in normalized
                    and raw_apis & {api.casefold() for api in change.apis}
                    for change in changes
                ):
                    continue
                seen.add(key)
                changes.append(
                    BreakingChange(
                        id=f"BC{len(changes) + 1}",
                        package=package,
                        release_version=note.version,
                        title=raw.title,
                        quote=raw.quote,
                        apis=raw.apis,
                        migration=raw.migration,
                        severity=raw.severity,
                        source_title=note.title,
                        source_url=note.url,
                        source_kind=note.source,
                        method="rule",
                    )
                )
                if len(changes) >= 80:
                    warnings.append("Stopped after 80 extracted breaking changes.")
                    stop = True
                    break
            if stop:
                break
        if stop:
            break

    fallback_count = sum(1 for change in changes if change.method == "rule")
    if fallback_count:
        warnings.append(
            f"Used deterministic breaking-line fallback for {fallback_count} change(s)."
        )
    if calls and successful_calls == 0 and not changes:
        raise ScoutError(
            "The model returned no parseable breaking-change JSON. "
            "Review the release notes or try a larger model."
        )
    return changes, warnings

def _candidate_files(
    root: Path,
    tracked_files: list[str] | None,
) -> list[tuple[Path, PurePosixPath]]:
    root = root.resolve()
    candidates: list[tuple[Path, PurePosixPath]] = []
    if tracked_files is not None:
        relatives = [PurePosixPath(name) for name in tracked_files]
    else:
        relatives = []
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            dirs[:] = [
                name
                for name in dirs
                if not is_skippable(PurePosixPath(current_path.name) / name)
                and not (current_path / name).is_symlink()
            ]
            for name in files:
                relative = (current_path / name).relative_to(root).as_posix()
                relatives.append(PurePosixPath(relative))

    for relative in relatives:
        if is_skippable(relative) or is_secret(relative):
            continue
        if relative.suffix.lower() not in SEARCHABLE_SUFFIXES:
            continue
        path = root / Path(relative)
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if resolved.is_file() and not resolved.is_symlink():
            candidates.append((resolved, relative))
    return candidates


def search_repository(
    root: Path,
    changes: list[BreakingChange],
    *,
    tracked_files: list[str] | None = None,
    max_matches: int = MAX_MATCHES,
) -> tuple[list[BreakingChange], int]:
    patterns: dict[str, re.Pattern[str]] = {}
    change_ids: dict[str, list[str]] = {}
    for change in changes:
        change.matches = []
        for api in change.apis:
            for alias in _api_aliases(api):
                patterns.setdefault(
                    alias,
                    re.compile(
                        rf"(?<![A-Za-z0-9_$]){re.escape(alias)}(?![A-Za-z0-9_$])"
                    ),
                )
                change_ids.setdefault(alias, []).append(change.id)

    by_id = {change.id: change for change in changes}
    seen: set[tuple[str, str, int, str]] = set()
    total = 0
    files_scanned = 0
    for path, relative in _candidate_files(root, tracked_files):
        text = read_text_limited(path, MAX_FILE_BYTES)
        if text is None:
            continue
        files_scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            matched_changes: set[str] = set()
            for api, pattern in patterns.items():
                match = pattern.search(line)
                if not match:
                    continue
                for change_id in change_ids[api]:
                    if change_id in matched_changes:
                        continue
                    key = (change_id, relative.as_posix(), line_number, api)
                    if key in seen:
                        continue
                    seen.add(key)
                    matched_changes.add(change_id)
                    by_id[change_id].matches.append(
                        CodeMatch(
                            path=relative.as_posix(),
                            line=line_number,
                            column=match.start() + 1,
                            snippet=line.strip()[:240],
                            api=api,
                            change_id=change_id,
                        )
                    )
                    total += 1
                    if total >= max_matches:
                        return changes, files_scanned
    return changes, files_scanned


def load_expected_apis(path: Path | None) -> list[str]:
    if path is None:
        return []
    try:
        payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoutError(f"Could not read expected-API file: {exc}") from exc
    raw = payload.get("apis") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        raise ScoutError("Expected-API file must be a JSON list or an object with an 'apis' list.")
    return normalize_api_tokens(raw)


def score_expected(changes: list[BreakingChange], expected: list[str]) -> ScoutScore | None:
    if not expected:
        return None
    extracted_lookup = {
        key for change in changes for api in change.apis for key in _api_match_keys(api)
    }
    touched_lookup = {
        key
        for change in changes
        if change.matches
        for api in change.apis
        for key in _api_match_keys(api)
    }
    extracted = [api for api in expected if _api_match_keys(api) & extracted_lookup]
    touched = [api for api in expected if _api_match_keys(api) & touched_lookup]
    missed = [api for api in expected if not (_api_match_keys(api) & extracted_lookup)]
    return ScoutScore(expected=expected, extracted=extracted, touched=touched, missed=missed)


def build_report(
    *,
    package: str,
    github_repo: str | None,
    from_version: str,
    to_version: str,
    repo: RepoSummary,
    model: str,
    provider: str,
    model_host: str | None,
    sources: list[ReleaseNote],
    analyzed_releases: int,
    changes: list[BreakingChange],
    files_scanned: int,
    score: ScoutScore | None,
    warnings: list[str],
) -> ScoutReport:
    touching = [change for change in changes if change.matches]
    unique_apis = {api.casefold() for change in changes for api in change.apis}
    return ScoutReport(
        package=package,
        github_repo=github_repo,
        from_version=from_version,
        to_version=to_version,
        repo=repo,
        model=model,
        provider=provider,
        model_host=model_host,
        created_at=utc_now(),
        sources=[
            ScoutSource(
                kind=note.source,
                title=note.title,
                url=note.url,
                version=note.version,
                published_at=note.published_at,
                note_chars=len(note.body),
            )
            for note in sources
        ],
        changes=changes,
        summary=ScoutSummary(
            releases=len(sources),
            analyzed_releases=analyzed_releases,
            changes=len(changes),
            fallback_changes=sum(1 for change in changes if change.method == "rule"),
            touching=len(touching),
            matches=sum(len(change.matches) for change in changes),
            files_scanned=files_scanned,
            apis_searched=len(unique_apis),
            expected_apis=len(score.expected) if score else 0,
            expected_extracted=len(score.extracted) if score else 0,
        ),
        score=score,
        warnings=warnings,
    )


def _blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def render_scout_markdown(report: ScoutReport) -> str:
    touching = [change for change in report.changes if change.matches]
    untouched = [change for change in report.changes if not change.matches]
    lines = [
        f"<!-- doxify-scout: {report.package} {report.from_version}->{report.to_version} -->",
        "",
        f"# Scout: {report.package} {report.from_version} → {report.to_version}",
        "",
        f"Repository: `{report.repo.name}` · Model: `{report.model}` · "
        f"Provider: `{report.provider}` · Generated: {report.created_at}",
        "",
        "## What touches you",
        "",
    ]

    if not touching:
        lines.extend(
            [
                "No extracted breaking change referenced an API found in the scanned files.",
                "",
                "This does not prove the upgrade is safe. Release notes can omit behavioral "
                "changes, and the model can miss APIs.",
                "",
            ]
        )
    else:
        for change in touching:
            lines.extend(
                [
                    f"### {change.title}",
                    "",
                    f"**Severity:** {change.severity} · **Release:** `{change.release_version}` · "
                    f"**APIs:** {', '.join(f'`{api}`' for api in change.apis)}",
                    "",
                    _blockquote(change.quote),
                    "",
                ]
            )
            if change.migration:
                lines.extend([f"Migration hint: {change.migration}", ""])
            for match in change.matches:
                lines.append(
                    f"- `{match.path}:{match.line}` — {match.snippet}"
                )
            lines.extend(
                [
                    "",
                    f"Source: [{change.source_title}]({change.source_url})",
                    "",
                ]
            )

    if untouched:
        lines.extend(
            [
                "## Filtered out",
                "",
                f"{len(untouched)} extracted breaking change(s) did not reference the scanned "
                "files. They remain in `scout.json` for audit.",
                "",
            ]
        )

    if report.score:
        score = report.score
        lines.extend(
            [
                "## Replay score",
                "",
                f"- Expected APIs: {len(score.expected)}",
                f"- Extracted: {len(score.extracted)}/{len(score.expected)}",
                f"- Extracted and found in repo: {len(score.touched)}/{len(score.expected)}",
            ]
        )
        if score.missed:
            lines.append(f"- Missed: {', '.join(f'`{api}`' for api in score.missed)}")
        lines.append("")

    model_changes = report.summary.changes - report.summary.fallback_changes
    method_lines = [
        "## Method and limits",
        "",
        f"- Read {report.summary.releases} release-note source(s).",
    ]
    if model_changes:
        method_lines.append(
            f"- The model supplied {model_changes} verified breaking change(s)."
        )
    if report.summary.fallback_changes:
        method_lines.append(
            f"- Deterministic fallback supplied {report.summary.fallback_changes} "
            "change(s) from exact breaking-change lines."
        )
    method_lines.extend(
        [
            f"- Searched {report.summary.files_scanned} tracked code file(s) for "
            f"{report.summary.apis_searched} API name(s).",
            "- Only matched changes are shown above; this is a review filter, not a "
            "correctness proof.",
            "",
        ]
    )
    lines.extend(method_lines)

    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
        lines.append("")

    lines.extend(["## Sources", ""])
    for source in report.sources:
        lines.append(
            f"- [{source.title}]({source.url}) — {source.kind} · `{source.version}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def resolve_ecosystem(package: str, github_repo: str | None) -> str | None:
    if github_repo:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github_repo):
            raise ScoutError("--github-repo must look like owner/name.")
        return github_repo
    return ECOSYSTEMS.get(package.strip().lower())


def scout_repo(
    repo_path: Path,
    package: str,
    from_version: str,
    to_version: str,
    *,
    client: OllamaClient,
    model: str,
    output: Path,
    github_repo: str | None = None,
    notes_file: Path | None = None,
    expected_file: Path | None = None,
    max_releases: int = MAX_RELEASES,
    deep: bool = False,
    force: bool = False,
    on_stage: Callable[[str, str], None] | None = None,
) -> ScoutResult:
    emit = on_stage or (lambda _stage, _detail: None)
    package = package.strip()
    if not package:
        raise ScoutError("Package name cannot be empty.")

    start = parse_version(from_version)
    end = parse_version(to_version)
    if start is None or end is None:
        raise ScoutError("Versions must look like 18, 18.2.0, or v19.0.0.")
    if _version_key(end) <= _version_key(start):
        raise ScoutError("The target version must be newer than the starting version.")

    emit("validate", "Checking repository")
    repo = open_repo(repo_path, allow_tool_root=True)
    context: RepoContext = collect_repo_context(repo)
    resolved_repo = resolve_ecosystem(package, github_repo)
    if notes_file is None and resolved_repo is None:
        raise ScoutError(
            f"Unknown package: {package}. Use --github-repo owner/name, "
            "or pass --notes FILE."
        )

    output = prepare_output_dir(output, force=force)
    client.ensure_ready()

    emit("notes", f"Fetching {package} release notes")
    notes, warnings = fetch_release_notes(
        package,
        resolved_repo,
        from_version,
        to_version,
        notes_file=notes_file,
        max_releases=max_releases,
    )

    notes_payload = {
        "package": package,
        "github_repo": resolved_repo,
        "from_version": from_version,
        "to_version": to_version,
        "notes": [note.model_dump() for note in notes],
    }
    notes_path = output / RELEASE_NOTES_JSON
    write_json(notes_path, notes_payload)

    now = utc_now()
    manifest = SessionManifest(
        created_at=now,
        updated_at=now,
        repo=context.summary,
        model=model,
        provider=getattr(client, "provider", "local"),
        model_host=getattr(client, "host", None),
        status="notes_fetched",
    )
    manifest_path = output / "manifest.json"
    write_manifest(manifest_path, manifest, [RELEASE_NOTES_JSON])

    analysis_notes = notes if deep else focus_notes(notes, from_version, to_version)
    if not analysis_notes:
        analysis_notes = notes
    emit("extract", f"Extracting breaking changes from {len(analysis_notes)} release source(s)")
    changes, extraction_warnings = extract_breaking_changes(
        client,
        analysis_notes,
        package,
        from_version,
        to_version,
    )
    warnings.extend(extraction_warnings)
    if len(analysis_notes) < len(notes):
        warnings.append(
            "Fast mode analyzed the first release of the target line; "
            "pass --deep to analyze every fetched release."
        )

    emit("search", f"Searching repository for {len(changes)} extracted change(s)")
    changes, files_scanned = search_repository(
        context.root,
        changes,
        tracked_files=context.tracked_files,
    )

    expected_apis = load_expected_apis(expected_file)
    score = score_expected(changes, expected_apis)
    report = build_report(
        package=package,
        github_repo=resolved_repo,
        from_version=from_version,
        to_version=to_version,
        repo=context.summary,
        model=model,
        provider=getattr(client, "provider", "local"),
        model_host=getattr(client, "host", None),
        sources=notes,
        analyzed_releases=len(analysis_notes),
        changes=changes,
        files_scanned=files_scanned,
        score=score,
        warnings=warnings,
    )

    emit("export", "Writing Scout report")
    markdown_path = output / SCOUT_MD
    json_path = output / SCOUT_JSON
    write_text(markdown_path, render_scout_markdown(report))
    write_json(json_path, report)
    manifest.status = "scouted"
    manifest.warnings = warnings
    write_manifest(
        manifest_path,
        manifest,
        [RELEASE_NOTES_JSON, SCOUT_JSON, SCOUT_MD],
    )
    emit("done", f"Scout report written to {output}")
    return ScoutResult(
        report=report,
        output_dir=output,
        markdown_path=markdown_path,
        json_path=json_path,
        notes_path=notes_path,
        manifest_path=manifest_path,
    )
