from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.services.quiz_v5.models import PlannedQuestion


SSA_QV5_VALIDATOR_VERSION = "SSA-QV5-VAL-V0.3"
SSA_QV5_VALIDATOR_HARDENING_VERSION = "SSA-QV5-VAL-V0.5"
SSA_QV5_VALIDATOR_BOUNDARY_VERSION = "SSA-QV5-VAL-V0.6"
SSA_QV5_VALIDATOR_INTEGRITY_VERSION = "SSA-QV5-VAL-V0.7"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    score: float
    issues: tuple[str, ...]


_BULLET_RE = re.compile(
    r"^\s*(?:[•●▪◦‣⁃*-]|\d+[.)])\s*"
)

_TRUNCATED_END_WORDS = {
    "và", "hoặc", "của", "với", "trong", "ở", "tại",
    "để", "nhằm", "theo", "cho", "vận", "gọi", "thành", "ra",
    "and", "or", "of", "with", "in", "at", "to", "for",
}


def _norm(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _words(value: str) -> list[str]:
    return re.findall(
        r"[A-Za-zÀ-ỹ0-9]+",
        str(value or ""),
        flags=re.UNICODE,
    )


def _looks_like_heading(value: str) -> bool:
    value = str(value or "").strip()

    if re.match(
        r"^(?:CHƯƠNG|CHUONG|CHAPTER|PHẦN|PHAN|PART|MỤC|MUC|SECTION)\b",
        value,
        flags=re.I,
    ):
        return True

    words = value.split()
    return (
        1 <= len(words) <= 4
        and value.isupper()
        and not any(char.isdigit() for char in value)
    )


def _looks_truncated(value: str) -> bool:
    words = _words(value)
    return bool(
        words
        and words[-1].casefold() in _TRUNCATED_END_WORDS
    )


_FORMULA_IDENTIFIER_RE = r"(?:[A-Za-zΑ-Ωα-ωπΠ]|[A-ZΑ-Ω]{2,8})"
_FORMULA_TOKEN_FULL_RE = re.compile(
    rf"(?:"
    rf"{_FORMULA_IDENTIFIER_RE}\d*"
    r"(?![A-Za-zÀ-ỹΑ-Ωα-ω])"
    r"|\d+(?:[.,]\d+)?"
    r"|[-+*/^()√×÷]"
    r")"
)


def _formula_shape_issue(value: str) -> str | None:
    text = str(value or "").strip()

    match = re.fullmatch(
        rf"(?P<lhs>{_FORMULA_IDENTIFIER_RE})\s*=\s*(?P<rhs>.+)",
        text,
    )

    if match is None:
        return "formula_invalid_lhs_or_equals"

    rhs = match.group("rhs")
    pos = 0
    saw_value = False

    while pos < len(rhs):
        while pos < len(rhs) and rhs[pos].isspace():
            pos += 1

        if pos >= len(rhs):
            break

        token = _FORMULA_TOKEN_FULL_RE.match(
            rhs,
            pos,
        )

        if token is None:
            return "formula_contains_prose"

        raw = token.group(0)

        if raw not in {
            "+", "-", "*", "/", "^",
            "(", ")", "√", "×", "÷",
        }:
            saw_value = True

        pos = token.end()

    if not saw_value:
        return "formula_missing_rhs_value"

    return None


def option_quality_issue(
    value: str,
    *,
    family: str,
) -> str | None:
    text = str(value or "").strip()

    if not text:
        return "empty_option"

    if _BULLET_RE.match(text):
        return "bullet_option"

    if _looks_like_heading(text):
        return "heading_option"

    if _looks_truncated(text):
        return "truncated_option"

    family_key = str(family or "").strip().upper()
    words = _words(text)

    if family_key == "DATE":
        if not (
            re.fullmatch(r"\d{3,4}", text)
            or re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)
        ):
            return "date_shape_mismatch"

    elif family_key == "NUMBER":
        if not re.match(r"^[+-]?\d", text):
            return "number_shape_mismatch"

    elif family_key == "FORMULA":
        return _formula_shape_issue(text)

    elif family_key == "TERM":
        if any(char in text for char in (":", ";")):
            return "term_clause_shape"

        first_alpha = next(
            (char for char in text if char.isalpha()),
            "",
        )

        if (
            first_alpha
            and first_alpha.islower()
            and any(
                token[:1].isupper()
                for token in words[1:]
                if token
            )
        ):
            return "term_broken_proper_noun"

        if len(words) > 12:
            return "term_too_long"

    elif family_key == "DEFINITION":
        if len(words) < 4:
            return "definition_too_short"

    return None


def validate_planned_question(
    question: PlannedQuestion,
    *,
    forbidden_answer_norms: set[str] | None = None,
) -> ValidationResult:
    issues: list[str] = []

    stem = str(question.blueprint.stem or "").strip()
    correct = str(question.blueprint.correct_answer or "").strip()
    distractors = tuple(
        str(value or "").strip()
        for value in question.distractors
    )

    if len(stem) < 8:
        issues.append("stem_too_short")

    if "____" in stem or "___" in stem:
        issues.append("raw_cloze_marker")

    if _looks_like_heading(stem):
        issues.append("stem_looks_like_heading")

    if not correct:
        issues.append("missing_correct_answer")

    if len(distractors) != 3:
        issues.append("distractor_count_not_three")

    all_options = (correct, *distractors)
    norms = [_norm(value) for value in all_options]

    if any(not value for value in norms):
        issues.append("empty_option")

    if len(set(norms)) != len(norms):
        issues.append("duplicate_options")

    forbidden = {
        _norm(value)
        for value in (forbidden_answer_norms or set())
        if _norm(value)
    }

    if any(value in forbidden for value in norms[1:]):
        issues.append("distractor_matches_other_selected_correct")

    family = question.blueprint.distractor_family

    correct_issue = option_quality_issue(correct, family=family)
    if correct_issue:
        issues.append("correct_" + correct_issue)

    for distractor in distractors:
        issue = option_quality_issue(distractor, family=family)
        if issue:
            issues.append("distractor_" + issue)

    if not question.blueprint.evidence.text:
        issues.append("missing_evidence_text")

    if question.blueprint.evidence.chunk_id <= 0:
        issues.append("invalid_chunk_lineage")

    unique_issues = tuple(sorted(set(issues)))
    score = max(0.0, 100.0 - 12.5 * len(unique_issues))

    return ValidationResult(
        valid=not unique_issues,
        score=round(score, 2),
        issues=unique_issues,
    )
