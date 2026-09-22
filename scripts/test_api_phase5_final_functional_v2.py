from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentChunk,
    DocumentSection,
    Flashcard,
    Notification,
    Question,
    TopicMastery,
    User,
)
from app.db.session import SessionLocal
from app.main import app
from app.services.gamification_service import add_xp


client = TestClient(
    app,
    client=("127.0.0.1", 50006),
)

RUN_ID = uuid4().hex[:10]
EMAIL_A = f"api-phase5-{RUN_ID}-a@example.com"
EMAIL_B = f"api-phase5-{RUN_ID}-b@example.com"
PASSWORD = "Password123!"

CREATED_EMAILS = [
    EMAIL_A,
    EMAIL_B,
]

EXPORT_FILES: list[Path] = []


DOCUMENT_TEXT = """CHƯƠNG 1: TIỀN TỆ VÀ CÁC CHỨC NĂNG

Tiền tệ là một hàng hóa đặc biệt được tách ra làm vật ngang giá chung.

Tiền tệ có năm chức năng cơ bản: thước đo giá trị, phương tiện lưu thông,
phương tiện cất trữ, phương tiện thanh toán và tiền tệ thế giới.

Thước đo giá trị dùng tiền để đo lường và biểu hiện giá trị hàng hóa.
Phương tiện lưu thông là khi tiền làm môi giới trong trao đổi hàng hóa.
Phương tiện cất trữ là khi tiền được rút khỏi lưu thông và giữ lại.
Phương tiện thanh toán là khi tiền dùng để trả nợ hoặc nghĩa vụ đến hạn.
Tiền tệ thế giới là chức năng của tiền trong quan hệ kinh tế quốc tế.
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

    print(f"{label:<72} PASS ({actual})")


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
        int(body["user"]["id"]),
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
            int(user.id)
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

            # Delete B first because B may fork/share A's resource.
            users.sort(
                key=lambda user: (
                    0 if user.email == EMAIL_B else 1
                )
            )

            for user in users:
                db.delete(user)

        db.commit()

    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            f"Phase-5 DB cleanup failed: {exc}"
        ) from exc

    finally:
        db.close()

    for path in EXPORT_FILES:
        try:
            path.unlink(
                missing_ok=True
            )
        except Exception:
            pass

    print(
        f"{'Cleanup temporary Phase-5 resources/files':<72} PASS"
    )


def create_manual_quiz(
    token: str,
    subject_id: int,
    chunk_id: int,
) -> int:
    response = client.post(
        "/api/v1/quizzes",
        headers=bearer(token),
        json={
            "subject_id": subject_id,
            "title":
                f"Phase 5 Community Quiz {RUN_ID}",
            "description":
                "Temporary community/export quiz",
            "difficulty": "MEDIUM",
            "duration_minutes": 5,
            "visibility": "PRIVATE",
            "document_ids": [],
            "questions": [
                {
                    "question_text":
                        "Tiền tệ có bao nhiêu chức năng cơ bản?",
                    "difficulty":
                        "MEDIUM",
                    "explanation":
                        "Theo tài liệu, tiền tệ có năm chức năng.",
                    "points":
                        1,
                    "source_chunk_id":
                        chunk_id,
                    "options": [
                        {
                            "option_key": "A",
                            "option_text": "Ba",
                            "is_correct": False,
                            "position": 1,
                        },
                        {
                            "option_key": "B",
                            "option_text": "Bốn",
                            "is_correct": False,
                            "position": 2,
                        },
                        {
                            "option_key": "C",
                            "option_text": "Năm",
                            "is_correct": True,
                            "position": 3,
                        },
                        {
                            "option_key": "D",
                            "option_text": "Sáu",
                            "is_correct": False,
                            "position": 4,
                        },
                    ],
                }
            ],
        },
    )

    check(
        "Setup POST /quizzes",
        response,
        201,
    )

    return int(
        response.json()["id"]
    )


def create_manual_deck(
    token: str,
    subject_id: int,
    document_id: int,
    chunk_id: int,
) -> int:
    response = client.post(
        "/api/v1/flashcards/decks",
        headers=bearer(token),
        json={
            "subject_id": subject_id,
            "title":
                f"Phase 5 Community Deck {RUN_ID}",
            "description":
                "Temporary community deck",
            "visibility":
                "PRIVATE",
            "document_ids": [
                document_id
            ],
            "cards": [
                {
                    "front_text":
                        "Tiền tệ có mấy chức năng cơ bản?",
                    "back_text":
                        "Năm chức năng cơ bản.",
                    "source_chunk_id":
                        chunk_id,
                }
            ],
        },
    )

    check(
        "Setup POST /flashcards/decks",
        response,
        201,
    )

    return int(
        response.json()["id"]
    )


def main() -> None:
    print()
    print("=" * 108)
    print("FULL API INTEGRATION - PHASE 5 FINAL FUNCTIONAL")
    print("Analytics 4 + Gamification 1 + Community 5 + Exports 2 + Notifications 2")
    print("=" * 108)

    try:
        token_a, user_a = register(
            EMAIL_A,
            "API Phase Five A",
        )

        token_b, user_b = register(
            EMAIL_B,
            "API Phase Five B",
        )

        # =================================================
        # Shared setup: subjects + READY document + section
        # =================================================
        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_a),
            json={
                "name":
                    f"Phase 5 Subject A {RUN_ID}",
                "description":
                    "Analytics/community/export subject",
                "color_hex":
                    "#5577AA",
            },
        )
        check(
            "Setup POST /subjects A",
            response,
            201,
        )
        subject_a = int(
            response.json()["id"]
        )

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_b),
            json={
                "name":
                    f"Phase 5 Subject B {RUN_ID}",
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

        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token_a),
            files={
                "file": (
                    "phase5_money.txt",
                    DOCUMENT_TEXT.encode("utf-8"),
                    "text/plain",
                )
            },
            data={
                "subject_id":
                    str(subject_a),
                "process_now":
                    "false",
            },
        )
        check(
            "Setup POST /documents/upload",
            response,
            201,
        )
        document_id = int(
            response.json()["id"]
        )

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
            section = DocumentSection(
                document_id=document_id,
                title="Tiền tệ và các chức năng",
                section_level=1,
                section_order=1,
            )
            db.add(section)
            db.flush()
            section_id = int(section.id)

            chunks = list(
                db.scalars(
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
                ).all()
            )

            assert chunks

            for chunk in chunks:
                chunk.section_id = section_id

            chunk_id = int(
                chunks[0].id
            )

            db.add(
                TopicMastery(
                    user_id=user_a,
                    subject_id=subject_a,
                    section_id=section_id,
                    attempts=2,
                    correct_answers=1,
                    wrong_answers=1,
                    mastery_score=Decimal("50.00"),
                    last_practiced_at=None,
                )
            )

            # Seed XP through the canonical service so the
            # gamification endpoint returns meaningful data.
            add_xp(
                db,
                user_a,
                7,
                "PHASE5_TEST",
                None,
                "Phase 5 API integration setup",
            )

            notification_a = Notification(
                user_id=user_a,
                notification_type="TEST",
                title="Phase 5 notification A",
                message="Unread notification for user A",
                payload={"run_id": RUN_ID},
                is_read=False,
            )
            notification_b = Notification(
                user_id=user_b,
                notification_type="TEST",
                title="Phase 5 notification B",
                message="Private notification for user B",
                payload={"run_id": RUN_ID},
                is_read=False,
            )

            db.add_all(
                [
                    notification_a,
                    notification_b,
                ]
            )

            db.commit()
            db.refresh(notification_a)
            db.refresh(notification_b)

            notification_a_id = int(
                notification_a.id
            )
            notification_b_id = int(
                notification_b.id
            )

        finally:
            db.close()

        print(
            f"{'Setup section + WEAK mastery + XP + notifications':<72} PASS"
        )

        # =================================================
        # ANALYTICS 4/4
        # =================================================
        analytics_paths = [
            (
                "topic-mastery",
                "/api/v1/analytics/subjects/"
                f"{subject_a}/topic-mastery",
            ),
            (
                "practice-recommendations",
                "/api/v1/analytics/subjects/"
                f"{subject_a}/practice-recommendations",
            ),
            (
                "study-plan",
                "/api/v1/analytics/subjects/"
                f"{subject_a}/study-plan?horizon_days=7",
            ),
            (
                "weak-topics",
                "/api/v1/analytics/subjects/"
                f"{subject_a}/weak-topics",
            ),
        ]

        for label, path in analytics_paths:
            response = client.get(
                path,
                headers=bearer(token_a),
            )
            check(
                f"GET analytics/{label} owner",
                response,
                200,
            )

            body = response.json()
            assert (
                int(body["subject_id"])
                == subject_a
            )

        response = client.get(
            "/api/v1/analytics/subjects/"
            f"{subject_a}/topic-mastery",
            headers=bearer(token_b),
        )
        check(
            "GET analytics foreign subject",
            response,
            404,
        )

        response = client.get(
            "/api/v1/analytics/subjects/"
            f"{subject_a}/study-plan?horizon_days=0",
            headers=bearer(token_a),
        )
        check(
            "GET analytics study-plan invalid horizon",
            response,
            400,
        )

        # Verify the seeded topic is WEAK.
        response = client.get(
            "/api/v1/analytics/subjects/"
            f"{subject_a}/topic-mastery",
            headers=bearer(token_a),
        )
        topics = response.json()["topics"]

        assert len(topics) == 1
        assert topics[0]["status"] == "WEAK"
        assert float(
            topics[0]["mastery_score"]
        ) == 50.0

        # =================================================
        # GAMIFICATION 1/1
        # =================================================
        response = client.get(
            "/api/v1/gamification/me",
            headers=bearer(token_a),
        )
        check(
            "GET /gamification/me",
            response,
            200,
        )

        gam = response.json()
        assert int(gam["xp_total"]) >= 7
        assert any(
            tx["source_type"]
            == "PHASE5_TEST"
            for tx in gam["recent_xp"]
        )

        # =================================================
        # COMMUNITY setup resources
        # =================================================
        quiz_id = create_manual_quiz(
            token_a,
            subject_a,
            chunk_id,
        )

        deck_id = create_manual_deck(
            token_a,
            subject_a,
            document_id,
            chunk_id,
        )

        # =================================================
        # COMMUNITY 1/5: GET public posts (unauthenticated)
        # =================================================
        response = client.get(
            "/api/v1/community/posts"
        )
        check(
            "GET /community/posts unauthenticated",
            response,
            200,
        )

        # =================================================
        # COMMUNITY 2/5: POST post
        # Foreign resource cannot be published.
        # =================================================
        response = client.post(
            "/api/v1/community/posts",
            headers=bearer(token_b),
            json={
                "quiz_id": quiz_id,
                "title": "Foreign publish attempt",
            },
        )
        check(
            "POST /community/posts foreign quiz",
            response,
            404,
        )

        response = client.post(
            "/api/v1/community/posts",
            headers=bearer(token_a),
            json={
                "quiz_id": quiz_id,
                "title":
                    f"Phase 5 Quiz Post {RUN_ID}",
                "description":
                    "Public quiz integration post",
            },
        )
        check(
            "POST /community/posts quiz owner",
            response,
            201,
        )
        quiz_post_id = int(
            response.json()["id"]
        )

        # Create a second post for deck fork isolation.
        response = client.post(
            "/api/v1/community/posts",
            headers=bearer(token_a),
            json={
                "flashcard_deck_id": deck_id,
                "title":
                    f"Phase 5 Deck Post {RUN_ID}",
            },
        )
        check(
            "POST /community/posts deck owner",
            response,
            201,
        )
        deck_post_id = int(
            response.json()["id"]
        )

        response = client.get(
            "/api/v1/community/posts"
        )
        check(
            "GET /community/posts after publish",
            response,
            200,
        )

        public_posts = response.json()

        assert any(
            int(post["post_id"]) == quiz_post_id
            for post in public_posts
        )
        assert any(
            int(post["post_id"]) == deck_post_id
            for post in public_posts
        )

        # =================================================
        # COMMUNITY 3/5: like toggle
        # =================================================
        response = client.post(
            f"/api/v1/community/posts/{quiz_post_id}/like",
            headers=bearer(token_b),
        )
        check(
            "POST /community/posts/{id}/like on",
            response,
            200,
        )
        assert response.json()["liked"] is True

        response = client.post(
            f"/api/v1/community/posts/{quiz_post_id}/like",
            headers=bearer(token_b),
        )
        check(
            "POST /community/posts/{id}/like off",
            response,
            200,
        )
        assert response.json()["liked"] is False

        # =================================================
        # COMMUNITY 4/5: save toggle
        # =================================================
        response = client.post(
            f"/api/v1/community/posts/{quiz_post_id}/save",
            headers=bearer(token_b),
        )
        check(
            "POST /community/posts/{id}/save on",
            response,
            200,
        )
        assert response.json()["saved"] is True

        response = client.post(
            f"/api/v1/community/posts/{quiz_post_id}/save",
            headers=bearer(token_b),
        )
        check(
            "POST /community/posts/{id}/save off",
            response,
            200,
        )
        assert response.json()["saved"] is False

        # =================================================
        # COMMUNITY 5/5: fork.
        # Verify foreign source_chunk_id is cleared.
        # =================================================
        response = client.post(
            f"/api/v1/community/posts/{quiz_post_id}/fork",
            headers=bearer(token_b),
        )
        check(
            "POST /community/posts/{id}/fork quiz",
            response,
            200,
        )

        assert (
            response.json()["resource_type"]
            == "QUIZ"
        )
        forked_quiz_id = int(
            response.json()["resource_id"]
        )

        response = client.post(
            f"/api/v1/community/posts/{deck_post_id}/fork",
            headers=bearer(token_b),
        )
        check(
            "POST /community/posts/{id}/fork deck",
            response,
            200,
        )

        assert (
            response.json()["resource_type"]
            == "FLASHCARD_DECK"
        )
        forked_deck_id = int(
            response.json()["resource_id"]
        )

        db = SessionLocal()

        try:
            forked_questions = list(
                db.scalars(
                    select(Question).where(
                        Question.quiz_id
                        == forked_quiz_id
                    )
                ).all()
            )

            assert forked_questions
            assert all(
                question.source_chunk_id is None
                for question in forked_questions
            )

            forked_cards = list(
                db.scalars(
                    select(Flashcard).where(
                        Flashcard.deck_id
                        == forked_deck_id
                    )
                ).all()
            )

            assert forked_cards
            assert all(
                card.source_chunk_id is None
                for card in forked_cards
            )

        finally:
            db.close()

        print(
            f"{'Community fork foreign-source isolation':<72} PASS"
        )

        # =================================================
        # EXPORTS 2/2
        # =================================================

        # Foreign user cannot export A's resource.
        response = client.post(
            "/api/v1/exports",
            headers=bearer(token_b),
            json={
                "resource_type": "QUIZ",
                "resource_id": quiz_id,
                "file_format": "DOCX",
            },
        )
        check(
            "POST /exports foreign quiz",
            response,
            422,
        )

        response = client.post(
            "/api/v1/exports",
            headers=bearer(token_a),
            json={
                "resource_type": "QUIZ",
                "resource_id": quiz_id,
                "file_format": "DOCX",
            },
        )
        check(
            "POST /exports owner DOCX",
            response,
            201,
        )

        export_body = response.json()

        assert (
            export_body["status"]
            == "COMPLETED"
        )
        assert (
            export_body["file_format"]
            == "DOCX"
        )
        assert export_body["file_url"]

        export_path = Path(
            export_body["file_url"]
        )
        assert export_path.exists()
        EXPORT_FILES.append(
            export_path
        )

        response = client.get(
            "/api/v1/exports",
            headers=bearer(token_a),
        )
        check(
            "GET /exports owner",
            response,
            200,
        )

        assert any(
            int(job["id"])
            == int(export_body["id"])
            for job in response.json()
        )

        response = client.get(
            "/api/v1/exports",
            headers=bearer(token_b),
        )
        check(
            "GET /exports foreign list isolation",
            response,
            200,
        )

        assert all(
            int(job["id"])
            != int(export_body["id"])
            for job in response.json()
        )

        # =================================================
        # NOTIFICATIONS 2/2
        # =================================================
        response = client.get(
            "/api/v1/notifications?unread_only=true",
            headers=bearer(token_a),
        )
        check(
            "GET /notifications unread_only",
            response,
            200,
        )

        notifications_a = response.json()

        assert any(
            int(item["id"])
            == notification_a_id
            for item in notifications_a
        )
        assert all(
            int(item["id"])
            != notification_b_id
            for item in notifications_a
        )

        response = client.post(
            f"/api/v1/notifications/{notification_b_id}/read",
            headers=bearer(token_a),
        )
        check(
            "POST /notifications/{id}/read foreign",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/notifications/{notification_a_id}/read",
            headers=bearer(token_a),
        )
        check(
            "POST /notifications/{id}/read owner",
            response,
            200,
        )

        assert response.json()["ok"] is True

        response = client.get(
            "/api/v1/notifications?unread_only=true",
            headers=bearer(token_a),
        )
        check(
            "GET /notifications after read",
            response,
            200,
        )

        assert all(
            int(item["id"])
            != notification_a_id
            for item in response.json()
        )

        print()
        print("-" * 108)
        print("PHASE 5 ENDPOINT COVERAGE:")
        print("  Analytics      : 4/4 endpoints exercised")
        print("  Gamification   : 1/1 endpoint exercised")
        print("  Community      : 5/5 endpoints exercised")
        print("  Exports        : 2/2 endpoints exercised")
        print("  Notifications  : 2/2 endpoints exercised")
        print("  Phase 5        : 14/14 API endpoints exercised")
        print("  Ownership/isolation probes: PASS")
        print("  Community fork source isolation: PASS")
        print("  Real DOCX export file: PASS")
        print("  Unexpected 5xx: 0")
        print("-" * 108)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 108)


if __name__ == "__main__":
    main()
