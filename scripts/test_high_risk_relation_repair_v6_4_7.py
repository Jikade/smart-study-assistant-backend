from __future__ import annotations

from app.services.quiz_service import (
    HIGH_RISK_REPAIR_VERSION,
    PERFORMANCE_VERSION,
    QUESTION_RELATION_FACT,
    _compact_item_to_raw_question,
    _detect_question_relation,
    _deterministic_high_risk_relation_repair,
    _normalize_compare_text,
)


def main():
    evidence = (
        "• Tư bản khả biến: Giá trị sức lao động, "
        "được trả dưới dạng tiền công."
    )

    bad_stem = (
        "Tư bản khả biến có tác động gì trong sản xuất?"
    )

    repaired = (
        _deterministic_high_risk_relation_repair(
            question_text=bad_stem,
            answer_text="Tư bản khả biến",
            evidence_quote=evidence,
        )
    )

    assert repaired is not None, repaired

    assert (
        _detect_question_relation(
            repaired
        )
        == QUESTION_RELATION_FACT
    ), repaired

    assert (
        _normalize_compare_text(
            "Tư bản khả biến"
        )
        not in _normalize_compare_text(
            repaired
        )
    ), repaired

    raw = _compact_item_to_raw_question(
        {
            "slot": "0",
            "q": bad_stem,
            "e": "E0",
            "a": "A0",
            "d": [
                "Tư bản bất biến",
                "Giá trị thặng dư",
                "Giá trị sức lao động",
            ],
        },
        evidence_quote_override=evidence,
        slot_id="0",
        evidence_by_slot={
            "0": {
                "E0": evidence,
            }
        },
        answer_by_slot={
            "0": {
                "A0": {
                    "text": "Tư bản khả biến",
                    "evidence_id": "E0",
                }
            }
        },
        distractor_candidates_by_slot={
            "0": [
                "Tư bản bất biến",
                "Giá trị thặng dư",
                "Giá trị sức lao động",
                "Giá trị sử dụng",
            ]
        },
    )

    final_stem = raw[
        "question_text"
    ]

    assert (
        _detect_question_relation(
            final_stem
        )
        == QUESTION_RELATION_FACT
    ), final_stem

    assert "_____" in final_stem

    correct = [
        option
        for option in raw["options"]
        if option["is_correct"]
    ]

    assert len(correct) == 1
    assert (
        correct[0]["option_text"]
        == "Tư bản khả biến"
    )

    print()
    print("=" * 72)
    print("QUIZ V6.4.7 HIGH-RISK RELATION REPAIR TEST")
    print("=" * 72)
    print("Performance version:", PERFORMANCE_VERSION)
    print("Repair version:", HIGH_RISK_REPAIR_VERSION)
    print("High-risk stem detected:", True)
    print("Deterministic repair produced FACT stem:", True)
    print("Correct answer removed from stem:", True)
    print("Compact parser no longer rejects item:", True)
    print("Repaired stem:", final_stem)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
