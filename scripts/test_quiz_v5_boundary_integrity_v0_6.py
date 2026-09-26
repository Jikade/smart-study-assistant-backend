from __future__ import annotations

from app.services.quiz_v5 import (
    BlueprintType,
    ChunkInput,
    EvidenceRef,
    QuestionBlueprint,
    extract_knowledge_objects,
    select_diverse_blueprints,
)
from app.services.quiz_v5.distractors import (
    SSA_QV5_DISTRACTOR_BOUNDARY_VERSION,
)
from app.services.quiz_v5.extractor import (
    SSA_QV5_EXTRACTOR_BOUNDARY_VERSION,
)
from app.services.quiz_v5.selector import (
    SSA_QV5_SELECTOR_ADAPTIVE_VERSION,
)
from app.services.quiz_v5.validators import (
    SSA_QV5_VALIDATOR_BOUNDARY_VERSION,
    option_quality_issue,
)


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def event_bp(
    ident: str,
    *,
    answer: str,
    score: float,
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=ident,
        blueprint_type=BlueprintType.EVENT_DATE,
        knowledge_id=f"k-{ident}",
        stem=f"Sự kiện {ident} diễn ra khi nào?",
        correct_answer=answer,
        distractor_family="DATE",
        section_id=None,
        quality_score=score,
        evidence=EvidenceRef(
            document_id=19,
            chunk_id=492,
            section_id=None,
            text=f"{ident} diễn ra năm {answer}",
        ),
    )


def main() -> None:
    print()
    print("=" * 112)
    print(
        "QUIZ V5 BOUNDARY INTEGRITY + "
        "ADAPTIVE DIVERSITY V0.6 REGRESSION"
    )
    print("=" * 112)

    must(
        "Extractor boundary version exposed",
        SSA_QV5_EXTRACTOR_BOUNDARY_VERSION
        == "SSA-QV5-KX-V0.6",
    )
    must(
        "Selector adaptive version exposed",
        SSA_QV5_SELECTOR_ADAPTIVE_VERSION
        == "SSA-QV5-SEL-V0.6",
    )
    must(
        "Validator boundary version exposed",
        SSA_QV5_VALIDATOR_BOUNDARY_VERSION
        == "SSA-QV5-VAL-V0.6",
    )
    must(
        "Distractor boundary version exposed",
        SSA_QV5_DISTRACTOR_BOUNDARY_VERSION
        == "SSA-QV5-DX-V0.6",
    )

    # Real doc-19 pattern: after a sparse FUNCTION is removed, the
    # remaining pool can legitimately contain only EVENT_DATE.
    dates = [
        event_bp("Bạch Đằng", answer="938", score=99),
        event_bp("Cách mạng tháng Tám", answer="1945", score=98),
        event_bp("Điện Biên Phủ", answer="1954", score=97),
        event_bp("Chiến dịch Hồ Chí Minh", answer="1975", score=96),
        event_bp("Đổi mới", answer="1986", score=95),
    ]

    selected, diag = select_diverse_blueprints(
        dates,
        target=5,
    )

    must(
        "Single-family fallback can fill exact target",
        len(selected) == 5
        and diag.exact,
    )

    # Real doc-20 bad subject: predicate is cut at chunk boundary.
    incomplete_event = extract_knowledge_objects(
        [
            ChunkInput(
                document_id=20,
                chunk_id=521,
                section_id=None,
                chunk_index=8,
                text=(
                    "Năm 1804, quốc hiệu được đổi thành"
                ),
            )
        ],
        subject_family="history",
    )

    must(
        "Incomplete historical predicate is rejected",
        not any(
            item.kind.value == "DATE"
            for item in incomplete_event
        ),
    )

    complete_event = extract_knowledge_objects(
        [
            ChunkInput(
                document_id=20,
                chunk_id=522,
                section_id=None,
                chunk_index=9,
                text=(
                    "Năm 1804, quốc hiệu được đổi thành Việt Nam"
                ),
            )
        ],
        subject_family="history",
    )

    must(
        "Complete historical predicate is retained",
        any(
            item.kind.value == "DATE"
            and item.object == "1804"
            for item in complete_event
        ),
    )

    range_tail = extract_knowledge_objects(
        [
            ChunkInput(
                document_id=20,
                chunk_id=513,
                section_id=None,
                chunk_index=2,
                text=(
                    "Năm 544 - 602 Lý Bí (Lý Nam Đế) "
                    "đánh đuổi quân nhà Lương"
                ),
            )
        ],
        subject_family="history",
    )

    must(
        "Ambiguous year-range tail is not misparsed as event subject",
        not any(
            item.kind.value == "DATE"
            for item in range_tail
        ),
    )

    # Real doc-20 boundary fragments.
    boundary_defs = extract_knowledge_objects(
        [
            ChunkInput(
                document_id=20,
                chunk_id=511,
                section_id=None,
                chunk_index=4,
                text=(
                    "iệt Nam là một quốc gia có bề dày "
                    "lịch sử hàng nghìn năm"
                ),
            ),
            ChunkInput(
                document_id=20,
                chunk_id=515,
                section_id=None,
                chunk_index=5,
                text=(
                    "hiệu riêng là sự khẳng định mạnh mẽ "
                    "chủ quyền tuyệt đối"
                ),
            ),
        ],
        subject_family="history",
    )

    must(
        "Lowercase first-unit boundary definition fragments are rejected",
        not any(
            item.kind.value == "DEFINITION"
            for item in boundary_defs
        ),
    )

    clean_definition = extract_knowledge_objects(
        [
            ChunkInput(
                document_id=2,
                chunk_id=430,
                section_id=1,
                chunk_index=0,
                text=(
                    "Quy luật giá trị là quy luật kinh tế "
                    "cơ bản của sản xuất hàng hóa"
                ),
            )
        ],
        subject_family="economics",
    )

    must(
        "Clean first-chunk definition remains extractable",
        any(
            item.kind.value == "DEFINITION"
            and item.subject == "Quy luật giá trị"
            for item in clean_definition
        ),
    )

    # Real doc-2 chunk-tail fragments.
    tail_fragments = extract_knowledge_objects(
        [
            ChunkInput(
                document_id=2,
                chunk_id=429,
                section_id=1,
                chunk_index=1,
                text=(
                    "Phân công lao động xã hội là sự phân chia "
                    "lao động xã hội thành các ngành, các nghề "
                    "khác nhau, làm cho"
                ),
            ),
            ChunkInput(
                document_id=2,
                chunk_id=435,
                section_id=3,
                chunk_index=6,
                text=(
                    "Thể chế kinh tế thị trường định hướng XHCN "
                    "là hệ thống các quy tắc, luật pháp, bộ máy "
                    "quản lý và cơ chế vận"
                ),
            ),
        ],
        subject_family="economics",
    )

    must(
        "Definition objects ending in incomplete Vietnamese tails are rejected",
        not any(
            item.kind.value == "DEFINITION"
            for item in tail_fragments
        ),
    )

    must(
        "TERM option ending in 'gọi' is rejected",
        option_quality_issue(
            "biểu hiện bằng tiền gọi",
            family="TERM",
        )
        == "truncated_option",
    )

    print()
    print(
        f"Adaptive DATE selection : "
        f"{[item.correct_answer for item in selected]}"
    )
    print(
        f"Clean definitions       : "
        f"{[(item.subject, item.object) for item in clean_definition]}"
    )

    print("-" * 112)
    print("RESULT: PASS")
    print("=" * 112)


if __name__ == "__main__":
    main()
