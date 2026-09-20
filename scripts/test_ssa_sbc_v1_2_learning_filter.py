from __future__ import annotations

from types import SimpleNamespace

from app.services.structural_chunker import (
    SSA_SBC_VERSION,
    learning_block_skip_reasons,
    structural_chunk_text,
)


def long_body(topic: str) -> str:
    base = (
        f"{topic}. Nội dung chi tiết được trình bày đầy đủ để "
        "hình thành một phần học tập thực sự, không chỉ là danh "
        "sách mục lục. Các khái niệm, quy luật, mối quan hệ và "
        "ví dụ được giải thích rõ ràng cho người học. "
    )
    return base * 6


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

    source = f"""
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
{long_body("Hàng hóa, giá trị sử dụng, giá trị và tiền tệ")}

CHƯƠNG 2: SẢN XUẤT GIÁ TRỊ THẶNG DƯ TRONG CNTB
{long_body("Hàng hóa sức lao động, tư bản bất biến và tư bản khả biến")}

CHƯƠNG 3: CÁC HÌNH THÁI TƯ BẢN VÀ BIỂU HIỆN
{long_body("Chi phí sản xuất, lợi nhuận, lợi tức và địa tô")}

CHƯƠNG 4: CẠNH TRANH VÀ ĐỘC QUYỀN
{long_body("Cạnh tranh nội bộ ngành, cạnh tranh giữa các ngành và độc quyền")}

CHƯƠNG 5: KTTT ĐỊNH HƯỚNG XÃ HỘI CHỦ NGHĨA
{long_body("Kinh tế thị trường định hướng xã hội chủ nghĩa ở Việt Nam")}
""".strip()

    reasons = learning_block_skip_reasons(
        source
    )

    assert set(reasons) == {
        0, 1, 2, 3, 4, 5
    }, reasons

    chunks = structural_chunk_text(
        source,
        sections=sections,
        size=1800,
        overlap=250,
    )

    block_map = {}

    for chunk in chunks:
        block_map.setdefault(
            chunk.block_index,
            chunk.section_id,
        )

    assert set(block_map) == {
        6, 7, 8, 9, 10
    }, block_map

    assert block_map[6] == 1, block_map
    assert block_map[7] == 2, block_map
    assert block_map[8] == 2, block_map
    assert block_map[9] == 4, block_map
    assert block_map[10] == 3, block_map

    print()
    print("=" * 72)
    print("SSA-SBC-V1.2 LEARNING-CONTENT FILTER TEST")
    print("=" * 72)
    print("Version:", SSA_SBC_VERSION)
    print("Skipped blocks:", reasons)
    print("Learning blocks:", sorted(block_map))
    print("Semantic mapping:", block_map)
    print("Preamble excluded:", 0 not in block_map)
    print("Repeated TOC summaries excluded:", True)
    print("Body chapters preserved:", True)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
