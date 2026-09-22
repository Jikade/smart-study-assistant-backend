from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select, text

from app.api.deps import CurrentUser, DbSession
from app.db.models import (
    CommunityPost,
    CommunityReaction,
    CommunitySave,
    Flashcard,
    FlashcardDeck,
    Question,
    QuestionOption,
    Quiz,
)
from app.schemas.community import CommunityPostCreate, CommunityPostOut

router = APIRouter(prefix="/community", tags=["community"])


@router.get("/posts")
def public_posts(db: DbSession, limit: int = 50, offset: int = 0):
    rows = db.execute(text("""
        SELECT * FROM vw_public_community_resources
        ORDER BY published_at DESC
        LIMIT :limit OFFSET :offset
    """), {"limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/posts", response_model=CommunityPostOut, status_code=201)
def publish(payload: CommunityPostCreate, db: DbSession, user: CurrentUser):
    if payload.quiz_id is not None:
        quiz = db.get(Quiz, payload.quiz_id)
        if not quiz or quiz.owner_id != user.id:
            raise HTTPException(404, "Quiz not found")
        quiz.visibility = "PUBLIC"; quiz.status = "PUBLISHED"
    else:
        deck = db.get(FlashcardDeck, payload.flashcard_deck_id)
        if not deck or deck.owner_id != user.id:
            raise HTTPException(404, "Flashcard deck not found")
        deck.visibility = "PUBLIC"
    post = CommunityPost(owner_id=user.id, **payload.model_dump(), status="PUBLISHED")
    db.add(post)
    try:
        db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(400, str(exc)) from exc
    db.refresh(post)
    return post


@router.post("/posts/{post_id}/like")
def like(post_id: int, db: DbSession, user: CurrentUser):
    if not db.get(CommunityPost, post_id): raise HTTPException(404, "Post not found")
    row = db.get(CommunityReaction, (post_id, user.id))
    if row:
        db.delete(row); liked = False
    else:
        db.add(CommunityReaction(post_id=post_id, user_id=user.id)); liked = True
    db.commit(); return {"liked": liked}


@router.post("/posts/{post_id}/save")
def save(post_id: int, db: DbSession, user: CurrentUser):
    if not db.get(CommunityPost, post_id): raise HTTPException(404, "Post not found")
    row = db.get(CommunitySave, (post_id, user.id))
    if row:
        db.delete(row); saved = False
    else:
        db.add(CommunitySave(post_id=post_id, user_id=user.id)); saved = True
    db.commit(); return {"saved": saved}


@router.post("/posts/{post_id}/fork")
def fork(post_id: int, db: DbSession, user: CurrentUser):
    post = db.get(CommunityPost, post_id)
    if not post or post.status != "PUBLISHED":
        raise HTTPException(404, "Post not found")
    if post.quiz_id:
        src = db.get(Quiz, post.quiz_id)
        new = Quiz(owner_id=user.id, subject_id=None, source_quiz_id=src.id, title=f"{src.title} (fork)", description=src.description, generation_mode="FORKED", difficulty=src.difficulty, duration_minutes=src.duration_minutes, status="DRAFT", visibility="PRIVATE")
        db.add(new); db.flush()
        for q in db.scalars(select(Question).where(Question.quiz_id == src.id).order_by(Question.question_order)).all():
            nq = Question(quiz_id=new.id, # A community fork copies the public quiz content, not the source-document ownership link.
                source_chunk_id=None, question_order=q.question_order, question_text=q.question_text, difficulty=q.difficulty, explanation=q.explanation, points=q.points, metadata_={})
            db.add(nq); db.flush()
            for o in db.scalars(select(QuestionOption).where(QuestionOption.question_id == q.id).order_by(QuestionOption.position)).all():
                db.add(QuestionOption(question_id=nq.id, option_key=o.option_key, option_text=o.option_text, is_correct=o.is_correct, explanation=o.explanation, position=o.position))
        db.commit(); return {"resource_type": "QUIZ", "resource_id": new.id}
    src = db.get(FlashcardDeck, post.flashcard_deck_id)
    new = FlashcardDeck(owner_id=user.id, source_deck_id=src.id, title=f"{src.title} (fork)", description=src.description, generation_mode="FORKED", visibility="PRIVATE", status="ACTIVE")
    db.add(new); db.flush()
    for c in db.scalars(select(Flashcard).where(Flashcard.deck_id == src.id).order_by(Flashcard.card_order)).all():
        db.add(Flashcard(deck_id=new.id, # A community fork copies the public card content, not the source-document ownership link.
            source_chunk_id=None, front_text=c.front_text, back_text=c.back_text, hint=c.hint, card_order=c.card_order))
    db.commit(); return {"resource_type": "FLASHCARD_DECK", "resource_id": new.id}
