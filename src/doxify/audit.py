from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .claims import CITATION_RE, extract_claims
from .errors import SessionError
from .models import Claim, ClaimStatus, CompileSummary, EvidenceCard
from .readme import GENERATED_MARKER
from .verifier import summarize_claims, verify_claims

EVIDENCE_MARKER_RE = re.compile(
    r"<!--\s*doxify-evidence:\s*([^>]*?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)
ATTESTED_MARKER_RE = re.compile(
    r"<!--\s*doxify-attested:\s*([^>]*?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
VISIBLE_MARKER_RE = re.compile(r"\[(needs evidence|rejected|GAP)\]", re.IGNORECASE)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
CASE_STUDY_SKIP_TITLES = {"verification summary", "evidence appendix"}


@dataclass
class ArtifactSection:
    title: str
    evidence_ids: list[str] = field(default_factory=list)
    attested: bool = False
    attestation: str | None = None
    claims: list[Claim] = field(default_factory=list)
    visible_markers: list[str] = field(default_factory=list)


@dataclass
class ArtifactReport:
    path: Path
    mode: str
    sections: list[ArtifactSection]
    claims: list[Claim]
    summary: CompileSummary
    unmarked_sections: list[str] = field(default_factory=list)


def parse_fail_on(value: str) -> set[ClaimStatus]:
    if not value or value.strip().lower() in {"", "none"}:
        return set()

    requested = {item.strip().lower() for item in value.split(",") if item.strip()}
    unknown = requested - {status.value for status in ClaimStatus}
    if unknown:
        choices = ", ".join(status.value for status in ClaimStatus)
        raise ValueError(f"Unknown failure status: {', '.join(sorted(unknown))}. Choose from {choices}.")
    return {ClaimStatus(item) for item in requested}


def failing_claims(claims: Iterable[Claim], fail_on: set[ClaimStatus]) -> list[Claim]:
    return [claim for claim in claims if claim.status in fail_on]


def audit_artifact(
    path: Path,
    evidence: list[EvidenceCard],
    *,
    strict: bool = True,
) -> ArtifactReport:
    artifact = path.expanduser().resolve()
    try:
        text = artifact.read_text(encoding="utf-8")
    except OSError as exc:
        raise SessionError(f"Could not read artifact: {artifact}") from exc

    mode = _detect_mode(text)
    sections: list[ArtifactSection] = []
    extracted: list[Claim] = []
    synthetic: list[tuple[str, str, str, ClaimStatus]] = []
    unmarked: list[str] = []

    for title, body in _split_sections(text):
        if mode == "case_study" and title == "preamble":
            continue
        if mode == "case_study" and title.lower() in CASE_STUDY_SKIP_TITLES:
            continue

        evidence_match = EVIDENCE_MARKER_RE.search(body)
        attested_match = ATTESTED_MARKER_RE.search(body)
        evidence_ids = _marker_ids(evidence_match.group(1)) if evidence_match else []
        section_id = _section_id(title)
        visible = [
            match.group(1).lower()
            for match in VISIBLE_MARKER_RE.finditer(_visible_text(body))
        ]
        section = ArtifactSection(
            title=title,
            evidence_ids=evidence_ids,
            attested=bool(attested_match) and not evidence_ids,
            attestation=(
                attested_match.group(1).strip()
                if attested_match is not None
                else None
            ),
            visible_markers=visible,
        )

        if mode == "case_study":
            claims = extract_claims(
                section_id,
                _visible_text(body),
                start_index=len(extracted) + 1,
            )
            section.claims = claims
            extracted.extend(claims)
        elif evidence_ids:
            claims = extract_claims(
                section_id,
                _visible_text(body),
                start_index=len(extracted) + 1,
            )
            for claim in claims:
                if not claim.evidence_ids:
                    claim.evidence_ids = evidence_ids
            section.claims = claims
            extracted.extend(claims)
        elif section.attested:
            reason = section.attestation or "Author-attested section."
            synthetic.append(
                (
                    section_id,
                    f"{title} (author-attested)",
                    f"Author attestation; not verified from repository evidence. {reason}".strip(),
                    ClaimStatus.ATTESTED,
                )
            )
        else:
            unmarked.append(title)
            if strict:
                synthetic.append(
                    (
                        section_id,
                        f"{title} (unmarked)",
                        "Section has no doxify-evidence or doxify-attested marker.",
                        ClaimStatus.NEEDS_EVIDENCE,
                    )
                )

        for marker in visible:
            status = ClaimStatus.REJECTED if marker == "rejected" else ClaimStatus.NEEDS_EVIDENCE
            synthetic.append(
                (
                    section_id,
                    f"{title} contains visible marker [{marker}]",
                    "The artifact still contains an unresolved claim marker.",
                    status,
                )
            )

        sections.append(section)

    verified = verify_claims(extracted, evidence)
    claims = list(verified)
    for section_id, text_value, reason, status in synthetic:
        claims.append(
            Claim(
                id=f"S{len(claims) + 1}",
                text=text_value,
                section_id=section_id,
                status=status,
                reason=reason,
            )
        )

    summary = summarize_claims(
        claims,
        section_count=len(sections),
        evidence_count=len(evidence),
    )
    return ArtifactReport(
        path=artifact,
        mode=mode,
        sections=sections,
        claims=claims,
        summary=summary,
        unmarked_sections=unmarked,
    )


def _detect_mode(text: str) -> str:
    if (
        GENERATED_MARKER in text
        or EVIDENCE_MARKER_RE.search(text)
        or ATTESTED_MARKER_RE.search(text)
    ):
        return "readme"
    if VISIBLE_MARKER_RE.search(text) or CITATION_RE.search(text):
        return "case_study"
    raise SessionError(
        "Artifact has no Doxify evidence markers or citations. "
        "Mark verified sections with <!-- doxify-evidence: E1 E2 --> "
        "or author-owned sections with <!-- doxify-attested: reason -->."
    )


def _split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title = "preamble"
    body: list[str] = []
    in_fence = False

    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            body.append(line)
            continue
        match = None if in_fence else SECTION_RE.match(line)
        if match is None:
            body.append(line)
            continue
        if body or title != "preamble":
            sections.append((title, "\n".join(body)))
        title = match.group(1).strip()
        body = []

    if body or title != "preamble":
        sections.append((title, "\n".join(body)))
    return sections


def _visible_text(text: str) -> str:
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return COMMENT_RE.sub("", "\n".join(lines))


def _marker_ids(value: str) -> list[str]:
    return list(dict.fromkeys(part for part in re.split(r"[\s,]+", value.strip()) if part))


def _section_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "preamble"
