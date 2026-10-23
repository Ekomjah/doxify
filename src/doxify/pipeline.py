from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from .claims import extract_claims
from .defense import build_defense
from .errors import SessionError
from .exporter import (
    write_case_study,
    write_claims_json,
    write_defense,
    write_defense_json,
    write_evidence_json,
    write_sections_json,
    write_verification_json,
)
from .generator import GeneratedSection, generate_section, template_section
from .models import (
    CaseStudySection,
    CaseStudySentence,
    ClaimsDocument,
    ClaimStatus,
    CompileResult,
    DefenseDocument,
    EvidenceCard,
    RepoSummary,
    ScanResult,
    SectionsDocument,
    SessionManifest,
    VerificationReport,
)
from .ollama_client import OllamaClient
from .readme import (
    ReadmeResult,
    backup_readme,
    build_readme,
    resolve_readme_target,
)
from .retrieval import SECTION_SPECS, retrieve_evidence
from .scanner import scan_repository
from .session import (
    prepare_output_dir,
    read_model,
    utc_now,
    write_json,
    write_manifest,
    write_text,
)
from .verifier import attest_claim as mark_attested
from .verifier import summarize_claims, verify_claims

StageCallback = Callable[[str, str], None]

CASE_STUDY = "case-study.md"
DEFENSE = "defense.md"
EVIDENCE = "evidence.json"
SECTIONS = "sections.json"
CLAIMS = "claims.json"
VERIFICATION = "verification.json"
DEFENSE_JSON = "defense.json"
MANIFEST = "manifest.json"


def scan_only(
    repo_path: Path,
    output_dir: Path,
    *,
    model: str,
    on_stage: StageCallback | None = None,
    force: bool = False,
) -> tuple[RepoSummary, list[EvidenceCard], Path, SessionManifest]:
    emit = on_stage or (lambda _stage, _detail: None)
    emit("validate", "Checking repository path")
    _context, scan = scan_repository(repo_path)
    output = prepare_output_dir(output_dir, force=force)
    emit("scan", f"Collected {len(scan.evidence)} evidence cards")
    write_evidence_json(output, scan.repo, scan.evidence)

    now = utc_now()
    manifest = SessionManifest(
        created_at=now,
        updated_at=now,
        repo=scan.repo,
        model=model,
        status="scanned",
    )
    write_manifest(output / MANIFEST, manifest, [EVIDENCE])
    emit("done", f"Evidence written to {output}")
    return scan.repo, scan.evidence, output, manifest


def compile_repo(
    repo_path: Path,
    output_dir: Path,
    *,
    client: OllamaClient,
    model: str,
    draft: str | None = None,
    role: str | None = None,
    on_stage: StageCallback | None = None,
    force: bool = False,
) -> CompileResult:
    emit = on_stage or (lambda _stage, _detail: None)
    emit("validate", "Checking repository and model")
    client.ensure_ready()
    _context, scan = scan_repository(repo_path)
    output = prepare_output_dir(output_dir, force=force)

    now = utc_now()
    manifest = SessionManifest(
        created_at=now,
        updated_at=now,
        repo=scan.repo,
        model=model,
        status="running",
    )
    write_manifest(output / MANIFEST, manifest, [])
    write_evidence_json(output, scan.repo, scan.evidence)
    emit("scan", f"Collected {len(scan.evidence)} evidence cards")

    sections: list[CaseStudySection] = []
    claims = []
    warnings: list[str] = []

    for index, spec in enumerate(SECTION_SPECS, start=1):
        emit("generate", f"[{index}/{len(SECTION_SPECS)}] Drafting {spec.title}")
        cards = retrieve_evidence(scan.evidence, spec, limit=3)
        if spec.id in {"snapshot", "problem", "reflection"}:
            generated = GeneratedSection(
                body=template_section(spec, cards),
                fallback_used=False,
            )
        else:
            generated = generate_section(
                client,
                spec,
                cards,
                repo_name=scan.repo.name,
                role=role,
                draft=draft,
            )
        if generated.fallback_used:
            warnings.append(f"{spec.title}: template fallback ({generated.error}).")
        section_claims = extract_claims(
            spec.id,
            generated.body,
            start_index=len(claims) + 1,
        )
        claims.extend(section_claims)
        sections.append(
            CaseStudySection(
                id=spec.id,
                title=spec.title,
                body=generated.body,
                sentences=[
                    CaseStudySentence(
                        text=claim.text,
                        claim_id=claim.id,
                        evidence_ids=claim.evidence_ids,
                    )
                    for claim in section_claims
                ],
            )
        )

    emit("verify", f"Verifying {len(claims)} claims")
    claims = verify_claims(claims, scan.evidence)
    summary = summarize_claims(
        claims,
        section_count=len(sections),
        evidence_count=len(scan.evidence),
    )

    emit("defense", "Building interview defense pack")
    defense = build_defense(
        client,
        sections,
        claims,
        scan.evidence,
        repo_name=scan.repo.name,
        use_model=False,
    )

    emit("export", "Writing Markdown and JSON artifacts")
    write_sections_json(output, sections)
    write_claims_json(output, claims, summary)
    write_verification_json(output, claims, summary)
    write_defense_json(output, defense)
    write_case_study(output, scan.repo, sections, scan.evidence, summary, claims)
    write_defense(output, scan.repo, defense)

    manifest.status = "done"
    manifest.warnings = warnings
    artifacts = [
        EVIDENCE,
        SECTIONS,
        CLAIMS,
        VERIFICATION,
        DEFENSE_JSON,
        CASE_STUDY,
        DEFENSE,
    ]
    write_manifest(output / MANIFEST, manifest, artifacts)
    emit("done", f"Session complete: {output}")

    return CompileResult(
        manifest=manifest,
        evidence=scan.evidence,
        sections=sections,
        claims=claims,
        defense=defense,
        summary=summary,
    )


def readme_repo(
    repo_path: Path,
    *,
    client: OllamaClient,
    model: str,
    output: Path | None = None,
    draft: str | None = None,
    role: str | None = None,
    force: bool = False,
    cleanup: bool = False,
    on_stage: StageCallback | None = None,
) -> ReadmeResult:
    emit = on_stage or (lambda _stage, _detail: None)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", repo_path.name) or "repository"
    session_dir = Path(tempfile.mkdtemp(prefix=f"doxify-readme-{safe_name}-"))
    emit("prepare", f"Created temporary compile session: {session_dir}")

    result = compile_repo(
        repo_path,
        session_dir,
        client=client,
        model=model,
        draft=draft,
        role=role,
        on_stage=on_stage,
    )

    emit("readme", "Rendering evidence-backed README")
    content = build_readme(result, session_dir=session_dir)
    target = resolve_readme_target(
        Path(result.manifest.repo.path),
        output,
        force=force,
    )

    backup_path: Path | None = None
    if target.exists():
        emit("backup", f"Backing up existing README to {session_dir / 'backups'}")
        backup_path = backup_readme(target, session_dir)

    emit("write", f"Writing README to {target}")
    write_text(target, content)

    omitted = [
        claim
        for claim in result.claims
        if claim.status not in {ClaimStatus.VERIFIED, ClaimStatus.ATTESTED}
    ]
    readme_result = ReadmeResult(
        path=target,
        session_dir=session_dir,
        content=content,
        compile_result=result,
        omitted_claims=omitted,
        warnings=list(result.manifest.warnings),
        backup_path=backup_path,
    )

    if cleanup:
        emit("cleanup", f"Removing temporary compile session: {session_dir}")
        shutil.rmtree(session_dir, ignore_errors=True)
        readme_result.session_cleaned = True

    emit("done", f"README written to {target}")
    return readme_result


def load_session(output_dir: Path) -> tuple[ScanResult, SectionsDocument, ClaimsDocument, DefenseDocument, SessionManifest]:
    output = output_dir.expanduser().resolve()
    if not output.is_dir():
        raise SessionError(f"Session directory does not exist: {output}")
    scan = read_model(output / EVIDENCE, ScanResult)
    sections = read_model(output / SECTIONS, SectionsDocument)
    claims = read_model(output / CLAIMS, ClaimsDocument)
    defense = read_model(output / DEFENSE_JSON, DefenseDocument)
    manifest = read_model(output / MANIFEST, SessionManifest)
    return scan, sections, claims, defense, manifest


def verify_session(output_dir: Path) -> VerificationReport:
    output = output_dir.expanduser().resolve()
    scan, sections, claims_doc, defense, manifest = load_session(output)
    claims = verify_claims(claims_doc.claims, scan.evidence)
    summary = summarize_claims(
        claims,
        section_count=len(sections.sections),
        evidence_count=len(scan.evidence),
    )
    write_claims_json(output, claims, summary)
    report = VerificationReport(summary=summary, claims=claims)
    write_json(output / VERIFICATION, report)
    write_case_study(output, scan.repo, sections.sections, scan.evidence, summary, claims)
    write_defense(output, scan.repo, defense.questions)
    manifest.status = "verified"
    write_manifest(
        output / MANIFEST,
        manifest,
        [EVIDENCE, SECTIONS, CLAIMS, VERIFICATION, DEFENSE_JSON, CASE_STUDY, DEFENSE],
    )
    return report


def attest_session(output_dir: Path, claim_id: str, answer: str) -> VerificationReport:
    output = output_dir.expanduser().resolve()
    scan, sections, claims_doc, defense, manifest = load_session(output)
    try:
        mark_attested(claims_doc.claims, claim_id, answer)
    except ValueError as exc:
        raise SessionError(str(exc)) from exc
    claims = verify_claims(claims_doc.claims, scan.evidence)
    summary = summarize_claims(
        claims,
        section_count=len(sections.sections),
        evidence_count=len(scan.evidence),
    )
    write_claims_json(output, claims, summary)
    report = VerificationReport(summary=summary, claims=claims)
    write_json(output / VERIFICATION, report)
    write_case_study(output, scan.repo, sections.sections, scan.evidence, summary, claims)
    write_defense(output, scan.repo, defense.questions)
    manifest.status = "attested"
    write_manifest(
        output / MANIFEST,
        manifest,
        [EVIDENCE, SECTIONS, CLAIMS, VERIFICATION, DEFENSE_JSON, CASE_STUDY, DEFENSE],
    )
    return report


def export_session(output_dir: Path) -> Path:
    output = output_dir.expanduser().resolve()
    scan, sections, claims_doc, defense, manifest = load_session(output)
    summary = claims_doc.summary
    write_sections_json(output, sections.sections)
    write_claims_json(output, claims_doc.claims, summary)
    write_verification_json(output, claims_doc.claims, summary)
    write_defense_json(output, defense.questions)
    write_case_study(output, scan.repo, sections.sections, scan.evidence, summary, claims_doc.claims)
    write_defense(output, scan.repo, defense.questions)
    manifest.status = "exported"
    write_manifest(
        output / MANIFEST,
        manifest,
        [EVIDENCE, SECTIONS, CLAIMS, VERIFICATION, DEFENSE_JSON, CASE_STUDY, DEFENSE],
    )
    return output
