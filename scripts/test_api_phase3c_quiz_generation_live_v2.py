from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentChunk,
    DocumentSection,
    Question,
    Quiz,
    TopicMastery,
    User,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50004),
)

RUN_ID = uuid4().hex[:10]
EMAIL = f"api-phase3c-{RUN_ID}@example.com"
PASSWORD = "Password123!"


DOCUMENT_TEXT = """CHƯƠNG 1: TIỀN TỆ VÀ CÁC CHỨC NĂNG CƠ BẢN

Tiền tệ là một hàng hóa đặc biệt được tách ra làm vật ngang giá chung
cho thế giới hàng hóa.

Tiền tệ có năm chức năng cơ bản.

Thước đo giá trị là chức năng dùng tiền để đo lường và biểu hiện giá trị
của hàng hóa. Giá trị hàng hóa biểu hiện bằng tiền được gọi là giá cả.

Phương tiện lưu thông là chức năng trong đó tiền làm môi giới cho quá
trình trao đổi hàng hóa.

Phương tiện cất trữ là chức năng trong đó tiền được rút khỏi lưu thông
và được giữ lại để sử dụng trong tương lai.

Phương tiện thanh toán là chức năng trong đó tiền được dùng để trả nợ,
nộp thuế hoặc thanh toán các nghĩa vụ đến hạn.

Tiền tệ thế giới là chức năng của tiền trong thanh toán và trao đổi
kinh tế quốc tế.

Năm chức năng trên có nội dung khác nhau. Muốn xác định đúng chức năng
của tiền cần dựa vào vai trò cụ thể mà tiền thực hiện trong từng tình
huống kinh tế.

Ví dụ, khi một hàng hóa được ghi giá 100 nghìn đồng, tiền đang thực hiện
chức năng thước đo giá trị. Khi người mua giao tiền và nhận hàng ngay,
tiền thực hiện chức năng phương tiện lưu thông. Khi một người giữ tiền
để dành cho tương lai, tiền thực hiện chức năng phương tiện cất trữ.
Khi một khoản nợ đến hạn được trả bằng tiền, tiền thực hiện chức năng
phương tiện thanh toán.
"""


def check(
    label: str,
    response,
    expected: int,
) -> None:
    actual = response.status_code

    if actual != expected:
        body = response.text

        if len(body) > 2200:
            body = body[:2200] + "..."

        raise AssertionError(
            f"{label}: expected HTTP {expected}, "
            f"got {actual}\nResponse: {body}"
        )

    print(f"{label:<70} PASS ({actual})")


def bearer(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


def cleanup() -> None:
    db = SessionLocal()

    try:
        user = db.scalar(
            select(User).where(
                User.email == EMAIL
            )
        )

        if user is not None:
            documents = list(
                db.scalars(
                    select(Document).where(
                        Document.owner_id == user.id
                    )
                ).all()
            )

            for document in documents:
                if document.storage_url:
                    try:
                        Path(
                            document.storage_url
                        ).unlink(
                            missing_ok=True
                        )
                    except Exception:
                        pass

            db.delete(user)

        db.commit()

        print(
            f"{'Cleanup temporary Phase-3C resources':<70} PASS"
        )

    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            f"Phase-3C cleanup failed: {exc}"
        ) from exc

    finally:
        db.close()


def validate_generated_quiz(
    *,
    quiz_id: int,
    owner_id: int,
    subject_id: int,
    document_id: int,
    section_id: int,
    expected_audit_marker: str | None = None,
) -> None:
    db = SessionLocal()

    try:
        quiz = db.get(
            Quiz,
            quiz_id,
        )

        assert quiz is not None
        assert quiz.owner_id == owner_id
        assert quiz.subject_id == subject_id
        assert quiz.generation_mode == "AI"
        assert quiz.question_count == 1
        assert quiz.status == "DRAFT"

        if expected_audit_marker is not None:
            audit = quiz.generation_prompt or ""

            assert expected_audit_marker in audit, (
                expected_audit_marker,
                audit,
            )

        questions = list(
            db.scalars(
                select(Question).where(
                    Question.quiz_id == quiz_id
                )
            ).all()
        )

        assert len(questions) == 1

        question = questions[0]
        assert question.source_chunk_id is not None

        source_chunk = db.get(
            DocumentChunk,
            question.source_chunk_id,
        )

        assert source_chunk is not None
        assert source_chunk.document_id == document_id
        assert source_chunk.section_id == section_id
        assert source_chunk.is_active is True

    finally:
        db.close()


def main() -> None:
    print()
    print("=" * 104)
    print("FULL API INTEGRATION - PHASE 3C V2")
    print("Quiz AI Generation LIVE: Ollama + V6.x quality pipeline + database persistence")
    print("=" * 104)

    try:
        # -------------------------------------------------
        # Setup user
        # -------------------------------------------------
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "full_name": "API Phase Three C",
            },
        )
        check(
            "Setup register Phase 3C user",
            response,
            201,
        )

        registered = response.json()
        token = registered["access_token"]
        owner_id = registered["user"]["id"]

        # -------------------------------------------------
        # Setup subject
        # -------------------------------------------------
        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token),
            json={
                "name":
                    f"Phase 3C Live AI Subject {RUN_ID}",
                "description":
                    "Temporary live AI quiz integration subject",
                "color_hex":
                    "#668844",
            },
        )
        check(
            "Setup POST /subjects",
            response,
            201,
        )

        subject_id = response.json()["id"]

        # -------------------------------------------------
        # Upload document
        # -------------------------------------------------
        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token),
            files={
                "file": (
                    "phase3c_money.txt",
                    DOCUMENT_TEXT.encode("utf-8"),
                    "text/plain",
                )
            },
            data={
                "subject_id": str(subject_id),
                "process_now": "false",
            },
        )
        check(
            "Setup POST /documents/upload",
            response,
            201,
        )

        document_id = response.json()["id"]

        # -------------------------------------------------
        # Process document: structural chunking + embeddings.
        # -------------------------------------------------
        response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=bearer(token),
        )
        check(
            "Setup POST /documents/{id}/process",
            response,
            200,
        )

        processed = response.json()

        assert processed["status"] == "READY"
        assert processed["chunks_created"] >= 1
        assert processed["embeddings_created"] >= 1

        # -------------------------------------------------
        # Build a deterministic section fixture.
        #
        # A tiny synthetic TXT file may legitimately produce
        # active chunks with section_id=NULL because there were
        # no pre-existing DocumentSection rows to map against.
        # Section mapping itself is already covered by dedicated
        # SSA-SBC tests. This Phase focuses on Quiz endpoints.
        #
        # Therefore:
        #   1) create one document section,
        #   2) attach every active test chunk to it,
        #   3) seed WEAK + immediately-due TopicMastery.
        # -------------------------------------------------
        db = SessionLocal()

        try:
            section = DocumentSection(
                document_id=document_id,
                title="Tiền tệ và các chức năng cơ bản",
                section_level=1,
                section_order=1,
            )

            db.add(section)
            db.flush()

            section_id = int(section.id)

            active_chunks = list(
                db.scalars(
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.is_active.is_(True),
                    )
                    .order_by(
                        DocumentChunk.chunk_index
                    )
                ).all()
            )

            assert active_chunks, (
                "Processed test document has no active chunks."
            )

            for chunk in active_chunks:
                chunk.section_id = section_id

            mastery = TopicMastery(
                user_id=owner_id,
                subject_id=subject_id,
                section_id=section_id,
                attempts=2,
                correct_answers=0,
                wrong_answers=2,
                mastery_score=Decimal("0.00"),
                last_practiced_at=None,
            )

            db.add(mastery)
            db.commit()

        finally:
            db.close()

        print(
            f"{'Attach active chunks to deterministic test section':<70} "
            "PASS"
        )
        print(
            f"{'Seed WEAK + immediately-due TopicMastery':<70} "
            "PASS"
        )

        # Verify fixture persisted.
        db = SessionLocal()

        try:
            mapped_chunk_count = len(
                list(
                    db.scalars(
                        select(DocumentChunk.id).where(
                            DocumentChunk.document_id == document_id,
                            DocumentChunk.is_active.is_(True),
                            DocumentChunk.section_id == section_id,
                        )
                    ).all()
                )
            )

            assert mapped_chunk_count >= 1

            seeded_mastery = db.scalar(
                select(TopicMastery).where(
                    TopicMastery.user_id == owner_id,
                    TopicMastery.section_id == section_id,
                )
            )

            assert seeded_mastery is not None
            assert int(seeded_mastery.attempts) == 2
            assert Decimal(
                seeded_mastery.mastery_score
            ) == Decimal("0.00")

        finally:
            db.close()

        print(
            f"{'Section/mastery fixture verification':<70} PASS"
        )

        base_payload = {
            "subject_id": subject_id,
            "difficulty": "MEDIUM",
            "question_count": 1,
            "duration_minutes": 5,
            "document_ids": [
                document_id
            ],
        }

        cases = [
            (
                "/api/v1/quizzes/generate",
                f"Phase 3C Normal Live {RUN_ID}",
                None,
            ),
            (
                "/api/v1/quizzes/generate-weak-topic",
                f"Phase 3C Weak Topic Live {RUN_ID}",
                None,
            ),
            (
                "/api/v1/quizzes/generate-adaptive",
                f"Phase 3C Adaptive Live {RUN_ID}",
                "adaptive_generation=enabled",
            ),
            (
                "/api/v1/quizzes/generate-due",
                f"Phase 3C Due Live {RUN_ID}",
                "due_generation=enabled",
            ),
        ]

        generated_ids: list[int] = []

        for path, title, audit_marker in cases:
            response = client.post(
                path,
                headers=bearer(token),
                json={
                    **base_payload,
                    "title": title,
                },
            )

            check(
                f"POST {path} (LIVE)",
                response,
                201,
            )

            body = response.json()

            assert body["owner_id"] == owner_id
            assert body["subject_id"] == subject_id
            assert body["generation_mode"] == "AI"
            assert body["question_count"] == 1
            assert body["status"] == "DRAFT"

            quiz_id = body["id"]
            generated_ids.append(
                quiz_id
            )

            validate_generated_quiz(
                quiz_id=quiz_id,
                owner_id=owner_id,
                subject_id=subject_id,
                document_id=document_id,
                section_id=section_id,
                expected_audit_marker=audit_marker,
            )

            print(
                f"{'  persisted active source chunk validation':<70} "
                "PASS"
            )

        assert len(
            set(generated_ids)
        ) == 4

        print()
        print("-" * 104)
        print("PHASE 3C LIVE ENDPOINT COVERAGE:")
        print("  POST /quizzes/generate             PASS (LIVE)")
        print("  POST /quizzes/generate-weak-topic  PASS (LIVE)")
        print("  POST /quizzes/generate-adaptive    PASS (LIVE)")
        print("  POST /quizzes/generate-due         PASS (LIVE)")
        print("  AI generation routes LIVE: 4/4")
        print("  Each generated quiz persisted exactly 1 question")
        print("  Each question references an active chunk from the owned document/section")
        print("  Unexpected 5xx: 0")
        print("-" * 104)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 104)


if __name__ == "__main__":
    main()
