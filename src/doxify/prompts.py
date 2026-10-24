from __future__ import annotations

from .models import EvidenceCard, SectionSpec

SYSTEM_PROMPT = """You are a technical portfolio editor working inside a compiler.

You will receive evidence cards and a section goal. You may only use the
evidence cards provided. You must cite evidence for every sentence using
tokens like [E1] or [E2][E5].

Rules:
- Never invent a number, user count, performance result, team size, award,
  deployment status, or security claim.
- Never claim tests pass, a project is production-ready, or a project is
  deployed unless an evidence card explicitly says so.
- If the evidence is insufficient, write a short gap sentence marked [GAP]
  followed by a specific question for the author.
- Prefer concrete, plain language over marketing language.
- Do not use phrases like "revolutionary", "seamless", "cutting-edge", or
  "game-changing".
- Write in first person when describing the developer's work.
- Keep sentences short.
- Do not start with "Okay", "Here is", "Certainly", or any conversational
  preamble. Start directly with the first factual sentence.
- Put each citation token immediately before the final period of the sentence.
- Write exactly two short paragraphs.
"""


def format_cards(cards: list[EvidenceCard]) -> str:
    blocks: list[str] = []
    for card in cards:
        refs = []
        for ref in card.refs:
            if ref.path:
                refs.append(ref.path + (f":{ref.lines}" if ref.lines else ""))
            elif ref.commit:
                refs.append(f"commit {ref.commit}")
        block = [
            f"[{card.id}] ({card.kind.value}) {card.title}",
            f"Fact: {card.text}",
        ]
        if card.quote:
            block.append(f"Quote: {card.quote[:350]}")
        if refs:
            block.append(f"Refs: {', '.join(refs)}")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def section_messages(
    spec: SectionSpec,
    cards: list[EvidenceCard],
    *,
    repo_name: str,
    role: str | None = None,
    draft: str | None = None,
) -> list[dict[str, str]]:
    user_parts = [
        f"Project: {repo_name}",
        f"Section: {spec.title}",
        f"Goal: {spec.goal}",
    ]
    if role:
        user_parts.append(f"Target role: {role}")
    if draft:
        user_parts.append(
            "Author notes (context only; do not treat as code evidence):\n"
            + draft.strip()[:4000]
        )
    user_parts.append("Evidence cards:\n" + format_cards(cards))
    user_parts.append(
        "Write exactly 2 short paragraphs for this section. "
        "Every sentence must end with one or more citation tokens. "
        "Do not write any preamble or heading. Start immediately with the content. "
        "If a sentence cannot be supported, write a [GAP] question instead. "
        "Return only the section text."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def repair_messages(
    spec: SectionSpec,
    cards: list[EvidenceCard],
    previous: str,
    problems: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Section: {spec.title}\n"
                f"Goal: {spec.goal}\n\n"
                f"The previous output had these problems:\n{problems}\n\n"
                "Rewrite the section using only the evidence cards below.\n"
                "Every sentence must cite evidence. Do not add new claims.\n\n"
                f"Evidence cards:\n{format_cards(cards)}\n\n"
                f"Previous output:\n{previous[:3000]}"
            ),
        },
    ]


SCOUT_SYSTEM_PROMPT = """You are a release-note analyst working inside a compiler.

Your job is to extract breaking changes from release notes, not to summarize
the release or recommend an upgrade.

Rules:
- Only include changes that can break existing code or require a migration.
- Every change must include a verbatim quote copied from the release notes.
- Every change must include at least one exact API, identifier, package path,
  or config key affected by the change.
- Do not invent APIs, versions, migration steps, or quotes.
- Do not include new features, bug fixes, performance improvements, or
  deprecations unless they require a code change.
- Ignore changes outside the requested package and version range.
- Return at most 8 changes. Prefer changes that affect named APIs.
- Keep each quote under 220 characters.
- If there are no breaking changes, return {"changes": []}.
- Return JSON only. Do not use Markdown fences or add an explanation.

Return a JSON object with one key, "changes". Its value must be an array of
strings. Each string must be one contiguous quote copied from the release
notes. Do not wrap a quote in another object, rewrite it, or combine separate
bullets. Return {"changes": []} when there are no breaking changes. Do not copy
instructions or examples into the output.
"""


def scout_batch_messages(
    package: str,
    from_version: str,
    to_version: str,
    excerpt: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Package: {package}\n"
                f"Upgrade: {from_version} -> {to_version}\n\n"
                "The excerpts are separated by release headers. Do not copy the "
                "headers into a quote.\n\n"
                "Release notes excerpts:\n"
                f"{excerpt[:11000]}\n\n"
                "Return only breaking-change lines that affect this upgrade. "
                "Copy each line exactly from the excerpt. Return JSON only."
            ),
        },
    ]


def defense_messages(
    repo_name: str,
    claims: list[dict[str, str]],
    evidence: list[EvidenceCard],
) -> list[dict[str, str]]:
    claim_text = "\n".join(
        f"- {claim['id']}: {claim['text']} [{', '.join(claim['evidence_ids'])}]"
        for claim in claims
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Project: {repo_name}\n\n"
                "Using only the verified claims and evidence below, write 4-6 "
                "technical interview questions.\n\n"
                f"Claims:\n{claim_text}\n\n"
                f"Evidence:\n{format_cards(evidence)}\n\n"
                "Use exactly this format for each question:\n"
                "Q: <question>\n"
                "WHY: <why an interviewer asks it>\n"
                "- <answer outline bullet>\n"
                "- <answer outline bullet>\n"
                "- <answer outline bullet>\n"
                "EVIDENCE: E1, E2\n"
                "GAP: <missing information, or NONE>\n\n"
                "Do not invent outcomes or metrics. Return only the questions."
            ),
        },
    ]
