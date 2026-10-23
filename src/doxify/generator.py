from __future__ import annotations

import re
from dataclasses import dataclass

from .claims import CITATION_RE, GAP_RE
from .errors import GenerationError, ModelError
from .models import EvidenceCard, SectionSpec
from .ollama_client import OllamaClient
from .prompts import repair_messages, section_messages


@dataclass
class GeneratedSection:
    body: str
    fallback_used: bool
    error: str | None = None


def generate_section(
    client: OllamaClient,
    spec: SectionSpec,
    cards: list[EvidenceCard],
    *,
    repo_name: str,
    role: str | None = None,
    draft: str | None = None,
) -> GeneratedSection:
    messages = section_messages(
        spec,
        cards,
        repo_name=repo_name,
        role=role,
        draft=draft,
    )
    try:
        body = _clean(client.chat(messages, num_predict=260))
        if not _valid(body):
            body = _clean(
                client.chat(
                    repair_messages(
                        spec,
                        cards,
                        body,
                        "The output did not include a citation token or a [GAP] marker.",
                    ),
                    num_predict=260,
                )
            )
        if _valid(body):
            return GeneratedSection(body=body, fallback_used=False)
        raise GenerationError("The model returned text without citations.")
    except (ModelError, GenerationError) as exc:
        return GeneratedSection(
            body=template_section(spec, cards),
            fallback_used=True,
            error=str(exc),
        )


def template_section(spec: SectionSpec, cards: list[EvidenceCard]) -> str:
    usable = [card for card in cards if card.text]
    if not usable:
        return (
            f"The repository does not contain enough evidence for this section. "
            f"[GAP] What would you add to the {spec.title.lower()} section?"
        )

    if spec.id == "snapshot":
        return "\n\n".join(f"{card.text} [{card.id}]" for card in usable)

    if spec.id in {"problem", "reflection"}:
        sentences = [f"{card.text} [{card.id}]" for card in usable]
        if spec.id == "problem":
            sentences.append(
                "[GAP] What user problem motivated this project, and what evidence can you add?"
            )
        else:
            sentences.append(
                "[GAP] Which gap matters most, and what would you change before calling this finished?"
            )
        return "\n\n".join(sentences)

    lead = {
        "snapshot": "The repository provides a concrete snapshot of the project.",
        "problem": "The project context is visible in the repository evidence.",
        "approach": "The implementation follows a structure that can be traced through the evidence.",
        "hard_part": "The hardest part is visible in the implementation and its supporting code.",
        "shipped": "The project ships concrete, inspectable functionality.",
    }.get(spec.id, "The repository provides evidence for this section.")

    sentences = [f"{lead} " + " ".join(f"[{card.id}]" for card in usable[:2]) + "."]
    for card in usable[:3]:
        sentences.append(f"{card.text} [{card.id}]")
    return "\n\n".join(sentences)


def _valid(body: str) -> bool:
    return bool(body.strip()) and (
        bool(CITATION_RE.search(body)) or bool(GAP_RE.search(body))
    )


def _clean(body: str) -> str:
    text = body.strip()
    text = re.sub(r"^```(?:markdown|md|text)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^\s*#{1,6}\s+.*\n+", "", text, count=1)
    text = re.sub(
        r"^(?:okay|sure|certainly)[^\n]*?(?:\.|:)\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:here(?:['\u2019]s| is)|the following)[^\n]*\n+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    text = text.strip()
    if len(text) >= 2 and text[0] in "“\"" and text[-1] in "”\"":
        text = text[1:-1].strip()
    text = re.sub(r"\s*\[(?:E\d*)?$", "", text).strip()
    if text and text[-1] not in ".!?]":
        boundary = max(text.rfind(". "), text.rfind("? "), text.rfind("! "))
        if boundary > 0:
            text = text[: boundary + 1].strip()
    return text
