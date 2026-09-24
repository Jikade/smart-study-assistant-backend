from __future__ import annotations

import re
from typing import Iterable

QSP_VERSION = "QSP-V1"
ACQ_VERSION = "ACQ-V1"
PQG_VERSION = "PQG-V1"
DSP_VERSION = "DSP-V2"


def _norm(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    return text.strip(" \t\r\n,;:.!?-–—")


def _words(value: str) -> list[str]:
    return re.findall(r"\w+", str(value or ""), flags=re.UNICODE)


def _looks_like_heading(value: str) -> bool:
    text = _norm(value)
    if not text:
        return True
    patterns = (
        r"^(?:chương|chapter)\s+(?:\d+|[ivxlcdm]+)\b.*$",
        r"^(?:phần|part)\s+(?:\d+|[ivxlcdm]+)\b.*$",
        r"^(?:mục|section)\s+(?:\d+(?:\.\d+)*)\b.*$",
        r"^\d+(?:\.\d+){0,4}\s+[\wÀ-ỹĐđ].*$",
    )
    if any(re.match(p, text, flags=re.I | re.UNICODE) for p in patterns):
        return len(_words(text)) <= 12
    return False


def _fragment_issue(value: str) -> str | None:
    text = _norm(value)
    if not text:
        return "empty text"
    suffixes = (
        " vào", " về", " của", " cho", " với", " từ", " để", " nhằm",
        " bởi", " do", " tại", " theo", " dựa trên", " bao gồm", " gồm",
        " tập trung vào", " hướng tới", " liên quan đến", " phụ thuộc vào",
        " được gọi là", " được hiểu là", " có nghĩa là",
        " such as", " including", " based on", " focuses on", " consists of",
    )
    if any(text.endswith(s) for s in suffixes):
        return "incomplete/dangling phrase"
    prefixes = (
        "do đó ", "vì vậy ", "như vậy ", "từ đó ", "theo đó ",
        "đồng thời ", "mặt khác ", "therefore ", "thus ", "hence ",
    )
    if any(text.startswith(p) for p in prefixes):
        return "context-dependent connector fragment"
    return None


def qsp_chunk_issue(content: str) -> str | None:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if not text:
        return "empty chunk"
    if len(text) < 160:
        return "chunk too short for reliable study-question generation"
    upper = text.upper()
    if "MỤC LỤC" in upper[:700] or "TABLE OF CONTENTS" in upper[:700]:
        return "table-of-contents-like chunk"
    lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
    if lines:
        heading_lines = sum(1 for line in lines if _looks_like_heading(line))
        if heading_lines >= 3 and heading_lines / max(1, len(lines)) >= 0.45:
            return "heading-dominated chunk"
    return None


def qsp_score(content: str) -> float:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if not text:
        return -1000.0
    if qsp_chunk_issue(content):
        return -250.0

    norm = _norm(text)
    score = 0.0
    if 450 <= len(text) <= 2400:
        score += 18.0
    elif 250 <= len(text) < 450:
        score += 8.0
    elif len(text) > 2400:
        score += 4.0

    groups = (
        (" là ", " được hiểu là ", " được gọi là ", " có nghĩa là ", " khái niệm ", " định nghĩa "),
        (" điều kiện ", " điều kiện tiên quyết ", " yêu cầu ", " cần "),
        (" nguyên nhân ", " hệ quả ", " kết quả ", " tác động ", " ảnh hưởng ", " dẫn đến "),
        (" vai trò ", " chức năng ", " nhiệm vụ ", " ý nghĩa "),
        (" bao gồm ", " gồm ", " đặc điểm ", " yếu tố ", " thành phần ", " phân loại "),
        (" quy luật ", " nguyên tắc ", " công thức ", " phương trình "),
    )
    padded = f" {norm} "
    for markers in groups:
        hits = sum(1 for m in markers if m in padded)
        score += min(hits, 3) * 7.0

    score += min(
        len(re.findall(r"(?:^|\s)(?:\d+[\.\)]|[a-zA-Z][\.\)])\s+", text)),
        5,
    ) * 2.5

    for marker in ("tài liệu tham khảo", "references", "mục lục", "nhà xuất bản", "isbn"):
        if marker in norm:
            score -= 6.0

    if len(re.findall(r"\b[A-ZÀ-ỸĐ]{3,}\b", text)) >= 8:
        score -= 12.0
    return round(score, 3)


def acq_answer_issue(answer_text: str) -> str | None:
    answer = re.sub(r"\s+", " ", str(answer_text or "")).strip()
    norm = _norm(answer)
    if not norm:
        return "ACQ: empty answer candidate"
    if _looks_like_heading(answer):
        return "ACQ: heading/section label is not a standalone answer"
    fragment = _fragment_issue(answer)
    if fragment:
        return f"ACQ: {fragment}"
    generic = {
        "nội dung", "đặc điểm", "khái niệm", "yếu tố", "vấn đề", "trường hợp",
        "nguyên nhân", "kết quả", "một điều kiện duy nhất", "hai yếu tố chính",
        "một nguyên nhân chính", "đáp án khác", "tất cả các đáp án trên",
        "không có đáp án nào",
    }
    if norm in generic:
        return "ACQ: generic/non-instructional answer"
    if len(_words(answer)) > 22 and "=" not in answer:
        return "ACQ: answer candidate is too sentence-like"
    if answer.rstrip().endswith(":"):
        return "ACQ: label fragment ending with colon"
    return None


def acq_score_bonus(answer_text: str, evidence_text: str) -> float:
    answer = re.sub(r"\s+", " ", str(answer_text or "")).strip()
    evidence = re.sub(r"\s+", " ", str(evidence_text or "")).strip()
    if acq_answer_issue(answer):
        return -1000.0

    score = 15.0 if 2 <= len(_words(answer)) <= 10 else 0.0
    norm_evidence = _norm(evidence)
    norm_answer = _norm(answer)
    if norm_answer:
        patterns = (
            rf"\b{re.escape(norm_answer)}\s+là\b",
            rf"\b{re.escape(norm_answer)}\s+được hiểu là\b",
            rf"\b{re.escape(norm_answer)}\s+được gọi là\b",
            rf"\b{re.escape(norm_answer)}\s*:",
        )
        if any(re.search(p, norm_evidence, flags=re.UNICODE) for p in patterns):
            score += 25.0
    return score


_VI_NUMBERS = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "bon": 4, "năm": 5, "nam": 5, "sáu": 6, "sau": 6}


def _requested_list_count(question_text: str) -> int | None:
    q = _norm(question_text)
    m = re.search(
        r"\b(một|hai|ba|bốn|bon|năm|nam|sáu|sau|\d+)\s+"
        r"(?:điều kiện|yếu tố|đặc điểm|nguyên nhân|tác động|chức năng|vai trò|"
        r"thành phần|nội dung|biện pháp|giải pháp)\b",
        q,
        flags=re.UNICODE,
    )
    if not m:
        return None
    raw = m.group(1)
    return int(raw) if raw.isdigit() else _VI_NUMBERS.get(raw)


def _list_item_count(answer_text: str) -> int:
    text = re.sub(r"\s+", " ", str(answer_text or "")).strip()
    if not text:
        return 0
    parts = re.split(r"\s*(?:;|\+|/)\s*|\s*,\s*|\s+và\s+", text, flags=re.I)
    return len([p for p in parts if p.strip()])



def _pedagogy_content_tokens(value: str) -> set[str]:
    stopwords = {
        "là", "gì", "nào", "được", "dùng", "để", "của", "và",
        "trong", "theo", "một", "các", "những", "cho", "với",
        "what", "which", "is", "are", "the", "of", "to", "for",
    }
    return {
        token
        for token in re.findall(
            r"\w+",
            _norm(value),
            flags=re.UNICODE,
        )
        if len(token) >= 2
        and token not in stopwords
    }


def _lexical_answer_cue_issue(
    question_text: str,
    correct_text: str,
) -> str | None:
    if "=" in str(correct_text or ""):
        return None

    question_raw = str(
        question_text
        or ""
    )
    question_norm = _norm(
        question_raw
    )

    # Cloze/definition questions naturally reuse vocabulary
    # from the concept definition. Lexical overlap alone is
    # therefore not evidence that the answer is being leaked.
    #
    # Exact-answer leakage is still handled by the existing
    # deterministic question-answer fit gate, so this exemption
    # does NOT permit the correct answer to appear verbatim.
    is_cloze = (
        bool(
            re.search(
                r"_{3,}|\.{3,}|…",
                question_raw,
                flags=re.UNICODE,
            )
        )
        or "chỗ trống" in question_norm
        or "fill in the blank" in question_norm
    )

    if is_cloze:
        return None

    answer_tokens = _pedagogy_content_tokens(
        correct_text
    )
    question_tokens = _pedagogy_content_tokens(
        question_text
    )

    if len(answer_tokens) < 2:
        return None

    overlap = answer_tokens.intersection(
        question_tokens
    )
    ratio = len(overlap) / max(
        1,
        len(answer_tokens),
    )

    if (
        len(overlap) >= 2
        and ratio >= 0.67
    ):
        return (
            "PQG: question lexically cues/paraphrases "
            "too much of the correct answer"
        )

    return None


def _parenthetical_descriptor(value: str) -> str | None:
    match = re.search(
        r"\(([^()]{3,})\)",
        str(value or ""),
        flags=re.UNICODE,
    )
    if not match:
        return None

    descriptor = _norm(match.group(1))
    return descriptor or None


def pqg_question_issue(*, question_text: str, correct_text: str, evidence_text: str = "") -> str | None:
    q_norm = _norm(question_text)
    if not q_norm:
        return "PQG: empty question stem"

    deictic_terms = (
        "nó",
        "điều này",
        "điều đó",
        "thể chế này",
        "chính sách này",
        "quá trình này",
        "mô hình này",
        "hệ thống này",
        "cơ chế này",
        "this",
        "it",
        "these",
        "those",
    )

    # A deictic reference can appear after a wrapper such as:
    # "Điền cụm từ thích hợp vào chỗ trống: Nó ..."
    # Therefore checking only q_norm.startswith(...) is insufficient.
    #
    # Reject deictic terms when they begin the whole stem OR begin
    # a new clause/sentence after punctuation. Ordinary occurrences
    # inside a self-contained sentence are not rejected by this rule.
    deictic_pattern = (
        r"(?:^|[:.!?;]\s+)(?:"
        + "|".join(
            re.escape(term)
            for term in deictic_terms
        )
        + r")\b"
    )

    if re.search(
        deictic_pattern,
        q_norm,
        flags=re.UNICODE,
    ):
        return "PQG: context-dependent/deictic question stem"

    lexical_issue = _lexical_answer_cue_issue(
        question_text,
        correct_text,
    )
    if lexical_issue:
        return lexical_issue

    vague_transition_phrases = (
        "sau khi thay đổi",
        "sau khi biến đổi",
        "sau khi chuyển đổi",
        "sau đó",
        "trong trường hợp này",
        "ở trường hợp này",
    )
    if any(
        phrase in q_norm
        for phrase in vague_transition_phrases
    ):
        return "PQG: vague transition/context phrase"

    requested = _requested_list_count(question_text)
    if requested and requested >= 2:
        actual = _list_item_count(correct_text)
        if actual < requested:
            return (
                "PQG: explicit multi-item question has an answer "
                f"with only {actual} discernible item(s); expected at least {requested}"
            )

    if _looks_like_heading(correct_text):
        return "PQG: correct option is a heading/section label"
    fragment = _fragment_issue(correct_text)
    if fragment:
        return f"PQG: correct option is {fragment}"
    return None


def _option_kind(value: str) -> str:
    text = str(value or "").strip()
    if "=" in text:
        return "FORMULA"
    if _looks_like_heading(text):
        return "HEADING"
    if _fragment_issue(text):
        return "FRAGMENT"
    if _list_item_count(text) >= 2 and any(sep in text for sep in (",", ";", " và ", "+", "/")):
        return "LIST"
    return "TERM" if len(_words(text)) <= 4 else "PHRASE"


def dsp_distractor_issue(*, correct_text: str, distractors: Iterable[str]) -> str | None:
    correct = re.sub(r"\s+", " ", str(correct_text or "")).strip()
    correct_kind = _option_kind(correct)
    correct_descriptor = _parenthetical_descriptor(
        correct
    )
    seen = {_norm(correct)}

    for distractor in distractors:
        value = re.sub(r"\s+", " ", str(distractor or "")).strip()
        norm = _norm(value)
        if not norm:
            return "DSP: empty distractor"
        if norm in seen:
            return "DSP: duplicate/equivalent distractor"
        seen.add(norm)

        distractor_descriptor = _parenthetical_descriptor(
            value
        )
        if (
            correct_descriptor
            and distractor_descriptor
            and correct_descriptor == distractor_descriptor
        ):
            return (
                "DSP: distractor repeats the same semantic "
                "parenthetical label as the correct answer"
            )

        issue = acq_answer_issue(value)
        if issue:
            return f"DSP: low-quality distractor ({issue})"

        kind = _option_kind(value)
        if correct_kind == "FORMULA" and kind != "FORMULA":
            return "DSP: formula answer paired with non-formula distractor"
        if correct_kind == "LIST" and kind != "LIST":
            return "DSP: list answer paired with non-list distractor"
        if kind in {"HEADING", "FRAGMENT"}:
            return f"DSP: distractor has invalid shape {kind}"

        cw = max(1, len(_words(correct)))
        dw = max(1, len(_words(value)))
        if correct_kind in {"TERM", "PHRASE"} and max(cw, dw) / min(cw, dw) > 3.5:
            return "DSP: distractor length/shape is not parallel to correct answer"
    return None


def pedagogical_question_issue(
    *,
    question_text: str,
    correct_text: str,
    distractors: Iterable[str],
    evidence_text: str = "",
) -> str | None:
    issue = pqg_question_issue(
        question_text=question_text,
        correct_text=correct_text,
        evidence_text=evidence_text,
    )
    if issue:
        return issue
    return dsp_distractor_issue(correct_text=correct_text, distractors=distractors)
