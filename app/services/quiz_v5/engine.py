from __future__ import annotations

from dataclasses import dataclass

from app.services.quiz_v5.distractors import (
    PlanBuildDiagnostics,
    build_validated_quiz_plan,
)
from app.services.quiz_v5.extractor import (
    ChunkInput,
    extract_knowledge_objects,
)
from app.services.quiz_v5.models import (
    KnowledgeObject,
    PlannedQuestion,
    QuestionBlueprint,
)
from app.services.quiz_v5.planner import (
    plan_blueprints,
)


SSA_QV5_ENGINE_VERSION = "SSA-QV5-ENGINE-V0.1"


@dataclass(frozen=True)
class QuizV5EngineResult:
    """
    Pure deterministic Quiz V5 orchestration result.

    No database access.
    No API access.
    No AI/model calls.
    No persistence side effects.
    """

    version: str
    requested: int
    exact: bool
    source_chars: int
    knowledge: tuple[KnowledgeObject, ...]
    blueprints: tuple[QuestionBlueprint, ...]
    questions: tuple[PlannedQuestion, ...]
    diagnostics: PlanBuildDiagnostics


def run_quiz_v5_engine(
    chunks: list[ChunkInput],
    *,
    target: int = 5,
    subject_family: str = "general",
    max_per_section: int | None = 2,
) -> QuizV5EngineResult:
    """
    SSA-QV5-ENGINE-V0.1

    Deterministic orchestration:
      chunks
        -> knowledge extraction
        -> blueprint planning
        -> deterministic selection
        -> distractor construction
        -> validation/replacement
        -> immutable result
    """
    requested = max(
        0,
        int(target),
    )

    source_chars = sum(
        len(str(chunk.text or ""))
        for chunk in chunks
    )

    knowledge = extract_knowledge_objects(
        chunks,
        subject_family=subject_family,
    )

    blueprints = plan_blueprints(
        knowledge
    )

    questions, diagnostics = (
        build_validated_quiz_plan(
            blueprints,
            target=requested,
            max_per_section=max_per_section,
        )
    )

    return QuizV5EngineResult(
        version=SSA_QV5_ENGINE_VERSION,
        requested=requested,
        exact=(
            len(questions) == requested
        ),
        source_chars=source_chars,
        knowledge=tuple(knowledge),
        blueprints=tuple(blueprints),
        questions=tuple(questions),
        diagnostics=diagnostics,
    )
