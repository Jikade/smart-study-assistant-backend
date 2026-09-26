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
    SSA_QV5_DISTRACTOR_HARDENING_VERSION,
    build_distractors,
)
from app.services.quiz_v5.extractor import (
    SSA_QV5_EXTRACTOR_HARDENING_VERSION,
)
from app.services.quiz_v5.selector import (
    SSA_QV5_SELECTOR_HARDENING_VERSION,
)
from app.services.quiz_v5.validators import (
    SSA_QV5_VALIDATOR_HARDENING_VERSION,
    option_quality_issue,
)


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def bp(
    ident: str,
    *,
    stem: str,
    answer: str,
    family: str,
    kind: BlueprintType,
    score: float,
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=ident,
        blueprint_type=kind,
        knowledge_id=f"k-{ident}",
        stem=stem,
        correct_answer=answer,
        distractor_family=family,
        section_id=1,
        quality_score=score,
        evidence=EvidenceRef(
            document_id=1,
            chunk_id=100 + len(ident),
            section_id=1,
            text=f"Evidence {ident}",
        ),
    )


def main() -> None:
    print()
    print("=" * 112)
    print("QUIZ V5 REAL-DOCUMENT QUALITY HARDENING V0.5 REGRESSION")
    print("=" * 112)

    observed_bad_history = ChunkInput(
        document_id=20,
        chunk_id=511,
        section_id=None,
        text=(
            "Xuyên suốt chiều dài lịch sử, đặc điểm nổi bật nhất "
            "của dân tộc Việt Nam là sức sống mãnh liệt. "
            "Năm 791 Phùng Hưng Được nhân dân suy tôn là "
            "Bố Cái Đại Vương, lãnh đạo. "
            "Đây là giai đoạn kiến thiết. "
            'Về ngoại giao, với phương châm "Việt Nam muốn '
            'là bạn với tất cả các nước", chúng ta đã phá vỡ thế.'
        ),
    )

    bad_knowledge = extract_knowledge_objects(
        [observed_bad_history],
        subject_family="history",
    )
    subjects = {item.subject.casefold() for item in bad_knowledge}

    must("Generic subject 'Đây' is rejected", "đây" not in subjects)
    must(
        "Long narrative clause is not a definition term",
        not any(s.startswith("xuyên suốt chiều dài lịch sử") for s in subjects),
    )
    must(
        "Temporal narrative clause is not a definition term",
        not any(s.startswith("năm 791") for s in subjects),
    )
    must(
        "Punctuated diplomatic clause is not a definition term",
        not any(s.startswith("về ngoại giao") for s in subjects),
    )

    historical = ChunkInput(
        document_id=19,
        chunk_id=492,
        section_id=None,
        text=(
            "Năm 938, Ngô Quyền đánh bại quân Nam Hán trên sông Bạch Đằng. "
            "968 – Đinh Bộ Lĩnh dẹp loạn 12 sứ quân."
        ),
    )

    history_knowledge = extract_knowledge_objects(
        [historical],
        subject_family="history",
    )
    dates = {
        item.object
        for item in history_knowledge
        if item.kind.value == "DATE"
    }

    must("Leading-year historical prose extracts 938", "938" in dates)
    must("Year-label historical prose extracts 968", "968" in dates)

    formula_chunk = ChunkInput(
        document_id=2,
        chunk_id=433,
        section_id=2,
        text=(
            "Khi đó, công thức W = c + v + m chuyển thành "
            "W = k + m. Khi bán hàng hóa, giá trị thặng dư mang hình thái lợi nhuận."
        ),
    )

    formula_knowledge = extract_knowledge_objects(
        [formula_chunk],
        subject_family="economics",
    )
    formulas = {
        item.object
        for item in formula_knowledge
        if item.kind.value == "FORMULA"
    }

    must("Formula parser stops before Vietnamese prose", "W = c + v + m" in formulas)
    must("Formula parser finds second equation independently", "W = k + m" in formulas)
    must(
        "Formula parser never keeps prose tails",
        all("chuy" not in v.casefold() and "khi b" not in v.casefold() for v in formulas),
    )

    candidates = [
        bp(
            "w1",
            stem='Biểu thức nào mô tả đại lượng “W” theo tài liệu?',
            answer="W = c + v + m",
            family="FORMULA",
            kind=BlueprintType.FORMULA_APPLICATION,
            score=99,
        ),
        bp(
            "w2",
            stem='Biểu thức nào mô tả đại lượng “W” theo tài liệu?',
            answer="W = k + m",
            family="FORMULA",
            kind=BlueprintType.FORMULA_APPLICATION,
            score=98,
        ),
        bp(
            "term1",
            stem="Khái niệm nào là quy luật kinh tế cơ bản?",
            answer="Quy luật giá trị",
            family="TERM",
            kind=BlueprintType.TERM_FROM_DEFINITION,
            score=90,
        ),
    ]

    selected, diag = select_diverse_blueprints(candidates, target=3)
    must(
        "Duplicate normalized stems cannot coexist",
        sum(1 for item in selected if "đại lượng “w”" in item.stem.casefold()) == 1,
    )
    must(
        "Selector safely returns partial when duplicate stem blocks target",
        len(selected) == 2 and not diag.exact,
    )

    must(
        "Extractor hardening version exposed",
        SSA_QV5_EXTRACTOR_HARDENING_VERSION == "SSA-QV5-KX-V0.5",
    )
    must(
        "Selector hardening version exposed",
        SSA_QV5_SELECTOR_HARDENING_VERSION == "SSA-QV5-SEL-V0.5",
    )
    must(
        "Validator hardening version exposed",
        SSA_QV5_VALIDATOR_HARDENING_VERSION == "SSA-QV5-VAL-V0.5",
    )
    must(
        "Distractor hardening version exposed",
        SSA_QV5_DISTRACTOR_HARDENING_VERSION == "SSA-QV5-DX-V0.5",
    )

    must(
        "Bullet term is rejected",
        option_quality_issue("• Giá trị sử dụng", family="TERM") == "bullet_option",
    )
    must(
        "Clause-shaped term is rejected",
        option_quality_issue(
            "Lượng giá trị của hàng hóa: Được đo bằng thời gian lao động",
            family="TERM",
        ) == "term_clause_shape",
    )
    must(
        "Malformed formula prose is rejected",
        option_quality_issue("W = k + m. Khi b", family="FORMULA") is not None,
    )

    target = bp(
        "term-target",
        stem="Khái niệm nào phù hợp?",
        answer="Quy luật giá trị",
        family="TERM",
        kind=BlueprintType.TERM_FROM_DEFINITION,
        score=99,
    )
    pool = [
        target,
        bp("good-1", stem="s1", answer="Giá trị sử dụng", family="TERM",
           kind=BlueprintType.TERM_FROM_DEFINITION, score=90),
        bp("bad-bullet", stem="s2", answer="• Giá trị của hàng hóa", family="TERM",
           kind=BlueprintType.TERM_FROM_DEFINITION, score=95),
        bp("bad-clause", stem="s3",
           answer="Lượng giá trị hàng hóa: Được đo bằng thời gian lao động",
           family="TERM", kind=BlueprintType.TERM_FROM_DEFINITION, score=94),
        bp("good-2", stem="s4", answer="Giá trị trao đổi", family="TERM",
           kind=BlueprintType.TERM_FROM_DEFINITION, score=89),
        bp("good-3", stem="s5", answer="Hàng hóa", family="TERM",
           kind=BlueprintType.TERM_FROM_DEFINITION, score=88),
    ]

    distractors, _ = build_distractors(target, candidate_pool=pool)
    must(
        "TERM builder skips bullet/clause distractors",
        distractors is not None
        and set(distractors) == {
            "Giá trị sử dụng",
            "Giá trị trao đổi",
            "Hàng hóa",
        },
    )

    print()
    print(f"Historical DATE facts : {sorted(dates)}")
    print(f"Clean formulas        : {sorted(formulas)}")
    print(f"Selected IDs          : {[item.id for item in selected]}")
    print("-" * 112)
    print("RESULT: PASS")
    print("=" * 112)


if __name__ == "__main__":
    main()
