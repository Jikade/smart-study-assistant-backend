from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentChunk,
    DocumentSection,
    User,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50110),
)

RUN_ID = uuid4().hex[:10]
EMAIL = f"analytics-flow-{RUN_ID}@example.com"
PASSWORD = "Password123!"

DOCUMENT_TEXT = (
    "Phân công lao động xã hội là sự phân chia lao động xã hội thành "
    "các ngành và nghề khác nhau, làm cho mỗi người sản xuất một hoặc "
    "một vài sản phẩm nhất định và tạo ra sự phụ thuộc lẫn nhau.\n\n"
    "Tiền tệ có chức năng thước đo giá trị. Chức năng này dùng tiền "
    "để đo lường và biểu hiện giá trị của các hàng hóa khác."
)


class _NoEmbeddingProvider:
    can_embed = False
    can_chat = False


def check(label: str, response, expected: int) -> None:
    actual = response.status_code
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected}, got {actual}\n"
            f"{response.text[:1800]}"
        )
    print(f"{label:<72} PASS ({actual})")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def cleanup() -> None:
    db = SessionLocal()
    try:
        user = db.scalar(
            select(User).where(
                User.email == EMAIL
            )
        )

        if user is not None:
            docs = list(
                db.scalars(
                    select(Document).where(
                        Document.owner_id == user.id
                    )
                ).all()
            )
            for doc in docs:
                if doc.storage_url:
                    try:
                        Path(doc.storage_url).unlink(
                            missing_ok=True
                        )
                    except Exception:
                        pass
            db.delete(user)

        db.commit()
        print(f"{'Cleanup temporary learning-flow resources':<72} PASS")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    print()
    print("=" * 104)
    print("SYSTEM LEARNING INTEGRITY V1 — REAL QUIZ → MASTERY → ANALYTICS FLOW")
    print("=" * 104)

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "full_name": "Analytics Flow Test",
            },
        )
        check("Register", response, 201)
        token = response.json()["access_token"]

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token),
            json={
                "name": f"Analytics Flow {RUN_ID}",
                "description": "End-to-end mastery test",
                "color_hex": "#557799",
            },
        )
        check("Create subject", response, 201)
        subject_id = response.json()["id"]

        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token),
            files={
                "file": (
                    "analytics_flow.txt",
                    DOCUMENT_TEXT.encode("utf-8"),
                    "text/plain",
                )
            },
            data={
                "subject_id": str(subject_id),
                "process_now": "false",
            },
        )
        check("Upload headingless document", response, 201)
        document_id = response.json()["id"]

        with patch(
            "app.services.document_service.get_ai_provider",
            return_value=_NoEmbeddingProvider(),
        ):
            response = client.post(
                f"/api/v1/documents/{document_id}/process",
                headers=bearer(token),
            )

        check("Process document with section bootstrap", response, 200)

        db = SessionLocal()
        try:
            sections = list(
                db.scalars(
                    select(DocumentSection)
                    .where(
                        DocumentSection.document_id == document_id
                    )
                    .order_by(DocumentSection.section_order)
                ).all()
            )
            assert len(sections) == 1, (
                f"Expected one synthetic section, got {len(sections)}"
            )

            chunk = db.scalar(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.is_active.is_(True),
                )
                .order_by(DocumentChunk.chunk_index)
            )
            assert chunk is not None
            assert chunk.section_id == sections[0].id, (
                "Active headingless chunk must inherit the synthetic section"
            )

            chunk_id = int(chunk.id)
            section_id = int(sections[0].id)
        finally:
            db.close()

        print("Synthetic section exists and owns active chunk                PASS")

        quiz_payload = {
            "subject_id": subject_id,
            "title": f"Analytics E2E Quiz {RUN_ID}",
            "description": "Manual quiz with real source ownership",
            "difficulty": "MEDIUM",
            "duration_minutes": 5,
            "visibility": "PRIVATE",
            "document_ids": [document_id],
            "questions": [
                {
                    "question_text":
                        "Chức năng nào của tiền dùng để đo lường và biểu hiện giá trị hàng hóa?",
                    "difficulty": "MEDIUM",
                    "points": 1,
                    "source_chunk_id": chunk_id,
                    "options": [
                        {
                            "option_key": "A",
                            "option_text": "Thước đo giá trị",
                            "is_correct": True,
                            "position": 1,
                        },
                        {
                            "option_key": "B",
                            "option_text": "Phương tiện cất trữ",
                            "is_correct": False,
                            "position": 2,
                        },
                        {
                            "option_key": "C",
                            "option_text": "Phương tiện thanh toán",
                            "is_correct": False,
                            "position": 3,
                        },
                        {
                            "option_key": "D",
                            "option_text": "Tiền tệ thế giới",
                            "is_correct": False,
                            "position": 4,
                        },
                    ],
                }
            ],
        }

        response = client.post(
            "/api/v1/quizzes",
            headers=bearer(token),
            json=quiz_payload,
        )
        check("Create source-grounded manual quiz", response, 201)
        quiz_id = response.json()["id"]

        response = client.get(
            f"/api/v1/quizzes/{quiz_id}",
            headers=bearer(token),
        )
        check("Read quiz and answer key", response, 200)
        q = response.json()["questions"][0]
        question_id = q["id"]
        correct_id = next(
            o["id"] for o in q["options"] if o["is_correct"]
        )
        wrong_id = next(
            o["id"] for o in q["options"] if not o["is_correct"]
        )

        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/attempts",
            headers=bearer(token),
        )
        check("Start attempt 1", response, 201)
        attempt_id = response.json()["attempt_id"]

        response = client.post(
            f"/api/v1/quizzes/attempts/{attempt_id}/submit",
            headers=bearer(token),
            json={
                "answers": [
                    {
                        "question_id": question_id,
                        "selected_option_id": correct_id,
                    }
                ]
            },
        )
        check("Submit correct attempt", response, 200)

        response = client.get(
            f"/api/v1/analytics/subjects/{subject_id}/topic-mastery",
            headers=bearer(token),
        )
        check("Analytics after attempt 1", response, 200)
        mastery = next(
            x for x in response.json()["topics"]
            if x["section_id"] == section_id
        )
        assert mastery["attempts"] == 1
        assert mastery["correct_answers"] == 1
        assert float(mastery["mastery_score"]) == 100.0
        assert mastery["status"] == "NOT_ENOUGH_DATA"
        print("Attempt 1 persisted into TopicMastery                         PASS")

        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/attempts",
            headers=bearer(token),
        )
        check("Start attempt 2", response, 201)
        attempt_id = response.json()["attempt_id"]

        response = client.post(
            f"/api/v1/quizzes/attempts/{attempt_id}/submit",
            headers=bearer(token),
            json={
                "answers": [
                    {
                        "question_id": question_id,
                        "selected_option_id": wrong_id,
                    }
                ]
            },
        )
        check("Submit wrong attempt", response, 200)

        response = client.get(
            f"/api/v1/analytics/subjects/{subject_id}/topic-mastery",
            headers=bearer(token),
        )
        check("Analytics after attempt 2", response, 200)
        mastery = next(
            x for x in response.json()["topics"]
            if x["section_id"] == section_id
        )
        assert mastery["attempts"] == 2
        assert mastery["correct_answers"] == 1
        assert mastery["wrong_answers"] == 1
        assert float(mastery["mastery_score"]) == 50.0
        assert mastery["status"] == "WEAK"
        print("Second attempt changes mastery to 50% / WEAK                   PASS")

        response = client.get(
            f"/api/v1/analytics/subjects/{subject_id}/weak-topics",
            headers=bearer(token),
        )
        check("Weak-topics endpoint sees learned section", response, 200)
        assert response.json()["count"] >= 1
        assert any(
            x["section_id"] == section_id
            for x in response.json()["topics"]
        )

        response = client.get(
            f"/api/v1/analytics/subjects/{subject_id}/practice-recommendations",
            headers=bearer(token),
        )
        check("Recommendations see weak section", response, 200)
        assert any(
            x["section_id"] == section_id
            for x in response.json()["recommendations"]
        )

        print()
        print("-" * 104)
        print("RESULT: PASS — upload/process creates measurable sections and quiz attempts")
        print("update topic mastery consumed by analytics/recommendations.")
        print("-" * 104)

    finally:
        cleanup()


if __name__ == "__main__":
    main()
