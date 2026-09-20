from __future__ import annotations

from app.services.quiz_service import (
    CLOZE_RELATION_PRECEDENCE_VERSION,
    HIGH_RISK_REPAIR_VERSION,
    PERFORMANCE_VERSION,
    QUESTION_RELATION_FACT,
    QUESTION_RELATION_FORMULA,
    _detect_question_relation,
    _deterministic_high_risk_relation_repair,
)


def main():
    # --------------------------------------------------
    # Regression 1:
    # source text contains "tác động", but repaired cloze
    # must be FACT, not EFFECT.
    # --------------------------------------------------
    bad_effect_stem = (
        "Quy luật giá trị có những tác động gì?"
    )

    effect_evidence = (
        "Tác động của quy luật giá trị: "
        "Điều tiết sản xuất và lưu thông hàng hóa."
    )

    repaired_effect = (
        _deterministic_high_risk_relation_repair(
            question_text=bad_effect_stem,
            answer_text=(
                "Điều tiết sản xuất và lưu thông hàng hóa"
            ),
            evidence_quote=effect_evidence,
        )
    )

    assert repaired_effect is not None, repaired_effect
    assert "_____" in repaired_effect

    assert (
        _detect_question_relation(
            repaired_effect
        )
        == QUESTION_RELATION_FACT
    ), repaired_effect

    # --------------------------------------------------
    # Regression 2:
    # source text contains "mục đích", but deterministic
    # cloze still represents FACT identification.
    # --------------------------------------------------
    purpose_cloze = (
        "Điền cụm từ thích hợp vào chỗ trống: "
        "Mục đích của lưu thông hàng hóa là _____."
    )

    assert (
        _detect_question_relation(
            purpose_cloze
        )
        == QUESTION_RELATION_FACT
    ), purpose_cloze

    # --------------------------------------------------
    # Regression 3:
    # formula cloze keeps FORMULA relation precedence.
    # --------------------------------------------------
    formula_cloze = (
        "Điền công thức thích hợp vào chỗ trống: "
        "Sau khi thay đổi, công thức W chuyển thành _____."
    )

    assert (
        _detect_question_relation(
            formula_cloze
        )
        == QUESTION_RELATION_FORMULA
    ), formula_cloze

    print()
    print("=" * 72)
    print("QUIZ V6.4.8 CLOZE RELATION PRECEDENCE TEST")
    print("=" * 72)
    print("Performance version:", PERFORMANCE_VERSION)
    print("High-risk repair version:", HIGH_RISK_REPAIR_VERSION)
    print(
        "Cloze precedence version:",
        CLOZE_RELATION_PRECEDENCE_VERSION,
    )
    print("Effect wording inside evidence no longer misclassifies cloze:", True)
    print("Purpose wording inside cloze context remains FACT:", True)
    print("Formula cloze remains FORMULA:", True)
    print("Repaired production-like stem:", repaired_effect)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
