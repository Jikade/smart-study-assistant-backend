from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect

from app.services import quiz_domain
from app.services import quiz_service


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)

    print(f"[PASS] {label}")


def main() -> None:
    print("=" * 112)
    print("DAQ-V1.10 ATOMIC DATE ANSWERS + PROSE/HYPHEN FORMULA GUARD REGRESSION")
    print("=" * 112)

    history_source = (
        "LỊCH SỬ VIỆT NAM – DỮ LIỆU KIỂM THỬ DAQ-V1. "
        "Cách mạng tháng Tám thành công năm 1945. "
        "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
        "ngày 2/9/1945. "
        "Chiến thắng Điện Biên Phủ diễn ra năm 1954. "
        "Chiến dịch Hồ Chí Minh kết thúc năm 1975. "
        "Công cuộc Đổi mới bắt đầu năm 1986."
    )

    timeline_profile = (
        quiz_domain.infer_knowledge_profile(
            answer_text=(
                "1954 – Chiến thắng Điện Biên Phủ "
                "và Hiệp định Giơ-ne-vơ"
            ),
            evidence_text=(
                "Chiến thắng Điện Biên Phủ diễn ra năm 1954 "
                "và Hiệp định Giơ-ne-vơ được ký năm 1954."
            ),
            source_text=history_source,
        )
    )

    print(
        "[INFO] timeline_profile="
        f"{timeline_profile.domain}/"
        f"{timeline_profile.knowledge_type}"
    )

    check(
        "History timeline label is not MATHEMATICS/FORMULA",
        not (
            timeline_profile.domain
            == quiz_domain.MATHEMATICS
            or timeline_profile.knowledge_type
            == quiz_domain.FORMULA
        ),
    )

    title_profile = (
        quiz_domain.infer_knowledge_profile(
            answer_text=(
                "LỊCH SỬ VIỆT NAM – "
                "DỮ LIỆU KIỂM THỬ DAQ-V1"
            ),
            evidence_text=(
                "LỊCH SỬ VIỆT NAM – "
                "DỮ LIỆU KIỂM THỬ DAQ-V1"
            ),
            source_text=history_source,
        )
    )

    check(
        "DAQ-V1 prose title is not FORMULA",
        title_profile.knowledge_type
        != quiz_domain.FORMULA,
    )

    math_profile = (
        quiz_domain.infer_knowledge_profile(
            answer_text="x-y",
            evidence_text="Cho biểu thức x-y.",
            source_text="Đại số toán học.",
        )
    )

    check(
        "Compact symbolic subtraction remains FORMULA",
        math_profile.knowledge_type
        == quiz_domain.FORMULA,
    )

    equation_profile = (
        quiz_domain.infer_knowledge_profile(
            answer_text="f'(x) = 2x",
            evidence_text="Nếu f=x² thì f'(x)=2x.",
            source_text="Đạo hàm toán học.",
        )
    )

    check(
        "Explicit equation remains MATHEMATICS/FORMULA",
        equation_profile.domain
        == quiz_domain.MATHEMATICS
        and equation_profile.knowledge_type
        == quiz_domain.FORMULA,
    )

    shared_chunk = SimpleNamespace(
        id=492
    )

    slot_specs = [
        {
            "id": "0",
            "source_chunk": shared_chunk,
            "source_text": (
                "Chiến dịch Hồ Chí Minh kết thúc thắng lợi năm 1975. "
                "Công cuộc Đổi mới bắt đầu năm 1986. "
                "Chiến thắng Điện Biên Phủ diễn ra năm 1954."
            ),
        },
        {
            "id": "1",
            "source_chunk": shared_chunk,
            "source_text": (
                "Cách mạng tháng Tám thành công năm 1945. "
                "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
                "ngày 2/9/1945. "
                "Chiến thắng Điện Biên Phủ diễn ra năm 1954."
            ),
        },
        {
            "id": "2",
            "source_chunk": shared_chunk,
            "source_text": (
                "Công cuộc Đổi mới bắt đầu năm 1986. "
                "Chiến dịch Hồ Chí Minh kết thúc năm 1975. "
                "Chiến thắng Điện Biên Phủ diễn ra năm 1954."
            ),
        },
        {
            "id": "3",
            "source_chunk": shared_chunk,
            "source_text": (
                "LỊCH SỬ VIỆT NAM – DỮ LIỆU KIỂM THỬ DAQ-V1. "
                "Cách mạng tháng Tám thành công năm 1945. "
                "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
                "ngày 2/9/1945."
            ),
        },
        {
            "id": "4",
            "source_chunk": shared_chunk,
            "source_text": (
                "Chiến thắng Điện Biên Phủ diễn ra năm 1954. "
                "Hiệp định Giơ-ne-vơ được ký năm 1954. "
                "Chiến dịch Hồ Chí Minh kết thúc năm 1975."
            ),
        },
    ]

    evidence_by_slot = {
        "0": {
            "E0": "Chiến dịch Hồ Chí Minh kết thúc thắng lợi năm 1975.",
            "E1": "Công cuộc Đổi mới ở Việt Nam bắt đầu từ năm 1986.",
            "E2": "Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
        },
        "1": {
            "E0": "Cách mạng tháng Tám thành công năm 1945.",
            "E1": (
                "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
                "ngày 2/9/1945."
            ),
            "E2": "Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
        },
        "2": {
            "E0": "Công cuộc Đổi mới ở Việt Nam bắt đầu từ năm 1986.",
            "E1": "Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
            "E2": "Chiến dịch Hồ Chí Minh kết thúc năm 1975.",
        },
        "3": {
            "E0": "LỊCH SỬ VIỆT NAM – DỮ LIỆU KIỂM THỬ DAQ-V1",
            "E1": "Cách mạng tháng Tám thành công năm 1945.",
            "E2": (
                "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập "
                "ngày 2/9/1945."
            ),
        },
        "4": {
            "E0": "Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
            "E1": "Hiệp định Giơ-ne-vơ được ký năm 1954.",
            "E2": "Chiến dịch Hồ Chí Minh kết thúc năm 1975.",
        },
    }

    answer_by_slot = {
        "0": {
            "A0": {"text": "Chiến dịch Hồ Chí Minh", "evidence_id": "E0"},
            "A1": {"text": "Công cuộc Đổi mới", "evidence_id": "E1"},
        },
        "1": {
            "A0": {"text": "Cách mạng tháng Tám năm 1945", "evidence_id": "E0"},
            "A1": {"text": "Chủ tịch Hồ Chí Minh", "evidence_id": "E1"},
            "A2": {"text": "Chiến thắng Điện Biên Phủ", "evidence_id": "E2"},
        },
        "2": {
            "A0": {"text": "Công cuộc Đổi mới", "evidence_id": "E0"},
            "A1": {
                "text": "1975 – Kết thúc Chiến dịch Hồ Chí Minh",
                "evidence_id": "E2",
            },
        },
        "3": {
            "A0": {
                "text": "LỊCH SỬ VIỆT NAM – DỮ LIỆU KIỂM THỬ DAQ-V1",
                "evidence_id": "E0",
            },
            "A1": {"text": "Cách mạng tháng Tám năm 1945", "evidence_id": "E1"},
            "A2": {"text": "Chủ tịch Hồ Chí Minh", "evidence_id": "E2"},
        },
        "4": {
            "A0": {"text": "Chiến thắng Điện Biên Phủ", "evidence_id": "E0"},
            "A1": {"text": "Hiệp định Giơ-ne-vơ", "evidence_id": "E1"},
            "A2": {"text": "Chiến dịch Hồ Chí Minh", "evidence_id": "E2"},
        },
    }

    original_local_ids = {
        slot_id: set(bucket.keys())
        for slot_id, bucket in answer_by_slot.items()
    }

    quiz_service._daq_enrich_atomic_date_answers(
        slot_specs=slot_specs,
        evidence_by_slot=evidence_by_slot,
        answer_by_slot=answer_by_slot,
    )

    slot3_texts = {
        spec["text"]
        for spec in answer_by_slot["3"].values()
    }

    print(
        f"[INFO] slot3_enriched={sorted(slot3_texts)!r}"
    )

    check(
        "Slot 3 gains bare year 1945",
        "1945" in slot3_texts,
    )

    check(
        "Slot 3 gains full date 2/9/1945",
        "2/9/1945" in slot3_texts,
    )

    check(
        "Derived DATE answers preserve local evidence ownership",
        any(
            spec.get("text") == "1945"
            and spec.get("evidence_id") == "E1"
            for spec in answer_by_slot["3"].values()
        )
        and any(
            spec.get("text") == "2/9/1945"
            and spec.get("evidence_id") == "E2"
            for spec in answer_by_slot["3"].values()
        ),
    )

    check(
        "Original answer IDs remain untouched",
        all(
            original_local_ids[slot_id].issubset(
                set(answer_by_slot[slot_id].keys())
            )
            for slot_id in original_local_ids
        ),
    )

    # Existing V1.8 sibling sharing should now also see the
    # new atomic dates as distractor candidates.
    distractor_candidates_by_slot = {
        str(i): []
        for i in range(5)
    }

    quiz_service._daq_share_sibling_microcontext_distractors(
        slot_specs=slot_specs,
        answer_by_slot=answer_by_slot,
        distractor_candidates_by_slot=distractor_candidates_by_slot,
    )

    check(
        "Sibling pool receives grounded atomic years",
        any(
            value in distractor_candidates_by_slot["3"]
            for value in (
                "1954",
                "1975",
                "1986",
            )
        ),
    )

    generate_source = inspect.getsource(
        quiz_service._generate_compact_slot_questions
    )

    enrich_pos = generate_source.find(
        "_daq_enrich_atomic_date_answers("
    )

    diagnostic_pos = generate_source.find(
        "_daq_log_catalog_diagnostics("
    )

    sibling_pos = generate_source.find(
        "_daq_share_sibling_microcontext_distractors("
    )

    check(
        "Atomic enrichment runs before diagnostics and sibling sharing",
        enrich_pos >= 0
        and diagnostic_pos >= 0
        and sibling_pos >= 0
        and enrich_pos < diagnostic_pos < sibling_pos,
    )

    print("-" * 112)
    print(
        "RESULT: PASS — DAQ-V1.10 derives only evidence-grounded atomic "
        "history dates, preserves local evidence ownership, and blocks "
        "prose hyphens from becoming false math formulas"
    )
    print("=" * 112)


if __name__ == "__main__":
    main()
