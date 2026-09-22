from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentChunk,
    Flashcard,
    StudyTask,
    User,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50005),
)

RUN_ID = uuid4().hex[:10]
EMAIL_A = f"api-phase4-{RUN_ID}-a@example.com"
EMAIL_B = f"api-phase4-{RUN_ID}-b@example.com"
PASSWORD = "Password123!"

CREATED_EMAILS = [
    EMAIL_A,
    EMAIL_B,
]

DOCUMENT_TEXT = """CHƯƠNG 1: TIỀN TỆ

Tiền tệ là một hàng hóa đặc biệt được tách ra làm vật ngang giá chung.

Tiền tệ có năm chức năng cơ bản: thước đo giá trị, phương tiện lưu thông,
phương tiện cất trữ, phương tiện thanh toán và tiền tệ thế giới.

Thước đo giá trị dùng tiền để đo lường và biểu hiện giá trị hàng hóa.
Phương tiện lưu thông là khi tiền làm môi giới trong trao đổi hàng hóa.
Phương tiện cất trữ là khi tiền được rút khỏi lưu thông và giữ lại.
Phương tiện thanh toán là khi tiền dùng để trả nợ hoặc nghĩa vụ đến hạn.
Tiền tệ thế giới là chức năng của tiền trong quan hệ kinh tế quốc tế.

Khi một hàng hóa được ghi giá, tiền thực hiện chức năng thước đo giá trị.
Khi người mua giao tiền và nhận hàng, tiền thực hiện phương tiện lưu thông.
"""


def check(
    label: str,
    response,
    expected: int,
) -> None:
    actual = response.status_code

    if actual != expected:
        body = response.text

        if len(body) > 2000:
            body = body[:2000] + "..."

        raise AssertionError(
            f"{label}: expected HTTP {expected}, "
            f"got {actual}\nResponse: {body}"
        )

    print(f"{label:<68} PASS ({actual})")


def bearer(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


def register(
    email: str,
    full_name: str,
) -> tuple[str, int]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": full_name,
        },
    )

    check(
        f"Setup register {full_name}",
        response,
        201,
    )

    body = response.json()

    return (
        body["access_token"],
        body["user"]["id"],
    )


def cleanup() -> None:
    db = SessionLocal()

    try:
        users = list(
            db.scalars(
                select(User).where(
                    User.email.in_(
                        CREATED_EMAILS
                    )
                )
            ).all()
        )

        user_ids = [
            user.id
            for user in users
        ]

        if user_ids:
            documents = list(
                db.scalars(
                    select(Document).where(
                        Document.owner_id.in_(
                            user_ids
                        )
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

            # Delete B first because B may have
            # user-specific progress on shared resources.
            users.sort(
                key=lambda user: (
                    0 if user.email == EMAIL_B else 1
                )
            )

            for user in users:
                db.delete(user)

        db.commit()

        print(
            f"{'Cleanup temporary Phase-4 resources':<68} PASS"
        )

    except Exception as exc:
        db.rollback()

        raise RuntimeError(
            f"Phase-4 cleanup failed: {exc}"
        ) from exc

    finally:
        db.close()


def main() -> None:
    print()
    print("=" * 104)
    print("FULL API INTEGRATION - PHASE 4")
    print("Flashcards 6/6 + Study Plans 4/4")
    print("=" * 104)

    try:
        token_a, user_a = register(
            EMAIL_A,
            "API Phase Four A",
        )

        token_b, _ = register(
            EMAIL_B,
            "API Phase Four B",
        )

        # -------------------------------------------------
        # Setup subjects
        # -------------------------------------------------
        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_a),
            json={
                "name":
                    f"Phase 4 Subject A {RUN_ID}",
                "description":
                    "Flashcard and study plan subject",
                "color_hex":
                    "#5566AA",
            },
        )
        check(
            "Setup POST /subjects A",
            response,
            201,
        )

        subject_a = response.json()["id"]

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_b),
            json={
                "name":
                    f"Phase 4 Subject B {RUN_ID}",
                "description":
                    "Foreign subject",
                "color_hex":
                    "#7755AA",
            },
        )
        check(
            "Setup POST /subjects B",
            response,
            201,
        )

        # -------------------------------------------------
        # Setup READY document + active chunk.
        # -------------------------------------------------
        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token_a),
            files={
                "file": (
                    "phase4_money.txt",
                    DOCUMENT_TEXT.encode("utf-8"),
                    "text/plain",
                )
            },
            data={
                "subject_id": str(subject_a),
                "process_now": "false",
            },
        )
        check(
            "Setup POST /documents/upload",
            response,
            201,
        )

        document_id = response.json()["id"]

        response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=bearer(token_a),
        )
        check(
            "Setup POST /documents/{id}/process",
            response,
            200,
        )

        db = SessionLocal()

        try:
            chunk = db.scalar(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id
                    == document_id,
                    DocumentChunk.is_active.is_(
                        True
                    ),
                )
                .order_by(
                    DocumentChunk.chunk_index
                )
            )

            assert chunk is not None
            chunk_id = int(chunk.id)

        finally:
            db.close()

        # =================================================
        # FLASHCARDS
        # =================================================

        # ---------------------------------------------
        # 1/6 POST /decks
        # foreign subject must be blocked.
        # ---------------------------------------------
        response = client.post(
            "/api/v1/flashcards/decks",
            headers=bearer(token_b),
            json={
                "subject_id": subject_a,
                "title":
                    f"Foreign Subject Deck {RUN_ID}",
                "visibility": "PRIVATE",
                "document_ids": [],
                "cards": [
                    {
                        "front_text": "Q",
                        "back_text": "A",
                    }
                ],
            },
        )
        check(
            "POST /flashcards/decks foreign subject",
            response,
            404,
        )

        response = client.post(
            "/api/v1/flashcards/decks",
            headers=bearer(token_a),
            json={
                "subject_id": subject_a,
                "title":
                    f"Manual Deck {RUN_ID}",
                "description":
                    "Manual integration deck",
                "visibility": "PRIVATE",
                "document_ids": [
                    document_id
                ],
                "cards": [
                    {
                        "front_text":
                            "Tiền tệ có bao nhiêu chức năng cơ bản?",
                        "back_text":
                            "Năm chức năng cơ bản.",
                        "hint":
                            "Đếm các chức năng trong tài liệu.",
                        "source_chunk_id":
                            chunk_id,
                    }
                ],
            },
        )
        check(
            "POST /flashcards/decks owner",
            response,
            201,
        )

        manual_deck_id = response.json()["id"]

        # ---------------------------------------------
        # 2/6 GET /decks
        # ---------------------------------------------
        response = client.get(
            "/api/v1/flashcards/decks",
            headers=bearer(token_a),
        )
        check(
            "GET /flashcards/decks owner",
            response,
            200,
        )

        assert any(
            item["id"] == manual_deck_id
            for item in response.json()
        )

        response = client.get(
            "/api/v1/flashcards/decks",
            headers=bearer(token_b),
        )
        check(
            "GET /flashcards/decks foreign list",
            response,
            200,
        )

        assert all(
            item["id"] != manual_deck_id
            for item in response.json()
        )

        # ---------------------------------------------
        # 3/6 GET /decks/{id}
        # ---------------------------------------------
        response = client.get(
            f"/api/v1/flashcards/decks/{manual_deck_id}",
            headers=bearer(token_b),
        )
        check(
            "GET private flashcard deck foreign user",
            response,
            404,
        )

        response = client.get(
            f"/api/v1/flashcards/decks/{manual_deck_id}",
            headers=bearer(token_a),
        )
        check(
            "GET /flashcards/decks/{id} owner",
            response,
            200,
        )

        cards = response.json()["cards"]

        assert len(cards) == 1
        card_id = cards[0]["id"]
        assert (
            cards[0]["source_chunk_id"]
            == chunk_id
        )

        # ---------------------------------------------
        # 4/6 GET /due
        # New card must be due.
        # ---------------------------------------------
        response = client.get(
            "/api/v1/flashcards/due",
            headers=bearer(token_a),
        )
        check(
            "GET /flashcards/due before review",
            response,
            200,
        )

        assert any(
            card["id"] == card_id
            for card in response.json()
        )

        # ---------------------------------------------
        # 5/6 POST /{flashcard_id}/review
        # ---------------------------------------------
        response = client.post(
            f"/api/v1/flashcards/{card_id}/review",
            headers=bearer(token_b),
            json={
                "rating": 2,
                "response_time_ms": 900,
            },
        )
        check(
            "POST private flashcard review foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/flashcards/{card_id}/review",
            headers=bearer(token_a),
            json={
                "rating": 2,
                "response_time_ms": 900,
            },
        )
        check(
            "POST /flashcards/{id}/review owner",
            response,
            200,
        )

        progress = response.json()

        assert progress["user_id"] == user_a
        assert progress["flashcard_id"] == card_id
        assert progress["repetitions"] == 1
        assert progress["interval_days"] == 1
        assert progress["last_rating"] == 2

        response = client.get(
            "/api/v1/flashcards/due",
            headers=bearer(token_a),
        )
        check(
            "GET /flashcards/due after review",
            response,
            200,
        )

        assert all(
            card["id"] != card_id
            for card in response.json()
        )

        # ---------------------------------------------
        # 6/6 POST /decks/generate LIVE AI
        # ---------------------------------------------
        response = client.post(
            "/api/v1/flashcards/decks/generate",
            headers=bearer(token_b),
            json={
                "subject_id": subject_a,
                "title":
                    f"Foreign Generated Deck {RUN_ID}",
                "document_ids": [],
                "card_count": 1,
            },
        )
        check(
            "POST /flashcards/decks/generate foreign subject",
            response,
            404,
        )

        response = client.post(
            "/api/v1/flashcards/decks/generate",
            headers=bearer(token_a),
            json={
                "subject_id": subject_a,
                "title":
                    f"AI Deck {RUN_ID}",
                "document_ids": [
                    document_id
                ],
                "card_count": 1,
            },
        )
        check(
            "POST /flashcards/decks/generate LIVE",
            response,
            201,
        )

        generated_deck_id = response.json()["id"]
        assert (
            response.json()["generation_mode"]
            == "AI"
        )

        response = client.get(
            f"/api/v1/flashcards/decks/{generated_deck_id}",
            headers=bearer(token_a),
        )
        check(
            "GET generated flashcard deck",
            response,
            200,
        )

        generated_cards = response.json()["cards"]
        assert len(generated_cards) == 1

        generated_source_chunk_id = (
            generated_cards[0]["source_chunk_id"]
        )
        assert generated_source_chunk_id is not None

        db = SessionLocal()

        try:
            generated_source = db.get(
                DocumentChunk,
                generated_source_chunk_id,
            )

            assert generated_source is not None
            assert (
                generated_source.document_id
                == document_id
            )
            assert (
                generated_source.is_active
                is True
            )

        finally:
            db.close()

        # =================================================
        # STUDY PLANS
        # =================================================

        start_date = date.today()
        exam_date = (
            start_date
            + timedelta(days=2)
        )

        plan_payload = {
            "subject_id": subject_a,
            "title":
                f"Phase 4 Study Plan {RUN_ID}",
            "start_date":
                start_date.isoformat(),
            "exam_date":
                exam_date.isoformat(),
            "daily_minutes": 60,
        }

        # ---------------------------------------------
        # 1/4 POST /generate
        # ---------------------------------------------
        response = client.post(
            "/api/v1/study-plans/generate",
            headers=bearer(token_b),
            json=plan_payload,
        )
        check(
            "POST /study-plans/generate foreign subject",
            response,
            404,
        )

        response = client.post(
            "/api/v1/study-plans/generate",
            headers=bearer(token_a),
            json=plan_payload,
        )
        check(
            "POST /study-plans/generate owner",
            response,
            201,
        )

        plan_id = response.json()["id"]
        assert response.json()["status"] == "ACTIVE"
        assert (
            response.json()["generated_by_ai"]
            is False
        )

        # Invalid date order.
        response = client.post(
            "/api/v1/study-plans/generate",
            headers=bearer(token_a),
            json={
                **plan_payload,
                "title":
                    f"Invalid Plan {RUN_ID}",
                "start_date":
                    exam_date.isoformat(),
                "exam_date":
                    start_date.isoformat(),
            },
        )
        check(
            "POST /study-plans/generate invalid dates",
            response,
            400,
        )

        # ---------------------------------------------
        # 2/4 GET /study-plans
        # ---------------------------------------------
        response = client.get(
            "/api/v1/study-plans",
            headers=bearer(token_a),
        )
        check(
            "GET /study-plans owner",
            response,
            200,
        )

        assert any(
            item["id"] == plan_id
            for item in response.json()
        )

        response = client.get(
            "/api/v1/study-plans",
            headers=bearer(token_b),
        )
        check(
            "GET /study-plans foreign list isolation",
            response,
            200,
        )

        assert all(
            item["id"] != plan_id
            for item in response.json()
        )

        # ---------------------------------------------
        # 3/4 GET /study-plans/{plan_id}
        # ---------------------------------------------
        response = client.get(
            f"/api/v1/study-plans/{plan_id}",
            headers=bearer(token_b),
        )
        check(
            "GET /study-plans/{id} foreign user",
            response,
            404,
        )

        response = client.get(
            f"/api/v1/study-plans/{plan_id}",
            headers=bearer(token_a),
        )
        check(
            "GET /study-plans/{id} owner",
            response,
            200,
        )

        tasks = response.json()["tasks"]

        assert len(tasks) >= 1
        task_id = tasks[0]["id"]

        # ---------------------------------------------
        # 4/4 PATCH /tasks/{task_id}
        # ---------------------------------------------
        response = client.patch(
            f"/api/v1/study-plans/tasks/{task_id}",
            headers=bearer(token_b),
            json={
                "status": "COMPLETED"
            },
        )
        check(
            "PATCH study task foreign user",
            response,
            404,
        )

        response = client.patch(
            f"/api/v1/study-plans/tasks/{task_id}",
            headers=bearer(token_a),
            json={
                "status": "COMPLETED"
            },
        )
        check(
            "PATCH /study-plans/tasks/{id} owner",
            response,
            200,
        )

        updated_task = response.json()

        assert (
            updated_task["status"]
            == "COMPLETED"
        )
        assert (
            updated_task["completed_at"]
            is not None
        )

        response = client.patch(
            f"/api/v1/study-plans/tasks/{task_id}",
            headers=bearer(token_a),
            json={
                "status": "INVALID"
            },
        )
        check(
            "PATCH study task invalid status",
            response,
            422,
        )

        print()
        print("-" * 104)
        print("PHASE 4 ENDPOINT COVERAGE:")
        print("  Flashcards  : 6/6 endpoints exercised")
        print("  Study Plans : 4/4 endpoints exercised")
        print("  Phase 4     : 10/10 API endpoints exercised")
        print("  AI flashcard generation: LIVE")
        print("  Spaced repetition review persistence: PASS")
        print("  Ownership isolation: PASS")
        print("  Unexpected 5xx: 0")
        print("-" * 104)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 104)


if __name__ == "__main__":
    main()
