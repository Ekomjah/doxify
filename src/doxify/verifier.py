from __future__ import annotations

import re

from .models import Claim, ClaimStatus, CompileSummary, EvidenceCard
from .text import content_tokens

NUMBER_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?![\w])")
CODE_TOKEN_RE = re.compile(r"`([^`]+)`|\b([a-z]+[A-Z][A-Za-z0-9_]*)\b")

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "oauth",
        re.compile(r"\boauth\b", re.IGNORECASE),
        "The cited evidence does not contain an OAuth implementation.",
    ),
    (
        "tests pass",
        re.compile(r"\b(?:all\s+)?tests?\s+(?:pass|passed|passing)\b", re.IGNORECASE),
        "Doxify did not run the project's tests.",
    ),
    (
        "deployment",
        re.compile(
            r"\b(?:deployed|in production|production-ready|live at|shipped to users)\b",
            re.IGNORECASE,
        ),
        "The cited evidence does not prove deployment.",
    ),
    (
        "users",
        re.compile(r"\b(?:thousands|millions|hundreds)\s+of\s+(?:users|customers)\b", re.IGNORECASE),
        "The cited evidence does not include a verifiable user count.",
    ),
    (
        "performance",
        re.compile(
            r"\b(?:reduced|improved|increased)\b.{0,30}\b(?:latency|performance|speed|by\s+\d+)"
            r"|\b(?:performance|latency|throughput|scalab\w*)\b"
            r"|\boptimi[sz]ed?\s+(?:database|query|queries)\b",
            re.IGNORECASE,
        ),
        "The cited evidence does not include a performance measurement.",
    ),
    (
        "schema validation",
        re.compile(r"\bschema\s+validation\b", re.IGNORECASE),
        "The cited evidence does not show schema validation.",
    ),
    (
        "async operations",
        re.compile(r"\basynchronous\s+operations?\b", re.IGNORECASE),
        "The cited evidence does not show asynchronous operations.",
    ),
    (
        "team size",
        re.compile(r"\b(?:led|managed)\s+(?:a\s+)?team\b|\bteam\s+of\s+\w+", re.IGNORECASE),
        "Code and git history cannot prove team size or leadership.",
    ),
    (
        "awards",
        re.compile(r"\b(?:award-winning|won\s+an?\s+award|awarded)\b", re.IGNORECASE),
        "The cited evidence does not include an award.",
    ),
    (
        "first or only",
        re.compile(r"\b(?:first|only)\b.{0,30}\b(?:tool|platform|project|solution)\b", re.IGNORECASE),
        "The cited evidence does not prove a first or only claim.",
    ),
]


def verify_claims(claims: list[Claim], evidence: list[EvidenceCard]) -> list[Claim]:
    evidence_by_id = {card.id: card for card in evidence}
    record_count = _max_meta_int(evidence, "record_count")

    verified: list[Claim] = []
    for claim in claims:
        if claim.status == ClaimStatus.ATTESTED or claim.user_answer:
            claim.status = ClaimStatus.ATTESTED
            claim.reason = "Author attestation; not verified from repository evidence."
            claim.gap_question = None
            verified.append(claim)
            continue
        verified.append(
            _verify_one(
                claim,
                evidence_by_id,
                record_count=record_count,
            )
        )
    return verified


def summarize_claims(
    claims: list[Claim], *, section_count: int = 0, evidence_count: int = 0
) -> CompileSummary:
    summary = CompileSummary(sections=section_count, evidence_cards=evidence_count)
    for claim in claims:
        if claim.status == ClaimStatus.VERIFIED:
            summary.verified += 1
        elif claim.status == ClaimStatus.ATTESTED:
            summary.attested += 1
        elif claim.status == ClaimStatus.REJECTED:
            summary.rejected += 1
        else:
            summary.needs_evidence += 1
    return summary


def attest_claim(claims: list[Claim], claim_id: str, answer: str) -> Claim:
    for claim in claims:
        if claim.id == claim_id:
            claim.user_answer = answer
            claim.status = ClaimStatus.ATTESTED
            claim.reason = "Author attestation; not verified from repository evidence."
            claim.gap_question = None
            return claim
    raise ValueError(f"Unknown claim: {claim_id}")


def _verify_one(
    claim: Claim,
    evidence_by_id: dict[str, EvidenceCard],
    *,
    record_count: int | None,
) -> Claim:
    lower = claim.text.lower()
    if not claim.evidence_ids:
        claim.status = ClaimStatus.NEEDS_EVIDENCE
        claim.reason = "No citation token was found."
        return claim

    cited = [evidence_by_id.get(evidence_id) for evidence_id in claim.evidence_ids]
    unknown = [evidence_id for evidence_id, card in zip(claim.evidence_ids, cited, strict=False) if card is None]
    if unknown:
        claim.status = ClaimStatus.REJECTED
        claim.reason = f"Unknown evidence citation(s): {', '.join(unknown)}."
        return claim

    cards = [card for card in cited if card is not None]
    evidence_text = " ".join(
        f"{card.title} {card.text} {card.quote or ''} {' '.join(map(str, card.meta.values()))}"
        for card in cards
    )
    evidence_lower = evidence_text.lower()

    forbidden = _forbidden_check(lower, evidence_lower)
    if forbidden is not None:
        status, reason = forbidden
        claim.status = status
        claim.reason = reason
        if status == ClaimStatus.NEEDS_EVIDENCE:
            claim.gap_question = _gap_for(claim.text)
        return claim

    numbers = [normalize_number(value) for value in NUMBER_RE.findall(claim.text)]
    evidence_numbers = {
        normalize_number(value) for value in NUMBER_RE.findall(evidence_text)
    }
    for number in numbers:
        if number in evidence_numbers:
            continue
        if (
            record_count is not None
            and number.isdigit()
            and int(number) > record_count
            and any(word in lower for word in ("scholarship", "record", "entry", "entries"))
        ):
            claim.status = ClaimStatus.REJECTED
            claim.reason = (
                f"Numeric contradiction: the repository contains {record_count} "
                f"records, not {number}."
            )
            return claim
        claim.status = ClaimStatus.NEEDS_EVIDENCE
        claim.reason = f"Number {number} is not supported by the cited evidence."
        claim.gap_question = _gap_for(claim.text)
        return claim

    missing_identifier = _missing_identifier(claim.text, evidence_text)
    if missing_identifier:
        claim.status = ClaimStatus.NEEDS_EVIDENCE
        claim.reason = f"Identifier {missing_identifier} is not present in the cited evidence."
        claim.gap_question = _gap_for(claim.text)
        return claim

    claim_tokens = content_tokens(claim.text)
    evidence_tokens = content_tokens(evidence_text)
    overlap = claim_tokens & evidence_tokens
    title_tokens = set()
    for card in cards:
        title_tokens |= content_tokens(card.title)
        for keyword in card.keywords:
            title_tokens |= content_tokens(keyword)
    minimum_overlap = 1 if len(claim_tokens) <= 4 else 2
    if len(overlap) < minimum_overlap and not (overlap & title_tokens):
        claim.status = ClaimStatus.NEEDS_EVIDENCE
        claim.reason = "Citation does not overlap with the claim's key terms."
        claim.gap_question = _gap_for(claim.text)
        return claim

    claim.status = ClaimStatus.VERIFIED
    claim.reason = "Supported by cited repository evidence."
    claim.gap_question = None
    return claim


def _forbidden_check(
    claim_lower: str, evidence_lower: str
) -> tuple[ClaimStatus, str] | None:
    for name, pattern, reason in FORBIDDEN_PATTERNS:
        if not pattern.search(claim_lower):
            continue
        if name == "oauth":
            if "oauth" not in evidence_lower:
                return ClaimStatus.REJECTED, reason
            return ClaimStatus.NEEDS_EVIDENCE, reason
        if name == "tests pass":
            if not re.search(r"\b(?:tests?|suite)\b.{0,40}\b(?:pass|passed|passing)\b", evidence_lower):
                return ClaimStatus.NEEDS_EVIDENCE, reason
            return ClaimStatus.NEEDS_EVIDENCE, reason
        if name == "deployment":
            if not re.search(r"\b(?:deploy|docker|fly|render|vercel|netlify|procfile)\b", evidence_lower):
                return ClaimStatus.NEEDS_EVIDENCE, reason
            return ClaimStatus.NEEDS_EVIDENCE, reason
        return ClaimStatus.NEEDS_EVIDENCE, reason
    return None


def _missing_identifier(claim_text: str, evidence_text: str) -> str | None:
    identifiers: list[str] = []
    for match in CODE_TOKEN_RE.finditer(claim_text):
        value = (match.group(1) or match.group(2) or "").strip()
        if value and value.lower() not in {"e1", "e2", "e3"}:
            identifiers.append(value)
    evidence_lower = evidence_text.lower()
    for identifier in identifiers:
        if identifier.lower() not in evidence_lower:
            return identifier
    return None


def _max_meta_int(evidence: list[EvidenceCard], key: str) -> int | None:
    values: list[int] = []
    for card in evidence:
        value = card.meta.get(key)
        if isinstance(value, int):
            values.append(value)
    return max(values) if values else None


def normalize_number(value: str) -> str:
    return value.replace(",", "")


def _gap_for(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ("deploy", "production", "live")):
        return "Was this deployed? Where, and what evidence can you point to?"
    if any(word in lower for word in ("user", "customer", "people")):
        return "Do you have a verifiable user count or outcome for this?"
    if any(word in lower for word in ("test", "passed", "coverage")):
        return "Did you run the tests? What was the result?"
    if any(word in lower for word in ("team", "led", "managed")):
        return "What was your specific role and team context?"
    if any(word in lower for word in ("performance", "latency", "faster", "reduced")):
        return "Do you have a measurement or benchmark that supports this?"
    return f"What evidence supports this sentence: {text[:140]}?"
