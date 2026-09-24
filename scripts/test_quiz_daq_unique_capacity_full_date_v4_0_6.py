from __future__ import annotations

from app.services import quiz_domain
from app.services import quiz_service


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    print("=" * 104)
    print("DAQ-V1.6 UNIQUE CAPACITY + FULL DATE REGRESSION")
    print("=" * 104)

    full_date_profile = quiz_domain.infer_knowledge_profile(
        answer_text="ngày 2/9/1945",
        evidence_text=(
            "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
            "ngày 2/9/1945."
        ),
        source_text="Tài liệu lịch sử Việt Nam.",
    )

    variants = quiz_domain.structured_distractor_variants(
        "ngày 2/9/1945",
        profile=full_date_profile,
    )

    print(f"[INFO] full_date_variants={variants!r}")

    check(
        "Full date produces at least three structured variants",
        len(variants) >= 3,
    )

    check(
        "Full date variants do not repeat the correct answer",
        "ngày 2/9/1945" not in variants,
    )

    source = """
LỊCH SỬ VIỆT NAM

Cách mạng tháng Tám:
Cách mạng tháng Tám thành công năm 1945.

Tuyên ngôn Độc lập:
Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập ngày 2/9/1945.

Chiến thắng Điện Biên Phủ:
Chiến thắng Điện Biên Phủ diễn ra năm 1954.

Chiến dịch Hồ Chí Minh:
Chiến dịch Hồ Chí Minh kết thúc năm 1975.

Công cuộc Đổi mới:
Công cuộc Đổi mới bắt đầu từ năm 1986.
""".strip()

    evidence = {
        "E_EVENT": "Cách mạng tháng Tám thành công năm 1945.",
        "E_PERSON": (
            "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
            "ngày 2/9/1945."
        ),
        "E1945": "Cách mạng tháng Tám thành công năm 1945.",
        "E1954": "Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
        "E1975": "Chiến dịch Hồ Chí Minh kết thúc năm 1975.",
        "E1986": "Công cuộc Đổi mới bắt đầu từ năm 1986.",
        "E_DATE": (
            "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
            "ngày 2/9/1945."
        ),
    }

    answer_template = {
        "A_EVENT": {
            "text": "Cách mạng tháng Tám",
            "evidence_id": "E_EVENT",
        },
        "A_PERSON": {
            "text": "Hồ Chí Minh",
            "evidence_id": "E_PERSON",
        },
        "A1945": {
            "text": "1945",
            "evidence_id": "E1945",
        },
        "A1954": {
            "text": "1954",
            "evidence_id": "E1954",
        },
        "A1975": {
            "text": "1975",
            "evidence_id": "E1975",
        },
        "A1986": {
            "text": "1986",
            "evidence_id": "E1986",
        },
        "A_DATE": {
            "text": "ngày 2/9/1945",
            "evidence_id": "E_DATE",
        },
    }

    slots = [{"slot": str(i)} for i in range(5)]

    slot_specs = [
        {
            "id": str(i),
            "source_text": source,
        }
        for i in range(5)
    ]

    evidence_by_slot = {
        str(i): dict(evidence)
        for i in range(5)
    }

    answer_by_slot = {
        str(i): {
            key: dict(value)
            for key, value in answer_template.items()
        }
        for i in range(5)
    }

    fixed = {
        "0": {
            "answer_id": "A_PERSON",
            "answer_text": "Hồ Chí Minh",
            "evidence_id": "E_PERSON",
            "evidence_text": evidence["E_PERSON"],
        },
        "1": {
            "answer_id": "A_EVENT",
            "answer_text": "Cách mạng tháng Tám",
            "evidence_id": "E_EVENT",
            "evidence_text": evidence["E_EVENT"],
        },
        "2": {
            "answer_id": "A_PERSON",
            "answer_text": "Hồ Chí Minh",
            "evidence_id": "E_PERSON",
            "evidence_text": evidence["E_PERSON"],
        },
        "3": {
            "answer_id": "A_EVENT",
            "answer_text": "Cách mạng tháng Tám",
            "evidence_id": "E_EVENT",
            "evidence_text": evidence["E_EVENT"],
        },
        "4": {
            "answer_id": "A_DATE",
            "answer_text": "ngày 2/9/1945",
            "evidence_id": "E_DATE",
            "evidence_text": evidence["E_DATE"],
        },
    }

    rebalanced = (
        quiz_service._daq_rebalance_fixed_choices_for_viability(
            slot_specs=slot_specs,
            slots=slots,
            evidence_by_slot=evidence_by_slot,
            answer_by_slot=answer_by_slot,
            distractor_candidates_by_slot={
                str(i): []
                for i in range(5)
            },
            fixed_choice_by_slot=fixed,
        )
    )

    chosen_texts = [
        rebalanced[str(i)]["answer_text"]
        for i in range(5)
    ]

    print(f"[INFO] chosen_texts={chosen_texts!r}")

    normalized = {
        quiz_service._normalize_compare_text(value)
        for value in chosen_texts
    }

    check(
        "Five slots receive five unique correct answers",
        len(normalized) == 5,
    )

    check(
        "Full date remains available as a distinct fifth answer",
        "ngày 2/9/1945" in chosen_texts,
    )

    check(
        "Bare year 1945 appears at most once",
        chosen_texts.count("1945") <= 1,
    )

    print("-" * 104)
    print(
        "RESULT: PASS — DAQ-V1.6 preserves full-date answers, "
        "forbids duplicate correct answers, and guarantees unique "
        "preflight capacity before any AI generation"
    )
    print("=" * 104)


if __name__ == "__main__":
    main()
