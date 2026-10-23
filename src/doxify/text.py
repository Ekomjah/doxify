from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]*|\d[\d,]*")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "which",
    "with",
    "project",
    "repository",
    "repo",
    "code",
    "file",
    "files",
    "using",
    "used",
    "uses",
    "use",
    "built",
    "build",
}


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def stem(token: str) -> str:
    if len(token) <= 4 or token.isdigit():
        return token
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def content_tokens(text: str) -> set[str]:
    return {
        stem(token)
        for token in tokenize(text)
        if token not in STOPWORDS and len(token) > 1
    }


def token_sets_overlap(left: set[str], right: set[str]) -> bool:
    for first in left:
        for second in right:
            if first == second:
                return True
            if (
                len(first) >= 4
                and len(second) >= 4
                and (first.startswith(second) or second.startswith(first))
            ):
                return True
    return False


def keywords_for(text: str, limit: int = 10) -> list[str]:
    seen: list[str] = []
    for token in tokenize(text):
        if token in STOPWORDS or token in seen or len(token) < 2:
            continue
        seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
