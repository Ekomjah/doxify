from __future__ import annotations

import re

from .errors import ModelError
from .models import CaseStudySection, Claim, ClaimStatus, DefenseQuestion, EvidenceCard
from .ollama_client import OllamaClient
from .prompts import defense_messages

QUESTION_RE = re.compile(r"^Q:\s*(.+)$", re.MULTILINE)
EVIDENCE_RE = re.compile(r"^EVIDENCE:\s*(.+)$", re.MULTILINE)
WHY_RE = re.compile(r"^WHY:\s*(.+)$", re.MULTILINE)
GAP_RE = re.compile(r"^GAP:\s*(.+)$", re.MULTILINE)


def build_defense(
    client: OllamaClient | None,
    sections: list[CaseStudySection],
    claims: list[Claim],
    evidence: list[EvidenceCard],
    *,
    repo_name: str,
    use_model: bool = True,
) -> list[DefenseQuestion]:
    usable = [
        claim
        for claim in claims
        if claim.status in {ClaimStatus.VERIFIED, ClaimStatus.ATTESTED}
    ]
    if not usable:
        return []

    if use_model and client is not None:
        used_ids = {
            evidence_id for claim in usable[:10] for evidence_id in claim.evidence_ids
        }
        defense_evidence = [card for card in evidence if card.id in used_ids][:10]
        try:
            response = client.chat(
                defense_messages(
                    repo_name,
                    [
                        {
                            "id": claim.id,
                            "text": claim.text,
                            "evidence_ids": claim.evidence_ids,
                        }
                        for claim in usable[:10]
                    ],
                    defense_evidence,
                ),
                num_predict=600,
            )
            questions = _parse(response, evidence)
            if questions:
                return questions
        except ModelError:
            pass

    return _fallback(sections, usable)


def _parse(response: str, evidence: list[EvidenceCard]) -> list[DefenseQuestion]:
    valid_ids = {card.id for card in evidence}
    blocks = re.split(r"(?=^Q:\s)", response.strip(), flags=re.MULTILINE)
    questions: list[DefenseQuestion] = []
    for block in blocks:
        question_match = QUESTION_RE.search(block)
        if not question_match:
            continue
        why_match = WHY_RE.search(block)
        evidence_match = EVIDENCE_RE.search(block)
        gap_match = GAP_RE.search(block)

        outline: list[str] = []
        after_why = block
        if why_match:
            after_why = block[why_match.end() :]
        for raw_line in after_why.splitlines():
            line = raw_line.strip()
            if line.startswith(("-", "*")) and not line.lower().startswith(("why:", "evidence:", "gap:")):
                outline.append(line[1:].strip())

        evidence_ids = []
        if evidence_match:
            evidence_ids = [
                value.strip()
                for value in re.findall(r"E\d+", evidence_match.group(1))
                if value.strip() in valid_ids
            ]

        gap = gap_match.group(1).strip() if gap_match else None
        if gap and gap.upper() == "NONE":
            gap = None

        questions.append(
            DefenseQuestion(
                id=f"Q{len(questions) + 1}",
                question=question_match.group(1).strip(),
                why_asked=why_match.group(1).strip() if why_match else "Tests technical understanding.",
                answer_outline=outline[:3],
                evidence_ids=list(dict.fromkeys(evidence_ids)),
                gap=gap,
            )
        )
        if len(questions) >= 6:
            break
    return questions


def _fallback(sections: list[CaseStudySection], claims: list[Claim]) -> list[DefenseQuestion]:
    questions_by_section = {
        "snapshot": (
            "What does this project actually do, and which evidence proves it?",
            "Interviewers want a concrete summary rather than a pitch.",
        ),
        "problem": (
            "Why does this project exist, and what problem does it solve?",
            "Interviewers test whether you understand the motivation.",
        ),
        "approach": (
            "Why did you structure the implementation this way?",
            "Interviewers want to hear the design reasoning behind the code.",
        ),
        "hard_part": (
            "What was the hardest technical problem, and how did you handle it?",
            "Interviewers probe for depth beyond the happy path.",
        ),
        "shipped": (
            "Which features actually shipped, and how can you prove it?",
            "Interviewers distinguish working software from intentions.",
        ),
        "reflection": (
            "What would you change before relying on this in production?",
            "Interviewers test self-awareness and engineering judgment.",
        ),
    }
    claims_by_section: dict[str, list[Claim]] = {}
    for claim in claims:
        claims_by_section.setdefault(claim.section_id, []).append(claim)

    questions: list[DefenseQuestion] = []
    for section in sections:
        section_claims = claims_by_section.get(section.id, [])
        if not section_claims:
            continue
        question, why = questions_by_section.get(
            section.id,
            (
                f"What is the most important decision in the {section.title.lower()} section?",
                "Interviewers test whether the author can defend the work.",
            ),
        )
        outline = [claim.text for claim in section_claims[:3]]
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for claim in section_claims[:3]
                for evidence_id in claim.evidence_ids
            )
        )
        questions.append(
            DefenseQuestion(
                id=f"Q{len(questions) + 1}",
                question=question,
                why_asked=why,
                answer_outline=outline,
                evidence_ids=evidence_ids,
            )
        )
        if len(questions) >= 6:
            break
    return questions
