from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from .console import (
    console,
    error,
    print_compile_summary,
    print_readme_summary,
    print_scan_summary,
    print_scout_summary,
    stage_progress,
)
from .errors import DoxifyError
from .models import CompileSummary, ScanResult
from .ollama_client import DEFAULT_MODEL, OllamaClient
from .pipeline import (
    attest_session,
    compile_repo,
    export_session,
    readme_repo,
    scan_only,
    verify_session,
)
from .scout import scout_repo

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Doxify compiles evidence-backed READMEs and portfolio case studies "
        "from local git repositories, and scouts breaking dependency upgrades."
    ),
)


def _default_output(repo: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / "doxify-out" / f"{repo.name}-{stamp}"


def _default_scout_output(package: str, from_version: str, to_version: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_package = re.sub(r"[^A-Za-z0-9_.-]+", "-", package).strip("-") or "package"
    safe_from = re.sub(r"[^A-Za-z0-9_.-]+", "-", from_version).strip("-") or "from"
    safe_to = re.sub(r"[^A-Za-z0-9_.-]+", "-", to_version).strip("-") or "to"
    return (
        Path.cwd()
        / "doxify-out"
        / f"scout-{safe_package}-{safe_from}-to-{safe_to}-{stamp}"
    )


def _read_draft(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise typer.BadParameter(f"Could not read draft file: {exc}") from exc


def _warn_cloud(client: OllamaClient) -> None:
    if not client.is_cloud:
        return
    console.print(
        "[yellow]Cloud mode sends repository evidence (file paths, snippets, "
        "commit messages, dependency names) to Ollama Cloud. Do not use it for "
        "confidential repositories. Cloud usage may incur charges.[/yellow]"
    )


@app.command()
def doctor(
    model: str | None = typer.Option(
        None,
        help=(
            "Model to check. Defaults to gemma3:1b locally or "
            "gemma4:31b on Ollama Cloud."
        ),
    ),
    host: str | None = typer.Option(None, help="Ollama endpoint URL."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Inference backend: local (default) or cloud.",
    ),
) -> None:
    """Check Python, git, and the configured model provider."""
    table = Table(title="Doxify doctor", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")

    git_path = shutil.which("git")
    table.add_row("git", "ok" if git_path else "missing", git_path or "install git")
    table.add_row("Python", "ok", "local CLI runtime")

    try:
        client = OllamaClient(model=model, host=host, provider=provider)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc

    table.add_row("Provider", client.label, client.host)
    table.add_row("Model", client.model, "cloud" if client.is_cloud else "local")
    if client.is_cloud:
        table.add_row(
            "API key",
            "set" if client.api_key else "missing",
            "OLLAMA_API_KEY (checked on first call)",
        )
    healthy, detail = client.health()
    table.add_row("Endpoint", "ok" if healthy else "missing", detail)
    console.print(table)

    if not git_path or not healthy:
        raise typer.Exit(code=1)


@app.command()
def scan(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output directory."),
    model: str = typer.Option(DEFAULT_MODEL, help="Model recorded in the manifest."),
    force: bool = typer.Option(False, "--force", help="Allow an existing output directory."),
) -> None:
    """Scan a repository and write deterministic evidence without calling Ollama."""
    output = out or _default_output(repo)
    try:
        scanned_repo, evidence, output, _ = scan_only(
            repo,
            output,
            model=model,
            force=force,
        )
        print_scan_summary(ScanResult(repo=scanned_repo, evidence=evidence), output)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def compile(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output directory."),
    draft: Path | None = typer.Option(None, "--draft", help="Optional Markdown notes."),
    role: str | None = typer.Option(None, "--role", help="Target role for tone."),
    model: str | None = typer.Option(
        None,
        help=(
            "Model to use. Defaults to gemma3:1b locally or "
            "gemma4:31b on Ollama Cloud."
        ),
    ),
    host: str | None = typer.Option(None, help="Ollama endpoint URL."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Inference backend: local (default) or cloud.",
    ),
    force: bool = typer.Option(False, "--force", help="Allow an existing output directory."),
) -> None:
    """Run the full scan, draft, verify, defense, and export pipeline."""
    output = out or _default_output(repo)
    draft_text = _read_draft(draft)

    try:
        client = OllamaClient(model=model, host=host, provider=provider)
        _warn_cloud(client)
        with stage_progress() as progress:
            task = progress.add_task("Starting", total=None)

            def on_stage(_stage: str, detail: str) -> None:
                progress.update(task, description=detail)

            result = compile_repo(
                repo,
                output,
                client=client,
                model=client.model,
                draft=draft_text,
                role=role,
                on_stage=on_stage,
                force=force,
            )
        print_compile_summary(result, output)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def readme(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    output: Path | None = typer.Option(
        None,
        "--output",
        "--out",
        "-o",
        help="README file or directory. Defaults to REPO/README.md.",
    ),
    draft: Path | None = typer.Option(None, "--draft", help="Optional Markdown notes."),
    role: str | None = typer.Option(None, "--role", help="Target role for tone."),
    model: str | None = typer.Option(
        None,
        help=(
            "Model to use. Defaults to gemma3:1b locally or "
            "gemma4:31b on Ollama Cloud."
        ),
    ),
    host: str | None = typer.Option(None, help="Ollama endpoint URL."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Inference backend: local (default) or cloud.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing README target."),
    cleanup: bool = typer.Option(
        False,
        "--cleanup",
        help="Remove the temporary compile session after success.",
    ),
) -> None:
    """Compile a repository into /tmp and write only an evidence-backed README."""
    draft_text = _read_draft(draft)

    try:
        client = OllamaClient(model=model, host=host, provider=provider)
        _warn_cloud(client)
        with stage_progress() as progress:
            task = progress.add_task("Starting", total=None)

            def on_stage(_stage: str, detail: str) -> None:
                progress.update(task, description=detail)

            result = readme_repo(
                repo,
                client=client,
                model=client.model,
                output=output,
                draft=draft_text,
                role=role,
                force=force,
                cleanup=cleanup,
                on_stage=on_stage,
            )
        print_readme_summary(result)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def scout(
    package: str = typer.Argument(
        ...,
        metavar="PACKAGE",
        help="Package or ecosystem, for example react.",
    ),
    from_version: str = typer.Argument(..., metavar="FROM", help="Current version, for example 18."),
    to_version: str = typer.Argument(..., metavar="TO", help="Target version, for example 19."),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="Repository to search. Defaults to the current directory.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory. Defaults to doxify-out/scout-<package>-<from>-to-<to>/.",
    ),
    notes: Path | None = typer.Option(
        None,
        "--notes",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Offline release notes file. Skips GitHub and SerpApi.",
    ),
    expected: Path | None = typer.Option(
        None,
        "--expect",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="JSON list of APIs known to break, for replay scoring.",
    ),
    github_repo: str | None = typer.Option(
        None,
        "--github-repo",
        help="GitHub repository for an unmapped package, for example owner/name.",
    ),
    max_releases: int = typer.Option(
        12,
        "--max-releases",
        help="Maximum number of GitHub releases to fetch.",
    ),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Analyze every fetched release instead of the first target-line release.",
    ),
    model: str | None = typer.Option(
        None,
        help=(
            "Model to use. Defaults to gemma3:1b locally or "
            "gemma4:31b on Ollama Cloud."
        ),
    ),
    host: str | None = typer.Option(None, help="Ollama endpoint URL."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Inference backend: local (default) or cloud.",
    ),
    force: bool = typer.Option(False, "--force", help="Allow an existing output directory."),
) -> None:
    """Fetch release notes, extract breaking changes, and search your repo."""
    repo_path = (repo or Path.cwd()).expanduser().resolve()
    output = out or _default_scout_output(package, from_version, to_version)

    try:
        client = OllamaClient(model=model, host=host, provider=provider)
        _warn_cloud(client)
        with stage_progress() as progress:
            task = progress.add_task("Starting", total=None)

            def on_stage(_stage: str, detail: str) -> None:
                progress.update(task, description=detail)

            result = scout_repo(
                repo_path,
                package,
                from_version,
                to_version,
                client=client,
                model=client.model,
                output=output,
                github_repo=github_repo,
                notes_file=notes,
                expected_file=expected,
                max_releases=max_releases,
                deep=deep,
                force=force,
                on_stage=on_stage,
            )
        print_scout_summary(result)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def verify(
    session: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
) -> None:
    """Re-run deterministic verification on an existing session."""
    try:
        report = verify_session(session)
        _print_verification(report.summary)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def attest(
    session: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    claim: str = typer.Option(..., "--claim", "-c", help="Claim ID, for example C7."),
    answer: str | None = typer.Option(None, "--answer", "-a", help="Author context."),
) -> None:
    """Attach author context to a claim and label it ATTESTED."""
    context = answer or typer.prompt("Author context")
    try:
        report = attest_session(session, claim, context)
        _print_verification(report.summary)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def export(
    session: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
) -> None:
    """Re-render Markdown and JSON artifacts from an existing session."""
    try:
        output = export_session(session)
        console.print(f"[green]Exported[/green] {output}")
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


def _print_verification(summary: CompileSummary) -> None:
    table = Table(title="Verification", show_header=False)
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("Verified", str(summary.verified))
    table.add_row("Attested", str(summary.attested))
    table.add_row("Needs evidence", str(summary.needs_evidence))
    table.add_row("Rejected", str(summary.rejected))
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
