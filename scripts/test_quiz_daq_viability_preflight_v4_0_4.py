from __future__ import annotations

from app.services import quiz_domain
from app.services import quiz_service


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    print("=" * 104)
    print("DAQ-V1.4 DISTRACTOR-VIABILITY PREFLIGHT REGRESSION")
    print("=" * 104)

    date_phrase = quiz_domain.infer_knowledge_profile(
        answer_text="ngày 2/9/1945",
        evidence_text=(
            "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
            "ngày 2/9/1945."
        ),
        source_text=(
            "Tài liệu lịch sử Việt Nam."
        ),
    )

    print(
        "[INFO] date_phrase -> "
        f"domain={date_phrase.domain} "
        f"type={date_phrase.knowledge_type}"
    )

    check(
        "Slash-separated date phrase is HISTORY/DATE",
        date_phrase.domain == quiz_domain.HISTORY
        and date_phrase.knowledge_type == quiz_domain.DATE,
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
        "E_EVENT": (
            "Cách mạng tháng Tám thành công năm 1945."
        ),
        "E_PERSON": (
            "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
            "ngày 2/9/1945."
        ),
        "E1945": (
            "Cách mạng tháng Tám thành công năm 1945."
        ),
        "E1954": (
            "Chiến thắng Điện Biên Phủ diễn ra năm 1954."
        ),
        "E1975": (
            "Chiến dịch Hồ Chí Minh kết thúc năm 1975."
        ),
        "E1986": (
            "Công cuộc Đổi mới bắt đầu từ năm 1986."
        ),
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

    slots = [
        {"slot": str(i)}
        for i in range(5)
    ]

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

    # Deliberately poor initial choices:
    # PERSON/EVENT candidates cannot all build three
    # same-type distractors in this tiny one-chunk source.
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

    print(
        f"[INFO] chosen_texts={chosen_texts!r}"
    )

    chosen_profiles = [
        quiz_domain.infer_knowledge_profile(
            answer_text=rebalanced[str(i)]["answer_text"],
            evidence_text=rebalanced[str(i)]["evidence_text"],
            source_text=source,
        )
        for i in range(5)
    ]

    check(
        "Five slots receive five unique backend-owned answers",
        len(
            {
                quiz_service._normalize_compare_text(value)
                for value in chosen_texts
            }
        )
        == 5,
    )

    check(
        "Tiny history source is rebalanced toward viable DATE answers",
        all(
            profile.knowledge_type
            == quiz_domain.DATE
            for profile in chosen_profiles
        ),
    )

    # Verify each rebalanced choice can really make three
    # safe distractors before any model call.
    global_rows = []

    for slot_id, bucket in answer_by_slot.items():
        for answer_id, spec in bucket.items():
            global_rows.append(
                {
                    "slot_id": slot_id,
                    "answer_id": answer_id,
                    "answer_text": spec["text"],
                    "evidence_id": spec["evidence_id"],
                    "evidence_text": evidence[
                        spec["evidence_id"]
                    ],
                }
            )

    for i in range(5):
        slot_id = str(i)
        choice = rebalanced[slot_id]
        profile = chosen_profiles[i]

        pool = quiz_service._daq_viable_distractor_pool(
            correct_text=choice["answer_text"],
            evidence_text=choice["evidence_text"],
            source_text=source,
            profile=profile,
            global_answer_rows=global_rows,
            fallback_candidates=[],
        )

        distractors, _ = (
            quiz_service._sanitize_v6_distractors(
                model_distractors=[],
                answer_text=choice["answer_text"],
                evidence_quote=choice["evidence_text"],
                slot_answers={
                    choice["answer_id"]: {
                        "text": choice["answer_text"],
                    }
                },
                extra_candidates=pool,
            )
        )

        print(
            f"[INFO] slot={slot_id} "
            f"answer={choice['answer_text']!r} "
            f"distractors={distractors!r}"
        )

        check(
            f"Slot {slot_id} has exactly three safe distractors",
            len(distractors) == 3,
        )

    print("-" * 104)
    print(
        "RESULT: PASS — DAQ-V1.4 detects distractor viability before AI, "
        "reselects grounded answers for tiny one-chunk documents, and "
        "does not confuse slash-separated dates with math formulas"
    )
    print("=" * 104)


if __name__ == "__main__":
    main()
