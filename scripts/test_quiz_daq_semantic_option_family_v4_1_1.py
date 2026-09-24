from __future__ import annotations

from types import SimpleNamespace
import inspect

from fastapi import HTTPException

from app.services import quiz_domain
from app.services import quiz_service


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)

    print(f"[PASS] {label}")


def expect_sanitizer_failure(
    *,
    answer_text: str,
    evidence_quote: str,
    candidates: list[str],
) -> None:
    failed = False

    try:
        quiz_service._sanitize_v6_distractors(
            model_distractors=[],
            answer_text=answer_text,
            evidence_quote=evidence_quote,
            slot_answers={
                "A0": {
                    "text": answer_text,
                },
            },
            extra_candidates=candidates,
        )

    except ValueError:
        failed = True

    if not failed:
        raise AssertionError(
            "Expected sanitizer failure"
        )


def option(
    text: str,
    *,
    correct: bool,
):
    return SimpleNamespace(
        option_text=text,
        is_correct=correct,
    )


def question(
    correct_text: str,
):
    return SimpleNamespace(
        options=[
            option(
                correct_text,
                correct=True,
            ),
            option(
                "D1",
                correct=False,
            ),
            option(
                "D2",
                correct=False,
            ),
            option(
                "D3",
                correct=False,
            ),
        ]
    )


def raw_question(
    correct_text: str,
) -> dict:
    return {
        "question_text": "Q?",
        "options": [
            {
                "option_key": "A",
                "option_text": correct_text,
                "is_correct": True,
            },
            {
                "option_key": "B",
                "option_text": "D1",
                "is_correct": False,
            },
            {
                "option_key": "C",
                "option_text": "D2",
                "is_correct": False,
            },
            {
                "option_key": "D",
                "option_text": "D3",
                "is_correct": False,
            },
        ],
    }


def history_reservation_fixture():
    source_text = (
        "Cách mạng tháng Tám thành công năm 1945. "
        "Chiến thắng Điện Biên Phủ diễn ra năm 1954. "
        "Chiến dịch Hồ Chí Minh kết thúc năm 1975. "
        "Công cuộc Đổi mới bắt đầu năm 1986."
    )

    slot_specs = [
        {
            "id": "0",
            "source_text": source_text,
        }
    ]

    slots = [
        {
            "slot": "0",
            "source_ref": "S0",
        }
    ]

    evidence_by_slot = {
        "0": {
            "E0": "Cách mạng tháng Tám thành công năm 1945.",
            "E1": "Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
            "E2": "Chiến dịch Hồ Chí Minh kết thúc năm 1975.",
            "E3": "Công cuộc Đổi mới bắt đầu năm 1986.",
        }
    }

    answer_by_slot = {
        "0": {
            "A0": {
                "text": "1945",
                "evidence_id": "E0",
            },
            "A1": {
                "text": "1954",
                "evidence_id": "E1",
            },
            "A2": {
                "text": "1975",
                "evidence_id": "E2",
            },
            "A3": {
                "text": "1986",
                "evidence_id": "E3",
            },
        }
    }

    fixed_choice_by_slot = {
        "0": {
            "answer_id": "A0",
            "answer_text": "1945",
            "evidence_id": "E0",
            "evidence_text": (
                evidence_by_slot[
                    "0"
                ][
                    "E0"
                ]
            ),
        }
    }

    distractor_candidates_by_slot = {
        "0": []
    }

    return (
        slot_specs,
        slots,
        evidence_by_slot,
        answer_by_slot,
        distractor_candidates_by_slot,
        fixed_choice_by_slot,
    )


def main() -> None:
    print("=" * 118)
    print(
        "DAQ-V1.11 SEMANTIC OPTION FAMILY + "
        "RECOVERY RESERVATION + FINAL UNIQUENESS REGRESSION"
    )
    print("=" * 118)

    # -----------------------------------------------------
    # 1. Strong semantic option families.
    # -----------------------------------------------------
    check(
        "Campaign family outranks person-name substring",
        quiz_service._daq_option_family(
            "Chiến dịch Hồ Chí Minh"
        )
        == "CAMPAIGN",
    )

    check(
        "Explicit person title is PERSON",
        quiz_service._daq_option_family(
            "Chủ tịch Hồ Chí Minh"
        )
        == "PERSON",
    )

    check(
        "Treaty label is TREATY",
        quiz_service._daq_option_family(
            "Hiệp định Giơ-ne-vơ"
        )
        == "TREATY",
    )

    check(
        "Bare year is DATE",
        quiz_service._daq_option_family(
            "1945"
        )
        == "DATE",
    )

    expect_sanitizer_failure(
        answer_text="Chủ tịch Hồ Chí Minh",
        evidence_quote=(
            "Chủ tịch Hồ Chí Minh đọc "
            "Tuyên ngôn Độc lập ngày 2/9/1945."
        ),
        candidates=[
            "Chiến dịch Hồ Chí Minh",
            "Chiến thắng Điện Biên Phủ",
            "Hiệp định Giơ-ne-vơ",
        ],
    )

    print(
        "[PASS] PERSON correct answer rejects event/treaty distractors"
    )

    expect_sanitizer_failure(
        answer_text="Hiệp định Giơ-ne-vơ",
        evidence_quote=(
            "Hiệp định Giơ-ne-vơ được ký năm 1954."
        ),
        candidates=[
            "Công cuộc Đổi mới",
            "Chiến dịch Hồ Chí Minh",
            "Chiến thắng Điện Biên Phủ",
        ],
    )

    print(
        "[PASS] TREATY correct answer rejects reform/campaign/victory distractors"
    )

    dates, _ = (
        quiz_service._sanitize_v6_distractors(
            model_distractors=[],
            answer_text="1945",
            evidence_quote=(
                "Cách mạng tháng Tám "
                "thành công năm 1945."
            ),
            slot_answers={
                "A0": {
                    "text": "1945",
                },
            },
            extra_candidates=[
                "1954",
                "1975",
                "1986",
            ],
        )
    )

    check(
        "DATE keeps three DATE distractors",
        dates
        == [
            "1954",
            "1975",
            "1986",
        ],
    )

    check(
        "Generic economics term has no strong family",
        quiz_service._daq_option_family(
            "Phương tiện lưu thông"
        )
        is None,
    )

    econ, _ = (
        quiz_service._sanitize_v6_distractors(
            model_distractors=[],
            answer_text="Phương tiện lưu thông",
            evidence_quote=(
                "Phương tiện lưu thông: tiền làm môi giới "
                "trong quá trình trao đổi hàng hóa."
            ),
            slot_answers={
                "A0": {
                    "text": "Phương tiện lưu thông",
                },
            },
            extra_candidates=[
                "Phương tiện cất trữ",
                "Phương tiện thanh toán",
                "Tiền tệ thế giới",
            ],
        )
    )

    check(
        "Generic TERM behavior remains compatible",
        len(
            econ
        )
        == 3,
    )

    # -----------------------------------------------------
    # 2. Meta correct-answer rejection.
    # -----------------------------------------------------
    history_profile = (
        quiz_domain.infer_knowledge_profile(
            answer_text=(
                "Một số mốc dùng để phân biệt"
            ),
            evidence_text=(
                "Một số mốc dùng để phân biệt:"
            ),
            source_text=(
                "LỊCH SỬ VIỆT NAM. "
                "Một số mốc dùng để phân biệt."
            ),
        )
    )

    meta_pool = (
        quiz_service._daq_viable_distractor_pool(
            correct_text=(
                "Một số mốc dùng để phân biệt"
            ),
            evidence_text=(
                "Một số mốc dùng để phân biệt:"
            ),
            source_text=(
                "LỊCH SỬ VIỆT NAM. "
                "Một số mốc dùng để phân biệt."
            ),
            profile=history_profile,
            global_answer_rows=[
                {
                    "slot_id": "0",
                    "answer_id": "A0",
                    "answer_text": (
                        "Chiến dịch Hồ Chí Minh"
                    ),
                    "evidence_id": "E0",
                    "evidence_text": (
                        "Chiến dịch Hồ Chí Minh "
                        "kết thúc năm 1975."
                    ),
                },
            ],
            fallback_candidates=[
                "Chiến dịch Hồ Chí Minh",
                "Chiến thắng Điện Biên Phủ",
                "Cách mạng tháng Tám năm 1945",
            ],
        )
    )

    check(
        "Meta answer candidate has zero viable distractor pool",
        meta_pool
        == [],
    )

    check(
        "Test-data title is rejected as a correct answer",
        quiz_service._daq_correct_answer_issue(
            "LỊCH SỬ VIỆT NAM – "
            "DỮ LIỆU KIỂM THỬ DAQ-V1"
        )
        is not None,
    )

    # -----------------------------------------------------
    # 3. Request-wide recovery reservations.
    # -----------------------------------------------------
    reserved = (
        quiz_service._daq_collect_correct_answer_norms(
            [
                raw_question(
                    "1945"
                ),
                question(
                    "Chủ tịch Hồ Chí Minh"
                ),
            ]
        )
    )

    check(
        "Correct answers are collected from raw and prepared questions",
        "1945" in reserved
        and "chủ tịch hồ chí minh" in reserved,
    )

    (
        slot_specs,
        slots,
        evidence_by_slot,
        answer_by_slot,
        distractor_candidates_by_slot,
        fixed_choice_by_slot,
    ) = history_reservation_fixture()

    baseline = (
        quiz_service._daq_rebalance_fixed_choices_for_viability(
            slot_specs=slot_specs,
            slots=slots,
            evidence_by_slot=evidence_by_slot,
            answer_by_slot=answer_by_slot,
            distractor_candidates_by_slot=(
                distractor_candidates_by_slot
            ),
            fixed_choice_by_slot=(
                fixed_choice_by_slot
            ),
            reserved_correct_norms=set(),
        )
    )

    check(
        "Unreserved isolated slot keeps viable current answer 1945",
        baseline[
            "0"
        ][
            "answer_text"
        ]
        == "1945",
    )

    recovered = (
        quiz_service._daq_rebalance_fixed_choices_for_viability(
            slot_specs=slot_specs,
            slots=slots,
            evidence_by_slot=evidence_by_slot,
            answer_by_slot=answer_by_slot,
            distractor_candidates_by_slot=(
                distractor_candidates_by_slot
            ),
            fixed_choice_by_slot=(
                fixed_choice_by_slot
            ),
            reserved_correct_norms={
                "1945"
            },
        )
    )

    recovered_text = str(
        recovered[
            "0"
        ][
            "answer_text"
        ]
    )

    check(
        "Reserved 1945 is marked used during isolated recovery",
        recovered_text
        != "1945",
    )

    check(
        "Recovery selects a different grounded DATE answer",
        recovered_text
        in {
            "1954",
            "1975",
            "1986",
        },
    )

    rebalance_signature = inspect.signature(
        quiz_service._daq_rebalance_fixed_choices_for_viability
    )

    check(
        "DAQ preflight exposes request-wide reservation input",
        "reserved_correct_norms"
        in rebalance_signature.parameters,
    )

    compact_signature = inspect.signature(
        quiz_service._generate_compact_slot_questions
    )

    check(
        "Compact generator exposes request-wide reservation input",
        "reserved_correct_norms"
        in compact_signature.parameters,
    )

    generate_source = inspect.getsource(
        quiz_service.generate_quiz
    )

    check(
        "Initial partial/single recovery inherits already-returned correct answers",
        generate_source.count(
            "raw_by_slot.values()"
        )
        >= 2,
    )

    check(
        "Fast retry recovery inherits already-accepted correct answers",
        generate_source.count(
            "fast_outcomes.values()"
        )
        >= 2,
    )

    check(
        "Slot replacement inherits already-accepted correct answers",
        "accepted_by_id.values()"
        in generate_source,
    )

    # -----------------------------------------------------
    # 4. Final uniqueness defense-in-depth.
    # -----------------------------------------------------
    duplicate_rejected = False

    try:
        quiz_service._daq_assert_unique_correct_answers(
            [
                question(
                    "1945"
                ),
                question(
                    "1945"
                ),
            ]
        )

    except HTTPException as exc:
        duplicate_rejected = (
            exc.status_code
            == 422
        )

    check(
        "Duplicate correct answers are blocked before persistence",
        duplicate_rejected,
    )

    quiz_service._daq_assert_unique_correct_answers(
        [
            question(
                "1975"
            ),
            question(
                "Chủ tịch Hồ Chí Minh"
            ),
            question(
                "1945"
            ),
            question(
                "2/9/1945"
            ),
            question(
                "1954"
            ),
        ]
    )

    print(
        "[PASS] Distinct correct answers pass final persistence guard"
    )

    check(
        "Final uniqueness guard runs inside generate_quiz",
        "_daq_assert_unique_correct_answers("
        in generate_source,
    )

    sanitizer_source = inspect.getsource(
        quiz_service._sanitize_v6_distractors
    )

    check(
        "Runtime sanitizer invokes semantic option-family guard",
        "DAQ-V1.11 strong semantic option-family guard"
        in sanitizer_source,
    )

    print("-" * 118)
    print(
        "RESULT: PASS — DAQ-V1.11 blocks cross-category history "
        "distractors, rejects meta answers, propagates request-wide "
        "correct-answer reservations through recovery, and retains a "
        "final uniqueness guard before persistence"
    )
    print("=" * 118)


if __name__ == "__main__":
    main()
