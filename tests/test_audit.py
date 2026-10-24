from __future__ import annotations

from pathlib import Path

import pytest

from doxify.audit import audit_artifact, failing_claims, parse_fail_on
from doxify.errors import SessionError
from doxify.models import ClaimStatus, EvidenceCard, EvidenceKind, EvidenceStrength


def _card(
    card_id: str = "E1",
    text: str = "Demo has 3 files.",
) -> EvidenceCard:
    return EvidenceCard(
        id=card_id,
        kind=EvidenceKind.METRIC,
        title="Repository facts",
        text=text,
        strength=EvidenceStrength.DETERMINISTIC,
    )


def test_annotated_readme_verifies_evidence_and_attested_sections(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

Intro prose is author-owned.

<!-- doxify-attested: project description -->

## Facts

Demo has 3 files.

<!-- doxify-evidence: E1 -->
""",
        encoding="utf-8",
    )

    report = audit_artifact(readme, [_card()])

    assert report.mode == "readme"
    assert report.summary.verified == 1
    assert report.summary.attested == 1
    assert report.summary.needs_evidence == 0
    assert report.unmarked_sections == []
    assert failing_claims(report.claims, {ClaimStatus.NEEDS_EVIDENCE}) == []


def test_annotated_readme_flags_unsupported_claims(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

<!-- doxify-attested: title -->

## Facts

Demo has 99 users.

<!-- doxify-evidence: E1 -->
""",
        encoding="utf-8",
    )

    report = audit_artifact(readme, [_card()])

    assert report.summary.needs_evidence == 1
    assert failing_claims(report.claims, {ClaimStatus.NEEDS_EVIDENCE})


def test_unmarked_section_fails_in_strict_mode(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

<!-- doxify-attested: intro -->

## Facts

Demo has 3 files.

<!-- doxify-evidence: E1 -->

## Unclassified

This section was never classified.
""",
        encoding="utf-8",
    )

    report = audit_artifact(readme, [_card()])

    assert report.unmarked_sections == ["Unclassified"]
    assert report.summary.needs_evidence == 1


def test_unmarked_section_can_be_allowed(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

<!-- doxify-attested: intro -->

## Unclassified

This section was never classified.
""",
        encoding="utf-8",
    )

    report = audit_artifact(readme, [_card()], strict=False)

    assert report.unmarked_sections == ["Unclassified"]
    assert report.summary.needs_evidence == 0


def test_unknown_evidence_id_is_rejected(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        """# Demo

## Facts

Demo has 3 files.

<!-- doxify-evidence: E9 -->
""",
        encoding="utf-8",
    )

    report = audit_artifact(readme, [_card()])

    assert report.summary.rejected == 1
    assert failing_claims(report.claims, {ClaimStatus.REJECTED})


def test_case_study_flags_visible_markers(tmp_path: Path) -> None:
    case_study = tmp_path / "case-study.md"
    case_study.write_text(
        """# Demo: an evidence-backed case study

## Snapshot

Demo has 3 files. [E1]

The author used this in production. [needs evidence]

## Evidence appendix

- **E1** - Demo has 3 files.
""",
        encoding="utf-8",
    )

    report = audit_artifact(case_study, [_card()])

    assert report.mode == "case_study"
    assert report.summary.needs_evidence >= 1
    assert failing_claims(report.claims, {ClaimStatus.NEEDS_EVIDENCE})


def test_artifact_without_markers_is_rejected(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Demo\n\nPlain prose.\n", encoding="utf-8")

    with pytest.raises(SessionError, match="no Doxify evidence markers"):
        audit_artifact(readme, [_card()])


def test_parse_fail_on_accepts_none_and_rejects_unknown() -> None:
    assert parse_fail_on("none") == set()
    assert parse_fail_on("needs_evidence, rejected") == {
        ClaimStatus.NEEDS_EVIDENCE,
        ClaimStatus.REJECTED,
    }

    with pytest.raises(ValueError, match="Unknown failure status"):
        parse_fail_on("nonsense")
