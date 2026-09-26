from __future__ import annotations

from app.services.quiz_v5 import ChunkInput, extract_knowledge_objects


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    print()
    print("=" * 116)
    print("QUIZ V5 TIMELINE BOUNDARY HARDENING V0.8.1 REGRESSION")
    print("=" * 116)

    fixture = ChunkInput(
        document_id=19,
        chunk_id=492,
        section_id=None,
        chunk_index=0,
        text=(
            "Một số mốc dùng để phân biệt:\n"
            "1945 – Cách mạng tháng Tám và Tuyên ngôn Độc lập.\n"
            "1954 – Chiến thắng Điện Biên Phủ và Hiệp định Giơ-ne-vơ.\n"
            "1975 – Kết thúc Chiến dịch Hồ Chí Minh.\n"
            "1986 – Bắt đầu công cuộc Đổi mới."
        ),
    )

    facts = extract_knowledge_objects(
        [fixture],
        subject_family="history",
    )

    answers = {
        item.object
        for item in facts
        if item.kind.value == "DATE"
    }

    must("Timeline row 1945 starts a new logical unit", "1945" in answers)
    must(
        "All bare-year timeline rows remain extractable",
        {"1945", "1954", "1975", "1986"} <= answers,
    )

    wrapped = ChunkInput(
        document_id=20,
        chunk_id=521,
        section_id=None,
        chunk_index=10,
        text=(
            "Năm 1771, ba anh em\n"
            "Nguyễn Nhạc, Nguyễn Huệ, Nguyễn Lữ phất cờ khởi nghĩa."
        ),
    )

    wrapped_facts = extract_knowledge_objects(
        [wrapped],
        subject_family="history",
    )

    event_1771 = [
        item
        for item in wrapped_facts
        if item.kind.value == "DATE" and item.object == "1771"
    ]

    must("'Năm 1771,' remains soft for wrapped prose", len(event_1771) == 1)
    must(
        "Wrapped 1771 subject still contains Nguyễn Nhạc",
        "Nguyễn Nhạc" in event_1771[0].subject,
    )

    print()
    print(f"Timeline answers : {sorted(answers)}")
    print(f"1771 subject     : {event_1771[0].subject}")
    print("-" * 116)
    print("RESULT: PASS")
    print("=" * 116)


if __name__ == "__main__":
    main()
