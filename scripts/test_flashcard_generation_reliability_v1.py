from __future__ import annotations

import json

from app.services.flashcard_service import (
    FLASHCARD_GENERATION_MAX_RETRIES,
    _flashcard_front_key,
    _parse_flashcard_batch,
)


def main() -> None:
    print()
    print("=" * 82)
    print("FLASHCARD GENERATION RELIABILITY V1 REGRESSION")
    print("=" * 82)

    two_cards = {
        "cards": [
            {
                "front_text": "Tiền tệ là gì?",
                "back_text": "Một hàng hóa đặc biệt.",
                "hint": None,
                "source_chunk_id": 101,
            },
            {
                "front_text": "Tiền tệ có mấy chức năng?",
                "back_text": "Năm.",
                "hint": None,
                "source_chunk_id": 101,
            },
        ]
    }

    parsed = _parse_flashcard_batch(
        json.dumps(
            two_cards,
            ensure_ascii=False,
        )
    )

    assert len(parsed) == 2
    print("Valid multi-card JSON parsing        : PASS")

    fenced = (
        "```json\n"
        + json.dumps(
            {"cards": [two_cards["cards"][0]]},
            ensure_ascii=False,
        )
        + "\n```"
    )

    parsed_fenced = _parse_flashcard_batch(
        fenced
    )

    assert len(parsed_fenced) == 1
    print("Markdown-fenced JSON recovery        : PASS")

    assert (
        _flashcard_front_key(
            "  Tiền   tệ là gì? "
        )
        == "tiền tệ là gì?"
    )
    print("Front-text duplicate normalization   : PASS")

    assert (
        FLASHCARD_GENERATION_MAX_RETRIES
        == 2
    )
    print("Retry budget                         : PASS")

    print()
    print("Result: PASS")
    print("=" * 82)


if __name__ == "__main__":
    main()
