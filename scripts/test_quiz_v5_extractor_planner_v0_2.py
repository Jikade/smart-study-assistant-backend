from __future__ import annotations

from app.services.quiz_v5 import (
    BlueprintType,
    ChunkInput,
    KnowledgeKind,
    SSA_QV5_EXTRACTOR_VERSION,
    SSA_QV5_PLANNER_VERSION,
    extract_knowledge_objects,
    plan_blueprints,
    select_diverse_blueprints,
)


def must(
    label: str,
    condition: bool,
) -> None:
    if not condition:
        raise AssertionError(
            label
        )
    print(
        f"[PASS] {label}"
    )


def main() -> None:
    print()
    print("=" * 104)
    print(
        "QUIZ V5 KNOWLEDGE EXTRACTION + "
        "BLUEPRINT PLANNER V0.2 REGRESSION"
    )
    print("=" * 104)

    corpus = [
        ChunkInput(
            document_id=1,
            chunk_id=101,
            section_id=11,
            text=(
                "Chiến thắng Bạch Đằng diễn ra năm 938. "
                "Cách mạng tháng Tám diễn ra năm 1945."
            ),
        ),
        ChunkInput(
            document_id=2,
            chunk_id=201,
            section_id=21,
            text=(
                "Phân công lao động xã hội là sự phân chia "
                "lao động xã hội thành các ngành và nghề khác nhau. "
                "Thước đo giá trị dùng để đo lường và biểu hiện "
                "giá trị hàng hóa."
            ),
        ),
        ChunkInput(
            document_id=3,
            chunk_id=301,
            section_id=31,
            text=(
                "Công suất là đại lượng đặc trưng cho tốc độ "
                "thực hiện công.\n"
                "P = A/t"
            ),
        ),
        ChunkInput(
            document_id=4,
            chunk_id=401,
            section_id=41,
            text=(
                "Ti thể có chức năng cung cấp năng lượng "
                "cho hoạt động của tế bào."
            ),
        ),
        ChunkInput(
            document_id=5,
            chunk_id=501,
            section_id=51,
            text=(
                "Đỉnh Phan Xi Păng có độ cao 3143 m. "
                "Sự chênh lệch khí áp gây ra gió."
            ),
        ),
        ChunkInput(
            document_id=6,
            chunk_id=601,
            section_id=61,
            text=(
                "Chu vi hình tròn được hiểu là độ dài "
                "đường biên của hình tròn.\n"
                "C = 2πr"
            ),
        ),
        ChunkInput(
            document_id=7,
            chunk_id=701,
            section_id=71,
            text=(
                "The present perfect is used to describe "
                "actions connected to the present."
            ),
        ),
    ]

    knowledge = extract_knowledge_objects(
        corpus,
        subject_family="mixed_regression",
    )

    must(
        "Extractor version exposed",
        SSA_QV5_EXTRACTOR_VERSION
        == "SSA-QV5-KX-V0.2",
    )

    must(
        "Planner version exposed",
        SSA_QV5_PLANNER_VERSION
        == "SSA-QV5-BP-V0.2",
    )

    kinds = {
        item.kind
        for item in knowledge
    }

    for expected in [
        KnowledgeKind.DATE,
        KnowledgeKind.DEFINITION,
        KnowledgeKind.FUNCTION,
        KnowledgeKind.FORMULA,
        KnowledgeKind.PROPERTY,
        KnowledgeKind.CAUSE,
    ]:
        must(
            f"Corpus extracts {expected.value}",
            expected in kinds,
        )

    must(
        "Single-letter formula symbols are preserved",
        any(
            item.kind
            == KnowledgeKind.FORMULA
            and item.subject in {"P", "C"}
            for item in knowledge
        ),
    )

    must(
        "All extracted facts keep evidence lineage",
        all(
            item.evidence.chunk_id > 0
            and item.evidence.document_id > 0
            and item.evidence.text
            for item in knowledge
        ),
    )

    must(
        "No extracted fact has identical subject/object",
        all(
            item.subject.casefold()
            != item.object.casefold()
            for item in knowledge
        ),
    )

    knowledge_again = extract_knowledge_objects(
        list(
            reversed(
                corpus
            )
        ),
        subject_family="mixed_regression",
    )

    must(
        "Knowledge extraction IDs are deterministic",
        sorted(
            item.id
            for item in knowledge
        )
        == sorted(
            item.id
            for item in knowledge_again
        ),
    )

    blueprints = plan_blueprints(
        knowledge
    )

    blueprint_types = {
        item.blueprint_type
        for item in blueprints
    }

    for expected in [
        BlueprintType.EVENT_DATE,
        BlueprintType.TERM_FROM_DEFINITION,
        BlueprintType.CONCEPT_FUNCTION,
        BlueprintType.FORMULA_APPLICATION,
        BlueprintType.PROPERTY_RECALL,
        BlueprintType.CAUSE_EFFECT,
    ]:
        must(
            f"Planner creates {expected.value}",
            expected
            in blueprint_types,
        )

    must(
        "Every blueprint points to a knowledge object",
        all(
            item.knowledge_id
            for item in blueprints
        ),
    )

    must(
        "Every blueprint retains source evidence",
        all(
            item.evidence.text
            and item.evidence.chunk_id > 0
            for item in blueprints
        ),
    )

    target = 7

    must(
        "Planner oversamples beyond final target",
        len(
            blueprints
        )
        > target,
    )

    selected, diag = select_diverse_blueprints(
        blueprints,
        target=target,
        max_per_section=2,
    )

    must(
        "Selector fills seven-question mixed-domain target",
        len(selected) == target
        and diag.exact,
    )

    must(
        "Final selection is diverse",
        diag.distinct_blueprint_types >= 5
        and diag.distinct_sections >= 5,
    )

    must(
        "Final answers are unique",
        len(
            {
                item.correct_answer.casefold()
                for item in selected
            }
        )
        == len(selected),
    )

    print()
    print(
        f"Extracted knowledge objects: {len(knowledge)}"
    )
    print(
        f"Planned blueprints        : {len(blueprints)}"
    )
    print(
        f"Selected final blueprints : {len(selected)}"
    )
    print(
        f"Distinct blueprint types  : "
        f"{diag.distinct_blueprint_types}"
    )
    print(
        f"Distinct source sections  : "
        f"{diag.distinct_sections}"
    )

    print("-" * 104)
    print("RESULT: PASS")
    print("=" * 104)


if __name__ == "__main__":
    main()
