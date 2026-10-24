from __future__ import annotations

from pathlib import Path

from .models import (
    CaseStudySection,
    Claim,
    ClaimsDocument,
    ClaimStatus,
    CompileSummary,
    DefenseDocument,
    DefenseQuestion,
    EvidenceCard,
    RepoSummary,
    SectionsDocument,
    VerificationReport,
)
from .session import write_json, write_text


def write_case_study(
    output: Path,
    repo: RepoSummary,
    sections: list[CaseStudySection],
    evidence: list[EvidenceCard],
    summary: CompileSummary,
    claims: list[Claim] | None = None,
) -> Path:
    path = output / "case-study.md"
    lines = [
        f"# {repo.name}: an evidence-backed case study",
        "",
        "> Compiled with Doxify. Citations point to the evidence appendix.",
        "> Unverified statements are marked [needs evidence]; author context is marked [attested].",
        "",
    ]
    claims_by_id = {claim.id: claim for claim in (claims or [])}
    for section in sections:
        body = section.body.strip()
        for sentence in section.sentences:
            claim = claims_by_id.get(sentence.claim_id)
            if claim is None or claim.status == ClaimStatus.VERIFIED:
                continue
            if claim.status == ClaimStatus.ATTESTED:
                marker = "[attested]"
            elif claim.status == ClaimStatus.REJECTED:
                marker = "[rejected]"
            elif claim.text.rstrip().endswith("?"):
                continue
            else:
                marker = "[needs evidence]"
            body = body.replace(claim.text, f"{claim.text} {marker}", 1)
        lines.extend([f"## {section.title}", "", body, ""])

    lines.extend(["## Verification summary", ""])
    lines.append(
        f"- {summary.verified} verified, {summary.attested} attested, "
        f"{summary.needs_evidence} needing evidence, {summary.rejected} rejected."
    )
    lines.extend(
        [
            "",
            "> Claims marked ATTESTED are based on the author's statement, not code evidence.",
            "",
            "## Evidence appendix",
            "",
        ]
    )
    for card in evidence:
        refs = _format_refs(card)
        suffix = f" ({refs})" if refs else ""
        lines.append(f"- **{card.id}** — {card.title}. {card.text}{suffix}")
    write_text(path, "\n".join(lines))
    return path


def write_defense(
    output: Path,
    repo: RepoSummary,
    questions: list[DefenseQuestion],
) -> Path:
    path = output / "defense.md"
    lines = [f"# Interview defense pack: {repo.name}", ""]
    for question in questions:
        lines.extend(
            [
                f"## {question.id}. {question.question}",
                "",
                f"**Why this comes up:** {question.why_asked}",
                "",
                "**Answer outline:**",
            ]
        )
        if question.answer_outline:
            lines.extend(f"- {item}" for item in question.answer_outline)
        else:
            lines.append("- [GAP] Add a grounded answer from the evidence.")
        lines.extend(
            [
                "",
                f"**Evidence:** {', '.join(question.evidence_ids) if question.evidence_ids else 'none'}",
            ]
        )
        if question.gap:
            lines.append(f"**Gap:** {question.gap}")
        lines.append("")
    write_text(path, "\n".join(lines))
    return path


def write_claims_json(output: Path, claims: list[Claim], summary: CompileSummary) -> Path:
    path = output / "claims.json"
    write_json(path, ClaimsDocument(summary=summary, claims=claims))
    return path


def write_verification_json(
    output: Path, claims: list[Claim], summary: CompileSummary
) -> Path:
    path = output / "verification.json"
    write_json(
        path,
        VerificationReport(summary=summary, claims=claims),
    )
    return path


def write_sections_json(output: Path, sections: list[CaseStudySection]) -> Path:
    path = output / "sections.json"
    write_json(path, SectionsDocument(sections=sections))
    return path


def write_defense_json(output: Path, questions: list[DefenseQuestion]) -> Path:
    path = output / "defense.json"
    write_json(path, DefenseDocument(questions=questions))
    return path


def write_evidence_json(
    output: Path, repo: RepoSummary, evidence: list[EvidenceCard]
) -> Path:
    path = output / "evidence.json"
    write_json(
        path,
        {
            "schema_version": "1.0",
            "repo": repo.model_dump(mode="json"),
            "evidence": [card.model_dump(mode="json") for card in evidence],
        },
    )
    return path


def _format_refs(card: EvidenceCard) -> str:
    refs: list[str] = []
    for ref in card.refs:
        if ref.path:
            refs.append(ref.path + (f":{ref.lines}" if ref.lines else ""))
        elif ref.commit:
            refs.append(f"commit {ref.commit}")
    return ", ".join(refs)
