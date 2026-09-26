from __future__ import annotations

from app.services.quiz_v5.distractors import (
    build_validated_quiz_plan,
)
from app.services.quiz_v5.engine import (
    SSA_QV5_ENGINE_VERSION,
    run_quiz_v5_engine,
)
from app.services.quiz_v5.extractor import (
    ChunkInput,
    extract_knowledge_objects,
)
from app.services.quiz_v5.planner import (
    plan_blueprints,
)
from app.services.quiz_v5.shadow import (
    shadow_from_chunks,
)


def _question_signature(item):
    return (
        item.blueprint.id,
        item.blueprint.knowledge_id,
        item.blueprint.blueprint_type.value,
        item.blueprint.stem,
        item.blueprint.correct_answer,
        item.distractors,
        item.validation_score,
        tuple(
            item.metadata.get(
                "distractor_origins",
                (),
            )
            or ()
        ),
    )


def _shadow_signature(item):
    return (
        item.blueprint_id,
        item.knowledge_id,
        item.blueprint_type,
        item.stem,
        item.correct_answer,
        item.distractors,
        item.validation_score,
        item.distractor_origins,
    )


def main() -> None:
    chunks = [
        ChunkInput(
            document_id=9001,
            chunk_id=9101,
            section_id=101,
            chunk_index=0,
            text=(
                "Năm 968, Đinh Bộ Lĩnh dẹp yên các sứ quân, "
                "thống nhất đất nước.\n"
                "Năm 1009, Lý Công Uẩn lên ngôi, lập ra nhà Lý.\n"
                "Năm 1226, nhà Trần được thành lập."
            ),
        ),
        ChunkInput(
            document_id=9001,
            chunk_id=9102,
            section_id=102,
            chunk_index=1,
            text=(
                "Năm 1400, Hồ Quý Ly lập ra nhà Hồ.\n"
                "Năm 1418, Lê Lợi dựng cờ khởi nghĩa Lam Sơn.\n"
                "Năm 1527, Mạc Đăng Dung lập ra nhà Mạc."
            ),
        ),
        ChunkInput(
            document_id=9001,
            chunk_id=9103,
            section_id=103,
            chunk_index=2,
            text=(
                "Năm 1771, ba anh em Nguyễn Nhạc, Nguyễn Huệ, "
                "Nguyễn Lữ phất cờ khởi nghĩa ở Tây Sơn.\n"
                "Năm 1785, Nguyễn Huệ đánh tan quân Xiêm.\n"
                "Năm 1804, quốc hiệu Việt Nam được sử dụng."
            ),
        ),
        ChunkInput(
            document_id=9001,
            chunk_id=9104,
            section_id=104,
            chunk_index=3,
            text=(
                "Năm 1858, liên quân Pháp - Tây Ban Nha "
                "tấn công Đà Nẵng.\n"
                "Năm 1884, Việt Nam trở thành thuộc địa của Pháp.\n"
                "Năm 1945, nước Việt Nam Dân chủ Cộng hòa ra đời."
            ),
        ),
        ChunkInput(
            document_id=9001,
            chunk_id=9105,
            section_id=105,
            chunk_index=4,
            text=(
                "Năm 1954, chiến thắng Điện Biên Phủ kết thúc "
                "cuộc kháng chiến chống Pháp.\n"
                "Năm 1975, miền Nam được giải phóng.\n"
                "Năm 1986, Đại hội VI đề ra đường lối Đổi Mới."
            ),
        ),
    ]

    target = 5

    knowledge = extract_knowledge_objects(
        chunks,
        subject_family="history",
    )

    blueprints = plan_blueprints(
        knowledge
    )

    manual_questions, manual_diag = (
        build_validated_quiz_plan(
            blueprints,
            target=target,
            max_per_section=2,
        )
    )

    engine = run_quiz_v5_engine(
        chunks,
        target=target,
        subject_family="history",
        max_per_section=2,
    )

    assert (
        engine.version
        == "SSA-QV5-ENGINE-V0.1"
        == SSA_QV5_ENGINE_VERSION
    )
    assert engine.requested == target
    assert engine.exact
    assert len(engine.questions) == target

    assert tuple(
        item.id for item in knowledge
    ) == tuple(
        item.id for item in engine.knowledge
    )

    assert tuple(
        item.id for item in blueprints
    ) == tuple(
        item.id for item in engine.blueprints
    )

    manual_signature = tuple(
        _question_signature(item)
        for item in manual_questions
    )

    engine_signature = tuple(
        _question_signature(item)
        for item in engine.questions
    )

    assert engine_signature == manual_signature
    assert engine.diagnostics == manual_diag

    shadow = shadow_from_chunks(
        chunks,
        target=target,
        subject_family="history",
        max_per_section=2,
    )

    shadow_signature = tuple(
        _shadow_signature(item)
        for item in shadow.questions
    )

    engine_for_shadow = tuple(
        (
            item.blueprint.id,
            item.blueprint.knowledge_id,
            item.blueprint.blueprint_type.value,
            item.blueprint.stem,
            item.blueprint.correct_answer,
            item.distractors,
            item.validation_score,
            tuple(
                item.metadata.get(
                    "distractor_origins",
                    (),
                )
                or ()
            ),
        )
        for item in engine.questions
    )

    assert shadow_signature == engine_for_shadow
    assert shadow.knowledge_count == len(engine.knowledge)
    assert shadow.blueprint_count == len(engine.blueprints)
    assert shadow.final_question_count == len(engine.questions)
    assert shadow.exact == engine.exact
    assert (
        shadow.replacement_iterations
        == engine.diagnostics.iterations
    )
    assert (
        shadow.rejected_blueprint_ids
        == engine.diagnostics.rejected_blueprint_ids
    )
    assert (
        shadow.structured_fallback_count
        == engine.diagnostics.structured_fallback_count
    )

    print()
    print("=" * 90)
    print("QUIZ V5 ENGINE V0.1 REGRESSION")
    print("=" * 90)
    print("Engine version            :", engine.version)
    print("Knowledge objects         :", len(engine.knowledge))
    print("Blueprint candidates      :", len(engine.blueprints))
    print("Validated final questions :", len(engine.questions))
    print("Exact target              :", engine.exact)
    print("Manual == engine          :", True)
    print("Engine == shadow          :", True)
    print("Diagnostics preserved     :", True)
    print("DB/API/AI side effects    :", False)
    print("Result                    : PASS")
    print("=" * 90)


if __name__ == "__main__":
    main()
