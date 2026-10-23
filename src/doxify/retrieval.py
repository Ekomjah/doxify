from __future__ import annotations

from .models import EvidenceCard, SectionSpec
from .text import content_tokens

SECTION_SPECS: list[SectionSpec] = [
    SectionSpec(
        id="snapshot",
        title="Snapshot",
        goal="Summarize what the project is, its stack, size, and timeline.",
        keywords=["identity", "stack", "languages", "commits", "files", "readme"],
    ),
    SectionSpec(
        id="problem",
        title="The problem",
        goal="Explain the problem this project addresses and why it matters.",
        keywords=["problem", "purpose", "readme", "description", "context"],
    ),
    SectionSpec(
        id="approach",
        title="The approach",
        goal="Describe the main technical approach and major components.",
        keywords=["architecture", "structure", "approach", "tools", "models", "routes", "services"],
    ),
    SectionSpec(
        id="hard_part",
        title="The hard part",
        goal="Explain the hardest technical problem and how it was handled.",
        keywords=["match", "filter", "scoring", "validation", "refactor", "fix"],
    ),
    SectionSpec(
        id="shipped",
        title="What shipped",
        goal="Describe the concrete features, tools, routes, and tests that exist.",
        keywords=["tools", "features", "tests", "smoke", "routes", "models", "records"],
    ),
    SectionSpec(
        id="reflection",
        title="What I would change",
        goal="Name honest gaps, missing documentation, and sensible next steps.",
        keywords=["missing", "readme", "tests", "gap", "next", "deploy"],
    ),
]


def retrieve_evidence(
    cards: list[EvidenceCard],
    spec: SectionSpec,
    *,
    limit: int = 3,
) -> list[EvidenceCard]:
    if not cards:
        return []

    intent = content_tokens(
        " ".join([spec.title, spec.goal, *spec.keywords])
    )
    scored: list[tuple[float, int, EvidenceCard]] = []
    for index, card in enumerate(cards):
        card_tokens = content_tokens(
            " ".join([card.title, card.text, card.quote or "", *card.keywords])
        )
        overlap = len(intent & card_tokens)
        keyword_hits = sum(
            1 for keyword in spec.keywords if content_tokens(keyword) & card_tokens
        )
        score = float(overlap + keyword_hits * 2)
        if card.kind.value in {"metric", "stack"}:
            score += 0.5
        if card.kind.value == "commit":
            score -= 1.5
        if spec.id == "shipped" and any(
            key in card.meta
            for key in ("tool_count", "model_count", "route_count", "record_count", "test_count")
        ):
            score += 4
        if score > 0:
            scored.append((score, index, card))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [card for _, _, card in scored[:limit]]

    if len(selected) < min(3, len(cards)):
        selected_ids = {card.id for card in selected}
        for card in cards:
            if card.id not in selected_ids:
                selected.append(card)
                selected_ids.add(card.id)
            if len(selected) >= min(3, len(cards)):
                break

    return selected
