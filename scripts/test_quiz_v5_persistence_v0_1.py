from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.main import app
import app.api.v1.routers.quizzes as quiz_router

from app.schemas.quizzes import (
    QuizV5GenerateRequest,
)
from app.services.quiz_v5.distractors import (
    PlanBuildDiagnostics,
)
from app.services.quiz_v5.engine import (
    QuizV5EngineResult,
    run_quiz_v5_engine,
)
from app.services.quiz_v5.extractor import (
    ChunkInput,
)
from app.services.quiz_v5.persistence import (
    SSA_QV5_PERSISTENCE_VERSION,
    build_quiz_create_payload,
)


def fixture_chunks() -> list[ChunkInput]:
    rows = [
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

    chunks: list[ChunkInput] = []

    for offset in range(0, len(rows), 3):
        batch = rows[offset:offset + 3]

        chunks.append(
            ChunkInput(
                document_id=20,
                chunk_id=5000 + offset,
                section_id=100 + offset // 3,
                chunk_index=offset // 3,
                text="\n".join(
                    f"Năm {year}, {event}."
                    for year, event in batch
                ),
            )
        )

    return chunks


def request() -> QuizV5GenerateRequest:
    return QuizV5GenerateRequest(
        subject_id=40,
        document_ids=[20],
        title="V5 persistence regression",
        description="deterministic test",
        question_count=5,
        difficulty="MEDIUM",
        duration_minutes=10,
        visibility="PRIVATE",
        subject_family="history",
        max_per_section=2,
    )


def main() -> None:
    schema = app.openapi()

    assert (
        "/api/v1/quizzes/generate-v5"
        in schema["paths"]
    )
    assert (
        "/api/v1/quizzes/generate"
        in schema["paths"]
    )
    assert (
        "/api/v1/quizzes/generate-v5-preview"
        in schema["paths"]
    )

    req = request()

    engine = run_quiz_v5_engine(
        fixture_chunks(),
        target=req.question_count,
        subject_family=req.subject_family,
        max_per_section=req.max_per_section,
    )

    assert engine.exact
    assert len(engine.questions) == 5

    payload1 = build_quiz_create_payload(
        engine,
        request=req,
        document_ids=[20],
    )

    payload2 = build_quiz_create_payload(
        engine,
        request=req,
        document_ids=[20],
    )

    # Pure deterministic conversion.
    assert (
        payload1.model_dump()
        == payload2.model_dump()
    )

    assert len(payload1.questions) == 5

    correct_positions = []

    for question in payload1.questions:
        assert len(question.options) == 4
        assert {
            option.option_key
            for option in question.options
        } == {"A", "B", "C", "D"}

        correct = [
            option
            for option in question.options
            if option.is_correct
        ]

        assert len(correct) == 1
        correct_positions.append(
            correct[0].position
        )

        assert (
            question.source_chunk_id
            is not None
        )

    # We do not require all four positions in a five-question sample,
    # only prove the key is deterministic and not hard-coded to A.
    assert any(
        position != 1
        for position in correct_positions
    ), correct_positions

    # Partial results must be refused before persistence conversion.
    partial = QuizV5EngineResult(
        version=engine.version,
        requested=5,
        exact=False,
        source_chars=engine.source_chars,
        knowledge=engine.knowledge,
        blueprints=engine.blueprints,
        questions=engine.questions[:4],
        diagnostics=PlanBuildDiagnostics(
            requested=5,
            selected=4,
            exact=False,
            iterations=1,
            rejected_blueprint_ids=("bp-test",),
            structured_fallback_count=0,
        ),
    )

    try:
        build_quiz_create_payload(
            partial,
            request=req,
            document_ids=[20],
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Partial V5 result was incorrectly accepted."
        )

    # Route wiring: exact result reaches persistence exactly once.
    persisted: dict[str, object] = {}

    with (
        patch.object(
            quiz_router,
            "validate_owned_subject_id",
            return_value=40,
        ),
        patch.object(
            quiz_router,
            "validate_owned_document_ids",
            return_value=[20],
        ),
        patch.object(
            quiz_router,
            "load_v5_document_chunks",
            return_value=fixture_chunks(),
        ),
        patch.object(
            quiz_router,
            "persist_quiz_v5",
            side_effect=lambda *args, **kwargs: (
                persisted.update(kwargs)
                or SimpleNamespace(id=999)
            ),
        ),
    ):
        result = quiz_router.generate_v5(
            payload=req,
            db=object(),
            user=SimpleNamespace(id=1),
        )

    assert result.id == 999
    assert persisted["owner_id"] == 1
    assert persisted["document_ids"] == [20]
    assert persisted["result"].exact is True

    # Partial route path must never call persistence.
    partial_called = {"value": False}

    with (
        patch.object(
            quiz_router,
            "validate_owned_subject_id",
            return_value=40,
        ),
        patch.object(
            quiz_router,
            "validate_owned_document_ids",
            return_value=[20],
        ),
        patch.object(
            quiz_router,
            "load_v5_document_chunks",
            return_value=fixture_chunks(),
        ),
        patch.object(
            quiz_router,
            "run_quiz_v5_engine",
            return_value=partial,
        ),
        patch.object(
            quiz_router,
            "persist_quiz_v5",
            side_effect=lambda *args, **kwargs: (
                partial_called.__setitem__(
                    "value",
                    True,
                )
            ),
        ),
    ):
        try:
            quiz_router.generate_v5(
                payload=req,
                db=object(),
                user=SimpleNamespace(id=1),
            )
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError(
                "Partial route result did not return 422."
            )

    assert partial_called["value"] is False

    print()
    print("=" * 92)
    print("QUIZ V5 PERSISTENCE V0.1 REGRESSION")
    print("=" * 92)
    print("Persistence version          :", SSA_QV5_PERSISTENCE_VERSION)
    print("Route registered             :", True)
    print("Existing V4 /generate intact:", True)
    print("Preview route intact         :", True)
    print("Exact conversion deterministic:", True)
    print("One correct option/question  :", True)
    print("Correct answer not fixed at A:", True)
    print("Source chunk lineage retained:", True)
    print("Partial result rejected      :", True)
    print("Partial result persisted     :", False)
    print("Result                       : PASS")
    print("=" * 92)


if __name__ == "__main__":
    main()
