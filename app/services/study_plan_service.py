from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentSection, StudyPlan, StudyTask
from app.schemas.study_plans import StudyPlanGenerateRequest
from app.services.source_access import validate_owned_subject_id


def generate_plan(db: Session, user_id: int, payload: StudyPlanGenerateRequest) -> StudyPlan:
    validate_owned_subject_id(
        db,
        user_id,
        payload.subject_id,
    )

    if payload.exam_date < payload.start_date:
        raise HTTPException(400, "exam_date must be on or after start_date")
    plan = StudyPlan(
        user_id=user_id,
        subject_id=payload.subject_id,
        title=payload.title,
        start_date=payload.start_date,
        exam_date=payload.exam_date,
        daily_minutes=payload.daily_minutes,
        status="ACTIVE",
        generated_by_ai=False,
        generation_notes="Deterministic workload allocation from document sections; AI can be added as a refinement layer.",
    )
    db.add(plan)
    db.flush()

    docs_stmt = select(Document).where(Document.owner_id == user_id, Document.status == "READY")
    if payload.subject_id:
        docs_stmt = docs_stmt.where(Document.subject_id == payload.subject_id)
    docs = list(db.scalars(docs_stmt.order_by(Document.created_at)).all())
    if not docs:
        db.rollback()
        raise HTTPException(400, "No READY documents found for this study plan")

    units: list[tuple[Document, DocumentSection | None, str]] = []
    for doc in docs:
        sections = list(db.scalars(select(DocumentSection).where(DocumentSection.document_id == doc.id).order_by(DocumentSection.section_order)).all())
        if sections:
            units.extend((doc, section, section.title or f"Section {section.section_order + 1}") for section in sections)
        else:
            units.append((doc, None, doc.original_name))

    days = (payload.exam_date - payload.start_date).days + 1
    # Reserve the final day for consolidation when possible.
    study_days = max(1, days - 1) if days > 2 else days
    current_day_index = 0
    minutes_used = 0
    sort_order = 0
    default_unit_minutes = max(15, min(45, payload.daily_minutes // 2 or 30))

    for doc, section, label in units:
        if minutes_used + default_unit_minutes > payload.daily_minutes and current_day_index < study_days - 1:
            current_day_index += 1
            minutes_used = 0
            sort_order = 0
        task_date = payload.start_date + timedelta(days=current_day_index)
        db.add(StudyTask(
            plan_id=plan.id,
            document_id=doc.id,
            section_id=section.id if section else None,
            task_date=task_date,
            task_type="STUDY",
            title=f"Học: {label}",
            description=f"Tài liệu: {doc.original_name}",
            estimated_minutes=default_unit_minutes,
            sort_order=sort_order,
            status="PENDING",
        ))
        minutes_used += default_unit_minutes
        sort_order += 1

    if days > 1:
        db.add(StudyTask(
            plan_id=plan.id,
            task_date=payload.exam_date,
            task_type="REVIEW",
            title="Ôn tập tổng hợp trước kỳ thi",
            description="Ôn các chủ đề yếu, flashcard đến hạn và các câu hỏi đã làm sai.",
            estimated_minutes=payload.daily_minutes,
            sort_order=0,
            status="PENDING",
        ))
    db.commit()
    db.refresh(plan)
    return plan
