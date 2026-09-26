from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable, TYPE_CHECKING

from app.services.quiz_v5.distractors import (
    PlanBuildDiagnostics,
)
from app.services.quiz_v5.db_adapter import (
    load_document_chunks,
)
from app.services.quiz_v5.engine import (
    run_quiz_v5_engine,
)
from app.services.quiz_v5.extractor import (
    ChunkInput,
)
from app.services.quiz_v5.models import (
    KnowledgeObject,
    PlannedQuestion,
    QuestionBlueprint,
)
if TYPE_CHECKING:
    from sqlalchemy.orm import Session


SSA_QV5_SHADOW_VERSION = "SSA-QV5-SHADOW-V0.4"


@dataclass(frozen=True)
class ReadyDocumentSummary:
    document_id: int
    owner_id: int
    subject_id: int | None
    subject_name: str | None
    original_name: str
    active_chunks: int
    chunks_with_section: int
    active_chars: int


@dataclass(frozen=True)
class ShadowQuestionReport:
    order: int
    blueprint_id: str
    blueprint_type: str
    knowledge_id: str
    stem: str
    correct_answer: str
    distractors: tuple[str, str, str]
    source_document_id: int
    source_chunk_id: int
    source_section_id: int | None
    evidence: str
    quality_score: float
    validation_score: float
    distractor_origins: tuple[str, ...]


@dataclass(frozen=True)
class ShadowReport:
    version: str
    document_ids: tuple[int, ...]
    target: int
    chunk_count: int
    source_chars: int
    knowledge_count: int
    blueprint_count: int
    final_question_count: int
    exact: bool
    extraction_coverage_per_1000_chars: float
    knowledge_by_kind: dict[str, int]
    blueprints_by_type: dict[str, int]
    rejected_blueprint_ids: tuple[str, ...]
    replacement_iterations: int
    structured_fallback_count: int
    questions: tuple[ShadowQuestionReport, ...]


def _clean_excerpt(
    value: str,
    *,
    limit: int = 360,
) -> str:
    text = " ".join(
        str(value or "").split()
    )

    if len(text) <= limit:
        return text

    return (
        text[: max(0, limit - 1)].rstrip()
        + "…"
    )


def list_ready_documents(
    db: "Session",
    *,
    owner_id: int | None = None,
    subject_id: int | None = None,
) -> list[ReadyDocumentSummary]:
    """
    Read-only inventory for choosing documents to shadow-test.

    DB imports are lazy so the pure V5 engine can be regression-tested
    without loading the entire application/database package.
    """
    from sqlalchemy import select
    from app.db.models import (
        Document,
        DocumentChunk,
        Subject,
    )

    stmt = (
        select(
            Document,
            Subject.name,
        )
        .outerjoin(
            Subject,
            Subject.id == Document.subject_id,
        )
        .where(
            Document.status == "READY",
        )
        .order_by(
            Document.id,
        )
    )

    if owner_id is not None:
        stmt = stmt.where(
            Document.owner_id == owner_id,
        )

    if subject_id is not None:
        stmt = stmt.where(
            Document.subject_id == subject_id,
        )

    rows = db.execute(
        stmt
    ).all()

    output: list[ReadyDocumentSummary] = []

    for document, subject_name in rows:
        chunks = list(
            db.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id
                    == document.id,
                    DocumentChunk.is_active.is_(True),
                )
                .order_by(
                    DocumentChunk.chunk_index,
                    DocumentChunk.id,
                )
            ).all()
        )

        output.append(
            ReadyDocumentSummary(
                document_id=int(document.id),
                owner_id=int(document.owner_id),
                subject_id=(
                    int(document.subject_id)
                    if document.subject_id is not None
                    else None
                ),
                subject_name=(
                    str(subject_name)
                    if subject_name is not None
                    else None
                ),
                original_name=str(document.original_name),
                active_chunks=len(chunks),
                chunks_with_section=sum(
                    1
                    for chunk in chunks
                    if chunk.section_id is not None
                ),
                active_chars=sum(
                    len(str(chunk.content or ""))
                    for chunk in chunks
                ),
            )
        )

    return output


def shadow_from_chunks(
    chunks: list[ChunkInput],
    *,
    target: int = 5,
    subject_family: str = "general",
    max_per_section: int | None = 2,
) -> ShadowReport:
    """
    Pure V5 shadow pipeline. No database writes and no AI calls.
    """
    document_ids = tuple(
        sorted(
            {
                int(chunk.document_id)
                for chunk in chunks
            }
        )
    )

    engine_result = run_quiz_v5_engine(
        chunks,
        target=target,
        subject_family=subject_family,
        max_per_section=max_per_section,
    )

    return _make_report(
        document_ids=document_ids,
        target=target,
        chunks=chunks,
        source_chars=engine_result.source_chars,
        knowledge=list(engine_result.knowledge),
        blueprints=list(engine_result.blueprints),
        planned=list(engine_result.questions),
        diagnostics=engine_result.diagnostics,
    )


def shadow_documents(
    db: "Session",
    *,
    document_ids: Iterable[int],
    target: int = 5,
    owner_id: int | None = None,
    subject_family: str = "general",
    max_per_section: int | None = 2,
) -> ShadowReport:
    """
    PostgreSQL read -> pure V5 pipeline -> diagnostics.

    This function never calls db.add(), flush(), commit(), delete(), or UPDATE.
    """
    chunks = load_document_chunks(
        db,
        document_ids=document_ids,
        owner_id=owner_id,
    )

    return shadow_from_chunks(
        chunks,
        target=target,
        subject_family=subject_family,
        max_per_section=max_per_section,
    )


def _make_report(
    *,
    document_ids: tuple[int, ...],
    target: int,
    chunks: list[ChunkInput],
    source_chars: int,
    knowledge: list[KnowledgeObject],
    blueprints: list[QuestionBlueprint],
    planned: list[PlannedQuestion],
    diagnostics: PlanBuildDiagnostics,
) -> ShadowReport:
    knowledge_counts = Counter(
        item.kind.value
        for item in knowledge
    )

    blueprint_counts = Counter(
        item.blueprint_type.value
        for item in blueprints
    )

    extraction_coverage = (
        (
            len(knowledge)
            * 1000.0
            / source_chars
        )
        if source_chars > 0
        else 0.0
    )

    questions = tuple(
        ShadowQuestionReport(
            order=index,
            blueprint_id=item.blueprint.id,
            blueprint_type=(
                item.blueprint.blueprint_type.value
            ),
            knowledge_id=item.blueprint.knowledge_id,
            stem=item.blueprint.stem,
            correct_answer=item.blueprint.correct_answer,
            distractors=item.distractors,
            source_document_id=int(
                item.blueprint.evidence.document_id
            ),
            source_chunk_id=int(
                item.blueprint.evidence.chunk_id
            ),
            source_section_id=(
                int(item.blueprint.evidence.section_id)
                if item.blueprint.evidence.section_id
                is not None
                else None
            ),
            evidence=_clean_excerpt(
                item.blueprint.evidence.text
            ),
            quality_score=float(
                item.blueprint.quality_score
            ),
            validation_score=float(
                item.validation_score
            ),
            distractor_origins=tuple(
                str(value)
                for value in (
                    item.metadata.get(
                        "distractor_origins",
                        (),
                    )
                    or ()
                )
            ),
        )
        for index, item in enumerate(
            planned,
            start=1,
        )
    )

    return ShadowReport(
        version=SSA_QV5_SHADOW_VERSION,
        document_ids=document_ids,
        target=int(target),
        chunk_count=len(chunks),
        source_chars=source_chars,
        knowledge_count=len(knowledge),
        blueprint_count=len(blueprints),
        final_question_count=len(planned),
        exact=len(planned) == int(target),
        extraction_coverage_per_1000_chars=round(
            extraction_coverage,
            4,
        ),
        knowledge_by_kind=dict(
            sorted(knowledge_counts.items())
        ),
        blueprints_by_type=dict(
            sorted(blueprint_counts.items())
        ),
        rejected_blueprint_ids=tuple(
            diagnostics.rejected_blueprint_ids
        ),
        replacement_iterations=int(
            diagnostics.iterations
        ),
        structured_fallback_count=int(
            diagnostics.structured_fallback_count
        ),
        questions=questions,
    )


def report_as_dict(
    report: ShadowReport,
) -> dict:
    return asdict(report)
