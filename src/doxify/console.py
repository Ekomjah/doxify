from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from .models import CompileResult, RepoSummary, ScanResult
from .readme import ReadmeResult
from .scout import ScoutResult

console = Console()


def stage_progress():
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


def print_scan_summary(result: ScanResult, output: Path) -> None:
    table = Table(title="Scan complete", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Repository", result.repo.name)
    table.add_row("Commits", str(result.repo.commit_count))
    table.add_row(
        "Timeline",
        f"{result.repo.first_commit_date or 'unknown'} to {result.repo.last_commit_date or 'unknown'}",
    )
    table.add_row("Tracked files", str(result.repo.tracked_file_count))
    table.add_row("README", result.repo.readme_path or "missing")
    table.add_row("Evidence cards", str(len(result.evidence)))
    table.add_row("Output", str(output))
    console.print(table)


def print_compile_summary(result: CompileResult, output: Path) -> None:
    summary = result.summary
    table = Table(title="Compile complete", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Repository", result.manifest.repo.name)
    table.add_row(
        "Model",
        f"{result.manifest.model} ({result.manifest.provider})",
    )
    table.add_row("Sections", str(summary.sections))
    table.add_row("Evidence cards", str(summary.evidence_cards))
    table.add_row(
        "Claims",
        f"{summary.verified} verified, {summary.attested} attested, "
        f"{summary.needs_evidence} needing evidence, {summary.rejected} rejected",
    )
    table.add_row("Defense questions", str(len(result.defense)))
    table.add_row("Output", str(output))
    console.print(table)

    if summary.needs_evidence or summary.rejected:
        console.print(
            "\n[yellow]Review claims.json for gaps. Use `doxify attest DIR --claim C1 --answer ...` to label author context.[/yellow]"
        )


def print_readme_summary(result: ReadmeResult) -> None:
    summary = result.compile_result.summary
    table = Table(title="README complete", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Repository", result.compile_result.manifest.repo.name)
    table.add_row("README", str(result.path))
    if result.session_cleaned:
        table.add_row("Compile session", f"removed ({result.session_dir})")
    else:
        table.add_row("Compile session", str(result.session_dir))
    table.add_row(
        "Claims",
        f"{summary.verified} verified, {summary.attested} attested, "
        f"{summary.needs_evidence} needing evidence, {summary.rejected} rejected",
    )
    table.add_row("Evidence cards", str(summary.evidence_cards))
    if result.backup_path is not None:
        table.add_row("Backup", str(result.backup_path))
    console.print(table)

    if result.omitted_claims:
        console.print(
            "\n[yellow]README omitted unresolved claims. Review claims.json in the "
            "compile session, then attest with `doxify attest SESSION --claim C1 --answer ...`.[/yellow]"
        )


def print_scout_summary(result: ScoutResult) -> None:
    report = result.report
    table = Table(title="Scout complete", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Repository", report.repo.name)
    table.add_row("Upgrade", f"{report.package} {report.from_version} -> {report.to_version}")
    table.add_row("Release sources", str(report.summary.releases))
    changes_label = str(report.summary.changes)
    if report.summary.fallback_changes:
        changes_label += f" ({report.summary.fallback_changes} fallback)"
    table.add_row("Breaking changes", changes_label)
    table.add_row(
        "Touches you",
        f"{report.summary.touching} change(s), {report.summary.matches} code match(es)",
    )
    table.add_row("Files scanned", str(report.summary.files_scanned))
    if report.score:
        table.add_row(
            "Replay score",
            f"{len(report.score.extracted)}/{len(report.score.expected)} extracted, "
            f"{len(report.score.touched)}/{len(report.score.expected)} touching code",
        )
    table.add_row("Report", str(result.markdown_path))
    table.add_row("Session", str(result.output_dir))
    console.print(table)

    touching = [change for change in report.changes if change.matches]
    for change in touching[:5]:
        console.print(
            f"  [bold]{change.id}[/bold] {change.title} "
            f"({len(change.matches)} match(es))"
        )
    if len(touching) > 5:
        console.print(f"  ... and {len(touching) - 5} more in the report.")
    if not touching:
        console.print(
            "\n[yellow]No extracted breaking change matched the scanned files. "
            "Review the report before treating the upgrade as safe.[/yellow]"
        )
    if report.warnings:
        console.print(f"\n[yellow]{len(report.warnings)} warning(s) recorded in the report.[/yellow]")


def print_repo(repo: RepoSummary) -> None:
    console.print(
        f"[bold]{repo.name}[/bold] · {repo.commit_count} commits · "
        f"{repo.tracked_file_count} tracked files"
    )


def error(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
