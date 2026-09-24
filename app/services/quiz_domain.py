from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata

DOMAIN_AWARE_QUIZ_VERSION = "DAQ-V1"

GENERAL = "GENERAL"
HISTORY = "HISTORY"
GEOGRAPHY = "GEOGRAPHY"
CHEMISTRY = "CHEMISTRY"
MATHEMATICS = "MATHEMATICS"
PHYSICS = "PHYSICS"
BIOLOGY = "BIOLOGY"
ECONOMICS = "ECONOMICS"

TERM = "TERM"
PERSON = "PERSON"
DATE = "DATE"
PLACE = "PLACE"
EVENT = "EVENT"
PROCESS = "PROCESS"
NUMERIC = "NUMERIC"
FORMULA = "FORMULA"
CHEMICAL_FORMULA = "CHEMICAL_FORMULA"
CHEMICAL_EQUATION = "CHEMICAL_EQUATION"


@dataclass(frozen=True)
class KnowledgeProfile:
    domain: str
    knowledge_type: str
    confidence: float
    reason: str


def _fold(value: str) -> str:
    raw = unicodedata.normalize("NFD", str(value or ""))
    raw = "".join(
        ch for ch in raw
        if unicodedata.category(ch) != "Mn"
    )
    return (
        raw.casefold()
        .replace("đ", "d")
        .strip()
    )


def _tokens(value: str) -> list[str]:
    return re.findall(
        r"[A-Za-zÀ-ỹ0-9]+",
        str(value or "").casefold(),
        flags=re.UNICODE,
    )


DOMAIN_KEYWORDS = {
    HISTORY: (
        "lich su", "chien tranh", "cach mang", "trieu dai",
        "vua", "hiep dinh", "khoi nghia", "the ky",
        "dynasty", "war", "revolution", "treaty", "empire",
    ),
    GEOGRAPHY: (
        "dia ly", "dia hinh", "khi hau", "chau luc", "quoc gia",
        "thu do", "dan so", "dien tich", "vi do", "kinh do",
        "geography", "climate", "population", "capital",
        "latitude", "longitude",
    ),
    CHEMISTRY: (
        "hoa hoc", "phan ung", "nguyen to", "phan tu", "mol",
        "axit", "bazo", "muoi", "oxi hoa", "chemistry",
        "reaction", "molecule", "element", "acid", "base",
    ),
    MATHEMATICS: (
        "toan", "ham so", "dao ham", "tich phan", "ma tran",
        "vector", "gioi han", "phuong trinh", "math",
        "derivative", "integral", "matrix", "limit", "equation",
    ),
    PHYSICS: (
        "vat ly", "van toc", "gia toc", "dong luong", "dien ap",
        "physics", "velocity", "acceleration", "force", "voltage",
    ),
    BIOLOGY: (
        "sinh hoc", "te bao", "gen", "dna", "rna", "enzyme",
        "he sinh thai", "biology", "cell", "gene", "ecosystem",
    ),
    ECONOMICS: (
        "kinh te", "hang hoa", "tien te", "tu ban",
        "gia tri thang du", "thi truong", "cung cau",
        "economics", "capital", "market", "surplus value",
    ),
}


def _looks_like_year(value: str) -> bool:
    text = str(value or "").strip()

    if re.fullmatch(
        r"(?:1[0-9]{3}|20[0-9]{2})",
        text,
    ):
        return True

    # DAQ-V1.4 date-phrase guard:
    # Accept both a bare date and a grounded phrase such as
    # "ngày 2/9/1945". This must run before formula detection
    # so slash-separated dates are never mistaken for division.
    if re.search(
        r"(?<!\d)"
        r"\d{1,2}[/-]\d{1,2}[/-]"
        r"(?:\d{2}|\d{4})"
        r"(?!\d)",
        text,
    ):
        return True

    return False


def _looks_like_numeric(value: str) -> bool:
    text = str(value or "").strip()
    return bool(
        re.fullmatch(
            r"[+-]?\d+(?:[.,]\d+)?"
            r"(?:\s*(?:%|°C|K|kg|g|mg|m|cm|mm|km|m/s|m/s²|"
            r"m/s2|N|Pa|J|W|V|A|mol|M|Hz|s|min|h))?",
            text,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_chemical_equation(value: str) -> bool:
    text = str(value or "").strip()
    if not any(x in text for x in ("→", "->", "⇌", "<=>")):
        return False
    return len(
        re.findall(
            r"[A-Z][a-z]?\d*",
            text,
        )
    ) >= 2


def _looks_like_chemical_formula(value: str) -> bool:
    text = str(value or "").strip()
    if not text or " " in text or _looks_like_year(text):
        return False
    return bool(
        re.fullmatch(r"(?:[A-Z][a-z]?\d*){1,8}", text)
        or re.fullmatch(
            r"(?:[A-Z][a-z]?\d*)+(?:\([A-Z][a-z]?\d*\)\d*)+",
            text,
        )
    )


def _looks_like_math_formula(value: str) -> bool:
    text = str(value or "").strip()
    folded = _fold(text)

    if "=" in text:
        return True

    if any(
        x in text
        for x in (
            "∫",
            "∑",
            "√",
            "∞",
            "≤",
            "≥",
            "≠",
        )
    ):
        return True

    if any(
        x in folded
        for x in (
            "sin(",
            "cos(",
            "tan(",
            "ln(",
            "log(",
            "lim ",
            "f'(",
            "dy/dx",
        )
    ):
        return True

    # DAQ-V1.10 prose/hyphen guard.
    #
    # Historical labels such as:
    #   "1954 – Chiến thắng Điện Biên Phủ và Hiệp định Giơ-ne-vơ"
    # or metadata labels such as:
    #   "LỊCH SỬ ... DAQ-V1"
    # contain hyphens but are prose, not mathematical formulas.
    #
    # If the text contains several real word tokens, do not
    # let an internal word hyphen alone promote it to FORMULA.
    prose_words = re.findall(
        r"[A-Za-zÀ-ỹĐđ]+",
        text,
        flags=re.UNICODE,
    )

    long_words = [
        token
        for token in prose_words
        if len(token) >= 3
    ]

    if (
        len(prose_words) >= 3
        and len(long_words) >= 2
    ):
        return False

    # Non-minus arithmetic operators remain strong signals.
    if re.search(
        r"[A-Za-z0-9)][+*/^][A-Za-z0-9(]",
        text,
    ):
        return True

    # Treat '-' as a math operator only for compact symbolic
    # operands. This preserves x-y, x-2 and 2-x while blocking
    # ordinary hyphenated prose words.
    if re.search(
        r"(?<![A-Za-zÀ-ỹĐđ])"
        r"(?:[A-Za-z]|\d+)"
        r"\s*-\s*"
        r"(?:[A-Za-z]|\d+)"
        r"(?![A-Za-zÀ-ỹĐđ])",
        text,
        flags=re.UNICODE,
    ):
        return True

    if re.search(
        r"[A-Za-z]\^?\d+",
        text,
    ):
        return True

    return False


def infer_domain(source_text: str, *, answer_text: str = "") -> str:
    text = _fold(f"{source_text} {answer_text}")
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[domain] += 1

    answer = str(answer_text or "").strip()
    if _looks_like_chemical_equation(answer):
        scores[CHEMISTRY] += 6
    elif _looks_like_chemical_formula(answer):
        scores[CHEMISTRY] += 3

    if (
        not _looks_like_year(answer)
        and not _looks_like_numeric(answer)
        and not _looks_like_chemical_equation(answer)
        and not _looks_like_chemical_formula(answer)
        and _looks_like_math_formula(answer)
    ):
        scores[MATHEMATICS] += 3

    domain, score = max(scores.items(), key=lambda item: item[1])
    return domain if score > 0 else GENERAL


PERSON_CUES = (
    "ong ", "ba ", "vua ", "chu tich ", "tong thong ", "tuong ",
    "nha van ", "nha tho ", "tac gia ", "author ", "president ",
    "king ", "queen ", "general ", "scientist ",
)

PLACE_CUES = (
    "thu do", "thanh pho", "tinh ", "quoc gia", "chau ", "khu vuc",
    "located", "capital", "city", "country", "province", "river", "sea",
)

EVENT_CUES = (
    "su kien", "cuoc chien", "chien dich", "cach mang", "khoi nghia",
    "hoi nghi", "hiep dinh", "event", "war", "campaign",
    "revolution", "conference", "treaty",
)

PROCESS_CUES = (
    "qua trinh", "chu trinh", "co che", "phan ung", "giai doan",
    "process", "cycle", "mechanism", "reaction", "stage",
)


def _context_has_cue(
    folded_context: str,
    cues: tuple[str, ...],
) -> bool:
    """
    Match semantic cues on token/phrase boundaries.

    This prevents false positives such as:
      PERSON cue "ong"
      matching inside Vietnamese "song" (sông).

    Cues are already accent-folded by the caller.
    """
    text = str(folded_context or "")

    for raw_cue in cues:
        cue = _fold(raw_cue).strip()

        if not cue:
            continue

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(cue)
            + r"(?![a-z0-9])"
        )

        if re.search(
            pattern,
            text,
            flags=re.UNICODE,
        ):
            return True

    return False


def infer_knowledge_profile(
    *,
    answer_text: str,
    evidence_text: str = "",
    source_text: str = "",
) -> KnowledgeProfile:
    answer = str(answer_text or "").strip()

    # DAQ-V1.5 split domain context from type context.
    #
    # DOMAIN needs broad document/source signals.
    # KNOWLEDGE TYPE must stay local to this answer's evidence;
    # otherwise one PERSON cue elsewhere in the same chunk can
    # contaminate unrelated EVENT/PLACE/TERM answers.
    domain_context = " ".join(
        part
        for part in (
            str(evidence_text or "").strip(),
            str(source_text or "").strip(),
        )
        if part
    )

    cue_context = (
        str(evidence_text or "").strip()
        or str(source_text or "").strip()
    )

    folded_context = _fold(
        cue_context
    )

    domain = infer_domain(
        domain_context,
        answer_text=answer,
    )

    if _looks_like_chemical_equation(answer):
        return KnowledgeProfile(CHEMISTRY, CHEMICAL_EQUATION, 0.99, "chemical equation")
    if domain == CHEMISTRY and _looks_like_chemical_formula(answer):
        return KnowledgeProfile(domain, CHEMICAL_FORMULA, 0.97, "chemical formula")
    if _looks_like_year(answer):
        return KnowledgeProfile(domain, DATE, 0.98, "date/year")
    if _looks_like_numeric(answer):
        return KnowledgeProfile(domain, NUMERIC, 0.94, "numeric value")
    if _looks_like_math_formula(answer):
        return KnowledgeProfile(domain, FORMULA, 0.97, "formula syntax")

    if (
        _context_has_cue(
            folded_context,
            PERSON_CUES,
        )
        and len(_tokens(answer)) >= 2
        and answer[:1].isupper()
    ):
        return KnowledgeProfile(domain, PERSON, 0.78, "person cue")

    if _context_has_cue(
        folded_context,
        PLACE_CUES,
    ):
        return KnowledgeProfile(domain, PLACE, 0.76, "place cue")

    if _context_has_cue(
        folded_context,
        EVENT_CUES,
    ):
        return KnowledgeProfile(domain, EVENT, 0.72, "event cue")

    if _context_has_cue(
        folded_context,
        PROCESS_CUES,
    ):
        return KnowledgeProfile(domain, PROCESS, 0.70, "process cue")

    return KnowledgeProfile(domain, TERM, 0.60, "default term")


def candidate_compatible_with_profile(
    candidate_text: str,
    *,
    correct_profile: KnowledgeProfile,
    candidate_context: str = "",
) -> bool:
    candidate = infer_knowledge_profile(
        answer_text=candidate_text,
        evidence_text=candidate_context,
    )

    strict = {
        PERSON, DATE, PLACE, NUMERIC, FORMULA,
        CHEMICAL_FORMULA, CHEMICAL_EQUATION,
    }

    if correct_profile.knowledge_type in strict:
        return candidate.knowledge_type == correct_profile.knowledge_type

    return candidate.knowledge_type in {TERM, EVENT, PROCESS}


STOP_WORDS = {
    "a", "b", "c", "d", "la", "va", "cua", "cac", "nhung", "mot",
    "ve", "theo", "trong", "giua", "duoc", "cho", "voi",
    "the", "of", "and", "or", "to", "in", "on", "for",
}


def _semantic_tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", _fold(value))
        if len(token) >= 2 and token not in STOP_WORDS
    ]


def domain_candidate_score(
    candidate_text: str,
    *,
    correct_text: str,
    correct_profile: KnowledgeProfile,
    candidate_context: str = "",
) -> float:
    if not candidate_compatible_with_profile(
        candidate_text,
        correct_profile=correct_profile,
        candidate_context=candidate_context,
    ):
        return -1000.0

    score = 100.0
    candidate_profile = infer_knowledge_profile(
        answer_text=candidate_text,
        evidence_text=candidate_context,
    )

    if (
        candidate_profile.domain == correct_profile.domain
        and correct_profile.domain != GENERAL
    ):
        score += 25.0

    if correct_profile.knowledge_type in {
        DATE, NUMERIC, FORMULA, CHEMICAL_FORMULA, CHEMICAL_EQUATION
    }:
        return score + 45.0

    left = _semantic_tokens(correct_text)
    right = _semantic_tokens(candidate_text)

    if not left or not right:
        return score

    left_set = set(left)
    right_set = set(right)
    shared = left_set & right_set
    union = left_set | right_set

    score += 50.0 * len(shared) / max(1, len(union))
    score += 12.0 * len(shared)

    if left[0] == right[0]:
        score += 35.0

    score += 15.0 * min(len(left), len(right)) / max(len(left), len(right))
    return score


def rank_domain_candidates(
    candidates: list[str],
    *,
    correct_text: str,
    correct_profile: KnowledgeProfile,
    candidate_context: str = "",
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()

    for raw in candidates:
        text = str(raw or "").strip()
        norm = _fold(text)

        if not text or not norm or norm in seen:
            continue
        if not candidate_compatible_with_profile(
            text,
            correct_profile=correct_profile,
            candidate_context=candidate_context,
        ):
            continue

        seen.add(norm)
        unique.append(text)

    unique.sort(
        key=lambda candidate: (
            -domain_candidate_score(
                candidate,
                correct_text=correct_text,
                correct_profile=correct_profile,
                candidate_context=candidate_context,
            ),
            _fold(candidate),
        )
    )
    return unique


def _format_number_like(value: float, template: str) -> str:
    if math.isclose(value, round(value), abs_tol=1e-9):
        out = str(int(round(value)))
    else:
        out = f"{value:.4f}".rstrip("0").rstrip(".")
    return out.replace(".", ",") if "," in template else out


def structured_distractor_variants(
    answer_text: str,
    *,
    profile: KnowledgeProfile,
) -> list[str]:
    answer = str(answer_text or "").strip()
    variants: list[str] = []

    if profile.knowledge_type == DATE:
        # DAQ-V1.6 full-date structured variants.
        if re.fullmatch(r"\d{4}", answer):
            year = int(answer)
            variants = [
                str(year + delta)
                for delta in (-1, 1, -5, 5, -10, 10)
                if 1 <= year + delta <= 2200
            ]
        else:
            date_match = re.search(
                r"(?<!\d)"
                r"(\d{1,2})([/-])(\d{1,2})\2(\d{2}|\d{4})"
                r"(?!\d)",
                answer,
            )

            if date_match:
                day = int(date_match.group(1))
                sep = date_match.group(2)
                month = int(date_match.group(3))
                raw_year = date_match.group(4)
                year = int(raw_year)

                if len(raw_year) == 2:
                    year += 2000

                raw_date = date_match.group(0)
                candidate_dates: list[str] = []

                for candidate_day in (day - 1, day + 1):
                    if 1 <= candidate_day <= 28:
                        candidate_dates.append(
                            f"{candidate_day}{sep}{month}{sep}{year}"
                        )

                for candidate_month in (month - 1, month + 1):
                    if 1 <= candidate_month <= 12:
                        candidate_dates.append(
                            f"{day}{sep}{candidate_month}{sep}{year}"
                        )

                for delta in (-1, 1, -5, 5):
                    candidate_year = year + delta
                    if 1 <= candidate_year <= 2200:
                        candidate_dates.append(
                            f"{day}{sep}{month}{sep}{candidate_year}"
                        )

                variants = [
                    answer.replace(
                        raw_date,
                        candidate_date,
                        1,
                    )
                    for candidate_date in candidate_dates
                ]

    elif profile.knowledge_type == NUMERIC:
        match = re.fullmatch(
            r"([+-]?\d+(?:[.,]\d+)?)(\s*.*)",
            answer,
        )
        if match:
            raw_number, suffix = match.groups()
            value = float(raw_number.replace(",", "."))
            step = 1.0 if abs(value) < 20 else max(1.0, abs(value) * 0.1)
            variants = [
                _format_number_like(v, raw_number) + suffix
                for v in (
                    value - step,
                    value + step,
                    value * 0.9,
                    value * 1.1,
                )
                if not math.isclose(v, value)
            ]

    elif profile.knowledge_type == CHEMICAL_FORMULA:
        digit = re.search(r"\d+", answer)
        if digit:
            original = int(digit.group(0))
            replacements: list[str] = []

            if original > 2:
                replacements.append(
                    str(original - 1)
                )
            elif original == 2:
                replacements.append(
                    ""
                )

            replacements.extend(
                [
                    str(original + 1),
                    str(original + 2),
                ]
            )

            for replacement in replacements:
                variants.append(
                    answer[:digit.start()]
                    + replacement
                    + answer[digit.end():]
                )
        else:
            elements = list(re.finditer(r"[A-Z][a-z]?", answer))
            if elements:
                first = elements[0]
                last = elements[-1]
                variants.extend([
                    answer[:first.end()] + "2" + answer[first.end():],
                    answer[:last.end()] + "2" + answer[last.end():],
                ])

    deduped: list[str] = []
    seen = {_fold(answer)}

    for candidate in variants:
        norm = _fold(candidate)
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(candidate)

    return deduped


def question_guidance(profile: KnowledgeProfile) -> str:
    rules = {
        DATE: "Ask WHEN/WHICH YEAR and explicitly name the event.",
        PERSON: "Ask WHO and explicitly name the role/event/context.",
        PLACE: "Ask WHERE/WHICH PLACE from an explicit geographic fact.",
        NUMERIC: "Ask for the numeric VALUE and preserve quantity/unit context.",
        FORMULA: "Ask for the formula/expression with explicit variable/context names.",
        CHEMICAL_FORMULA: (
            "Ask for the chemical formula only when evidence explicitly maps "
            "the substance/name to that formula."
        ),
        CHEMICAL_EQUATION: (
            "Ask for the reaction equation only when the complete reaction "
            "is explicitly present in evidence."
        ),
        EVENT: "Ask WHICH EVENT using a direct identifying fact.",
        PROCESS: "Ask WHICH PROCESS/MECHANISM from an explicit description.",
        TERM: (
            "Ask a natural concept identification/definition question; use "
            "cloze only when a direct stem would reveal the answer."
        ),
    }
    return rules.get(profile.knowledge_type, rules[TERM])
