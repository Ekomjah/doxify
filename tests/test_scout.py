from __future__ import annotations

import json
from pathlib import Path

import pytest
from git import Repo
from typer.testing import CliRunner

import doxify.cli as cli
import doxify.scout as scout
from doxify.models import (
    BreakingChange,
    CodeMatch,
    ReleaseNote,
    RepoSummary,
    ScoutReport,
    ScoutScore,
    ScoutSummary,
)
from doxify.scout import (
    ScoutResult,
    deterministic_changes,
    extract_apis_from_quote,
    fetch_github_releases,
    normalize_api_tokens,
    parse_changes_response,
    parse_version,
    quote_in_notes,
    release_chunks,
    render_scout_markdown,
    score_expected,
    scout_repo,
    search_repository,
    select_releases,
)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def ensure_ready(self) -> None:
        return None

    def chat(self, *_args: object, **_kwargs: object) -> str:
        self.calls += 1
        return self.response


def _note(version: str, body: str) -> ReleaseNote:
    return ReleaseNote(
        version=version,
        title=f"Release {version}",
        url=f"https://example.test/{version}",
        body=body,
    )


def _change(change_id: str, apis: list[str]) -> BreakingChange:
    return BreakingChange(
        id=change_id,
        package="react",
        release_version="v19.0.0",
        title=f"Change {change_id}",
        quote=f"Quote for {change_id}",
        apis=apis,
        source_title="Release v19.0.0",
        source_url="https://example.test/v19.0.0",
        source_kind="github",
    )


def _repo_summary(path: Path) -> RepoSummary:
    return RepoSummary(
        path=str(path),
        name=path.name,
        commit_count=1,
        tracked_file_count=2,
    )


def test_parse_and_select_versions_across_major_boundary() -> None:
    assert parse_version("react@18.2.0") is not None
    assert parse_version("v19.0.0-rc.1").prerelease is True  # type: ignore[union-attr]
    notes = [
        _note("v18.0.0", "older"),
        _note("v18.3.1", "patch"),
        _note("v19.0.0", "major"),
        _note("v19.1.0", "minor"),
        _note("v20.0.0", "too new"),
    ]
    selected, dropped = select_releases(notes, "react", "18", "19")

    assert [note.version for note in selected] == ["v18.3.1", "v19.0.0", "v19.1.0"]
    assert dropped == 0


def test_select_releases_keeps_first_release_of_each_minor_under_cap() -> None:
    notes = [_note(f"v19.0.{index}", "patch") for index in range(40)]
    notes.append(_note("v19.1.0", "next minor"))
    selected, dropped = select_releases(notes, "react", "18", "19", max_releases=4)

    versions = [note.version for note in selected]
    assert "v19.0.0" in versions
    assert "v19.1.0" in versions
    assert dropped == len(notes) - len(selected)


def test_release_chunks_prefers_breaking_sections() -> None:
    note = _note(
        "v19.0.0",
        "## New Features\n\nA shiny new hook.\n\n"
        "## Breaking Changes\n\nRemoved: `ReactDOM.render`.\n",
    )
    chunks = release_chunks(note)

    assert len(chunks) == 1
    assert "ReactDOM.render" in chunks[0]
    assert "shiny new hook" not in chunks[0]


def test_quote_check_normalizes_markdown_but_rejects_invention() -> None:
    body = "Removed: `ReactDOM`.`render` in favor of [createRoot](https://example.test)."
    assert quote_in_notes("Removed: ReactDOM.render", body) is True
    assert quote_in_notes("Removed: ReactDOM.createPortal", body) is False


def test_normalize_api_tokens_strips_code_markers_and_generic_names() -> None:
    assert normalize_api_tokens(
        ["`ReactDOM.render()`", "react", "ReactDOM.hydrate, createRoot"]
    ) == ["ReactDOM.render", "ReactDOM.hydrate", "createRoot"]


def test_parse_changes_response_accepts_fenced_json_and_aliases() -> None:
    response = """```json
    {"changes": [{"change": "Render removal",
                  "evidence": "Removed `ReactDOM.render`.",
                  "api": "ReactDOM.render",
                  "severity": "HIGH"}]}
    ```"""
    changes = parse_changes_response(response)

    assert len(changes) == 1
    assert changes[0].title == "Render removal"
    assert changes[0].apis == ["ReactDOM.render"]
    assert changes[0].severity == "high"


def test_parse_changes_response_accepts_string_quotes() -> None:
    response = (
        '{"changes": ["Removed: `ReactDOM`.`render`, `ReactDOM`.`hydrate`: '
        'use `createRoot` instead."]}'
    )
    changes = parse_changes_response(response)

    assert len(changes) == 1
    assert changes[0].apis == ["ReactDOM.render", "ReactDOM.hydrate"]
    assert changes[0].severity == "high"


def test_extract_apis_ignores_links_and_migration_targets() -> None:
    quote = (
        "Removed: `react-test-renderer/shallow`: re-export of "
        "[react-shallow-renderer](https://github.com/enzymejs/react-shallow-renderer)."
    )

    assert extract_apis_from_quote(quote) == ["react-test-renderer/shallow"]


def test_deterministic_changes_extracts_exact_removed_apis() -> None:
    note = ReleaseNote(
        version="v19.0.0",
        title="Release v19.0.0",
        url="https://example.test/v19.0.0",
        source="file",
        body=(
            "## Breaking Changes\n\n"
            "* Removed: `ReactDOM.render`, `ReactDOM.hydrate`: use `createRoot`.\n"
            "* Removed: `propTypes`: silently ignored now.\n"
        ),
    )

    changes = deterministic_changes(note)

    assert [change.apis for change in changes] == [
        ["ReactDOM.render", "ReactDOM.hydrate"],
        ["propTypes"],
    ]
    assert all(change.quote in note.body for change in changes)


def test_search_repository_matches_unqualified_alias(tmp_path: Path) -> None:
    (tmp_path / "app.jsx").write_text("const node = findDOMNode(ref);\n", encoding="utf-8")
    change = _change("BC1", ["ReactDOM.findDOMNode"])

    updated, _ = search_repository(tmp_path, [change])

    assert len(updated[0].matches) == 1
    assert updated[0].matches[0].api == "findDOMNode"


def test_search_repository_finds_code_but_skips_dependencies_and_secrets(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.jsx").write_text(
        "ReactDOM.render(<App />, root);\n"
        "const node = findDOMNode(ref);\n",
        encoding="utf-8",
    )
    (source / "safe.js").write_text("export const x = 1;\n", encoding="utf-8")
    dependencies = tmp_path / "node_modules" / "pkg"
    dependencies.mkdir(parents=True)
    (dependencies / "index.js").write_text("ReactDOM.render(null, root);\n", encoding="utf-8")
    (tmp_path / ".env").write_text("ReactDOM.render=secret\n", encoding="utf-8")

    changes = [
        _change("BC1", ["ReactDOM.render"]),
        _change("BC2", ["findDOMNode"]),
        _change("BC3", ["useNotUsed"]),
    ]
    updated, files_scanned = search_repository(tmp_path, changes)

    assert files_scanned == 2
    assert len(updated[0].matches) == 1
    assert updated[0].matches[0].path == "src/app.jsx"
    assert updated[0].matches[0].line == 1
    assert len(updated[1].matches) == 1
    assert updated[2].matches == []


def test_render_scout_markdown_only_shows_touching_changes() -> None:
    touching = _change("BC1", ["ReactDOM.render"])
    touching.matches = [
        CodeMatch(
            path="src/app.jsx",
            line=4,
            column=1,
            snippet="ReactDOM.render(<App />, root);",
            api="ReactDOM.render",
            change_id="BC1",
        )
    ]
    untouched = _change("BC2", ["findDOMNode"])
    report = ScoutReport(
        package="react",
        from_version="18",
        to_version="19",
        repo=_repo_summary(Path("/tmp/demo")),
        model="test-model",
        created_at="2026-01-01T00:00:00+00:00",
        sources=[
            scout.ScoutSource(
                kind="github",
                title="Release v19.0.0",
                url="https://example.test/v19.0.0",
                version="v19.0.0",
            )
        ],
        changes=[touching, untouched],
        summary=ScoutSummary(releases=1, changes=2, touching=1, matches=1, files_scanned=3),
        score=ScoutScore(expected=["ReactDOM.render", "findDOMNode"], extracted=["ReactDOM.render"]),
    )
    markdown = render_scout_markdown(report)

    assert "src/app.jsx:4" in markdown
    assert "ReactDOM.render" in markdown
    assert "Change BC2" not in markdown
    assert "1 extracted breaking change(s) did not reference" in markdown
    assert "## Replay score" in markdown


def test_render_scout_markdown_includes_matches_for_every_touching_change() -> None:
    first = _change("BC1", ["ReactDOM.render"])
    first.matches = [
        CodeMatch(
            path="src/app.jsx",
            line=4,
            column=1,
            snippet="ReactDOM.render(<App />, root);",
            api="ReactDOM.render",
            change_id="BC1",
        )
    ]
    second = _change("BC2", ["findDOMNode"])
    second.matches = [
        CodeMatch(
            path="src/app.jsx",
            line=7,
            column=1,
            snippet="const node = findDOMNode(ref);",
            api="findDOMNode",
            change_id="BC2",
        )
    ]
    report = ScoutReport(
        package="react",
        from_version="18",
        to_version="19",
        repo=_repo_summary(Path("/tmp/demo")),
        model="test-model",
        created_at="2026-01-01T00:00:00+00:00",
        changes=[first, second],
        summary=ScoutSummary(
            releases=1,
            changes=2,
            fallback_changes=2,
            touching=2,
            matches=2,
            files_scanned=1,
        ),
        score=ScoutScore(expected=["ReactDOM.render", "findDOMNode"], extracted=["ReactDOM.render", "findDOMNode"]),
    )
    markdown = render_scout_markdown(report)

    assert "src/app.jsx:4" in markdown
    assert "src/app.jsx:7" in markdown
    assert "Deterministic fallback supplied 2 change(s)" in markdown
    assert "The model supplied" not in markdown
    assert "Extracted: 2/2" in markdown


def test_score_expected_reports_missed_apis() -> None:
    change = _change("BC1", ["ReactDOM.render"])
    change.matches = [
        CodeMatch(
            path="src/app.jsx",
            line=1,
            column=1,
            snippet="ReactDOM.render",
            api="ReactDOM.render",
            change_id="BC1",
        )
    ]
    score = score_expected([change], ["ReactDOM.render", "findDOMNode"])

    assert score is not None
    assert score.extracted == ["ReactDOM.render"]
    assert score.touched == ["ReactDOM.render"]
    assert score.missed == ["findDOMNode"]


def test_fetch_github_releases_filters_tags_and_drafts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        [
            {
                "tag_name": "v19.0.0",
                "name": "19.0.0",
                "body": "## Breaking Changes\n\nRemoved `ReactDOM.render`.",
                "html_url": "https://example.test/v19.0.0",
                "draft": False,
            },
            {
                "tag_name": "v19.1.0",
                "name": "19.1.0",
                "body": "## Breaking Changes\n\nRemoved `findDOMNode`.",
                "html_url": "https://example.test/v19.1.0",
                "draft": False,
            },
            {
                "tag_name": "v18.3.1",
                "name": "18.3.1",
                "body": "Patch release.",
                "html_url": "https://example.test/v18.3.1",
                "draft": False,
            },
            {
                "tag_name": "eslint-plugin-react-hooks@7.1.1",
                "name": "hooks",
                "body": "Not the react package.",
                "html_url": "https://example.test/hooks",
                "draft": False,
            },
        ]
    ).encode()
    monkeypatch.setattr(scout, "urlopen", lambda *_args, **_kwargs: _FakeResponse(payload))

    notes, dropped = fetch_github_releases(
        "react",
        "facebook/react",
        "18",
        "19",
        max_pages=1,
    )

    assert [note.version for note in notes] == ["v18.3.1", "v19.0.0", "v19.1.0"]
    assert dropped == 0


def _make_git_repo(path: Path) -> Repo:
    repo = Repo.init(path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Scout Test")
        config.set_value("user", "email", "scout@example.test")
    source = path / "src"
    source.mkdir()
    (source / "app.jsx").write_text("ReactDOM.render(<App />, root);\n", encoding="utf-8")
    repo.index.add(["src/app.jsx"])
    repo.index.commit("initial")
    return repo


def test_scout_repo_writes_report_and_scores_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "demo"
    repo_path.mkdir()
    _make_git_repo(repo_path)
    notes = tmp_path / "react-notes.md"
    notes.write_text(
        "## Breaking Changes\n\n"
        "Removed: `ReactDOM.render` in favor of `createRoot`.\n",
        encoding="utf-8",
    )
    expected = tmp_path / "expected.json"
    expected.write_text(
        json.dumps({"apis": ["ReactDOM.render", "findDOMNode"]}),
        encoding="utf-8",
    )
    client = _FakeClient(
        json.dumps(
            {
                "changes": [
                    {
                        "title": "ReactDOM.render removed",
                        "quote": "Removed: `ReactDOM.render`",
                        "apis": ["ReactDOM.render"],
                        "severity": "high",
                    }
                ]
            }
        )
    )
    output = tmp_path / "out"

    result = scout_repo(
        repo_path,
        "react",
        "18",
        "19",
        client=client,  # type: ignore[arg-type]
        model="test-model",
        output=output,
        notes_file=notes,
        expected_file=expected,
    )

    assert result.markdown_path.exists()
    assert result.json_path.exists()
    assert result.notes_path.exists()
    assert result.manifest_path.exists()
    assert result.report.summary.touching == 1
    assert result.report.score is not None
    assert result.report.score.missed == ["findDOMNode"]
    assert "src/app.jsx:1" in result.markdown_path.read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "scouted"


def test_scout_cli_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = ScoutReport(
        package="react",
        from_version="18",
        to_version="19",
        repo=_repo_summary(tmp_path),
        model="test-model",
        created_at="2026-01-01T00:00:00+00:00",
        changes=[_change("BC1", ["ReactDOM.render"])],
        summary=ScoutSummary(releases=1, changes=1, touching=0),
    )
    result = ScoutResult(
        report=report,
        output_dir=tmp_path,
        markdown_path=tmp_path / "scout.md",
        json_path=tmp_path / "scout.json",
        notes_path=tmp_path / "release-notes.json",
        manifest_path=tmp_path / "manifest.json",
    )

    def fake_scout(*_args: object, **_kwargs: object) -> ScoutResult:
        return result

    monkeypatch.setattr(cli, "scout_repo", fake_scout)
    runner = CliRunner()
    response = runner.invoke(cli.app, ["scout", "react", "18", "19", "--repo", str(tmp_path)])

    assert response.exit_code == 0, response.output
    assert "Scout complete" in response.output
    assert "react 18 -> 19" in response.output
