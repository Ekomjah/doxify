from __future__ import annotations

import re

from .models import Claim, ClaimStatus
from .text import compact_whitespace

CITATION_RE = re.compile(r"\[(E\d+)\]")
GAP_RE = re.compile(r"\[GAP\]", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])((?:\s*\[E\d+\])*)\s+(?=[A-Z0-9\"“']|\[GAP\])")
PREAMBLE_RE = re.compile(
    r"^(?:okay|sure|certainly|of course|here(?:['\u2019]s| is)|based on|the following)\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^\s*#{1,6}\s+")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def extract_claims(section_id: str, body: str, *, start_index: int = 1) -> list[Claim]:
    claims: list[Claim] = []
    for paragraph in _paragraphs(body):
        for sentence in _sentences(paragraph):
            text = compact_whitespace(sentence)
            if not text or _is_preamble(text):
                continue
            evidence_ids = list(dict.fromkeys(CITATION_RE.findall(text)))
            is_gap = bool(GAP_RE.search(text))
            clean_text = compact_whitespace(GAP_RE.sub("", text))
            status = ClaimStatus.NEEDS_EVIDENCE
            gap_question = None
            if is_gap or not evidence_ids:
                gap_question = _gap_question(clean_text)

            claims.append(
                Claim(
                    id=f"C{start_index + len(claims)}",
                    text=clean_text,
                    section_id=section_id,
                    evidence_ids=evidence_ids,
                    status=status,
                    gap_question=gap_question,
                )
            )
    return claims


def parse_citations(text: str) -> list[str]:
    return list(dict.fromkeys(CITATION_RE.findall(text)))


def _paragraphs(body: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in body.splitlines():
        line = HEADING_RE.sub("", raw_line)
        line = BULLET_RE.sub("", line).strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _sentences(paragraph: str) -> list[str]:
    chunks = SENTENCE_SPLIT_RE.split(paragraph)
    sentences: list[str] = []
    current = chunks[0] if chunks else ""
    for index in range(1, len(chunks) - 1, 2):
        citations = chunks[index].strip()
        if citations:
            current = f"{current} {citations}"
        if current.strip():
            sentences.append(current.strip())
        current = chunks[index + 1]
    if current.strip():
        sentences.append(current.strip())
    return sentences


def _is_preamble(text: str) -> bool:
    if CITATION_RE.search(text) or GAP_RE.search(text):
        return False
    return bool(PREAMBLE_RE.search(text.lstrip("\"“”'")))


def _gap_question(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ("deployed", "production", "live")):
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
