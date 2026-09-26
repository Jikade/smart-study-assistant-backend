from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class KnowledgeKind(str, Enum):
    ENTITY = "ENTITY"
    PERSON = "PERSON"
    PLACE = "PLACE"
    DATE = "DATE"
    NUMBER = "NUMBER"
    TERM = "TERM"
    DEFINITION = "DEFINITION"
    PROPERTY = "PROPERTY"
    FUNCTION = "FUNCTION"
    CAUSE = "CAUSE"
    EFFECT = "EFFECT"
    PROCESS = "PROCESS"
    SEQUENCE = "SEQUENCE"
    FORMULA = "FORMULA"
    RELATION = "RELATION"
    EXAMPLE = "EXAMPLE"
    COMPARISON = "COMPARISON"
    EVENT = "EVENT"


class BlueprintType(str, Enum):
    TERM_FROM_DEFINITION = "TERM_FROM_DEFINITION"
    DEFINITION_FROM_TERM = "DEFINITION_FROM_TERM"
    EVENT_DATE = "EVENT_DATE"
    PERSON_ACTION = "PERSON_ACTION"
    CAUSE_EFFECT = "CAUSE_EFFECT"
    CONCEPT_FUNCTION = "CONCEPT_FUNCTION"
    FORMULA_APPLICATION = "FORMULA_APPLICATION"
    SEQUENCE_ORDER = "SEQUENCE_ORDER"
    PROPERTY_RECALL = "PROPERTY_RECALL"
    EXAMPLE_CLASSIFICATION = "EXAMPLE_CLASSIFICATION"


@dataclass(frozen=True)
class EvidenceRef:
    document_id: int
    chunk_id: int
    section_id: int | None
    text: str


@dataclass(frozen=True)
class KnowledgeObject:
    id: str
    subject_family: str
    kind: KnowledgeKind
    subject: str
    relation: str
    object: str
    evidence: EvidenceRef
    confidence: float = 1.0
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestionBlueprint:
    id: str
    blueprint_type: BlueprintType
    knowledge_id: str
    stem: str
    correct_answer: str
    distractor_family: str
    section_id: int | None
    quality_score: float
    evidence: EvidenceRef
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlannedQuestion:
    blueprint: QuestionBlueprint
    distractors: tuple[str, str, str]
    validation_score: float
    metadata: dict[str, object] = field(default_factory=dict)
