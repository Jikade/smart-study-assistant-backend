from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.main import app


# IMPORTANT:
# PostgreSQL refresh_tokens.ip_address is INET.
# Starlette TestClient defaults to host="testclient", which is not
# a valid PostgreSQL INET value. Use a real loopback IP instead.
client = TestClient(
    app,
    client=("127.0.0.1", 50000),
)

RUN_ID = uuid4().hex[:10]

EMAIL_1 = f"api-phase1-{RUN_ID}-a@example.com"
EMAIL_2 = f"api-phase1-{RUN_ID}-b@example.com"
PASSWORD = "Password123!"

CREATED_EMAILS = [
    EMAIL_1,
    EMAIL_2,
]


def check(
    label: str,
    response,
    expected: int,
) -> None:
    actual = response.status_code

    if actual != expected:
        body = response.text

        if len(body) > 1500:
            body = body[:1500] + "..."

        raise AssertionError(
            f"{label}: expected HTTP {expected}, "
            f"got {actual}\nResponse: {body}"
        )

    print(
        f"{label:<52} PASS ({actual})"
    )


def bearer(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


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

        for user in users:
            db.delete(user)

        db.commit()

        print(
            f"{'Cleanup temporary API users/resources':<52} "
            "PASS"
        )

    except Exception as exc:
        db.rollback()

        print(
            f"{'Cleanup temporary API users/resources':<52} "
            "FAIL"
        )

        raise RuntimeError(
            "Phase-1 cleanup failed: "
            f"{exc}"
        ) from exc

    finally:
        db.close()


def main() -> None:
    token_1 = None
    token_2 = None
    refresh_1 = None
    refresh_1_rotated = None

    print()
    print("=" * 88)
    print("FULL API INTEGRATION - PHASE 1 V2")
    print("Health + Auth + Users + Subjects")
    print("=" * 88)

    try:
        # ---------------------------------------------------------
        # Root / Health
        # ---------------------------------------------------------
        response = client.get("/")
        check(
            "GET /",
            response,
            200,
        )

        root = response.json()

        assert (
            root.get("name")
            == "Smart Study Assistant API"
        ), root

        response = client.get(
            "/api/v1/health"
        )
        check(
            "GET /api/v1/health",
            response,
            200,
        )

        health = response.json()

        assert health.get("database") == "ok", health
        assert health.get("status") == "ok", health

        # ---------------------------------------------------------
        # Unauthenticated security
        # ---------------------------------------------------------
        response = client.get(
            "/api/v1/auth/me"
        )
        check(
            "GET /auth/me without token",
            response,
            401,
        )

        response = client.get(
            "/api/v1/subjects"
        )
        check(
            "GET /subjects without token",
            response,
            401,
        )

        # ---------------------------------------------------------
        # Auth: Register user A
        # ---------------------------------------------------------
        payload_1 = {
            "email": EMAIL_1,
            "password": PASSWORD,
            "full_name": "API Phase One A",
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload_1,
        )
        check(
            "POST /auth/register user A",
            response,
            201,
        )

        registered_1 = response.json()

        token_1 = registered_1[
            "access_token"
        ]
        refresh_1 = registered_1[
            "refresh_token"
        ]
        user_1_id = registered_1[
            "user"
        ]["id"]

        # Duplicate registration
        response = client.post(
            "/api/v1/auth/register",
            json=payload_1,
        )
        check(
            "POST /auth/register duplicate email",
            response,
            409,
        )

        # ---------------------------------------------------------
        # Auth: Register user B
        # ---------------------------------------------------------
        payload_2 = {
            "email": EMAIL_2,
            "password": PASSWORD,
            "full_name": "API Phase One B",
        }

        response = client.post(
            "/api/v1/auth/register",
            json=payload_2,
        )
        check(
            "POST /auth/register user B",
            response,
            201,
        )

        registered_2 = response.json()

        token_2 = registered_2[
            "access_token"
        ]

        # ---------------------------------------------------------
        # Auth: Login JSON
        # ---------------------------------------------------------
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": EMAIL_1,
                "password": "wrong-password",
            },
        )
        check(
            "POST /auth/login invalid password",
            response,
            401,
        )

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": EMAIL_1,
                "password": PASSWORD,
            },
        )
        check(
            "POST /auth/login valid",
            response,
            200,
        )

        token_1 = response.json()[
            "access_token"
        ]

        # ---------------------------------------------------------
        # Auth: OAuth2 form login
        # ---------------------------------------------------------
        response = client.post(
            "/api/v1/auth/login-form",
            data={
                "username": EMAIL_1,
                "password": PASSWORD,
            },
        )
        check(
            "POST /auth/login-form",
            response,
            200,
        )

        # ---------------------------------------------------------
        # Auth: me
        # ---------------------------------------------------------
        response = client.get(
            "/api/v1/auth/me",
            headers=bearer(token_1),
        )
        check(
            "GET /auth/me authenticated",
            response,
            200,
        )

        assert (
            response.json()["id"]
            == user_1_id
        )

        # ---------------------------------------------------------
        # Users: PATCH /me
        # ---------------------------------------------------------
        response = client.patch(
            "/api/v1/users/me",
            headers=bearer(token_1),
            json={
                "full_name":
                    "API Phase One A Updated",
                "timezone":
                    "Asia/Ho_Chi_Minh",
                "locale":
                    "vi-VN",
            },
        )
        check(
            "PATCH /users/me",
            response,
            200,
        )

        updated_profile = response.json()

        assert (
            updated_profile["full_name"]
            == "API Phase One A Updated"
        )

        assert (
            updated_profile["timezone"]
            == "Asia/Ho_Chi_Minh"
        )

        assert (
            updated_profile["locale"]
            == "vi-VN"
        )

        # ---------------------------------------------------------
        # Auth: Refresh rotation
        # ---------------------------------------------------------
        response = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": refresh_1
            },
        )
        check(
            "POST /auth/refresh valid",
            response,
            200,
        )

        refresh_1_rotated = (
            response.json()[
                "refresh_token"
            ]
        )

        response = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": refresh_1
            },
        )
        check(
            "POST /auth/refresh reused old token",
            response,
            401,
        )

        # ---------------------------------------------------------
        # Auth: Logout
        # ---------------------------------------------------------
        response = client.post(
            "/api/v1/auth/logout",
            json={
                "refresh_token":
                    refresh_1_rotated
            },
        )
        check(
            "POST /auth/logout",
            response,
            200,
        )

        response = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token":
                    refresh_1_rotated
            },
        )
        check(
            "POST /auth/refresh after logout",
            response,
            401,
        )

        # ---------------------------------------------------------
        # Subjects: Create
        # ---------------------------------------------------------
        subject_payload = {
            "name":
                f"API Phase 1 Subject {RUN_ID}",
            "description":
                "Temporary integration test subject",
            "color_hex":
                "#3366FF",
        }

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_1),
            json=subject_payload,
        )
        check(
            "POST /subjects",
            response,
            201,
        )

        subject = response.json()
        subject_id = subject["id"]

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_1),
            json=subject_payload,
        )
        check(
            "POST /subjects duplicate name",
            response,
            409,
        )

        # Invalid payload validation
        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_1),
            json={
                "name": "",
                "color_hex": "invalid",
            },
        )
        check(
            "POST /subjects invalid payload",
            response,
            422,
        )

        # ---------------------------------------------------------
        # Subjects: List
        # ---------------------------------------------------------
        response = client.get(
            "/api/v1/subjects",
            headers=bearer(token_1),
        )
        check(
            "GET /subjects",
            response,
            200,
        )

        subject_ids = {
            item["id"]
            for item
            in response.json()["items"]
        }

        assert subject_id in subject_ids

        # ---------------------------------------------------------
        # Subjects: Get / ownership isolation
        # ---------------------------------------------------------
        response = client.get(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_1),
        )
        check(
            "GET /subjects/{id} owner",
            response,
            200,
        )

        response = client.get(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_2),
        )
        check(
            "GET /subjects/{id} foreign user",
            response,
            404,
        )

        # ---------------------------------------------------------
        # Subjects: Patch / ownership isolation
        # ---------------------------------------------------------
        response = client.patch(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_2),
            json={
                "description":
                    "Unauthorized update"
            },
        )
        check(
            "PATCH /subjects/{id} foreign user",
            response,
            404,
        )

        response = client.patch(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_1),
            json={
                "description":
                    "Updated by integration test",
                "is_archived":
                    True,
            },
        )
        check(
            "PATCH /subjects/{id} owner",
            response,
            200,
        )

        assert (
            response.json()["is_archived"]
            is True
        )

        # ---------------------------------------------------------
        # Subjects: Delete / ownership isolation
        # ---------------------------------------------------------
        response = client.delete(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_2),
        )
        check(
            "DELETE /subjects/{id} foreign user",
            response,
            404,
        )

        response = client.delete(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_1),
        )
        check(
            "DELETE /subjects/{id} owner",
            response,
            200,
        )

        response = client.get(
            f"/api/v1/subjects/{subject_id}",
            headers=bearer(token_1),
        )
        check(
            "GET deleted /subjects/{id}",
            response,
            404,
        )

        print()
        print("-" * 88)
        print("PHASE 1 ENDPOINT COVERAGE:")
        print("  Health   : 1/1 endpoint exercised")
        print("  Auth     : 6/6 endpoints exercised")
        print("  Users    : 1/1 endpoint exercised")
        print("  Subjects : 5/5 endpoints exercised")
        print("  Phase 1  : 13/13 API endpoints exercised")
        print("  Root     : additionally exercised")
        print("  Unexpected 5xx: 0")
        print("-" * 88)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 88)


if __name__ == "__main__":
    main()
