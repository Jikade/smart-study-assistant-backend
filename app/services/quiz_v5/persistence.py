from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import TYPE_CHECKING

from app.schemas.quizzes import (
    OptionCreate,
    QuestionCreate,
    QuizCreate,
    QuizV5GenerateRequest,
)
from app.services.quiz_service import create_quiz
from app.services.quiz_v5.engine import QuizV5EngineResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.db.models import Quiz


SSA_QV5_PERSISTENCE_VERSION = "SSA-QV5-PERSIST-V0.1"
OPTION_KEYS = ("A", "B", "C", "D")


def _stable_correct_position(
    blueprint_id: str,
) -> int:
    """
    Deterministically rotate the correct answer across A-D.

    This avoids a fixed-position answer key without introducing randomness,
    making repeated runs reproducible for the same blueprint.
    """
    digest = hashlib.sha1(
        str(blueprint_id).encode("utf-8")
    ).hexdigest()

    return (
        int(digest[:8], 16)
        % 4
    )


def _question_options(
    *,
    blueprint_id: str,
    correct_answer: str,
    distractors: tuple[str, str, str],
) -> list[OptionCreate]:
    correct_index = _stable_correct_position(
        blueprint_id
    )

    ordered = list(
        distractors
    )

    ordered.insert(
        correct_index,
        correct_answer,
    )

    return [
        OptionCreate(
            option_key=OPTION_KEYS[index],
            option_text=str(text_value),
            is_correct=(
                index == correct_index
            ),
            explanation=None,
            position=index + 1,
        )
        for index, text_value in enumerate(
            ordered
        )
    ]


def build_quiz_create_payload(
    result: QuizV5EngineResult,
    *,
    request: QuizV5GenerateRequest,
    document_ids: list[int],
) -> QuizCreate:
    """
    Convert an exact deterministic engine result into the existing
    QuizCreate contract.

    No database access occurs here.
    """
    if (
        not result.exact
        or len(result.questions)
        != int(request.question_count)
    ):
        raise ValueError(
            "Quiz V5 engine did not reach the exact requested target."
        )

    questions: list[QuestionCreate] = []

    for planned in result.questions:
        blueprint = planned.blueprint

        questions.append(
            QuestionCreate(
                question_text=blueprint.stem,
                difficulty=request.difficulty,
                explanation=(
                    blueprint.evidence.text
                ),
                points=Decimal("1.00"),
                source_chunk_id=int(
                    blueprint.evidence.chunk_id
                ),
                options=_question_options(
                    blueprint_id=blueprint.id,
                    correct_answer=(
                        blueprint.correct_answer
                    ),
                    distractors=(
                        planned.distractors
                    ),
                ),
            )
        )

    return QuizCreate(
        subject_id=request.subject_id,
        title=request.title,
        description=request.description,
        difficulty=request.difficulty,
        duration_minutes=(
            request.duration_minutes
        ),
        visibility=request.visibility,
        document_ids=list(
            document_ids
        ),
        questions=questions,
    )


def persist_quiz_v5(
    db: "Session",
    *,
    owner_id: int,
    request: QuizV5GenerateRequest,
    document_ids: list[int],
    result: QuizV5EngineResult,
) -> "Quiz":
    """
    Persist one exact Quiz V5 result through the existing hardened
    create_quiz() path.

    create_quiz() re-validates:
    - subject ownership;
    - document ownership;
    - active source chunk ownership;
    and owns the DB commit/rollback.
    """
    payload = build_quiz_create_payload(
        result,
        request=request,
        document_ids=document_ids,
    )

    audit = json.dumps(
        {
            "engine_version": result.version,
            "persistence_version": (
                SSA_QV5_PERSISTENCE_VERSION
            ),
            "subject_family": (
                request.subject_family
            ),
            "requested": result.requested,
            "generated": len(
                result.questions
            ),
            "knowledge_count": len(
                result.knowledge
            ),
            "blueprint_count": len(
                result.blueprints
            ),
            "replacement_iterations": (
                result.diagnostics.iterations
            ),
            "structured_fallback_count": (
                result.diagnostics.structured_fallback_count
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    return create_quiz(
        db,
        owner_id,
        payload,
        generation_mode="V5_DETERMINISTIC",
        ai_model=None,
        generation_prompt=audit,
    )
