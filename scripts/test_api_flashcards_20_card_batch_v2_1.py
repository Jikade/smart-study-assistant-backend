from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentChunk,
    User,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(
    app,
    client=("127.0.0.1", 50120),
)

RUN_ID = uuid4().hex[:10]
EMAIL = f"flashcard20-{RUN_ID}@example.com"
PASSWORD = "Password123!"

DOCUMENT_TEXT = (
    "Tiền tệ là một hàng hóa đặc biệt được tách ra làm vật ngang giá chung. "
    "Tiền tệ có năm chức năng cơ bản gồm thước đo giá trị, phương tiện lưu thông, "
    "phương tiện cất trữ, phương tiện thanh toán và tiền tệ thế giới. "
    "Thước đo giá trị dùng tiền để đo lường và biểu hiện giá trị hàng hóa. "
    "Phương tiện lưu thông là khi tiền làm môi giới trong trao đổi hàng hóa. "
    "Phương tiện cất trữ là khi tiền được rút khỏi lưu thông và giữ lại. "
    "Phương tiện thanh toán là khi tiền dùng để trả nợ hoặc nghĩa vụ đến hạn. "
    "Tiền tệ thế giới là chức năng của tiền trong quan hệ kinh tế quốc tế. "
) * 10


class _NoEmbeddingProvider:
    can_embed = False
    can_chat = False


class _FakeChatResult:
    def __init__(self, content: str):
        self.content = content
        self.model = "fake-flashcard-batch-v2-1"


class _DeterministicFlashcardProvider:
    can_chat = True
    can_embed = False

    def __init__(self) -> None:
        self.calls = 0
        self.generated = 0

    def chat(
        self,
        messages,
        *,
        json_mode=False,
        temperature=0.0,
        max_tokens=None,
        reasoning_effort=None,
        **kwargs,
    ):
        self.calls += 1

        user_prompt = str(
            messages[-1]["content"]
        )

        target_match = re.search(
            r"Create exactly\s+(\d+)\s+concise study flashcards",
            user_prompt,
            flags=re.I,
        )

        if target_match is None:
            raise AssertionError(
                "Batch target missing from prompt"
            )

        target = int(
            target_match.group(1)
        )

        chunk_ids = [
            int(value)
            for value in re.findall(
                r"\[CHUNK_ID=(\d+)\]",
                user_prompt,
            )
        ]

        if not chunk_ids:
            raise AssertionError(
                "No CHUNK_ID found in prompt"
            )

        cards = []

        for index in range(target):
            self.generated += 1

            cards.append(
                {
                    "front_text":
                        f"Câu hỏi flashcard số {self.generated} là gì?",
                    "back_text":
                        f"Đáp án kiểm thử số {self.generated}.",
                    "hint":
                        f"Gợi ý {self.generated}",
                    "source_chunk_id":
                        chunk_ids[
                            index
                            % len(chunk_ids)
                        ],
                }
            )

        return _FakeChatResult(
            json.dumps(
                {
                    "cards": cards
                },
                ensure_ascii=False,
            )
        )


def check(
    label: str,
    response,
    expected: int,
) -> None:
    actual = response.status_code

    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected}, got {actual}\n"
            f"{response.text[:2000]}"
        )

    print(
        f"{label:<76} PASS ({actual})"
    )


def bearer(
    token: str,
) -> dict[str, str]:
    return {
        "Authorization":
            f"Bearer {token}"
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
            docs = list(
                db.scalars(
                    select(Document).where(
                        Document.owner_id
                        == user.id
                    )
                ).all()
            )

            for doc in docs:
                if doc.storage_url:
                    try:
                        Path(
                            doc.storage_url
                        ).unlink(
                            missing_ok=True
                        )
                    except Exception:
                        pass

            db.delete(
                user
            )

        db.commit()

        print(
            f"{'Cleanup temporary 20-card resources':<76} PASS"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def main() -> None:
    print()
    print("=" * 108)
    print("FLASHCARD BATCH V2.1 — FULL API 20-CARD ACCUMULATION REGRESSION")
    print("=" * 108)

    provider = (
        _DeterministicFlashcardProvider()
    )

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "full_name":
                    "Flashcard Twenty Test",
            },
        )

        check(
            "Register",
            response,
            201,
        )

        token = (
            response.json()[
                "access_token"
            ]
        )

        response = client.post(
            "/api/v1/subjects",
            headers=bearer(
                token
            ),
            json={
                "name":
                    f"Flashcard 20 {RUN_ID}",
                "description":
                    "20-card bounded batch regression",
                "color_hex":
                    "#557799",
            },
        )

        check(
            "Create subject",
            response,
            201,
        )

        subject_id = (
            response.json()["id"]
        )

        response = client.post(
            "/api/v1/documents/upload",
            headers=bearer(
                token
            ),
            files={
                "file": (
                    "flashcard20.txt",
                    DOCUMENT_TEXT.encode(
                        "utf-8"
                    ),
                    "text/plain",
                )
            },
            data={
                "subject_id":
                    str(
                        subject_id
                    ),
                "process_now":
                    "false",
            },
        )

        check(
            "Upload source document",
            response,
            201,
        )

        document_id = (
            response.json()["id"]
        )

        with patch(
            "app.services.document_service.get_ai_provider",
            return_value=(
                _NoEmbeddingProvider()
            ),
        ):
            response = client.post(
                f"/api/v1/documents/{document_id}/process",
                headers=bearer(
                    token
                ),
            )

        check(
            "Process source document",
            response,
            200,
        )

        db = SessionLocal()

        try:
            active_chunk_ids = {
                int(chunk.id)
                for chunk
                in db.scalars(
                    select(
                        DocumentChunk
                    ).where(
                        DocumentChunk.document_id
                        == document_id,
                        DocumentChunk.is_active.is_(
                            True
                        ),
                    )
                ).all()
            }

        finally:
            db.close()

        assert (
            active_chunk_ids
        ), "Expected active chunks"

        with patch(
            "app.services.flashcard_service.get_ai_provider",
            return_value=provider,
        ):
            response = client.post(
                "/api/v1/flashcards/decks/generate",
                headers=bearer(
                    token
                ),
                json={
                    "subject_id":
                        subject_id,
                    "title":
                        f"20 Card Deck {RUN_ID}",
                    "document_ids": [
                        document_id
                    ],
                    "card_count":
                        20,
                },
            )

        check(
            "Generate 20-card deck through API",
            response,
            201,
        )

        deck_id = (
            response.json()["id"]
        )

        response = client.get(
            f"/api/v1/flashcards/decks/{deck_id}",
            headers=bearer(
                token
            ),
        )

        check(
            "Read generated 20-card deck",
            response,
            200,
        )

        cards = (
            response.json()[
                "cards"
            ]
        )

        assert (
            len(cards)
            == 20
        )

        fronts = [
            str(
                card[
                    "front_text"
                ]
            ).strip().casefold()
            for card in cards
        ]

        assert (
            len(
                set(
                    fronts
                )
            )
            == 20
        ), "Expected 20 unique fronts"

        assert all(
            int(
                card[
                    "source_chunk_id"
                ]
            )
            in active_chunk_ids
            for card
            in cards
        )

        # 20 cards / batch size 4 = exactly 5 successful calls.
        assert (
            provider.calls
            == 5
        ), (
            "Expected exactly five deterministic full batches, "
            f"got {provider.calls}"
        )

        assert (
            provider.generated
            == 20
        )

        print(
            "20 unique cards persisted                             PASS"
        )

        print(
            "Every source_chunk_id belongs to active source set    PASS"
        )

        print(
            "20 cards accumulated in exactly five bounded calls    PASS"
        )

        print()
        print("-" * 108)
        print(
            "RESULT: PASS — UI-default 20-card request is supported "
            "by bounded batch accumulation."
        )
        print("-" * 108)

    finally:
        cleanup()


if __name__ == "__main__":
    main()
