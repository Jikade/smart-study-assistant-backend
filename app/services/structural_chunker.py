from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable

SSA_SBC_VERSION = "ssa-sbc-v1.2"


@dataclass(frozen=True)
class StructuralBlock:
    block_index: int
    content: str
    heading: str | None
    char_start: int
    char_end: int


@dataclass(frozen=True)
class StructuralChunk:
    content: str
    block_index: int
    structural_heading: str | None
    block_char_start: int
    block_char_end: int
    section_id: int | None = None


_HARD_HEADING_RE = re.compile(
    r"(?im)^\s*(?:CHƯƠNG|CHUONG|CHAPTER|PHẦN|PHAN|PART)\s+"
    r"(?:\d+|[IVXLCDM]+)\s*[:.\-–—]?[^\n]*$"
)


def _normalize_search_text(value: str) -> str:
    value = str(value or "").replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFD", value)
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    ).casefold()
    normalized = re.sub(r"\bkttt\b", "kinh te thi truong", normalized)
    normalized = re.sub(r"\bxhcn\b", "xa hoi chu nghia", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def split_structural_blocks(value: str) -> list[StructuralBlock]:
    """Split BEFORE chunk sizing. Hard headings always start a new block."""
    text = str(value or "").strip()
    if not text:
        return []

    matches = list(_HARD_HEADING_RE.finditer(text))
    if not matches:
        return [StructuralBlock(0, text, None, 0, len(text))]

    boundaries: list[tuple[int, str | None]] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        boundaries.append((0, None))

    for match in matches:
        boundaries.append((match.start(), match.group(0).strip()))

    blocks: list[StructuralBlock] = []
    for index, (start, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        content = text[start:end].strip()
        if content:
            blocks.append(
                StructuralBlock(
                    block_index=len(blocks),
                    content=content,
                    heading=heading,
                    char_start=start,
                    char_end=end,
                )
            )
    return blocks


def _choose_natural_end(text: str, start: int, size: int) -> int:
    hard_end = min(len(text), start + size)
    if hard_end >= len(text):
        return len(text)

    min_candidate = min(hard_end, start + max(1, int(size * 0.62)))
    window = text[min_candidate:hard_end]
    best: int | None = None

    for pattern in (r"\n\s*\n", r"(?<=[.!?])\s+", r"(?<=;)\s+", r"\n"):
        for match in re.finditer(pattern, window):
            candidate = min_candidate + match.end()
            if best is None or candidate > best:
                best = candidate

    if best is not None:
        return best

    whitespace = text.rfind(" ", min_candidate, hard_end)
    return whitespace if whitespace > start else hard_end


def _align_overlap_start(
    text: str,
    proposed_start: int,
    previous_start: int,
    previous_end: int,
) -> int:
    proposed_start = max(previous_start + 1, proposed_start)
    if proposed_start >= previous_end:
        return previous_end

    while (
        proposed_start < previous_end
        and proposed_start > 0
        and not text[proposed_start - 1].isspace()
        and not text[proposed_start].isspace()
    ):
        proposed_start += 1

    while proposed_start < previous_end and text[proposed_start].isspace():
        proposed_start += 1

    return min(proposed_start, previous_end)


def chunk_one_structural_block(
    block: StructuralBlock,
    *,
    size: int,
    overlap: int,
) -> list[StructuralChunk]:
    if size <= 0:
        raise ValueError("size must be > 0")

    overlap = max(0, min(overlap, size // 2))
    text = block.content
    chunks: list[StructuralChunk] = []
    start = 0

    while start < len(text):
        end = _choose_natural_end(text, start, size)
        if end <= start:
            end = min(len(text), start + size)

        content = text[start:end].strip()
        if content:
            chunks.append(
                StructuralChunk(
                    content=content,
                    block_index=block.block_index,
                    structural_heading=block.heading,
                    block_char_start=start,
                    block_char_end=end,
                )
            )

        if end >= len(text):
            break

        next_start = _align_overlap_start(text, end - overlap, start, end)
        start = end if next_start <= start else next_start

    return chunks


_STOPWORDS = {
    "va", "cua", "la", "mot", "cac", "nhung", "ve", "trong", "o", "cho",
    "theo", "chu", "nghia",
}


def _section_value(section: Any, name: str, default: Any = None) -> Any:
    if isinstance(section, dict):
        return section.get(name, default)
    return getattr(section, name, default)



def _roman_to_int(value: str) -> int | None:
    value = str(value or "").upper().strip()

    if not value:
        return None

    roman = {
        "I": 1,
        "V": 5,
        "X": 10,
        "L": 50,
        "C": 100,
        "D": 500,
        "M": 1000,
    }

    total = 0
    previous = 0

    for char in reversed(value):
        current = roman.get(char)

        if current is None:
            return None

        if current < previous:
            total -= current
        else:
            total += current
            previous = current

    return total or None


def extract_chapter_number(
    structural_heading: str | None,
) -> int | None:
    """
    Extract a stable chapter identity from a hard structural
    heading. This identity is independent from semantic
    section_id.
    """

    heading = str(
        structural_heading
        or ""
    )

    match = re.search(
        r"(?i)\b(?:CHƯƠNG|CHUONG|CHAPTER)\s+"
        r"(\d+|[IVXLCDM]+)\b",
        heading,
    )

    if not match:
        return None

    raw = match.group(1)

    if raw.isdigit():
        return int(raw)

    return _roman_to_int(
        raw
    )


def resolve_semantic_section_id(
    *,
    block_text: str,
    structural_heading: str | None,
    sections: Iterable[Any],
) -> int | None:
    """
    Structural heading decides WHERE TO CUT.
    document_sections decides WHICH semantic topic owns the block.
    """
    normalized_block = _normalize_search_text(block_text[:5000])
    normalized_heading = _normalize_search_text(structural_heading or "")
    first_context = normalized_block[:1800]

    ranked: list[tuple[float, int, int]] = []
    for section in sections:
        section_id = int(_section_value(section, "id"))
        section_order = int(_section_value(section, "section_order", 999999) or 999999)
        title = str(_section_value(section, "title", "") or "")
        normalized_title = _normalize_search_text(title)
        tokens = [
            token for token in normalized_title.split()
            if len(token) >= 2 and token not in _STOPWORDS
        ]

        score = 0.0
        if normalized_title and normalized_title in normalized_block:
            score += 120.0

        for token in tokens:
            if normalized_heading and re.search(rf"\b{re.escape(token)}\b", normalized_heading):
                score += 22.0
            if re.search(rf"\b{re.escape(token)}\b", first_context):
                score += 4.0

        for left, right in zip(tokens, tokens[1:]):
            phrase = f"{left} {right}"
            if phrase in normalized_heading:
                score += 28.0
            elif phrase in first_context:
                score += 8.0

        ranked.append((score, -section_order, section_id))

    if not ranked:
        return None

    ranked.sort(reverse=True)
    best_score, _, best_id = ranked[0]
    return best_id if best_score > 0 else None



def _learning_block_skip_reasons(
    blocks: list[StructuralBlock],
) -> dict[int, str]:
    """
    Identify non-learning structural blocks conservatively.

    Rules:
    - short headingless preamble/title page is skipped when
      the document clearly has chapter structure;
    - an earlier short CHAPTER occurrence is treated as
      TOC/summary only when the same chapter appears later
      with substantially more content.

    We do NOT infer TOC from wording alone.
    """

    reasons: dict[int, str] = {}

    has_chapter_blocks = any(
        extract_chapter_number(
            block.heading
        )
        is not None
        for block in blocks
    )

    if has_chapter_blocks:
        for block in blocks:
            if (
                block.heading is None
                and len(block.content) <= 600
            ):
                reasons[
                    block.block_index
                ] = "short_preamble"

    chapter_occurrences: dict[
        int,
        list[StructuralBlock],
    ] = {}

    for block in blocks:
        chapter_number = extract_chapter_number(
            block.heading
        )

        if chapter_number is None:
            continue

        chapter_occurrences.setdefault(
            chapter_number,
            [],
        ).append(
            block
        )

    for _, occurrences in chapter_occurrences.items():
        if len(occurrences) < 2:
            continue

        for index, block in enumerate(
            occurrences[:-1]
        ):
            later = occurrences[
                index + 1:
            ]

            later_max = max(
                len(item.content)
                for item in later
            )

            current_len = len(
                block.content
            )

            # Conservative TOC-like signal:
            # short earlier chapter summary + a later
            # substantially richer occurrence of same chapter.
            if (
                current_len <= 700
                and later_max >= 500
                and later_max >= current_len * 2
            ):
                reasons[
                    block.block_index
                ] = "repeated_short_chapter_summary"

    return reasons


def learning_block_skip_reasons(
    value: str,
) -> dict[int, str]:
    """
    Public preview/test helper.
    """
    return _learning_block_skip_reasons(
        split_structural_blocks(
            value
        )
    )


def structural_chunk_text(
    value: str,
    *,
    sections: Iterable[Any] = (),
    size: int = 1800,
    overlap: int = 250,
) -> list[StructuralChunk]:
    """
    SSA-SBC-V1.2

    HARD STRUCTURAL BOUNDARY > CHUNK SIZE > OVERLAP.

    Pass 1:
    resolve stable semantic section mapping for chapter
    identities across the whole document.

    Pass 2:
    exclude only conservatively detected non-learning blocks
    such as a short title-page preamble or an earlier short
    repeated chapter summary (TOC-like block).

    This keeps semantic mapping information from the TOC while
    preventing TOC/title-page chunks from entering RAG/quiz.
    """

    blocks = split_structural_blocks(
        value
    )

    section_list = list(
        sections
    )

    skip_reasons = _learning_block_skip_reasons(
        blocks
    )

    chapter_section_map: dict[
        int,
        int,
    ] = {}

    block_section_map: dict[
        int,
        int | None,
    ] = {}

    # -----------------------------------------------------
    # PASS 1 — semantic mapping
    # -----------------------------------------------------
    for block in blocks:
        chapter_number = extract_chapter_number(
            block.heading
        )

        if block.heading is None:
            # SSA-LI-V1 headingless semantic ownership:
            # a document with one semantic section should not
            # produce analytics-invisible chunks.
            if len(section_list) == 1:
                section_id = int(
                    _section_value(
                        section_list[0],
                        "id",
                    )
                )
            else:
                section_id = resolve_semantic_section_id(
                    block_text=block.content,
                    structural_heading=None,
                    sections=section_list,
                )

        elif (
            chapter_number is not None
            and chapter_number
            in chapter_section_map
        ):
            section_id = chapter_section_map[
                chapter_number
            ]

        else:
            section_id = resolve_semantic_section_id(
                block_text=block.content,
                structural_heading=block.heading,
                sections=section_list,
            )

            if (
                chapter_number is not None
                and section_id is not None
            ):
                chapter_section_map[
                    chapter_number
                ] = section_id

        block_section_map[
            block.block_index
        ] = section_id

    # -----------------------------------------------------
    # PASS 2 — learning chunks only
    # -----------------------------------------------------
    output: list[StructuralChunk] = []

    for block in blocks:
        if block.block_index in skip_reasons:
            continue

        section_id = block_section_map[
            block.block_index
        ]

        local_chunks = chunk_one_structural_block(
            block,
            size=size,
            overlap=overlap,
        )

        for item in local_chunks:
            output.append(
                StructuralChunk(
                    content=item.content,
                    block_index=item.block_index,
                    structural_heading=item.structural_heading,
                    block_char_start=item.block_char_start,
                    block_char_end=item.block_char_end,
                    section_id=section_id,
                )
            )

    return output

