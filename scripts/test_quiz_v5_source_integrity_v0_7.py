from __future__ import annotations

from app.services.quiz_v5 import (
    BlueprintType,
    ChunkInput,
    EvidenceRef,
    QuestionBlueprint,
    extract_knowledge_objects,
    select_diverse_blueprints,
)
from app.services.quiz_v5.validators import option_quality_issue


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)

    print(f"[PASS] {label}")


def bp(
    ident: str,
    *,
    answer: str,
    stem: str,
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=ident,
        blueprint_type=BlueprintType.EVENT_DATE,
        knowledge_id=f"k-{ident}",
        stem=stem,
        correct_answer=answer,
        distractor_family="DATE",
        section_id=None,
        quality_score=90.0,
        evidence=EvidenceRef(
            document_id=1,
            chunk_id=100,
            section_id=None,
            text=f"Evidence {ident}",
        ),
    )


def main() -> None:
    print()
    print("=" * 116)
    print(
        "QUIZ V5 SOURCE INTEGRITY + "
        "FORMULA LEXER V0.7 REGRESSION"
    )
    print("=" * 116)

    # Real doc-19 capacity: two different DATE facts answer 1954.
    candidates = [
        bp(
            "d1",
            answer="1954",
            stem="Điện Biên Phủ?",
        ),
        bp(
            "d2",
            answer="1954",
            stem="Điện Biên Phủ + Geneva?",
        ),
        bp(
            "d3",
            answer="1945",
            stem="Cách mạng tháng Tám?",
        ),
        bp(
            "d4",
            answer="1975",
            stem="Chiến dịch Hồ Chí Minh?",
        ),
        bp(
            "d5",
            answer="1986",
            stem="Đổi mới?",
        ),
    ]

    selected, _ = select_diverse_blueprints(
        candidates,
        target=5,
    )

    must(
        "Duplicate correct answers keep real DATE capacity at four",
        len(selected) == 4,
    )

    must(
        "Selected DATE answers remain globally unique",
        len(
            {
                item.correct_answer
                for item in selected
            }
        )
        == 4,
    )

    # Real doc-20 / doc-2 definition fragment shapes.
    source = ChunkInput(
        document_id=20,
        chunk_id=511,
        section_id=None,
        chunk_index=0,
        text=(
            "iệt Nam là một quốc gia có bề dày lịch sử hàng nghìn năm. "
            "Nó là nguồn. "
            "biểu hiện bằng tiền gọi là giá cả hàng hóa. "
            "hiệu riêng là sự khẳng định chủ quyền. "
            "Quy luật giá trị là quy luật kinh tế cơ bản."
        ),
    )

    subjects = {
        item.subject.casefold()
        for item in extract_knowledge_objects(
            [source],
            subject_family="mixed",
        )
        if item.kind.value == "DEFINITION"
    }

    must(
        "Broken lowercase proper-noun definition is rejected",
        "iệt nam" not in subjects,
    )

    must(
        "Pronoun definition subject is rejected",
        "nó" not in subjects,
    )

    must(
        "Predicate-like lowercase subject is rejected",
        "biểu hiện bằng tiền gọi" not in subjects,
    )

    must(
        "Lowercase fragment subject is rejected",
        "hiệu riêng" not in subjects,
    )

    must(
        "Clean sentence-initial definition remains accepted",
        "quy luật giá trị" in subjects,
    )

    # Real doc-2 lexer bug.
    formula_source = ChunkInput(
        document_id=2,
        chunk_id=434,
        section_id=4,
        chunk_index=5,
        text=(
            "Giá cả sản xuất = Chi phí sản xuất + Lợi nhuận bình quân. "
            "W = c + v + m. "
            "GDP = C + I + G + NX."
        ),
    )

    formulas = {
        item.object
        for item in extract_knowledge_objects(
            [formula_source],
            subject_family="economics",
        )
        if item.kind.value == "FORMULA"
    }

    must(
        "Unicode formula boundary removes t = Chi false positive",
        "t = Chi" not in formulas,
    )

    must(
        "Single-letter formula remains extractable",
        "W = c + v + m" in formulas,
    )

    must(
        "Uppercase acronym formula remains extractable",
        "GDP = C + I + G + NX" in formulas,
    )

    must(
        "Final validator rejects t = Chi shape",
        option_quality_issue(
            "t = Chi",
            family="FORMULA",
        )
        is not None,
    )

    # Open tail boundary.
    chunks = [
        ChunkInput(
            document_id=20,
            chunk_id=521,
            section_id=None,
            chunk_index=10,
            text=(
                "Năm 1785: Đánh tan quân Xiêm. "
                "Năm 1802, Nguyễn Ánh lên ngôi, lập ra triều"
            ),
        ),
        ChunkInput(
            document_id=20,
            chunk_id=522,
            section_id=None,
            chunk_index=11,
            text=(
                "Triều Nguyễn được củng cố trong những năm sau."
            ),
        ),
    ]

    dates = {
        (item.subject, item.object)
        for item in extract_knowledge_objects(
            chunks,
            subject_family="history",
        )
        if item.kind.value == "DATE"
    }

    must(
        "Closed event before open tail remains extractable",
        any(
            answer == "1785"
            for _, answer in dates
        ),
    )

    must(
        "Open chunk-tail event is skipped",
        not any(
            answer == "1802"
            for _, answer in dates
        ),
    )

    must(
        "TERM validator rejects broken proper noun",
        option_quality_issue(
            "iệt Nam",
            family="TERM",
        )
        == "term_broken_proper_noun",
    )

    print()
    print(
        f"Selected DATE answers : "
        f"{[item.correct_answer for item in selected]}"
    )
    print(
        f"Definitions retained  : "
        f"{sorted(subjects)}"
    )
    print(
        f"Formulas retained     : "
        f"{sorted(formulas)}"
    )

    print("-" * 116)
    print("RESULT: PASS")
    print("=" * 116)


if __name__ == "__main__":
    main()
