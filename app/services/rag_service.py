from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Conversation, ConversationDocument, Message, MessageCitation
from app.services.ai_provider import AIProviderError, get_ai_provider

settings = get_settings()


@dataclass
class RetrievedChunk:
    id: int
    document_id: int
    content: str
    score: float


def _vector_available(db: Session) -> bool:
    try:
        return bool(db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname='vector'
            ) AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='chunk_embeddings' AND column_name='embedding'
            )
        """)).scalar())
    except Exception:
        return False


def retrieve_chunks(db: Session, conversation: Conversation, query: str, top_k: int) -> list[RetrievedChunk]:
    document_ids = list(
        db.scalars(
            __import__("sqlalchemy").select(ConversationDocument.document_id).where(
                ConversationDocument.conversation_id == conversation.id
            )
        ).all()
    )
    params: dict = {"query": query, "limit": top_k}
    filters = ["d.status = 'READY'"]
    if document_ids:
        filters.append("dc.document_id = ANY(:doc_ids)")
        params["doc_ids"] = document_ids
    elif conversation.subject_id:
        filters.append("d.subject_id = :subject_id")
        params["subject_id"] = conversation.subject_id
    else:
        filters.append("d.owner_id = :owner_id")
        params["owner_id"] = conversation.user_id

    provider = get_ai_provider()
    if provider.can_embed and _vector_available(db):
        try:
            vector = provider.embeddings([query])[0]

            params["vector"] = (
                "["
                + ",".join(
                    f"{float(v):.10g}"
                    for v in vector
                )
                + "]"
            )

            vector_sql = text(
                f"""
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.content,
                    (
                        1 - (
                            ce.embedding
                            <=> CAST(:vector AS vector)
                        )
                    )::float AS score
                FROM chunk_embeddings ce
                JOIN document_chunks dc
                    ON dc.id = ce.chunk_id
                JOIN documents d
                    ON d.id = dc.document_id
                WHERE dc.is_active = TRUE
                AND {' AND '.join(filters)}
                AND ce.embedding IS NOT NULL
                ORDER BY
                    ce.embedding
                    <=> CAST(:vector AS vector)
                LIMIT :limit
                """
            )

            # Savepoint:
            # nếu pgvector query lỗi thì chỉ rollback phần này,
            # không rollback user_message bên ngoài.
            with db.begin_nested():
                rows = db.execute(
                    vector_sql,
                    params,
                ).mappings().all()

            if rows:
                vector_results = [
                    RetrievedChunk(
                        int(row["id"]),
                        int(row["document_id"]),
                        row["content"],
                        float(row["score"] or 0),
                    )
                    for row in rows
                    if (
                        row["score"] is not None
                        and float(row["score"])
                        >= settings.rag_min_score
                    )
                ]

                if vector_results:
                    return vector_results

                # Vector search chạy thành công,
                # nhưng không có chunk đủ liên quan.
                # Không fallback sang FTS.
                return []

        except Exception as exc:
            print(
                f"[RAG] Vector retrieval failed: {exc}"
            )

    sql = text(f"""
        SELECT dc.id, dc.document_id, dc.content,
               ts_rank_cd(dc.search_vector, plainto_tsquery('simple', :query)) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.is_active = TRUE
          AND {' AND '.join(filters)}
          AND dc.search_vector @@ plainto_tsquery('simple', :query)
        ORDER BY score DESC, dc.id
        LIMIT :limit
    """)
    rows = db.execute(sql, params).mappings().all()
    if not rows:
        params["like_query"] = f"%{query[:120]}%"
        sql2 = text(f"""
            SELECT dc.id, dc.document_id, dc.content, 0.01::float AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.is_active = TRUE
              AND {' AND '.join(filters)}
              AND dc.content ILIKE :like_query
            ORDER BY dc.id
            LIMIT :limit
        """)
        rows = db.execute(sql2, params).mappings().all()
    return [RetrievedChunk(int(r["id"]), int(r["document_id"]), r["content"], float(r["score"] or 0)) for r in rows]


def answer_question(db: Session, conversation: Conversation, question: str, input_mode: str = "TEXT", top_k: int | None = None):
    started = time.perf_counter()
    user_message = Message(
        conversation_id=conversation.id,
        role="USER",
        content=question,
        input_mode=input_mode,
        metadata_={},
    )
    db.add(user_message)
    db.flush()

    chunks = retrieve_chunks(db, conversation, question, top_k or settings.rag_top_k)
    context = "\n\n".join(f"[SOURCE {i+1}] {c.content}" for i, c in enumerate(chunks))
    provider = get_ai_provider()
    model_name = None
    prompt_tokens = None
    completion_tokens = None
    if provider.can_chat and context:
        result = provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are Smart Study Assistant. "
                        "Answer ONLY from the supplied CONTEXT. "
                        "Do not use outside knowledge. "
                        "If the context is insufficient, "
                        "clearly say that the uploaded documents "
                        "do not contain enough information. "
                        "Always answer in the same language "
                        "as the user's question."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"CONTEXT:\n{context}\n\n"
                        f"QUESTION:\n{question}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=400,
            reasoning_effort="none",
        )
        answer = result.content.strip()
        model_name = result.model
        prompt_tokens = result.prompt_tokens
        completion_tokens = result.completion_tokens
    elif chunks:
        # Runnable no-key fallback: retrieval works even before an LLM is configured.
        answer = (
            "Chưa cấu hình LLM. Đây là các đoạn tài liệu liên quan nhất để bạn kiểm tra:\n\n"
            + "\n\n".join(f"• {c.content[:700]}" for c in chunks[:3])
        )
        model_name = "retrieval-only"
    else:
        answer = "Không tìm thấy thông tin liên quan trong các tài liệu đã gắn với cuộc hội thoại."
        model_name = "retrieval-only"

    assistant = Message(
        conversation_id=conversation.id,
        parent_message_id=user_message.id,
        role="ASSISTANT",
        content=answer,
        input_mode="TEXT",
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=int((time.perf_counter() - started) * 1000),
        metadata_={},
    )
    db.add(assistant)
    db.flush()

    citations = []
    for i, chunk in enumerate(chunks, start=1):
        citation = MessageCitation(
            message_id=assistant.id,
            chunk_id=chunk.id,
            rank_order=i,
            similarity_score=chunk.score,
            excerpt=chunk.content[:400],
        )
        db.add(citation)
        citations.append({
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "rank_order": i,
            "similarity_score": chunk.score,
            "excerpt": chunk.content[:400],
        })
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant)
    return user_message, assistant, citations
