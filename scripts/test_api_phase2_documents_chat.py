
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Document, User
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50001),
)

RUN_ID = uuid4().hex[:10]
EMAIL_A = f"api-phase2-{RUN_ID}-a@example.com"
EMAIL_B = f"api-phase2-{RUN_ID}-b@example.com"
PASSWORD = "Password123!"

CREATED_EMAILS = [
    EMAIL_A,
    EMAIL_B,
]

DOCUMENT_TEXT = """CHƯƠNG 1 TIỀN TỆ VÀ CÁC CHỨC NĂNG CỦA TIỀN TỆ

Tiền tệ có năm chức năng cơ bản: thước đo giá trị, phương tiện lưu thông,
phương tiện cất trữ, phương tiện thanh toán và tiền tệ thế giới.

Chức năng thước đo giá trị cho phép dùng tiền để biểu hiện và đo lường giá trị
của hàng hóa. Chức năng phương tiện lưu thông thể hiện khi tiền làm môi giới
trong trao đổi hàng hóa. Chức năng phương tiện cất trữ xuất hiện khi tiền được
rút khỏi lưu thông để tích lũy. Chức năng phương tiện thanh toán thể hiện khi
tiền dùng để trả nợ, trả tiền mua chịu và thực hiện nghĩa vụ thanh toán. Chức
năng tiền tệ thế giới xuất hiện trong các quan hệ kinh tế quốc tế.

Trong học tập, năm chức năng này cần được phân biệt theo vai trò của tiền trong
từng tình huống. Khi hàng hóa được định giá, tiền đang thực hiện chức năng
thước đo giá trị. Khi tiền trực tiếp làm trung gian cho hành vi mua và bán,
tiền thực hiện chức năng phương tiện lưu thông. Khi giữ tiền để dành cho tương
lai, tiền thực hiện chức năng cất trữ. Khi trả một khoản nợ đến hạn, tiền thực
hiện chức năng thanh toán. Trong giao dịch quốc tế, tiền có thể thực hiện chức
năng tiền tệ thế giới.

Nội dung chương này nhấn mạnh rằng các chức năng của tiền tệ có quan hệ với
nhau nhưng không hoàn toàn giống nhau. Việc xác định đúng chức năng phụ thuộc
vào hoàn cảnh sử dụng tiền. Người học cần nhận biết đầy đủ năm chức năng và
vận dụng chúng vào các tình huống kinh tế cụ thể.
"""


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

    print(f"{label:<60} PASS ({actual})")


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

        user_ids = [
            user.id
            for user in users
        ]

        if user_ids:
            documents = list(
                db.scalars(
                    select(Document).where(
                        Document.owner_id.in_(user_ids)
                    )
                ).all()
            )

            for document in documents:
                if document.storage_url:
                    try:
                        Path(document.storage_url).unlink(
                            missing_ok=True
                        )
                    except Exception:
                        pass

            for user in users:
                db.delete(user)

        db.commit()

        print(
            f"{'Cleanup temporary Phase-2 resources':<60} PASS"
        )

    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            f"Phase-2 cleanup failed: {exc}"
        ) from exc

    finally:
        db.close()


def main() -> None:
    print()
    print("=" * 96)
    print("FULL API INTEGRATION - PHASE 2")
    print("Documents + Chat/RAG")
    print("=" * 96)

    try:
        token_a = register(
            EMAIL_A,
            "API Phase Two A",
        )

        token_b = register(
            EMAIL_B,
            "API Phase Two B",
        )

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(token_a),
            json={
                "name":
                    f"Phase 2 Subject {RUN_ID}",
                "description":
                    "Temporary Documents/RAG subject",
                "color_hex":
                    "#224488",
            },
        )
        check(
            "Setup POST /subjects user A",
            response,
            201,
        )

        subject_id = response.json()["id"]

        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token_b),
            files={
                "file": (
                    "foreign.txt",
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
            "POST /documents/upload with foreign subject",
            response,
            404,
        )

        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token_a),
            files={
                "file": (
                    "phase2_money.txt",
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
            "POST /documents/upload owner",
            response,
            201,
        )

        document = response.json()
        document_id = document["id"]
        assert document["status"] == "UPLOADED"

        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(token_a),
            files={
                "file": (
                    "blocked.exe",
                    b"not an allowed document",
                    "application/octet-stream",
                )
            },
            data={
                "subject_id": str(subject_id),
                "process_now": "false",
            },
        )
        check(
            "POST /documents/upload invalid extension",
            response,
            400,
        )

        response = client.get(
            "/api/v1/documents",
            headers=bearer(token_a),
            params={
                "subject_id": subject_id
            },
        )
        check(
            "GET /documents owner",
            response,
            200,
        )

        assert any(
            item["id"] == document_id
            for item in response.json()["items"]
        )

        response = client.get(
            "/api/v1/documents",
            headers=bearer(token_b),
        )
        check(
            "GET /documents foreign user",
            response,
            200,
        )

        assert all(
            item["id"] != document_id
            for item in response.json()["items"]
        )

        response = client.get(
            f"/api/v1/documents/{document_id}",
            headers=bearer(token_a),
        )
        check(
            "GET /documents/{id} owner",
            response,
            200,
        )

        response = client.get(
            f"/api/v1/documents/{document_id}",
            headers=bearer(token_b),
        )
        check(
            "GET /documents/{id} foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=bearer(token_b),
        )
        check(
            "POST /documents/{id}/process foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=bearer(token_a),
        )
        check(
            "POST /documents/{id}/process owner",
            response,
            200,
        )

        processed = response.json()

        assert processed["status"] == "READY"
        assert processed["chunks_created"] >= 1
        assert processed["embeddings_created"] >= 1

        response = client.get(
            f"/api/v1/documents/{document_id}/chunks",
            headers=bearer(token_a),
        )
        check(
            "GET /documents/{id}/chunks owner",
            response,
            200,
        )

        chunks = response.json()

        assert len(chunks) >= 1
        assert all(
            chunk["document_id"] == document_id
            for chunk in chunks
        )

        response = client.get(
            f"/api/v1/documents/{document_id}/chunks",
            headers=bearer(token_b),
        )
        check(
            "GET /documents/{id}/chunks foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/documents/{document_id}/embed",
            headers=bearer(token_b),
        )
        check(
            "POST /documents/{id}/embed foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/documents/{document_id}/embed",
            headers=bearer(token_a),
        )
        check(
            "POST /documents/{id}/embed owner",
            response,
            200,
        )

        embed_result = response.json()
        assert embed_result["document_id"] == document_id
        assert embed_result["chunks_total"] >= 1
        assert embed_result["embeddings_created"] == 0

        response = client.post(
            "/api/v1/chat/conversations",
            headers=bearer(token_b),
            json={
                "subject_id": subject_id,
                "title":
                    "Foreign subject should fail",
                "document_ids": [],
            },
        )
        check(
            "POST /chat/conversations foreign subject",
            response,
            404,
        )

        response = client.post(
            "/api/v1/chat/conversations",
            headers=bearer(token_b),
            json={
                "title":
                    "Foreign document should fail",
                "document_ids": [
                    document_id
                ],
            },
        )
        check(
            "POST /chat/conversations foreign document",
            response,
            400,
        )

        response = client.post(
            "/api/v1/chat/conversations",
            headers=bearer(token_a),
            json={
                "subject_id": subject_id,
                "title":
                    "Phase 2 RAG Conversation",
                "document_ids": [
                    document_id
                ],
            },
        )
        check(
            "POST /chat/conversations owner",
            response,
            201,
        )

        conversation_id = response.json()["id"]

        response = client.get(
            "/api/v1/chat/conversations",
            headers=bearer(token_a),
        )
        check(
            "GET /chat/conversations owner",
            response,
            200,
        )

        assert any(
            item["id"] == conversation_id
            for item in response.json()
        )

        response = client.get(
            "/api/v1/chat/conversations",
            headers=bearer(token_b),
        )
        check(
            "GET /chat/conversations foreign user",
            response,
            200,
        )

        assert all(
            item["id"] != conversation_id
            for item in response.json()
        )

        response = client.get(
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            headers=bearer(token_b),
        )
        check(
            "GET /chat/.../messages foreign user",
            response,
            404,
        )

        response = client.get(
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            headers=bearer(token_a),
        )
        check(
            "GET /chat/.../messages before ask",
            response,
            200,
        )

        assert response.json() == []

        response = client.post(
            f"/api/v1/chat/conversations/{conversation_id}/ask",
            headers=bearer(token_b),
            json={
                "question":
                    "Tiền tệ có những chức năng nào?",
                "input_mode":
                    "TEXT",
                "top_k":
                    1,
            },
        )
        check(
            "POST /chat/.../ask foreign user",
            response,
            404,
        )

        response = client.post(
            f"/api/v1/chat/conversations/{conversation_id}/ask",
            headers=bearer(token_a),
            json={
                "question":
                    "Tiền tệ có những chức năng nào?",
                "input_mode":
                    "TEXT",
                "top_k":
                    1,
            },
        )
        check(
            "POST /chat/.../ask owner (live RAG)",
            response,
            200,
        )

        answer = response.json()

        assert answer["answer"].strip()
        assert len(answer["citations"]) >= 1

        chunk_ids = {
            chunk["id"]
            for chunk in chunks
        }

        assert all(
            citation["document_id"] == document_id
            for citation in answer["citations"]
        )

        assert all(
            citation["chunk_id"] in chunk_ids
            for citation in answer["citations"]
        )

        response = client.get(
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            headers=bearer(token_a),
        )
        check(
            "GET /chat/.../messages after ask",
            response,
            200,
        )

        messages = response.json()

        assert len(messages) >= 2
        assert messages[-2]["role"] == "USER"
        assert messages[-1]["role"] == "ASSISTANT"

        response = client.delete(
            f"/api/v1/documents/{document_id}",
            headers=bearer(token_b),
        )
        check(
            "DELETE /documents/{id} foreign user",
            response,
            404,
        )

        response = client.delete(
            f"/api/v1/documents/{document_id}",
            headers=bearer(token_a),
        )
        check(
            "DELETE /documents/{id} owner",
            response,
            200,
        )

        response = client.get(
            f"/api/v1/documents/{document_id}",
            headers=bearer(token_a),
        )
        check(
            "GET deleted /documents/{id}",
            response,
            404,
        )

        print()
        print("-" * 96)
        print("PHASE 2 ENDPOINT COVERAGE:")
        print("  Documents : 7/7 endpoints exercised")
        print("  Chat/RAG  : 4/4 endpoints exercised")
        print("  Phase 2   : 11/11 API endpoints exercised")
        print("  Unexpected 5xx: 0")
        print("-" * 96)

    finally:
        cleanup()

    print()
    print("Result: PASS")
    print("=" * 96)


if __name__ == "__main__":
    main()
