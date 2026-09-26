from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.main import app
from app.schemas.quizzes import (
    QuizV5PreviewOut,
    QuizV5PreviewRequest,
)
from app.services.quiz_v5.extractor import ChunkInput

import app.api.v1.routers.quizzes as quiz_router


def fixture_chunks() -> list[ChunkInput]:
    years = [
        (968, "Đinh Bộ Lĩnh dẹp yên các sứ quân"),
        (1009, "Lý Công Uẩn lên ngôi, lập ra nhà Lý"),
        (1226, "nhà Trần được thành lập"),
        (1400, "Hồ Quý Ly lập ra nhà Hồ"),
        (1418, "Lê Lợi dựng cờ khởi nghĩa Lam Sơn"),
        (1527, "Mạc Đăng Dung lập ra nhà Mạc"),
        (1771, "khởi nghĩa Tây Sơn bùng nổ"),
        (1785, "Nguyễn Huệ đánh tan quân Xiêm"),
        (1804, "quốc hiệu Việt Nam được sử dụng"),
        (1858, "liên quân Pháp - Tây Ban Nha tấn công Đà Nẵng"),
        (1884, "Việt Nam trở thành thuộc địa của Pháp"),
        (1945, "nước Việt Nam Dân chủ Cộng hòa ra đời"),
        (1954, "chiến thắng Điện Biên Phủ"),
        (1975, "miền Nam được giải phóng"),
        (1986, "Đại hội VI đề ra đường lối Đổi Mới"),
    ]

    output: list[ChunkInput] = []

    for index in range(0, len(years), 3):
        batch = years[index:index + 3]
        text = "\n".join(
            f"Năm {year}, {event}."
            for year, event in batch
        )

        output.append(
            ChunkInput(
                document_id=20,
                chunk_id=1000 + index,
                section_id=200 + index // 3,
                text=text,
                chunk_index=index // 3,
            )
        )

    return output


class NoWriteDB:
    """
    The route test patches the DB adapter and source-access checks.
    Any accidental direct DB use by the route must fail.
    """

    def __getattr__(self, name):
        raise AssertionError(
            f"Unexpected direct DB access from preview route: {name}"
        )


def main() -> None:
    schema = app.openapi()

    path = (
        "/api/v1/quizzes/"
        "generate-v5-preview"
    )

    assert path in schema["paths"], path
    assert (
        "post"
        in schema["paths"][path]
    )

    # Existing V4 production route must remain present.
    assert (
        "/api/v1/quizzes/generate"
        in schema["paths"]
    )

    payload = QuizV5PreviewRequest(
        subject_id=40,
        document_ids=[20],
        question_count=5,
        subject_family="history",
        max_per_section=2,
    )

    seen: dict[str, object] = {}

    def fake_validate_subject(
        db,
        owner_id,
        subject_id,
    ):
        seen["subject"] = (
            owner_id,
            subject_id,
        )
        return subject_id

    def fake_validate_docs(
        db,
        owner_id,
        document_ids,
        *,
        subject_id=None,
    ):
        seen["documents"] = (
            owner_id,
            tuple(document_ids),
            subject_id,
        )
        return list(document_ids)

    def fake_load(
        db,
        *,
        document_ids,
        owner_id=None,
    ):
        seen["load"] = (
            tuple(document_ids),
            owner_id,
        )
        return fixture_chunks()

    with (
        patch.object(
            quiz_router,
            "validate_owned_subject_id",
            side_effect=fake_validate_subject,
        ),
        patch.object(
            quiz_router,
            "validate_owned_document_ids",
            side_effect=fake_validate_docs,
        ),
        patch.object(
            quiz_router,
            "load_v5_document_chunks",
            side_effect=fake_load,
        ),
    ):
        raw = quiz_router.generate_v5_preview(
            payload=payload,
            db=NoWriteDB(),
            user=SimpleNamespace(id=1),
        )

    result = QuizV5PreviewOut.model_validate(
        raw
    )

    assert seen["subject"] == (1, 40)
    assert seen["documents"] == (
        1,
        (20,),
        40,
    )
    assert seen["load"] == (
        (20,),
        1,
    )

    assert (
        result.engine_version
        == "SSA-QV5-ENGINE-V0.1"
    )
    assert result.requested == 5
    assert result.generated == 5
    assert result.exact is True
    assert result.knowledge_count >= 5
    assert result.blueprint_count >= 5
    assert len(result.questions) == 5

    assert all(
        question.source_document_id == 20
        for question in result.questions
    )

    assert all(
        len(question.distractors) == 3
        for question in result.questions
    )

    print()
    print("=" * 90)
    print("QUIZ V5 API PREVIEW V0.1 REGRESSION")
    print("=" * 90)
    print("Route registered              :", True)
    print("Existing V4 /generate intact :", True)
    print("Owner forwarded               :", True)
    print("Subject ownership checked     :", True)
    print("Document ownership checked    :", True)
    print("Engine version                :", result.engine_version)
    print("Generated                     :", f"{result.generated}/{result.requested}")
    print("Exact target                  :", result.exact)
    print("Direct DB writes in route     :", False)
    print("Result                        : PASS")
    print("=" * 90)


if __name__ == "__main__":
    main()
