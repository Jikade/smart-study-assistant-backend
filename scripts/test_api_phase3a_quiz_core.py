
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50002),
)

RUN_ID = uuid4().hex[:10]
EMAIL_A = f"api-phase3-{RUN_ID}-a@example.com"
EMAIL_B = f"api-phase3-{RUN_ID}-b@example.com"
PASSWORD = "Password123!"

CREATED_EMAILS = [
    EMAIL_A,
    EMAIL_B,
]


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

    print(f"{label:<64} PASS ({actual})")


def check_one_of(
    label: str,
    response,
    expected: set[int],
) -> None:
    actual = response.status_code

    if actual not in expected:
        body = response.text
        if len(body) > 1600:
            body = body[:1600] + "..."

        raise AssertionError(
            f"{label}: expected one of {sorted(expected)}, "
            f"got {actual}\nResponse: {body}"
        )

    print(
        f"{label:<64} "
        f"PASS ({actual})"
    )


def bearer(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


def register(email: str, full_name: str) -> str:
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

    return response.json()["access_token"]


def cleanup() -> None:
    db = SessionLocal()

    try:
        users = list(
            db.scalars(
                select(User).where(
                    User.email.in_(CREATED_EMAILS)
                )
            ).all()
        )

        # Delete B before A because B may have
        # attempts against A's public quiz.
        users.sort(
            key=lambda user: (
                0 if user.email == EMAIL_B else 1
            )
        )

        for user in users:
            db.delete(user)

        db.commit()

        print(
            f"{'Cleanup temporary Phase-3A resources':<64} "
            "PASS"
        )

    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            f"Phase-3A cleanup failed: {exc}"
        ) from exc

    finally:
        db.close()


def manual_quiz_payload(
    subject_id: int,
    title: str,
) -> dict:
    return {
        "subject_id": subject_id,
        "title": title,
        "description":
            "Temporary manual quiz for API integration",
        "difficulty": "MEDIUM",
        "duration_minutes": 10,
        "visibility": "PUBLIC",
        "document_ids": [],
        "questions": [
            {
                "question_text":
                    "Tiền tệ có bao nhiêu chức năng cơ bản "
                    "trong câu hỏi kiểm thử này?",
                "difficulty": "MEDIUM",
                "explanation":
                    "Đáp án kiểm thử được backend lưu trực tiếp.",
                "points": 1,
                "source_chunk_id": None,
                "options": [
                    {
                        "option_key": "A",
                        "option_text": "Ba",
                        "is_correct": False,
                        "explanation": None,
                        "position": 1,
                    },
                    {
                        "option_key": "B",
                        "option_text": "Bốn",
                        "is_correct": False,
                        "explanation": None,
                        "position": 2,
                    },
                    {
                        "option_key": "C",
                        "option_text": "Năm",
                        "is_correct": True,
                        "explanation":
                            "Đây là đáp án đúng của dữ liệu kiểm thử.",
                        "position": 3,
                    },
                    {
                        "option_key": "D",
                        "option_text": "Sáu",
                        "is_correct": False,
                        "explanation": None,
                        "position": 4,
                    },
                ],
            }
        ],
    }


def main() -> None:
    print()
    print("=" * 100)
    print("FULL API INTEGRATION - PHASE 3A")
    print("Quiz Core Runtime: CRUD visibility + publish + attempt + submit + result")
    print("=" * 100)

    try:
        token_a = register(
            EMAIL_A,
            "API Phase Three A",
        )
        token_b = register(
            EMAIL_B,
            "API Phase Three B",
        )

        # -------------------------------------------------
        # Setup subjects
        # -------------------------------------------------
        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_a),
            json={
                "name": f"Phase 3 Subject A {RUN_ID}",
                "description": "Quiz owner subject",
                "color_hex": "#7744AA",
            },
        )
        check(
            "Setup POST /subjects user A",
            response,
            201,
        )
        subject_a = response.json()["id"]

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_b),
            json={
                "name": f"Phase 3 Subject B {RUN_ID}",
                "description": "Foreign user subject",
                "color_hex": "#4477AA",
            },
        )
        check(
            "Setup POST /subjects user B",
            response,
            201,
        )

        # -------------------------------------------------
        # Security probe:
        # B must NOT be able to attach a manual quiz
        # to A's subject.
        # -------------------------------------------------
        response = client.post(
            "/api/v1/quizzes",
            headers=bearer(token_b),
            json=manual_quiz_payload(
                subject_a,
                f"Foreign Subject Probe {RUN_ID}",
            ),
        )

        check_one_of(
            "POST /quizzes foreign subject must be blocked",
            response,
            {403, 404},
        )

        # -------------------------------------------------
        # QUIZZES 1/7: create
        # -------------------------------------------------
        response = client.post(
            "/api/v1/quizzes",
            headers=bearer(token_a),
            json=manual_quiz_payload(
                subject_a,
                f"Phase 3 Manual Quiz {RUN_ID}",
            ),
        )
        check(
            "POST /quizzes owner",
            response,
            201,
        )

        quiz_id = response.json()["id"]
        assert response.json()["status"] == "DRAFT"

        # -------------------------------------------------
        # QUIZZES 2/7: list
        # -------------------------------------------------
        response = client.get(
            "/api/v1/quizzes",
            headers=bearer(token_a),
        )
        check(
            "GET /quizzes owner",
            response,
            200,
        )

        assert any(
            item["id"] == quiz_id
            for item in response.json()
        )

        response = client.get(
            "/api/v1/quizzes",
            headers=bearer(token_b),
        )
        check(
            "GET /quizzes foreign user list isolation",
            response,
            200,
        )

        assert all(
            item["id"] != quiz_id
            for item in response.json()
        )

        # -------------------------------------------------
        # QUIZZES 3/7: get
        # DRAFT PUBLIC is still invisible to B.
        # -------------------------------------------------
        response = client.get(
            f"/api/v1/quizzes/{quiz_id}",
            headers=bearer(token_b),
        )
        check(
            "GET /quizzes/{id} foreign while DRAFT",
            response,
            404,
        )

        response = client.get(
            f"/api/v1/quizzes/{quiz_id}",
            headers=bearer(token_a),
        )
        check(
            "GET /quizzes/{id} owner",
            response,
            200,
        )

        owner_quiz = response.json()
        assert len(owner_quiz["questions"]) == 1

        question = owner_quiz["questions"][0]
        question_id = question["id"]

        correct_options = [
            option
            for option in question["options"]
            if option.get("is_correct") is True
        ]
        assert len(correct_options) == 1

        correct_option_id = correct_options[0]["id"]

        # -------------------------------------------------
        # QUIZZES 4/7: publish
        # -------------------------------------------------
        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/publish",
            headers=bearer(token_b),
        )
        check(
            "POST /quizzes/{id}/publish foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/publish",
            headers=bearer(token_a),
        )
        check(
            "POST /quizzes/{id}/publish owner",
            response,
            200,
        )

        assert response.json()["status"] == "PUBLISHED"

        # Published PUBLIC quiz becomes visible to B,
        # but answer key must be hidden.
        response = client.get(
            f"/api/v1/quizzes/{quiz_id}",
            headers=bearer(token_b),
        )
        check(
            "GET published PUBLIC quiz as foreign user",
            response,
            200,
        )

        public_question = response.json()["questions"][0]

        assert (
            public_question.get("explanation")
            is None
        )
        assert (
            public_question.get("source_chunk_id")
            is None
        )
        assert all(
            "is_correct" not in option
            for option in public_question["options"]
        )

        # -------------------------------------------------
        # QUIZZES 5/7: start attempt
        # -------------------------------------------------
        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/attempts",
            headers=bearer(token_b),
        )
        check(
            "POST /quizzes/{id}/attempts foreign participant",
            response,
            201,
        )

        attempt_payload = response.json()
        attempt_id = attempt_payload["attempt_id"]

        assert len(attempt_payload["questions"]) == 1
        assert all(
            "is_correct" not in option
            for option
            in attempt_payload["questions"][0]["options"]
        )

        # -------------------------------------------------
        # QUIZZES 7/7 result, pre-submit must be 409.
        # -------------------------------------------------
        response = client.get(
            f"/api/v1/quizzes/attempts/{attempt_id}/result",
            headers=bearer(token_b),
        )
        check(
            "GET attempt result before submit",
            response,
            409,
        )

        # -------------------------------------------------
        # QUIZZES 6/7: submit attempt
        # -------------------------------------------------
        response = client.post(
            f"/api/v1/quizzes/attempts/{attempt_id}/submit",
            headers=bearer(token_a),
            json={
                "answers": [
                    {
                        "question_id": question_id,
                        "selected_option_id":
                            correct_option_id,
                    }
                ]
            },
        )
        check(
            "POST attempt submit by foreign attempt owner",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/quizzes/attempts/{attempt_id}/submit",
            headers=bearer(token_b),
            json={
                "answers": [
                    {
                        "question_id": question_id,
                        "selected_option_id":
                            correct_option_id,
                    }
                ]
            },
        )
        check(
            "POST /quizzes/attempts/{id}/submit",
            response,
            200,
        )

        submitted = response.json()
        assert submitted["status"] == "SUBMITTED"
        assert submitted["correct_count"] == 1
        assert float(submitted["percentage"]) == 100.0

        # Duplicate finalization must be blocked.
        response = client.post(
            f"/api/v1/quizzes/attempts/{attempt_id}/submit",
            headers=bearer(token_b),
            json={
                "answers": [
                    {
                        "question_id": question_id,
                        "selected_option_id":
                            correct_option_id,
                    }
                ]
            },
        )
        check(
            "POST duplicate attempt submit",
            response,
            409,
        )

        # -------------------------------------------------
        # QUIZZES 7/7: result
        # -------------------------------------------------
        response = client.get(
            f"/api/v1/quizzes/attempts/{attempt_id}/result",
            headers=bearer(token_a),
        )
        check(
            "GET attempt result by foreign user",
            response,
            404,
        )

        response = client.get(
            f"/api/v1/quizzes/attempts/{attempt_id}/result",
            headers=bearer(token_b),
        )
        check(
            "GET /quizzes/attempts/{id}/result",
            response,
            200,
        )

        result = response.json()
        assert result["status"] == "SUBMITTED"
        assert result["correct_count"] == 1
        assert float(result["percentage"]) == 100.0

        print()
        print("-" * 100)
        print("PHASE 3A ENDPOINT COVERAGE:")
        print("  GET  /quizzes                         PASS")
        print("  POST /quizzes                         PASS")
        print("  GET  /quizzes/{quiz_id}               PASS")
        print("  POST /quizzes/{quiz_id}/publish       PASS")
        print("  POST /quizzes/{quiz_id}/attempts      PASS")
        print("  POST /quizzes/attempts/{id}/submit    PASS")
        print("  GET  /quizzes/attempts/{id}/result    PASS")
        print("  Core Quiz endpoints: 7/7")
        print("  Unexpected 5xx: 0")
        print("-" * 100)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 100)


if __name__ == "__main__":
    main()
