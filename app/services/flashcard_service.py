from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DailyLearningStat,
    Document,
    DocumentChunk,
    Flashcard,
    FlashcardDeck,
    FlashcardDeckDocument,
    FlashcardProgress,
    FlashcardReview,
)
from app.schemas.flashcards import DeckCreate, DeckGenerateRequest, FlashcardCreate
from app.services.ai_provider import get_ai_provider
from app.services.gamification_service import add_xp, evaluate_badges


def create_deck(db: Session, owner_id: int, payload: DeckCreate, generation_mode: str = "MANUAL") -> FlashcardDeck:
    deck = FlashcardDeck(
        owner_id=owner_id,
        subject_id=payload.subject_id,
        title=payload.title,
        description=payload.description,
        generation_mode=generation_mode,
        visibility=payload.visibility,
        status="ACTIVE",
    )
    db.add(deck)
    db.flush()
    for doc_id in payload.document_ids:
        db.add(FlashcardDeckDocument(deck_id=deck.id, document_id=doc_id))
    for index, card in enumerate(payload.cards, start=1):
        db.add(Flashcard(
            deck_id=deck.id,
            source_chunk_id=card.source_chunk_id,
            front_text=card.front_text,
            back_text=card.back_text,
            hint=card.hint,
            card_order=index,
        ))
    db.commit()
    db.refresh(deck)
    return deck


def generate_deck(db: Session, owner_id: int, payload: DeckGenerateRequest) -> FlashcardDeck:
    provider = get_ai_provider()
    if not provider.can_chat:
        raise HTTPException(503, "AI chat model is not configured")
    stmt = (
        select(DocumentChunk)
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            Document.status == "READY",
            DocumentChunk.is_active.is_(True),
        )
    )
    if payload.document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_(payload.document_ids))
    elif payload.subject_id:
        stmt = stmt.where(Document.subject_id == payload.subject_id, Document.owner_id == owner_id)
    else:
        stmt = stmt.where(Document.owner_id == owner_id)
    chunks = list(db.scalars(stmt.order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(30)).all())
    if not chunks:
        raise HTTPException(400, "No READY document chunks found")
    context = "\n\n".join(f"[CHUNK_ID={c.id}]\n{c.content[:2500]}" for c in chunks)
    prompt = f"""
Create exactly {payload.card_count} study flashcards grounded only in CONTEXT.
Return JSON object {{"cards": [...]}}. Each card: front_text, back_text, hint (nullable), source_chunk_id.
source_chunk_id must be one of the supplied CHUNK_ID values. No markdown.
CONTEXT:\n{context}
""".strip()
    result = provider.chat([
        {"role": "system", "content": "Create concise grounded flashcards as strict JSON."},
        {"role": "user", "content": prompt},
    ], json_mode=True)
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.content.strip(), flags=re.I)
    try:
        data = json.loads(value[value.find("{"):value.rfind("}") + 1])
        raw_cards = data["cards"]
        if len(raw_cards) != payload.card_count:
            raise ValueError("wrong card count")
        cards = [FlashcardCreate.model_validate(c) for c in raw_cards]
    except Exception as exc:
        raise HTTPException(502, f"Invalid AI flashcard output: {exc}") from exc
    return create_deck(db, owner_id, DeckCreate(
        subject_id=payload.subject_id,
        title=payload.title,
        document_ids=payload.document_ids,
        cards=cards,
    ), generation_mode="AI")


def review_flashcard(db: Session, user_id: int, flashcard: Flashcard, rating: int, response_time_ms: int | None = None) -> FlashcardProgress:
    progress = db.get(FlashcardProgress, (user_id, flashcard.id))
    if progress is None:
        progress = FlashcardProgress(user_id=user_id, flashcard_id=flashcard.id)
        db.add(progress)
        db.flush()

    prev_interval = int(progress.interval_days or 0)
    prev_ease = float(progress.ease_factor or Decimal("2.50"))
    repetitions = int(progress.repetitions or 0)
    ease = prev_ease
    lapses = int(progress.lapse_count or 0)

    if rating == 0:  # Again
        repetitions = 0
        interval = 1
        ease = max(1.30, ease - 0.20)
        lapses += 1
    elif rating == 1:  # Hard
        repetitions += 1
        interval = max(1, round(max(1, prev_interval) * 1.2))
        ease = max(1.30, ease - 0.15)
    elif rating == 2:  # Good
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 3
        else:
            interval = max(1, round(max(1, prev_interval) * ease))
    else:  # Easy
        repetitions += 1
        interval = 4 if repetitions == 1 else max(2, round(max(1, prev_interval) * ease * 1.3))
        ease = min(3.50, ease + 0.15)

    now = datetime.now(timezone.utc)
    progress.repetitions = repetitions
    progress.interval_days = interval
    progress.ease_factor = Decimal(f"{ease:.2f}")
    progress.lapse_count = lapses
    progress.last_rating = rating
    progress.last_reviewed_at = now
    progress.next_review_at = now + timedelta(days=interval)

    db.add(FlashcardReview(
        user_id=user_id,
        flashcard_id=flashcard.id,
        rating=rating,
        response_time_ms=response_time_ms,
        previous_interval=prev_interval,
        next_interval=interval,
        previous_ease=Decimal(f"{prev_ease:.2f}"),
        next_ease=Decimal(f"{ease:.2f}"),
    ))
    stat = db.get(DailyLearningStat, (user_id, date.today()))
    if stat is None:
        stat = DailyLearningStat(user_id=user_id, activity_date=date.today())
        db.add(stat)
    stat.flashcards_reviewed = int(stat.flashcards_reviewed or 0) + 1
    add_xp(db, user_id, 2, "FLASHCARD_REVIEW", flashcard.id, "Reviewed flashcard")
    db.flush()
    evaluate_badges(db, user_id)
    db.commit()
    db.refresh(progress)
    return progress
