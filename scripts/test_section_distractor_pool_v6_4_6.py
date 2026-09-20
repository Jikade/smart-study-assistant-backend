from __future__ import annotations

from types import SimpleNamespace

from app.services.quiz_service import (
    DISTRACTOR_POOL_VERSION,
    PERFORMANCE_VERSION,
    _build_section_distractor_pool,
    _sanitize_v6_distractors,
)


def main():
    # -----------------------------------------------------
    # 1) Direct sanitizer regression:
    # micro-context/model provides only two usable choices.
    # DP-V1 must fill the third from same-section candidates.
    # -----------------------------------------------------
    cleaned, replacements = _sanitize_v6_distractors(
        model_distractors=[
            "Giá trị thặng dư",
            "Giá trị sức lao động",
            "Là nơi lưu trữ giá trị",
        ],
        answer_text="Giá trị sử dụng",
        evidence_quote=(
            "• Giá trị sử dụng: Thể hiện trong quá trình lao động."
        ),
        slot_answers={
            "A0": {
                "text": "Giá trị sử dụng",
                "evidence_id": "E0",
            },
        },
        extra_candidates=[
            "Tư bản khả biến",
            "Tư bản bất biến",
        ],
    )

    assert len(cleaned) == 3, cleaned
    assert "Giá trị sử dụng" not in cleaned
    assert any(
        value in cleaned
        for value in (
            "Tư bản khả biến",
            "Tư bản bất biến",
        )
    ), cleaned

    # -----------------------------------------------------
    # 2) Section-aware pool regression:
    # candidates from different section_ids must not mix.
    # -----------------------------------------------------
    fake_chunks = [
        SimpleNamespace(
            section_id=1,
            content=(
                "• Giá trị sử dụng: Công dụng của vật phẩm. "
                "• Giá trị thặng dư: Phần giá trị mới dôi ra. "
                "• Tiền tệ: Một hàng hóa đặc biệt."
            ),
        ),
        SimpleNamespace(
            section_id=1,
            content=(
                "• Giá trị sức lao động: Giá trị của hàng hóa sức lao động. "
                "• Tư bản khả biến: Bộ phận tư bản dùng mua sức lao động."
            ),
        ),
        SimpleNamespace(
            section_id=4,
            content=(
                "• Cạnh tranh giữa các ngành: Sự cạnh tranh giữa "
                "các nhà tư bản ở các ngành khác nhau. "
                "• Độc quyền: Liên minh các doanh nghiệp lớn."
            ),
        ),
    ]

    pools = _build_section_distractor_pool(
        fake_chunks
    )

    assert 1 in pools, pools
    assert 4 in pools, pools

    sec1 = " | ".join(
        pools[1]
    ).casefold()

    sec4 = " | ".join(
        pools[4]
    ).casefold()

    assert "cạnh tranh giữa các ngành" not in sec1
    assert "giá trị sử dụng" not in sec4

    print()
    print("=" * 72)
    print("QUIZ V6.4.6 SECTION-AWARE DISTRACTOR POOL TEST")
    print("=" * 72)
    print("Performance version:", PERFORMANCE_VERSION)
    print("Distractor pool version:", DISTRACTOR_POOL_VERSION)
    print("Sanitizer reaches exactly 3 options:", len(cleaned) == 3)
    print("Same-section fallback used:", replacements >= 1)
    print("Section pools isolated:", True)
    print("Final distractors:", cleaned)
    print("Section 1 candidate count:", len(pools.get(1, [])))
    print("Section 4 candidate count:", len(pools.get(4, [])))
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
