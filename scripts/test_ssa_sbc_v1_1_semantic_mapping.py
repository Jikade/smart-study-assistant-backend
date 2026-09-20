from __future__ import annotations

from types import SimpleNamespace

from app.services.structural_chunker import (
    SSA_SBC_VERSION,
    extract_chapter_number,
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
TÀI LIỆU TỔNG HỢP LÝ LUẬN
SỔ TAY KIẾN THỨC
KINH TẾ CHÍNH TRỊ MÁC - LÊNIN

CHƯƠNG 1: HÀNG HÓA, THỊ TRƯỜNG VÀ VAI TRÒ CỦA CÁC CHỦ THỂ
1. Sản xuất hàng hóa
2. Tiền tệ

CHƯƠNG 2: SẢN XUẤT GIÁ TRỊ THẶNG DƯ
1. Hàng hóa sức lao động

CHƯƠNG 3: CÁC HÌNH THÁI TƯ BẢN VÀ BIỂU HIỆN
1. Lợi nhuận và giá trị thặng dư

CHƯƠNG 4: CẠNH TRANH VÀ ĐỘC QUYỀN
1. Cạnh tranh giữa các ngành

CHƯƠNG 5: KTTT ĐỊNH HƯỚNG XÃ HỘI CHỦ NGHĨA
1. Đặc trưng của KTTT định hướng XHCN

CHƯƠNG 1: HÀNG HÓA VÀ THỊ TRƯỜNG
Kinh tế thị trường có nhiều chủ thể. Hàng hóa có giá trị sử dụng
và giá trị. Tiền tệ có nhiều chức năng.

CHƯƠNG 2: SẢN XUẤT GIÁ TRỊ THẶNG DƯ TRONG CNTB
Giá trị thặng dư do lao động làm thuê tạo ra.

CHƯƠNG 3: CÁC HÌNH THÁI TƯ BẢN VÀ BIỂU HIỆN
Lợi nhuận là hình thức biểu hiện của giá trị thặng dư.

CHƯƠNG 4: CẠNH TRANH VÀ ĐỘC QUYỀN
Cạnh tranh giữa các ngành hình thành tỷ suất lợi nhuận bình quân.

CHƯƠNG 5: KTTT ĐỊNH HƯỚNG XÃ HỘI CHỦ NGHĨA
Kinh tế thị trường định hướng xã hội chủ nghĩa ở Việt Nam.
""".strip()

    chunks = structural_chunk_text(
        source,
        sections=sections,
        size=500,
        overlap=80,
    )

    block_map = {}

    for chunk in chunks:
        block_map.setdefault(
            chunk.block_index,
            chunk.section_id,
        )

    # block 0 is preamble/title page.
    assert block_map[0] is None, block_map

    # First chapter occurrences.
    assert block_map[1] == 1, block_map
    assert block_map[2] == 2, block_map
    assert block_map[3] == 2, block_map
    assert block_map[4] == 4, block_map
    assert block_map[5] == 3, block_map

    # Repeated body chapter occurrences must reuse the
    # chapter mapping rather than drift semantically.
    assert block_map[6] == 1, block_map
    assert block_map[7] == 2, block_map
    assert block_map[8] == 2, block_map
    assert block_map[9] == 4, block_map
    assert block_map[10] == 3, block_map

    assert extract_chapter_number(
        "CHƯƠNG 4: CẠNH TRANH VÀ ĐỘC QUYỀN"
    ) == 4

    print()
    print("=" * 72)
    print("SSA-SBC-V1.1 SEMANTIC MAPPING TEST")
    print("=" * 72)
    print("Version:", SSA_SBC_VERSION)
    print("Preamble unassigned:", block_map[0] is None)
    print(
        "TOC mapping:",
        {
            key: block_map[key]
            for key in range(1, 6)
        },
    )
    print(
        "Repeated body mapping:",
        {
            key: block_map[key]
            for key in range(6, 11)
        },
    )
    print("Chapter identity reuse:", True)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
