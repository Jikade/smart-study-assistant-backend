from __future__ import annotations

from pathlib import Path

from app.services.structural_chunker import (
    SSA_SBC_VERSION,
    split_structural_blocks,
)

ROOT = Path(__file__).resolve().parents[1]


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def headings(text: str) -> list[str]:
    return [
        str(block.heading)
        for block in split_structural_blocks(text)
        if block.heading is not None
    ]


def main() -> None:
    print()
    print("=" * 92)
    print("SSA-SBC-V1.3 HEADING TOKEN-BOUNDARY REGRESSION")
    print("=" * 92)

    must(
        "Version bumped to ssa-sbc-v1.3",
        SSA_SBC_VERSION == "ssa-sbc-v1.3",
    )

    numeric = headings(
        "PHẦN 5: KINH TẾ HIỆN ĐẠI\n"
        "Nội dung học tập."
    )
    must(
        "Numeric PHẦN heading remains recognized",
        numeric == ["PHẦN 5: KINH TẾ HIỆN ĐẠI"],
    )

    roman = headings(
        "PHẦN V: KINH TẾ HIỆN ĐẠI\n"
        "Nội dung học tập."
    )
    must(
        "Roman PHẦN heading remains recognized",
        roman == ["PHẦN V: KINH TẾ HIỆN ĐẠI"],
    )

    chapter_roman = headings(
        "CHƯƠNG IV: THỜI KỲ MỚI\n"
        "Nội dung học tập."
    )
    must(
        "Roman CHƯƠNG heading remains recognized",
        chapter_roman == ["CHƯƠNG IV: THỜI KỲ MỚI"],
    )

    false_heading_text = (
        "CHƯƠNG 6: ĐỔI MỚI, VƯƠN MÌNH & HIỆN ĐẠI\n"
        "Nền kinh tế chuyển đổi từng bước.\n"
        "phần vận hành theo cơ chế thị trường, và mở cửa hội nhập quốc tế."
    )
    false_headings = headings(false_heading_text)

    must(
        "Natural sentence beginning 'phần vận hành' is NOT a heading",
        "phần vận hành theo cơ chế thị trường, và mở cửa hội nhập quốc tế."
        not in false_headings,
    )

    must(
        "Real CHƯƠNG 6 heading still preserved",
        false_headings
        == ["CHƯƠNG 6: ĐỔI MỚI, VƯƠN MÌNH & HIỆN ĐẠI"],
    )

    doc_service = (
        ROOT / "app" / "services" / "document_service.py"
    ).read_text(encoding="utf-8")

    must(
        "document_service validation regex has Roman token boundary",
        'r"\\s+(?:\\d+|[IVXLCDM]+)\\b"' in doc_service,
    )

    print()
    print("False-heading regression:", false_headings)
    print("-" * 92)
    print("RESULT: PASS")
    print("=" * 92)


if __name__ == "__main__":
    main()
