from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.db.models import Conversation, ConversationDocument, Document, Message, Subject
from app.schemas.chat import AskRequest, ChatAnswer, ConversationCreate, ConversationOut, MessageOut
from app.services.rag_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


def owned_conversation(db: DbSession, user_id: int, conversation_id: int) -> Conversation:
    row = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if row is None:
        raise HTTPException(404, "Conversation not found")
    return row


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationCreate, db: DbSession, user: CurrentUser):
    if payload.subject_id is not None:
        owned_subject = db.scalar(
            select(Subject.id).where(
                Subject.id == payload.subject_id,
                Subject.owner_id == user.id,
            )
        )
        if owned_subject is None:
            raise HTTPException(404, "Subject not found")

    row = Conversation(user_id=user.id, subject_id=payload.subject_id, title=payload.title)
    db.add(row); db.flush()
    if payload.document_ids:
        owned_ids = set(db.scalars(select(Document.id).where(Document.owner_id == user.id, Document.id.in_(payload.document_ids))).all())
        if owned_ids != set(payload.document_ids):
            raise HTTPException(400, "One or more documents are not accessible")
        for doc_id in payload.document_ids:
            db.add(ConversationDocument(conversation_id=row.id, document_id=doc_id))
    db.commit(); db.refresh(row)
    return row


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: DbSession, user: CurrentUser, limit: int = 50):
    return list(db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).limit(limit)).all())


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def messages(conversation_id: int, db: DbSession, user: CurrentUser):
    owned_conversation(db, user.id, conversation_id)
    return list(db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)).all())


@router.post("/conversations/{conversation_id}/ask", response_model=ChatAnswer)
def ask(conversation_id: int, payload: AskRequest, db: DbSession, user: CurrentUser):
    convo = owned_conversation(db, user.id, conversation_id)
    user_msg, assistant, citations = answer_question(db, convo, payload.question, payload.input_mode, payload.top_k)
    return ChatAnswer(
        user_message_id=user_msg.id,
        assistant_message_id=assistant.id,
        answer=assistant.content,
        model_name=assistant.model_name,
        citations=citations,
    )
