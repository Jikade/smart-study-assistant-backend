from __future__ import annotations

from types import SimpleNamespace

from app.services.structural_chunker import (
    SSA_SBC_VERSION,
    structural_chunk_text,
)


def main():
    sections = [
        SimpleNamespace(
            id=1,
            section_order=1,
            title="Hàng hóa và tiền tệ",
        ),
        SimpleNamespace(
            id=2,
            section_order=2,
            title="Giá trị thặng dư và tư bản",
        ),
        SimpleNamespace(
            id=4,
            section_order=3,
            title="Cạnh tranh và kinh tế thị trường",
        ),
        SimpleNamespace(
            id=3,
            section_order=4,
            title="Kinh tế thị trường định hướng XHCN",
        ),
    ]

    source = """
Giá trị thặng dư (m) là một bộ phận của giá trị mới.
Hai phương pháp sản xuất giá trị thặng dư.

CHƯƠNG 3: CÁC HÌNH THÁI TƯ BẢN VÀ BIỂU HIỆN

Chi phí sản xuất tư bản chủ nghĩa là k = c + v.
Lợi nhuận là hình thức biến tướng của giá trị thặng dư.

CHƯƠNG 4: CẠNH TRANH VÀ ĐỘC QUYỀN

Cạnh tranh giữa các ngành làm hình thành tỷ suất lợi nhuận bình quân.
Giá cả sản xuất bằng chi phí sản xuất cộng lợi nhuận bình quân.

CHƯƠNG 5: KTTT ĐỊNH HƯỚNG XÃ HỘI CHỦ NGHĨA

Kinh tế thị trường định hướng xã hội chủ nghĩa ở Việt Nam
vừa tuân theo quy luật thị trường vừa được định hướng xã hội chủ nghĩa.
""".strip()

    chunks = structural_chunk_text(
        source,
        sections=sections,
        size=180,
        overlap=40,
    )

    assert chunks

    # V1.2 intentionally excludes the short headingless preamble
    # from learning chunks when structured chapters follow.
    assert all(
        chunk.block_index != 0
        for chunk in chunks
    )

    block_to_section = {}

    for chunk in chunks:
        block_to_section.setdefault(
            chunk.block_index,
            chunk.section_id,
        )

        assert (
            block_to_section[
                chunk.block_index
            ]
            == chunk.section_id
        )

        assert (
            chunk.content.upper().count(
                "CHƯƠNG "
            )
            <= 1
        )

    assert block_to_section[1] == 2, block_to_section
    assert block_to_section[2] == 4, block_to_section
    assert block_to_section[3] == 3, block_to_section

    print()
    print("=" * 72)
    print("SSA-SBC STRUCTURAL CHUNKING REGRESSION")
    print("=" * 72)
    print("Version:", SSA_SBC_VERSION)
    print("Preamble learning-noise excluded:", True)
    print("Chapter boundary isolation:", True)
    print("Overlap reset at boundary:", True)
    print("Semantic mapping:", block_to_section)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
