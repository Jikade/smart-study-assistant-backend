from __future__ import annotations

from collections import Counter

from app.services.quiz_v5 import (
    BlueprintType,
    ChunkInput,
    EvidenceRef,
    QuestionBlueprint,
    extract_knowledge_objects,
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


def bp(
    ident: str,
    *,
    section_id: int,
    answer: str,
    score: float = 90.0,
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=ident,
        blueprint_type=(
            BlueprintType.TERM_FROM_DEFINITION
        ),
        knowledge_id=f"k-{ident}",
        stem=f"Câu hỏi {ident}?",
        correct_answer=answer,
        distractor_family="TERM",
        section_id=section_id,
        quality_score=score,
        evidence=EvidenceRef(
            document_id=1,
            chunk_id=100 + section_id,
            section_id=section_id,
            text=f"Evidence {ident}",
        ),
    )


def main() -> None:
    print()
    print("=" * 116)
    print(
        "QUIZ V5 LOGICAL SENTENCE RECONSTRUCTION + "
        "ADAPTIVE SECTION DIVERSITY V0.8 REGRESSION"
    )
    print("=" * 116)

    # Real doc-20 shapes: PDF wraps one historical sentence across lines.
    history_chunk = ChunkInput(
        document_id=20,
        chunk_id=523,
        section_id=None,
        chunk_index=12,
        text=(
            "Năm 1858, liên quân Pháp - Tây\n"
            "Ban Nha nổ súng tấn công bán đảo Sơn Trà (Đà Nẵng).\n"
            "Năm 1771, ba anh em\n"
            "Nguyễn Nhạc, Nguyễn Huệ, Nguyễn Lữ phất cờ khởi nghĩa."
        ),
    )

    history_knowledge = extract_knowledge_objects(
        [history_chunk],
        subject_family="history",
    )

    date_by_answer = {
        item.object: item.subject
        for item in history_knowledge
        if item.kind.value == "DATE"
    }

    must(
        "Soft PDF newline is joined inside 1858 event",
        "1858" in date_by_answer
        and "Ban Nha" in date_by_answer["1858"],
    )

    must(
        "Soft PDF newline is joined inside 1771 event",
        "1771" in date_by_answer
        and "Nguyễn Nhạc" in date_by_answer["1771"],
    )

    must(
        "Historical event is no longer truncated to 'liên quân Pháp - Tây'",
        date_by_answer.get("1858")
        != "liên quân Pháp - Tây",
    )

    must(
        "Historical event is no longer truncated to 'ba anh em'",
        date_by_answer.get("1771")
        != "ba anh em",
    )

    # Real doc-2 shape: definition body wraps before the semantic completion.
    economics_chunk = ChunkInput(
        document_id=2,
        chunk_id=429,
        section_id=1,
        chunk_index=0,
        text=(
            "Sản xuất hàng hóa là kiểu tổ chức kinh tế mà ở đó, "
            "những người sản xuất ra sản phẩm không nhằm mục đích\n"
            "phục vụ nhu cầu tiêu dùng của chính mình mà để trao đổi, "
            "mua bán trên thị trường."
        ),
    )

    economics_knowledge = extract_knowledge_objects(
        [economics_chunk],
        subject_family="economics",
    )

    definitions = {
        item.subject: item.object
        for item in economics_knowledge
        if item.kind.value == "DEFINITION"
    }

    must(
        "Wrapped definition keeps continuation after soft newline",
        "Sản xuất hàng hóa" in definitions
        and "phục vụ nhu cầu tiêu dùng" in definitions[
            "Sản xuất hàng hóa"
        ],
    )

    must(
        "Wrapped definition is not cut at 'không nhằm mục đích'",
        not definitions[
            "Sản xuất hàng hóa"
        ].rstrip().endswith(
            "không nhằm mục đích"
        ),
    )

    # Hard list boundaries must still remain separate.
    list_chunk = ChunkInput(
        document_id=2,
        chunk_id=430,
        section_id=1,
        chunk_index=1,
        text=(
            "Quy luật này có các tác động cơ bản:\n"
            "• Điều tiết sản xuất và lưu thông hàng hóa.\n"
            "• Kích thích cải tiến kỹ thuật."
        ),
    )

    list_knowledge = extract_knowledge_objects(
        [list_chunk],
        subject_family="economics",
    )

    must(
        "Bullet list boundaries do not create accidental merged definitions",
        not any(
            "Điều tiết sản xuất"
            in item.subject
            and "Kích thích"
            in item.subject
            for item in list_knowledge
        ),
    )

    # Real doc-2 selector shape: two viable sections, requested max=2,
    # target=5. A hard cap would mathematically stop at 4.
    candidates = [
        bp(
            "s1-a",
            section_id=1,
            answer="A1",
            score=99,
        ),
        bp(
            "s1-b",
            section_id=1,
            answer="A2",
            score=98,
        ),
        bp(
            "s1-c",
            section_id=1,
            answer="A3",
            score=97,
        ),
        bp(
            "s2-a",
            section_id=2,
            answer="B1",
            score=96,
        ),
        bp(
            "s2-b",
            section_id=2,
            answer="B2",
            score=95,
        ),
        bp(
            "s2-c",
            section_id=2,
            answer="B3",
            score=94,
        ),
    ]

    selected, diag = select_diverse_blueprints(
        candidates,
        target=5,
        max_per_section=2,
    )

    section_counts = Counter(
        item.section_id
        for item in selected
    )

    must(
        "Adaptive section cap fills five-question target",
        len(selected) == 5,
    )

    must(
        "Adaptive section cap raises 2 to minimum feasible 3",
        diag.effective_max_per_section == 3,
    )

    must(
        "Adaptive section cap still preserves section diversity",
        set(section_counts) == {1, 2}
        and max(section_counts.values()) == 3,
    )

    # If three sections make cap=2 feasible, do not relax it.
    feasible = candidates + [
        bp(
            "s3-a",
            section_id=3,
            answer="C1",
            score=93,
        ),
        bp(
            "s3-b",
            section_id=3,
            answer="C2",
            score=92,
        ),
    ]

    selected_feasible, diag_feasible = (
        select_diverse_blueprints(
            feasible,
            target=5,
            max_per_section=2,
        )
    )

    feasible_counts = Counter(
        item.section_id
        for item in selected_feasible
    )

    must(
        "Section cap stays at 2 when already feasible",
        diag_feasible.effective_max_per_section
        == 2,
    )

    must(
        "Feasible diversity never exceeds requested section cap",
        max(
            feasible_counts.values()
        )
        <= 2,
    )

    print()
    print(
        f"1858 subject          : "
        f"{date_by_answer.get('1858')}"
    )
    print(
        f"1771 subject          : "
        f"{date_by_answer.get('1771')}"
    )
    print(
        f"Adaptive section cap  : "
        f"{diag.effective_max_per_section}"
    )
    print(
        f"Selected section mix  : "
        f"{dict(section_counts)}"
    )

    print("-" * 116)
    print("RESULT: PASS")
    print("=" * 116)


if __name__ == "__main__":
    main()
