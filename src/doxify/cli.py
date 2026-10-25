from __future__ import annotations

import logging
import re
import shutil
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

import typer
from rich.table import Table

from .audit import (
    ArtifactReport,
    audit_artifact,
    failing_claims,
    parse_fail_on,
)
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
from .log import configure_logging, log_event
from .models import ClaimStatus, CompileSummary, ScanResult
from .monitoring import (
    begin_stage,
    command_transaction,
    cron_monitor,
    flush_monitoring,
    init_monitoring,
    monitoring_status,
    span,
)
from .ollama_client import DEFAULT_MODEL, OllamaClient
from .pipeline import (
    attest_session,
    compile_repo,
    export_session,
    load_evidence_file,
    readme_repo,
    scan_only,
    verify_session,
)
from .scout import scout_repo
from .selfcheck import SelfCheckError, run_self_check

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Doxify compiles evidence-backed READMEs and portfolio case studies "
        "from local git repositories, and scouts breaking dependency upgrades."
    ),
)


def _version_callback(value: bool) -> None:
    if not value:
        return
    try:
        current = package_version("doxify")
    except PackageNotFoundError:
        current = "0.1.0"
    typer.echo(current)
    raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed Doxify version and exit.",
    ),
) -> None:
    """Compile evidence-backed documentation from a local git repository."""


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


def _command_name() -> str:
    for argument in sys.argv[1:]:
        if not argument.startswith("-"):
            return argument
    return "help"


def _stage_callback(progress, task):
    def on_stage(stage: str, detail: str) -> None:
        progress.update(task, description=detail)
        log_event(logging.INFO, "stage.start", stage=stage)
        begin_stage(stage)

    return on_stage


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
    status = monitoring_status()
    table.add_row(
        "Monitoring",
        "enabled" if status.enabled else "disabled",
        (
            f"opt-in ({status.environment})"
            if status.enabled
            else "set SENTRY_DSN to opt in"
        ),
    )

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


@app.command(name="self-check")
def self_check(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
    check_model: bool = typer.Option(
        False, "--check-model", help="Also check the configured Ollama model."
    ),
    model: str | None = typer.Option(None, help="Model to check with --check-model."),
    host: str | None = typer.Option(None, help="Ollama endpoint URL."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Inference backend: local (default) or cloud.",
    ),
    monitor_slug: str | None = typer.Option(
        None,
        "--monitor-slug",
        help="Sentry cron monitor slug. Defaults to SENTRY_MONITOR_SLUG.",
    ),
) -> None:
    """Run lightweight health checks, optionally with a Sentry cron check-in."""
    client = None
    if check_model:
        try:
            client = OllamaClient(model=model, host=host, provider=provider)
        except DoxifyError as exc:
            error(str(exc))
            raise typer.Exit(code=1) from exc

    result = None
    try:
        with cron_monitor(monitor_slug):
            result = run_self_check(client=client)
            if not result.ok:
                raise SelfCheckError("Self-check failed.")
    except SelfCheckError as exc:
        if json_output and result is not None:
            typer.echo(result.to_json())
        else:
            error(str(exc))
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(result.to_json())
        return

    table = Table(title="Doxify self-check", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")
    for check in result.checks:
        table.add_row(check.name, "ok" if check.ok else "failed", check.detail)
    console.print(table)


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
        with span("scan.repository", op="scan") as current:
            scanned_repo, evidence, output, _ = scan_only(
                repo,
                output,
                model=model,
                force=force,
            )
            if current is not None:
                current.set_measurement("doxify.scan.cards", len(evidence))
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

            on_stage = _stage_callback(progress, task)

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

            on_stage = _stage_callback(progress, task)

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

            on_stage = _stage_callback(progress, task)

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
    session: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Compile session directory. Omit when auditing an artifact directly.",
    ),
    artifact: Path | None = typer.Option(
        None,
        "--artifact",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="README or case study to audit.",
    ),
    evidence: Path | None = typer.Option(
        None,
        "--evidence",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Evidence JSON for artifact-only verification.",
    ),
    fail_on: str = typer.Option(
        "needs_evidence,rejected",
        "--fail-on",
        help="Comma-separated statuses that fail: needs_evidence, rejected, attested, or none.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Read-only verification; do not rewrite session artifacts.",
    ),
) -> None:
    """Re-run deterministic verification on a session, README, or case study."""
    if session is None and artifact is None:
        raise typer.BadParameter("Provide SESSION or --artifact.")
    if artifact is None and evidence is not None:
        raise typer.BadParameter("--evidence requires --artifact.")
    try:
        fail_statuses = parse_fail_on(fail_on)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    session_report = None
    artifact_report = None
    try:
        with span("verify.claims", op="verify"):
            if session is not None:
                session_report = verify_session(session, write=not check)
            if artifact is not None:
                if evidence is not None:
                    scan = load_evidence_file(evidence)
                elif session is not None:
                    scan = load_evidence_file(session / "evidence.json")
                else:
                    raise typer.BadParameter(
                        "--artifact requires --evidence when SESSION is omitted."
                    )
                artifact_report = audit_artifact(artifact, scan.evidence)
    except DoxifyError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc

    if session_report is not None:
        _print_verification(session_report.summary)
    if artifact_report is not None:
        _print_artifact_verification(artifact_report, fail_statuses)

    failed = []
    if session_report is not None:
        failed.extend(failing_claims(session_report.claims, fail_statuses))
    if artifact_report is not None:
        failed.extend(failing_claims(artifact_report.claims, fail_statuses))

    if failed:
        console.print(
            f"[red]Verification failed:[/red] {len(failed)} claim(s) matched --fail-on."
        )
        raise typer.Exit(code=1)
    console.print("[green]Verification passed.[/green]")


@app.command()
def attest(
    session: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    claim: str = typer.Option(..., "--claim", "-c", help="Claim ID, for example C7."),
    answer: str | None = typer.Option(None, "--answer", "-a", help="Author context."),
) -> None:
    """Attach author context to a claim and label it ATTESTED."""
    context = answer or typer.prompt("Author context")
    try:
        with span("attest.claim", op="verify"):
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
        with span("export.write", op="export"):
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


def _print_artifact_verification(
    report: ArtifactReport,
    fail_on: set[ClaimStatus],
) -> None:
    summary = report.summary
    table = Table(title=f"Artifact: {report.path.name}", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Mode", report.mode)
    table.add_row("Sections", str(len(report.sections)))
    table.add_row(
        "Attested sections",
        str(sum(1 for section in report.sections if section.attested)),
    )
    if report.unmarked_sections:
        table.add_row("Unmarked sections", str(len(report.unmarked_sections)))
    table.add_row(
        "Claims",
        f"{summary.verified} verified, {summary.attested} attested, "
        f"{summary.needs_evidence} needing evidence, {summary.rejected} rejected",
    )
    console.print(table)

    failures = failing_claims(report.claims, fail_on)
    for claim in failures[:10]:
        console.print(f"[red]{claim.id} {claim.status.value}[/red] {claim.text}")
        if claim.reason:
            console.print(f"  {claim.reason}")
    if len(failures) > 10:
        console.print(f"  ... and {len(failures) - 10} more")


def main() -> None:
    configure_logging()
    init_monitoring()
    command = _command_name()
    log_event(logging.INFO, "cli.start", command=command)
    try:
        with command_transaction(command):
            app()
    finally:
        log_event(logging.INFO, "cli.finish", command=command)
        flush_monitoring()


if __name__ == "__main__":
    main()
