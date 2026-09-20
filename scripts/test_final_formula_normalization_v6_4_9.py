from __future__ import annotations

from types import SimpleNamespace

from app.services.quiz_service import (
    FINAL_FORMULA_NORMALIZATION_VERSION,
    PERFORMANCE_VERSION,
    _final_formula_normalization,
    _normalize_single_formula_expression,
)


def option(
    key: str,
    text: str,
    correct: bool,
):
    return SimpleNamespace(
        option_key=key,
        option_text=text,
        is_correct=correct,
        explanation=None,
        position=ord(key) - ord("A") + 1,
    )


def main():
    # --------------------------------------------------
    # Regression 1: preserve Unicode Δ while stripping
    # the discourse prefix from the formula answer.
    # --------------------------------------------------
    raw_formula = (
        "trong đó T' = T + ΔT"
    )

    normalized_formula = (
        _normalize_single_formula_expression(
            raw_formula
        )
    )

    assert (
        normalized_formula
        == "T' = T + ΔT"
    ), normalized_formula

    q1 = SimpleNamespace(
        question_text=(
            "Điền công thức thích hợp vào chỗ trống: "
            "Mục đích của lưu thông tư bản là giá trị "
            "và giá trị thặng dư, _____."
        ),
        options=[
            option(
                "A",
                "trong đó T' = T + ΔT",
                True,
            ),
            option(
                "B",
                "T' = T - ΔT",
                False,
            ),
            option(
                "C",
                "T' = ΔT",
                False,
            ),
            option(
                "D",
                "k = c + v",
                False,
            ),
        ],
    )

    q1_after, q1_normalized, q1_context = (
        _final_formula_normalization(
            q1,
            evidence_quote=(
                "Mục đích của lưu thông tư bản là "
                "giá trị và giá trị thặng dư, "
                "trong đó T' = T + ΔT."
            ),
        )
    )

    q1_correct = [
        item.option_text
        for item in q1_after.options
        if item.is_correct
    ][0]

    assert q1_correct == "T' = T + ΔT"
    assert q1_normalized == 1
    assert q1_context is False

    # --------------------------------------------------
    # Regression 2: generic W rewrite question must gain
    # concrete source context via deterministic cloze.
    # --------------------------------------------------
    q2 = SimpleNamespace(
        question_text=(
            "Công thức W được viết lại thành gì?"
        ),
        options=[
            option(
                "A",
                "W = k + v",
                False,
            ),
            option(
                "B",
                "W = k + m",
                True,
            ),
            option(
                "C",
                "W = m + c",
                False,
            ),
            option(
                "D",
                "T' = T",
                False,
            ),
        ],
    )

    evidence = (
        "Chi phí thực tế để sản xuất ra hàng hóa "
        "là c + v + m. Chi phí sản xuất tư bản "
        "chủ nghĩa là k = c + v. Khi đó, công thức "
        "W = c + v + m chuyển thành W = k + m."
    )

    q2_after, q2_normalized, q2_context = (
        _final_formula_normalization(
            q2,
            evidence_quote=evidence,
        )
    )

    assert q2_normalized == 0
    assert q2_context is True

    assert "_____" in q2_after.question_text
    assert (
        "W = c + v + m"
        in q2_after.question_text
    ), q2_after.question_text

    assert (
        q2_after.question_text
        != "Công thức W được viết lại thành gì?"
    )

    q2_correct = [
        item.option_text
        for item in q2_after.options
        if item.is_correct
    ][0]

    assert q2_correct == "W = k + m"

    print()
    print("=" * 72)
    print("QUIZ V6.4.9 FINAL FORMULA NORMALIZATION TEST")
    print("=" * 72)
    print("Performance version:", PERFORMANCE_VERSION)
    print(
        "Final formula normalization version:",
        FINAL_FORMULA_NORMALIZATION_VERSION,
    )
    print("Unicode Δ preserved:", True)
    print("Formula discourse prefix removed:", True)
    print("Generic W rewrite stem contextualized:", True)
    print("Correct formula remains source-grounded:", True)
    print("Normalized Q1 answer:", q1_correct)
    print("Contextualized Q2 stem:", q2_after.question_text)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
