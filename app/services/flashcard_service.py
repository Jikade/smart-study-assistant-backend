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
from app.services.ai_provider import AIProviderError, get_ai_provider
from app.services.gamification_service import add_xp, evaluate_badges, get_or_create_daily_stat
from app.services.source_access import validate_owned_subject_id
from app.services.source_access import (
    validate_owned_active_chunk_ids,
    validate_owned_document_ids,
)


def create_deck(db: Session, owner_id: int, payload: DeckCreate, generation_mode: str = "MANUAL") -> FlashcardDeck:
    validate_owned_subject_id(
        db,
        owner_id,
        payload.subject_id,
    )

    document_ids = validate_owned_document_ids(
        db,
        owner_id,
        payload.document_ids,
        subject_id=payload.subject_id,
    )

    validate_owned_active_chunk_ids(
        db,
        owner_id,
        [
            card.source_chunk_id
            for card in payload.cards
            if card.source_chunk_id is not None
        ],
        allowed_document_ids=document_ids or None,
        subject_id=payload.subject_id,
    )

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
    for doc_id in document_ids:
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


FLASHCARD_GENERATION_MAX_RETRIES = 2

# FLASHCARD-BATCH-V2.1
FLASHCARD_BATCH_SIZE = 4
FLASHCARD_CONTEXT_CHUNKS_PER_BATCH = 3
FLASHCARD_CONTEXT_CHARS_PER_CHUNK = 1000


def _parse_flashcard_batch(
    content: str,
) -> list[dict]:
    value = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        (content or "").strip(),
        flags=re.I,
    )

    start = value.find("{")
    end = value.rfind("}")

    if start < 0 or end <= start:
        raise ValueError(
            "AI response does not contain a JSON object"
        )

    data = json.loads(
        value[start:end + 1]
    )

    if not isinstance(data, dict):
        raise ValueError(
            "AI flashcard response must be a JSON object"
        )

    raw_cards = data.get("cards")

    if not isinstance(
        raw_cards,
        list,
    ):
        raise ValueError(
            "AI flashcard response field 'cards' must be a list"
        )

    return raw_cards


def _flashcard_front_key(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").strip().lower(),
    )


def _flashcard_context_window(
    chunks: list[DocumentChunk],
    cursor: int,
) -> tuple[list[DocumentChunk], int]:
    if not chunks:
        return [], 0

    count = min(
        FLASHCARD_CONTEXT_CHUNKS_PER_BATCH,
        len(chunks),
    )

    selected = [
        chunks[
            (cursor + offset)
            % len(chunks)
        ]
        for offset in range(count)
    ]

    next_cursor = (
        cursor + count
    ) % len(chunks)

    return selected, next_cursor


def generate_deck(
    db: Session,
    owner_id: int,
    payload: DeckGenerateRequest,
) -> FlashcardDeck:
    validate_owned_subject_id(
        db,
        owner_id,
        payload.subject_id,
    )

    document_ids = validate_owned_document_ids(
        db,
        owner_id,
        payload.document_ids,
        subject_id=payload.subject_id,
    )

    provider = get_ai_provider()

    if not provider.can_chat:
        raise HTTPException(
            503,
            "AI chat model is not configured",
        )

    stmt = (
        select(DocumentChunk)
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            Document.status == "READY",
            Document.owner_id == owner_id,
            DocumentChunk.is_active.is_(True),
        )
    )

    if document_ids:
        stmt = stmt.where(
            DocumentChunk.document_id.in_(
                document_ids
            )
        )
    elif payload.subject_id:
        stmt = stmt.where(
            Document.subject_id
            == payload.subject_id
        )

    chunks = list(
        db.scalars(
            stmt.order_by(
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
            ).limit(30)
        ).all()
    )

    if not chunks:
        raise HTTPException(
            400,
            "No READY document chunks found",
        )

    cards: list[FlashcardCreate] = []
    seen_fronts: set[str] = set()
    last_error: str | None = None

    base_calls = (
        payload.card_count
        + FLASHCARD_BATCH_SIZE
        - 1
    ) // FLASHCARD_BATCH_SIZE

    max_calls = (
        base_calls
        + FLASHCARD_GENERATION_MAX_RETRIES
    )

    cursor = 0
    calls_used = 0

    while (
        len(cards) < payload.card_count
        and calls_used < max_calls
    ):
        calls_used += 1

        remaining = (
            payload.card_count
            - len(cards)
        )

        batch_target = min(
            FLASHCARD_BATCH_SIZE,
            remaining,
        )

        context_chunks, cursor = (
            _flashcard_context_window(
                chunks,
                cursor,
            )
        )

        allowed_chunk_ids = {
            int(chunk.id)
            for chunk in context_chunks
        }

        context = "\n\n".join(
            (
                f"[CHUNK_ID={chunk.id}]\n"
                + str(
                    chunk.content
                    or ""
                )[
                    :FLASHCARD_CONTEXT_CHARS_PER_CHUNK
                ]
            )
            for chunk in context_chunks
        )

        recent_fronts = [
            card.front_text
            for card in cards[-20:]
        ]

        prompt = (
            "Create exactly "
            f"{batch_target} concise study flashcards "
            "grounded only in CONTEXT.\n\n"
            'Return one JSON object: {"cards":[...]}.\n\n'
            "Each card must contain:\n"
            "- front_text\n"
            "- back_text\n"
            "- hint (nullable)\n"
            "- source_chunk_id\n\n"
            "Rules:\n"
            "- source_chunk_id MUST be one of the supplied CHUNK_ID values.\n"
            "- front_text must be a natural study question or prompt.\n"
            "- back_text must answer the front_text directly.\n"
            "- Do not invent information outside CONTEXT.\n"
            "- Do not repeat an existing front_text.\n"
            "- Return JSON only, no markdown.\n\n"
            "Existing front_text values to avoid:\n"
            f"{json.dumps(recent_fronts, ensure_ascii=False)}\n\n"
            "CONTEXT:\n"
            f"{context}"
        )

        try:
            result = provider.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Create concise grounded flashcards "
                            "as strict JSON. Keep every card "
                            "answerable from its cited chunk."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                json_mode=True,
                temperature=0.0,
                max_tokens=min(
                    900,
                    max(
                        350,
                        batch_target * 180,
                    ),
                ),
                reasoning_effort="none",
            )

            raw_cards = _parse_flashcard_batch(
                result.content
            )

        except AIProviderError as exc:
            last_error = str(
                exc
            )
            continue

        except Exception as exc:
            last_error = (
                "invalid JSON/schema: "
                f"{exc}"
            )
            continue

        accepted_this_call = 0

        for raw_card in raw_cards:
            if len(cards) >= payload.card_count:
                break

            try:
                card = FlashcardCreate.model_validate(
                    raw_card
                )

            except Exception as exc:
                last_error = (
                    "flashcard schema validation failed: "
                    f"{exc}"
                )
                continue

            if card.source_chunk_id is None:
                last_error = (
                    "generated flashcard is missing "
                    "source_chunk_id"
                )
                continue

            if (
                int(
                    card.source_chunk_id
                )
                not in allowed_chunk_ids
            ):
                last_error = (
                    "generated flashcard references a "
                    "source_chunk_id outside the current "
                    "grounded context window"
                )
                continue

            front_key = _flashcard_front_key(
                card.front_text
            )

            back_key = _flashcard_front_key(
                card.back_text
            )

            if (
                not front_key
                or not back_key
            ):
                last_error = (
                    "generated flashcard contains "
                    "empty front/back text"
                )
                continue

            if front_key == back_key:
                last_error = (
                    "generated flashcard front and back "
                    "must not be identical"
                )
                continue

            if front_key in seen_fronts:
                last_error = (
                    "generated flashcard duplicates "
                    "an existing front_text"
                )
                continue

            cards.append(
                card
            )

            seen_fronts.add(
                front_key
            )

            accepted_this_call += 1

        print(
            "[FLASHCARD PERF] "
            "FLASHCARD-BATCH-V2.1 "
            f"call={calls_used}/{max_calls} "
            f"target={batch_target} "
            f"accepted={accepted_this_call} "
            f"total={len(cards)}/{payload.card_count} "
            f"context_chunks={sorted(allowed_chunk_ids)}"
        )

        if accepted_this_call == 0:
            last_error = (
                last_error
                or "AI returned no usable flashcards"
            )

    if len(cards) != payload.card_count:
        raise HTTPException(
            status_code=502,
            detail=(
                "Batched flashcard generation produced "
                f"{len(cards)} usable card(s), but "
                f"{payload.card_count} were requested "
                f"after {calls_used} bounded call(s). "
                f"Last reason: {last_error or 'unknown'}"
            ),
        )

    return create_deck(
        db,
        owner_id,
        DeckCreate(
            subject_id=payload.subject_id,
            title=payload.title,
            document_ids=document_ids,
            cards=cards,
        ),
        generation_mode="AI",
    )


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
    stat = get_or_create_daily_stat(
        db,
        user_id,
    )
    stat.flashcards_reviewed = (
        int(stat.flashcards_reviewed or 0)
        + 1
    )
    add_xp(db, user_id, 2, "FLASHCARD_REVIEW", flashcard.id, "Reviewed flashcard")
    db.flush()
    evaluate_badges(db, user_id)
    db.commit()
    db.refresh(progress)
    return progress
