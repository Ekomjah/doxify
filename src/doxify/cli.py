from __future__ import annotations

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

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Doxify compiles evidence-backed READMEs and portfolio case studies "
        "from local git repositories."
    ),
)


def _default_output(repo: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / "doxify-out" / f"{repo.name}-{stamp}"


def _read_draft(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise typer.BadParameter(f"Could not read draft file: {exc}") from exc


@app.command()
def doctor(
    model: str = typer.Option(DEFAULT_MODEL, help="Ollama model to check."),
    host: str | None = typer.Option(None, help="Ollama host URL."),
) -> None:
    """Check Python, git, Ollama, and the local model."""
    table = Table(title="Doxify doctor", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")

    git_path = shutil.which("git")
    table.add_row("git", "ok" if git_path else "missing", git_path or "install git")
    table.add_row("Python", "ok", "local CLI runtime")

    client = OllamaClient(model=model, host=host)
    healthy, detail = client.health()
    table.add_row("Ollama", "ok" if healthy else "missing", detail)
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
    model: str = typer.Option(DEFAULT_MODEL, help="Ollama model to use."),
    host: str | None = typer.Option(None, help="Ollama host URL."),
    force: bool = typer.Option(False, "--force", help="Allow an existing output directory."),
) -> None:
    """Run the full scan, draft, verify, defense, and export pipeline."""
    output = out or _default_output(repo)
    client = OllamaClient(model=model, host=host)
    draft_text = _read_draft(draft)

    try:
        with stage_progress() as progress:
            task = progress.add_task("Starting", total=None)

            def on_stage(_stage: str, detail: str) -> None:
                progress.update(task, description=detail)

            result = compile_repo(
                repo,
                output,
                client=client,
                model=model,
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
    model: str = typer.Option(DEFAULT_MODEL, help="Ollama model to use."),
    host: str | None = typer.Option(None, help="Ollama host URL."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing README target."),
    cleanup: bool = typer.Option(
        False,
        "--cleanup",
        help="Remove the temporary compile session after success.",
    ),
) -> None:
    """Compile a repository into /tmp and write only an evidence-backed README."""
    client = OllamaClient(model=model, host=host)
    draft_text = _read_draft(draft)

    try:
        with stage_progress() as progress:
            task = progress.add_task("Starting", total=None)

            def on_stage(_stage: str, detail: str) -> None:
                progress.update(task, description=detail)

            result = readme_repo(
                repo,
                client=client,
                model=model,
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
