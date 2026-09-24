from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect

from app.services import quiz_service


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)

    print(f"[PASS] {label}")


def main() -> None:
    print("=" * 108)
    print("DAQ-V1.8 SIBLING MICRO-CONTEXT DISTRACTOR SHARING REGRESSION")
    print("=" * 108)

    check(
        "Sibling distractor helper exists",
        hasattr(
            quiz_service,
            "_daq_share_sibling_microcontext_distractors",
        ),
    )

    shared_chunk = SimpleNamespace(
        id=777
    )

    other_chunk = SimpleNamespace(
        id=888
    )

    slot_specs = [
        {
            "id": "0",
            "source_chunk": shared_chunk,
            "source_text": (
                "Chiến dịch Hồ Chí Minh kết thúc thắng lợi năm 1975. "
                "Công cuộc Đổi mới bắt đầu từ năm 1986."
            ),
        },
        {
            "id": "1",
            "source_chunk": shared_chunk,
            "source_text": (
                "Cách mạng tháng Tám thành công năm 1945. "
                "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập."
            ),
        },
        {
            "id": "2",
            "source_chunk": shared_chunk,
            "source_text": (
                "Chiến thắng Điện Biên Phủ diễn ra năm 1954. "
                "Hiệp định Giơ-ne-vơ được ký năm 1954."
            ),
        },
        {
            "id": "3",
            "source_chunk": other_chunk,
            "source_text": (
                "Một tài liệu địa lý độc lập."
            ),
        },
    ]

    answer_by_slot = {
        "0": {
            "A0": {
                "text": "Chiến dịch Hồ Chí Minh",
                "evidence_id": "E0",
            },
            "A1": {
                "text": "Công cuộc Đổi mới",
                "evidence_id": "E1",
            },
        },
        "1": {
            "A0": {
                "text": "Cách mạng tháng Tám năm 1945",
                "evidence_id": "E0",
            },
            "A1": {
                "text": "Chủ tịch Hồ Chí Minh",
                "evidence_id": "E1",
            },
        },
        "2": {
            "A0": {
                "text": "Chiến thắng Điện Biên Phủ",
                "evidence_id": "E0",
            },
            "A1": {
                "text": "Hiệp định Giơ-ne-vơ",
                "evidence_id": "E1",
            },
        },
        "3": {
            "A0": {
                "text": "Đồng bằng sông Hồng",
                "evidence_id": "E0",
            },
        },
    }

    original_answers = deepcopy(
        answer_by_slot
    )

    distractor_candidates_by_slot = {
        "0": [],
        "1": [],
        "2": [],
        "3": [],
    }

    quiz_service._daq_share_sibling_microcontext_distractors(
        slot_specs=slot_specs,
        answer_by_slot=answer_by_slot,
        distractor_candidates_by_slot=(
            distractor_candidates_by_slot
        ),
    )

    slot1_pool = (
        distractor_candidates_by_slot[
            "1"
        ]
    )

    print(
        f"[INFO] slot1_pool={slot1_pool!r}"
    )

    check(
        "Sibling answers from same source chunk are shared as distractor text",
        "Chiến dịch Hồ Chí Minh"
        in slot1_pool
        and "Công cuộc Đổi mới"
        in slot1_pool
        and "Chiến thắng Điện Biên Phủ"
        in slot1_pool
        and "Hiệp định Giơ-ne-vơ"
        in slot1_pool,
    )

    check(
        "Cross-chunk answer is not shared",
        "Đồng bằng sông Hồng"
        not in slot1_pool,
    )

    check(
        "Correct-answer catalogs remain unchanged",
        answer_by_slot
        == original_answers,
    )

    check(
        "Target slot does not import sibling answer/evidence IDs",
        set(
            answer_by_slot[
                "1"
            ].keys()
        )
        == {
            "A0",
            "A1",
        },
    )

    # Downstream sanitizer remains authoritative.
    distractors, replacements = (
        quiz_service._sanitize_v6_distractors(
            model_distractors=[],
            answer_text=(
                "Cách mạng tháng Tám năm 1945"
            ),
            evidence_quote=(
                "Cách mạng tháng Tám thành công năm 1945. "
                "Sự kiện này dẫn tới sự ra đời của nước "
                "Việt Nam Dân chủ Cộng hòa."
            ),
            slot_answers=(
                answer_by_slot[
                    "1"
                ]
            ),
            extra_candidates=(
                slot1_pool
            ),
        )
    )

    print(
        f"[INFO] sanitized_distractors={distractors!r}"
    )
    print(
        f"[INFO] replacements={replacements}"
    )

    check(
        "Existing sanitizer can select exactly three safe distractors from sibling pool",
        len(
            distractors
        )
        == 3,
    )

    check(
        "Correct answer is never reintroduced as a distractor",
        all(
            item.casefold()
            != "Cách mạng tháng Tám năm 1945".casefold()
            for item in distractors
        ),
    )

    generate_source = inspect.getsource(
        quiz_service._generate_compact_slot_questions
    )

    share_pos = generate_source.find(
        "_daq_share_sibling_microcontext_distractors("
    )

    fixed_pos = generate_source.find(
        "fixed_choice_by_slot ="
    )

    check(
        "Sibling sharing runs before fixed-choice preselection",
        share_pos >= 0
        and fixed_pos >= 0
        and share_pos < fixed_pos,
    )

    helper_source = inspect.getsource(
        quiz_service._daq_share_sibling_microcontext_distractors
    )

    check(
        "Sibling helper changes only distractor candidate mapping",
        "answer_by_slot[" not in helper_source
        and "evidence_by_slot" not in helper_source,
    )

    print("-" * 108)
    print(
        "RESULT: PASS — DAQ-V1.8 shares only distractor text across "
        "micro-contexts of the same source chunk, preserves local "
        "answer/evidence ownership, and gives the existing sanitizer "
        "enough candidate capacity"
    )
    print("=" * 108)


if __name__ == "__main__":
    main()
