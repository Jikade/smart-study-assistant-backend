from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import unicodedata

from app.services.quiz_v5.models import (
    EvidenceRef,
    KnowledgeKind,
    KnowledgeObject,
)


SSA_QV5_EXTRACTOR_VERSION = "SSA-QV5-KX-V0.2"
SSA_QV5_EXTRACTOR_HARDENING_VERSION = "SSA-QV5-KX-V0.5"
SSA_QV5_EXTRACTOR_BOUNDARY_VERSION = "SSA-QV5-KX-V0.6"
SSA_QV5_EXTRACTOR_INTEGRITY_VERSION = "SSA-QV5-KX-V0.7"
SSA_QV5_EXTRACTOR_LOGICAL_SENTENCE_VERSION = "SSA-QV5-KX-V0.8"
SSA_QV5_EXTRACTOR_TIMELINE_VERSION = "SSA-QV5-KX-V0.8.1"


@dataclass(frozen=True)
class ChunkInput:
    document_id: int
    chunk_id: int
    section_id: int | None
    text: str
    chunk_index: int | None = None


_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"CHƯƠNG|CHUONG|CHAPTER|PHẦN|PHAN|PART|"
    r"MỤC|MUC|SECTION"
    r")\b",
    flags=re.I,
)

_BULLET_RE = re.compile(
    r"^\s*(?:[•●▪◦‣⁃*-]|\d+[.)])\s*"
)

_YEAR_LEADING_VI = re.compile(
    r"^(?:Vào\s+)?Năm\s+(?P<object>\d{3,4})"
    r"\s*[,;:–—-]\s*(?P<subject>.{4,220})$",
    flags=re.I,
)

_YEAR_LABEL_VI = re.compile(
    r"^(?P<object>\d{3,4})"
    r"\s*[-–—:]\s*(?P<subject>.{4,220})$",
    flags=re.I,
)

_GENERIC_SUBJECTS = {
    "đây", "đó", "này", "điều này", "việc này",
    "điều đó", "việc đó", "gọi", "đô",
    "nó", "họ", "chúng", "đầu tiên", "đỉnh cao",
    "here", "this", "that", "it", "they",
}

_SUBJECT_CLAUSE_CUES = (
    "xuyên suốt ", "về ngoại giao", "về kinh tế",
    "về chính trị", "với phương châm", "được nhân dân",
    "đã ", "đang ", "sẽ ", "khi ", "trong khi ",
)

_TRUNCATED_END_WORDS = {
    "và", "hoặc", "của", "với", "trong", "ở", "tại",
    "để", "nhằm", "theo", "do", "bởi",
    "cho", "vận", "gọi", "thành", "ra",
    "and", "or", "of", "with", "in", "at", "to", "for", "by",
}

_EVENT_INCOMPLETE_TAILS = (
    "đổi thành",
    "được đổi thành",
    "lập ra",
    "thành lập",
    "được gọi là",
    "gọi là",
    "mang tên",
    "trở thành",
    "xưng đế và lập ra",
)

_DATE_TOKEN = (
    r"(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}|"
    r"\d{4}"
    r")"
)

_EVENT_DATE_VI = re.compile(
    rf"^(?P<subject>.{{2,180}}?)\s+"
    rf"(?:diễn ra|xảy ra|bắt đầu|kết thúc)\s+"
    rf"(?:vào\s+)?(?:năm\s+)?(?P<object>{_DATE_TOKEN})\b",
    flags=re.I,
)

_EVENT_DATE_EN = re.compile(
    r"^(?P<subject>.{2,180}?)\s+"
    r"(?:occurred|took place|began|ended)\s+"
    r"(?:in|on)\s+"
    r"(?P<object>(?:\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|"
    r"[A-Za-z]+\s+\d{1,2},?\s+\d{4}))\b",
    flags=re.I,
)

_FUNCTION_PATTERNS = [
    re.compile(
        r"^(?P<subject>.{2,150}?)\s+"
        r"(?:có chức năng|có vai trò|dùng để|được dùng để)\s+"
        r"(?P<object>.{3,260})$",
        flags=re.I,
    ),
    re.compile(
        r"^chức năng của\s+(?P<subject>.{2,150}?)\s+là\s+"
        r"(?P<object>.{3,260})$",
        flags=re.I,
    ),
    re.compile(
        r"^(?P<subject>.{2,150}?)\s+"
        r"(?:is used to|is used for|serves to|functions to)\s+"
        r"(?P<object>.{3,260})$",
        flags=re.I,
    ),
    re.compile(
        r"^the function of\s+(?P<subject>.{2,150}?)\s+is\s+"
        r"(?P<object>.{3,260})$",
        flags=re.I,
    ),
]

_DEFINITION_PATTERNS = [
    re.compile(
        r"^(?P<subject>.{2,150}?)\s+"
        r"(?:là|được gọi là|được hiểu là)\s+"
        r"(?P<object>.{5,320})$",
        flags=re.I,
    ),
    re.compile(
        r"^(?P<subject>.{2,150}?)\s+"
        r"(?:is defined as|are defined as|is called|are called)\s+"
        r"(?P<object>.{5,320})$",
        flags=re.I,
    ),
]

_CAUSE_PATTERNS = [
    re.compile(
        r"^(?P<subject>.{3,180}?)\s+"
        r"(?:dẫn đến|gây ra|làm cho)\s+"
        r"(?P<object>.{3,280})$",
        flags=re.I,
    ),
    re.compile(
        r"^(?P<subject>.{3,180}?)\s+"
        r"(?:leads to|causes|results in)\s+"
        r"(?P<object>.{3,280})$",
        flags=re.I,
    ),
]

_NUMERIC_PROPERTY_VI = re.compile(
    r"^(?P<subject>.{2,160}?)\s+có\s+"
    r"(?P<relation>"
    r"diện tích|dân số|độ cao|chiều dài|khối lượng|"
    r"nhiệt độ|vận tốc|tốc độ|thể tích|bán kính"
    r")\s+"
    r"(?:là|khoảng|xấp xỉ)?\s*"
    r"(?P<object>"
    r"[+-]?\d[\d\s.,]*\s*"
    r"(?:km²|km2|km|m²|m2|m|cm|mm|kg|g|°c|c|"
    r"m/s|km/h|triệu|tỷ|nghìn)?"
    r")$",
    flags=re.I,
)

_NUMERIC_PROPERTY_EN = re.compile(
    r"^(?P<subject>.{2,160}?)\s+has\s+(?:an?\s+)?"
    r"(?P<relation>"
    r"area|population|height|length|mass|temperature|"
    r"speed|volume|radius"
    r")\s+(?:of\s+)?"
    r"(?P<object>[+-]?\d[\d\s.,]*\s*[A-Za-z°²/0-9]*)$",
    flags=re.I,
)

_FORMULA_IDENTIFIER = (
    r"(?:"
    r"[A-Za-zΑ-Ωα-ωπΠ]"
    r"|[A-ZΑ-Ω]{2,8}"
    r")"
)

_FORMULA_START_RE = re.compile(
    r"(?<![<>=A-Za-zÀ-ỹΑ-Ωα-ω0-9_])"
    rf"(?P<lhs>{_FORMULA_IDENTIFIER})"
    r"\s*=\s*"
)

_FORMULA_TOKEN_RE = re.compile(
    rf"\s*(?:"
    rf"(?P<var>{_FORMULA_IDENTIFIER}\d*)"
    r"(?![A-Za-zÀ-ỹΑ-Ωα-ω])"
    r"|(?P<num>\d+(?:[.,]\d+)?)"
    r"|(?P<op>[-+*/^()√×÷])"
    r")"
)


def _norm(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )
    value = _BULLET_RE.sub(
        "",
        value,
    )
    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()
    return value.strip(
        " \t\r\n.;,:"
    )


def _key(value: str) -> str:
    return _norm(value).casefold()


def _words(value: str) -> list[str]:
    return re.findall(
        r"[A-Za-zÀ-ỹ0-9]+",
        str(value or ""),
        flags=re.UNICODE,
    )


def _looks_truncated(value: str) -> bool:
    clean = _norm(value)
    words = _words(clean)

    if not words:
        return True

    if words[-1].casefold() in _TRUNCATED_END_WORDS:
        return True

    for left, right in (("(", ")"), ("[", "]"), ("“", "”")):
        if clean.count(left) != clean.count(right):
            return True

    if clean.count('"') % 2:
        return True

    return False


def _concept_subject_issue(value: str) -> str | None:
    clean = _norm(value)
    folded = clean.casefold()

    if not clean:
        return "empty"

    if folded in _GENERIC_SUBJECTS:
        return "generic_subject"

    if re.match(r"^(?:năm|vào năm)\s+\d{3,4}\b", folded):
        return "temporal_clause"

    if any(folded.startswith(cue) for cue in _SUBJECT_CLAUSE_CUES):
        return "clause_subject"

    if any(char in clean for char in (",", ";", ":", '"', "“", "”")):
        return "punctuated_clause"

    if len(_words(clean)) > 12:
        return "subject_too_long"

    return None


def _first_alpha_is_lower(value: str) -> bool:
    for char in str(value or ""):
        if char.isalpha():
            return char.islower()
    return False


def _event_subject_issue(value: str) -> str | None:
    clean = _norm(value)
    folded = clean.casefold()

    if len(_words(clean)) < 2:
        return "event_subject_too_short"

    if re.match(r"^\d{3,4}\b", clean):
        return "range_tail_in_subject"

    if any(
        folded.endswith(tail)
        for tail in _EVENT_INCOMPLETE_TAILS
    ):
        return "incomplete_event_predicate"

    if re.search(r"\b(?:lập ra triều|phế|đại phá)\s*\d*$", folded):
        return "incomplete_event_predicate"

    if re.search(r"\b\d{1,3}$", clean):
        return "bare_numeric_event_tail"

    if _looks_truncated(clean):
        return "truncated_event_subject"

    return None


def _boundary_start_fragment(
    chunk: ChunkInput,
    *,
    unit_index: int,
    unit: str,
) -> bool:
    if unit_index != 0:
        return False

    if chunk.chunk_index in (None, 0):
        return False

    return _first_alpha_is_lower(unit)


def _definition_subject_issue(value: str) -> str | None:
    """
    Precision-first definition label gate.

    Generic X-is-Y extraction is accepted only when X looks like a
    sentence-initial concept label. Lowercase-starting X is treated as a
    source/extraction fragment, not repaired or guessed.
    """
    base = _concept_subject_issue(value)

    if base is not None:
        return base

    clean = _norm(value)
    words = _words(clean)

    if _first_alpha_is_lower(clean):
        return "lowercase_definition_subject"

    if len(words) > 8:
        return "definition_subject_too_long"

    return None


def _chunk_has_open_tail(
    chunk: ChunkInput,
    *,
    has_following_chunk: bool,
) -> bool:
    """
    Non-final chunk + no terminal sentence punctuation => unresolved tail.
    """
    if not has_following_chunk:
        return False

    text = str(chunk.text or "").rstrip()

    if not text:
        return False

    return text[-1] not in ".!?…"


def _object_issue(value: str) -> str | None:
    clean = _norm(value)

    if len(clean) < 3:
        return "object_too_short"

    if _looks_truncated(clean):
        return "truncated_object"

    return None


def _is_bad_piece(
    value: str,
    *,
    allow_single_symbol: bool = False,
) -> bool:
    value = _norm(value)

    if not value:
        return True

    if len(value) < 2:
        if (
            allow_single_symbol
            and re.fullmatch(
                r"[A-Za-zΑ-Ωα-ω]",
                value,
            )
        ):
            return False
        return True

    if _HEADING_RE.match(value):
        return True

    if value in {"-", "–", "—"}:
        return True

    return False


def _stable_id(
    chunk_id: int,
    kind: KnowledgeKind,
    subject: str,
    relation: str,
    object_value: str,
) -> str:
    payload = "|".join(
        [
            str(chunk_id),
            kind.value,
            _key(subject),
            relation,
            _key(object_value),
        ]
    )
    digest = hashlib.sha1(
        payload.encode("utf-8")
    ).hexdigest()[:16]
    return f"kx-{digest}"


def _line_text_preserve_punctuation(
    value: str,
) -> str:
    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )

    text = _BULLET_RE.sub(
        "",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _line_is_hard_boundary(
    raw_line: str,
    clean_line: str,
) -> bool:
    """
    Distinguish semantic/list boundaries from PDF visual wrapping.

    PDF extractors frequently insert newline characters inside a sentence.
    Those newlines are soft unless the next line is clearly a heading/list
    item or the previous logical line already ended a sentence.
    """
    raw = str(raw_line or "").strip()
    clean = str(clean_line or "").strip()

    if not clean:
        return True

    if _HEADING_RE.match(clean):
        return True

    if _BULLET_RE.match(raw):
        return True

    # Bare-year timeline/list rows are structural boundaries.
    # "Năm 1771, ..." intentionally remains soft so wrapped prose can join.
    if re.match(
        r"^\d{3,4}\s*[-–—]\s+",
        clean,
    ):
        return True

    words = _words(clean)

    if (
        1 <= len(words) <= 16
        and clean.isupper()
        and not re.search(r"[.!?…]$", clean)
    ):
        return True

    return False


def _logical_text_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return

        joined = _line_text_preserve_punctuation(
            " ".join(buffer)
        )

        if joined:
            blocks.append(joined)

        buffer.clear()

    for raw_line in str(text or "").splitlines():
        raw = str(raw_line or "")
        clean = _line_text_preserve_punctuation(
            raw
        )

        if not clean:
            flush()
            continue

        hard_boundary = _line_is_hard_boundary(
            raw,
            clean,
        )

        if hard_boundary:
            flush()
            blocks.append(clean)
            continue

        if buffer:
            previous = _line_text_preserve_punctuation(
                " ".join(buffer)
            )

            if re.search(
                r"[.!?…][”\"')\]]?$",
                previous,
            ):
                flush()

        buffer.append(clean)

    flush()

    return blocks


def _sentence_units(text: str) -> list[str]:
    """
    SSA-QV5-KX-V0.8 logical sentence reconstruction.

    Newlines from PDF visual wrapping are joined first. Sentence splitting
    happens only after logical blocks have been reconstructed.
    """
    output: list[str] = []

    for block in _logical_text_blocks(
        text
    ):
        for part in re.split(
            r"(?<=[.!?…])\s+",
            block,
        ):
            value = _norm(part)

            if value:
                output.append(value)

    return output


def _knowledge(
    *,
    chunk: ChunkInput,
    subject_family: str,
    kind: KnowledgeKind,
    subject: str,
    relation: str,
    object_value: str,
    confidence: float,
    evidence_text: str,
    tags: tuple[str, ...],
    allow_single_symbol_subject: bool = False,
    concept_subject: bool = False,
) -> KnowledgeObject | None:
    subject = _norm(subject)
    object_value = _norm(object_value)

    if (
        _is_bad_piece(
            subject,
            allow_single_symbol=allow_single_symbol_subject,
        )
        or _is_bad_piece(object_value)
        or _key(subject) == _key(object_value)
    ):
        return None

    if concept_subject and _concept_subject_issue(subject):
        return None

    if _object_issue(object_value):
        return None

    return KnowledgeObject(
        id=_stable_id(
            chunk.chunk_id,
            kind,
            subject,
            relation,
            object_value,
        ),
        subject_family=subject_family,
        kind=kind,
        subject=subject,
        relation=relation,
        object=object_value,
        evidence=EvidenceRef(
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            section_id=chunk.section_id,
            text=evidence_text,
        ),
        confidence=confidence,
        tags=tags,
    )


def _scan_formula_rhs(
    text: str,
    start: int,
) -> tuple[str, int]:
    tokens: list[str] = []
    pos = start
    saw_value = False

    while pos < len(text):
        match = _FORMULA_TOKEN_RE.match(text, pos)

        if match is None:
            break

        token = (
            match.group("var")
            or match.group("num")
            or match.group("op")
            or ""
        )

        if not token:
            break

        tokens.append(token)
        if not match.group("op"):
            saw_value = True
        pos = match.end()

    while tokens and tokens[-1] in {
        "+", "-", "*", "/", "^", "×", "÷", "(",
    }:
        tokens.pop()

    if not tokens or not saw_value:
        return "", start

    rhs = " ".join(tokens)
    rhs = re.sub(r"\s+([)])", r"\1", rhs)
    rhs = re.sub(r"([(])\s+", r"\1", rhs)
    rhs = re.sub(r"\s*([+\-*/^×÷])\s*", r" \1 ", rhs)
    rhs = re.sub(r"\s+", " ", rhs).strip()

    return rhs, pos


def _extract_formula_objects(
    chunk: ChunkInput,
    unit: str,
    subject_family: str,
) -> list[KnowledgeObject]:
    output: list[KnowledgeObject] = []
    cursor = 0

    while cursor < len(unit):
        match = _FORMULA_START_RE.search(unit, cursor)

        if match is None:
            break

        lhs = _norm(match.group("lhs"))
        rhs, end = _scan_formula_rhs(unit, match.end())

        if rhs:
            item = _knowledge(
                chunk=chunk,
                subject_family=subject_family,
                kind=KnowledgeKind.FORMULA,
                subject=lhs,
                relation="formula",
                object_value=f"{lhs} = {rhs}",
                confidence=0.99,
                evidence_text=unit,
                tags=("explicit_equation", "formula_boundary_v0_5"),
                allow_single_symbol_subject=True,
            )

            if item is not None:
                output.append(item)

        cursor = max(end, match.end())
        if cursor <= match.start():
            cursor = match.end() + 1

    return output


def _extract_historical_date(
    *,
    chunk: ChunkInput,
    unit: str,
    subject_family: str,
) -> KnowledgeObject | None:
    for pattern in (_YEAR_LEADING_VI, _YEAR_LABEL_VI):
        match = pattern.match(unit.strip())
        if match is None:
            continue

        subject = _norm(match.group("subject"))

        if _event_subject_issue(subject) is not None:
            return None

        return _knowledge(
            chunk=chunk,
            subject_family=subject_family,
            kind=KnowledgeKind.DATE,
            subject=subject,
            relation="occurred_in",
            object_value=match.group("object"),
            confidence=0.96,
            evidence_text=unit,
            tags=("historical_date_leading",),
        )

    return None

def _extract_match(
    *,
    chunk: ChunkInput,
    unit: str,
    subject_family: str,
    pattern: re.Pattern[str],
    kind: KnowledgeKind,
    relation: str,
    confidence: float,
    tags: tuple[str, ...],
    concept_subject: bool = False,
    definition_subject: bool = False,
    event_subject: bool = False,
    boundary_start: bool = False,
) -> KnowledgeObject | None:
    match = pattern.match(unit)

    if match is None:
        return None

    raw_subject = match.group("subject")

    if event_subject and _event_subject_issue(raw_subject) is not None:
        return None

    if definition_subject and _definition_subject_issue(raw_subject) is not None:
        return None

    if (
        concept_subject
        and boundary_start
        and _first_alpha_is_lower(raw_subject)
    ):
        return None

    return _knowledge(
        chunk=chunk,
        subject_family=subject_family,
        kind=kind,
        subject=match.group("subject"),
        relation=relation,
        object_value=match.group("object"),
        confidence=confidence,
        evidence_text=unit,
        tags=tags,
        concept_subject=concept_subject,
    )


def extract_knowledge_objects(
    chunks: list[ChunkInput],
    *,
    subject_family: str = "general",
) -> list[KnowledgeObject]:
    """
    SSA-QV5-KX-V0.8

    Deterministic high-confidence fact extraction with boundary integrity.
    Precision is intentionally preferred over recall.
    Unsupported prose is left unextracted instead of guessed.
    """
    found: list[KnowledgeObject] = []

    chunk_positions = {
        (int(chunk.document_id), int(chunk.chunk_index))
        for chunk in chunks
        if chunk.chunk_index is not None
    }

    for chunk in chunks:
        units = _sentence_units(
            chunk.text
        )

        has_following_chunk = (
            chunk.chunk_index is not None
            and (
                int(chunk.document_id),
                int(chunk.chunk_index) + 1,
            )
            in chunk_positions
        )

        open_tail = _chunk_has_open_tail(
            chunk,
            has_following_chunk=has_following_chunk,
        )

        for unit_index, unit in enumerate(
            units
        ):
            last_open_unit = (
                open_tail
                and unit_index == len(units) - 1
            )
            if _HEADING_RE.match(unit):
                continue

            boundary_start = _boundary_start_fragment(
                chunk,
                unit_index=unit_index,
                unit=unit,
            )

            found.extend(
                _extract_formula_objects(
                    chunk,
                    unit,
                    subject_family,
                )
            )

            if last_open_unit:
                continue

            matched_primary = False

            for pattern in (
                _EVENT_DATE_VI,
                _EVENT_DATE_EN,
            ):
                item = _extract_match(
                    chunk=chunk,
                    unit=unit,
                    subject_family=subject_family,
                    pattern=pattern,
                    kind=KnowledgeKind.DATE,
                    relation="occurred_in",
                    confidence=0.99,
                    tags=("explicit_date_relation",),
                    event_subject=True,
                )

                if item is not None:
                    found.append(item)
                    matched_primary = True
                    break

            if not matched_primary:
                historical = _extract_historical_date(
                    chunk=chunk,
                    unit=unit,
                    subject_family=subject_family,
                )

                if historical is not None:
                    found.append(historical)
                    matched_primary = True

            if matched_primary:
                continue

            for pattern in _FUNCTION_PATTERNS:
                item = _extract_match(
                    chunk=chunk,
                    unit=unit,
                    subject_family=subject_family,
                    pattern=pattern,
                    kind=KnowledgeKind.FUNCTION,
                    relation="used_for",
                    confidence=0.96,
                    tags=("explicit_function_relation",),
                    concept_subject=True,
                    boundary_start=boundary_start,
                )

                if item is not None:
                    found.append(item)
                    matched_primary = True
                    break

            if matched_primary:
                continue

            for pattern in _CAUSE_PATTERNS:
                item = _extract_match(
                    chunk=chunk,
                    unit=unit,
                    subject_family=subject_family,
                    pattern=pattern,
                    kind=KnowledgeKind.CAUSE,
                    relation="causes",
                    confidence=0.95,
                    tags=("explicit_cause_effect",),
                )

                if item is not None:
                    found.append(item)
                    matched_primary = True
                    break

            if matched_primary:
                continue

            for pattern in (
                _NUMERIC_PROPERTY_VI,
                _NUMERIC_PROPERTY_EN,
            ):
                match = pattern.match(
                    unit
                )

                if match is None:
                    continue

                relation = _key(
                    match.group("relation")
                ).replace(
                    " ",
                    "_",
                )

                if (
                    boundary_start
                    and _first_alpha_is_lower(
                        match.group("subject")
                    )
                ):
                    break

                item = _knowledge(
                    chunk=chunk,
                    subject_family=subject_family,
                    kind=KnowledgeKind.PROPERTY,
                    subject=match.group("subject"),
                    relation=relation,
                    object_value=match.group("object"),
                    confidence=0.97,
                    evidence_text=unit,
                    tags=("explicit_numeric_property",),
                    concept_subject=True,
                )

                if item is not None:
                    found.append(item)
                    matched_primary = True

                break

            if matched_primary:
                continue

            for pattern in _DEFINITION_PATTERNS:
                item = _extract_match(
                    chunk=chunk,
                    unit=unit,
                    subject_family=subject_family,
                    pattern=pattern,
                    kind=KnowledgeKind.DEFINITION,
                    relation="defined_as",
                    confidence=0.96,
                    tags=(
                        "explicit_definition",
                        "definition_quality_gate_v0_5",
                        "definition_integrity_v0_7",
                    ),
                    concept_subject=True,
                    definition_subject=True,
                    boundary_start=boundary_start,
                )

                if item is not None:
                    found.append(item)

                break

    deduped: dict[
        tuple[str, str, str, str],
        KnowledgeObject,
    ] = {}

    for item in found:
        dedupe_key = (
            item.kind.value,
            _key(item.subject),
            item.relation,
            _key(item.object),
        )

        existing = deduped.get(
            dedupe_key
        )

        if (
            existing is None
            or item.confidence
            > existing.confidence
        ):
            deduped[
                dedupe_key
            ] = item

    return sorted(
        deduped.values(),
        key=lambda item: (
            int(
                item.evidence.document_id
            ),
            int(
                item.evidence.chunk_id
            ),
            item.kind.value,
            item.id,
        ),
    )
