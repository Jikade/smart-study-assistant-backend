
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50003),
)

RUN_ID = uuid4().hex[:10]
EMAIL = f"api-phase3b-{RUN_ID}@example.com"
PASSWORD = "Password123!"


def check(label: str, response, expected: int) -> None:
    actual = response.status_code

    if actual != expected:
        body = response.text
        if len(body) > 1600:
            body = body[:1600] + "..."

        raise AssertionError(
            f"{label}: expected HTTP {expected}, got {actual}\n"
            f"Response: {body}"
        )

    print(f"{label:<68} PASS ({actual})")


def bearer(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


class StubQuiz:
    def __init__(
        self,
        *,
        quiz_id: int,
        owner_id: int,
        subject_id: int,
        title: str,
        difficulty: str,
        duration_minutes: int | None,
        question_count: int,
    ):
        now = datetime.now(timezone.utc)

        self.id = quiz_id
        self.owner_id = owner_id
        self.subject_id = subject_id
        self.source_quiz_id = None
        self.title = title
        self.description = None
        self.generation_mode = "AI"
        self.difficulty = difficulty
        self.duration_minutes = duration_minutes
        self.question_count = question_count
        self.status = "DRAFT"
        self.visibility = "PRIVATE"
        self.published_at = None
        self.created_at = now
        self.updated_at = now


def cleanup() -> None:
    db = SessionLocal()

    try:
        user = db.scalar(
            select(User).where(
                User.email == EMAIL
            )
        )

        if user is not None:
            db.delete(user)

        db.commit()

        print(
            f"{'Cleanup temporary Phase-3B user':<68} PASS"
        )

    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            f"Phase-3B cleanup failed: {exc}"
        ) from exc

    finally:
        db.close()


def main() -> None:
    print()
    print("=" * 104)
    print("FULL API CONTRACT - PHASE 3B")
    print("Quiz AI Generation Routes: router/auth/schema/response contract")
    print("=" * 104)

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "full_name": "API Phase Three B",
            },
        )
        check(
            "Setup register Phase 3B user",
            response,
            201,
        )

        token = response.json()["access_token"]
        owner_id = response.json()["user"]["id"]

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token),
            json={
                "name": f"Phase 3B Subject {RUN_ID}",
                "description":
                    "AI route contract subject",
                "color_hex": "#557799",
            },
        )
        check(
            "Setup POST /subjects",
            response,
            201,
        )

        subject_id = response.json()["id"]

        counter = {"value": 900000}

        def stub_generator(
            db,
            owner_id: int,
            payload,
            **kwargs,
        ):
            counter["value"] += 1

            return StubQuiz(
                quiz_id=counter["value"],
                owner_id=owner_id,
                subject_id=payload.subject_id,
                title=payload.title,
                difficulty=payload.difficulty,
                duration_minutes=payload.duration_minutes,
                question_count=payload.question_count,
            )

        payload_base = {
            "subject_id": subject_id,
            "document_ids": [],
            "question_count": 1,
            "difficulty": "MEDIUM",
            "duration_minutes": 5,
        }

        route_cases = [
            (
                "/api/v1/quizzes/generate",
                "generate_quiz",
                "Phase 3B Normal Generate",
            ),
            (
                "/api/v1/quizzes/generate-adaptive",
                "generate_adaptive_quiz",
                "Phase 3B Adaptive Generate",
            ),
            (
                "/api/v1/quizzes/generate-due",
                "generate_due_quiz",
                "Phase 3B Due Generate",
            ),
            (
                "/api/v1/quizzes/generate-weak-topic",
                "generate_weak_topic_quiz",
                "Phase 3B Weak Topic Generate",
            ),
        ]

        for path, function_name, title in route_cases:
            payload = {
                **payload_base,
                "title": f"{title} {RUN_ID}",
            }

            patch_target = (
                "app.api.v1.routers.quizzes."
                + function_name
            )

            with patch(
                patch_target,
                side_effect=stub_generator,
            ) as mocked:
                response = client.post(
                    path,
                    headers=bearer(token),
                    json=payload,
                )

            check(
                f"POST {path}",
                response,
                201,
            )

            body = response.json()

            assert body["owner_id"] == owner_id
            assert body["subject_id"] == subject_id
            assert body["title"] == payload["title"]
            assert body["generation_mode"] == "AI"
            assert body["question_count"] == 1
            assert body["status"] == "DRAFT"
            assert mocked.call_count == 1

        # Validate request schema is active.
        with patch(
            "app.api.v1.routers.quizzes.generate_quiz",
            side_effect=stub_generator,
        ) as mocked:
            response = client.post(
                "/api/v1/quizzes/generate",
                headers=bearer(token),
                json={
                    **payload_base,
                    "title": "",
                },
            )

        check(
            "POST /quizzes/generate invalid title schema",
            response,
            422,
        )

        assert mocked.call_count == 0

        # Auth dependency is active on generation routes.
        response = client.post(
            "/api/v1/quizzes/generate",
            json={
                **payload_base,
                "title":
                    f"Unauthorized Generate {RUN_ID}",
            },
        )

        check(
            "POST /quizzes/generate without token",
            response,
            401,
        )

        print()
        print("-" * 104)
        print("PHASE 3B ENDPOINT COVERAGE:")
        print("  POST /quizzes/generate             PASS (contract)")
        print("  POST /quizzes/generate-adaptive    PASS (contract)")
        print("  POST /quizzes/generate-due         PASS (contract)")
        print("  POST /quizzes/generate-weak-topic  PASS (contract)")
        print("  AI generation routes: 4/4")
        print("  Service algorithms: intentionally NOT mocked in their dedicated V6.x regression suite")
        print("-" * 104)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 104)


if __name__ == "__main__":
    main()
