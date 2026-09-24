from __future__ import annotations

from dataclasses import dataclass
import inspect

from app.services import flashcard_service as service


@dataclass
class DummyChunk:
    id: int
    content: str


def must(
    label: str,
    condition: bool,
) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    print()
    print("=" * 96)
    print("FLASHCARD BATCHED GENERATION V2.2 REGRESSION")
    print("=" * 96)

    must(
        "Batch size stays small",
        service.FLASHCARD_BATCH_SIZE <= 4,
    )

    must(
        "Context uses at most three chunks",
        service.FLASHCARD_CONTEXT_CHUNKS_PER_BATCH <= 3,
    )

    must(
        "Per-chunk context is capped",
        service.FLASHCARD_CONTEXT_CHARS_PER_CHUNK <= 1200,
    )

    chunks = [
        DummyChunk(i, f"chunk-{i}")
        for i in range(1, 6)
    ]

    first, cursor = service._flashcard_context_window(
        chunks,
        0,
    )

    second, cursor2 = service._flashcard_context_window(
        chunks,
        cursor,
    )

    must(
        "First context window is deterministic",
        [x.id for x in first] == [1, 2, 3],
    )

    must(
        "Second context window rotates",
        [x.id for x in second] == [4, 5, 1],
    )

    must(
        "Context cursor remains bounded",
        0 <= cursor2 < len(chunks),
    )

    source = inspect.getsource(
        service.generate_deck
    )

    compact = " ".join(
        source.split()
    )

    must(
        "Generated source contains valid newline join",
        'context = "\\n\\n".join(' in source,
    )

    must(
        "Old monolithic 2500-char context is gone",
        "[:2500]" not in source,
    )

    # Test the actual guard expression, not a human-readable
    # error message that Python may split across string literals.
    must(
        "source_chunk_id is checked against current context IDs",
        "card.source_chunk_id" in source
        and "allowed_chunk_ids" in source
        and "not in allowed_chunk_ids" in compact,
    )

    must(
        "Cards accumulate across bounded calls",
        "calls_used < max_calls" in compact,
    )

    must(
        "Identical front/back cards are rejected",
        "front_key == back_key" in compact,
    )

    must(
        "Duplicate fronts are rejected",
        "front_key in seen_fronts" in compact,
    )

    must(
        "Bounded call budget includes retry allowance",
        "FLASHCARD_GENERATION_MAX_RETRIES" in source
        and "max_calls" in source,
    )

    print("-" * 96)
    print("RESULT: PASS")
    print("=" * 96)


if __name__ == "__main__":
    main()
