from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"
TOOL_NAME = "doxify"


class EvidenceKind(str, Enum):
    METRIC = "metric"
    STACK = "stack"
    FILE = "file"
    CODE = "code"
    COMMIT = "commit"
    TEST = "test"
    DEPLOY = "deploy"
    README = "readme"
    ATTESTED = "attested"


class EvidenceStrength(str, Enum):
    DETERMINISTIC = "deterministic"
    CODE = "code"
    COMMIT = "commit"
    README = "readme"
    ATTESTED = "attested"


class ClaimStatus(str, Enum):
    VERIFIED = "verified"
    ATTESTED = "attested"
    NEEDS_EVIDENCE = "needs_evidence"
    REJECTED = "rejected"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    lines: str | None = None
    commit: str | None = None
    url: str | None = None


class EvidenceCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: EvidenceKind
    title: str
    text: str
    quote: str | None = None
    refs: list[EvidenceRef] = Field(default_factory=list)
    strength: EvidenceStrength
    keywords: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class CommitInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hexsha: str
    date: str
    subject: str


class RepoSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    name: str
    head_sha: str | None = None
    branch: str | None = None
    commit_count: int = 0
    first_commit_date: str | None = None
    last_commit_date: str | None = None
    tracked_file_count: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    readme_path: str | None = None
    manifests: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    deploy_files: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    repo: RepoSummary
    evidence: list[EvidenceCard] = Field(default_factory=list)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    section_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.NEEDS_EVIDENCE
    reason: str | None = None
    gap_question: str | None = None
    user_answer: str | None = None


class CaseStudySentence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    claim_id: str
    evidence_ids: list[str] = Field(default_factory=list)


class CaseStudySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    body: str
    sentences: list[CaseStudySentence] = Field(default_factory=list)


class DefenseQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    why_asked: str
    answer_outline: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    gap: str | None = None


class CompileSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: int = 0
    attested: int = 0
    needs_evidence: int = 0
    rejected: int = 0
    sections: int = 0
    evidence_cards: int = 0


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    summary: CompileSummary
    claims: list[Claim] = Field(default_factory=list)


class ClaimsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    summary: CompileSummary
    claims: list[Claim] = Field(default_factory=list)


class SectionsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    sections: list[CaseStudySection] = Field(default_factory=list)


class DefenseDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    questions: list[DefenseQuestion] = Field(default_factory=list)


class SessionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    tool: str = TOOL_NAME
    tool_version: str = "0.1.0"
    created_at: str
    updated_at: str
    repo: RepoSummary
    model: str
    status: str = "created"
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)


class CompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: SessionManifest
    evidence: list[EvidenceCard] = Field(default_factory=list)
    sections: list[CaseStudySection] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    defense: list[DefenseQuestion] = Field(default_factory=list)
    summary: CompileSummary


class SectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    goal: str
    keywords: list[str] = Field(default_factory=list)
