from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata

from app.services.quiz_v5.models import (
    BlueprintType,
    PlannedQuestion,
    QuestionBlueprint,
)
from app.services.quiz_v5.selector import (
    select_diverse_blueprints,
)
from app.services.quiz_v5.validators import (
    option_quality_issue,
    validate_planned_question,
)


SSA_QV5_DISTRACTOR_VERSION = "SSA-QV5-DX-V0.3"
SSA_QV5_DISTRACTOR_HARDENING_VERSION = "SSA-QV5-DX-V0.5"
SSA_QV5_DISTRACTOR_BOUNDARY_VERSION = "SSA-QV5-DX-V0.6"
SSA_QV5_DISTRACTOR_INTEGRITY_VERSION = "SSA-QV5-DX-V0.7"


@dataclass(frozen=True)
class DistractorChoice:
    text: str
    origin: str
    source_blueprint_id: str | None
    rank: tuple


@dataclass(frozen=True)
class PlanBuildDiagnostics:
    requested: int
    selected: int
    exact: bool
    iterations: int
    rejected_blueprint_ids: tuple[str, ...]
    structured_fallback_count: int


def _norm(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()
    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()
    return value


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"\w+",
            _norm(value),
            flags=re.UNICODE,
        )
        if len(token) >= 2
    }


def _family(value: str) -> str:
    return _norm(value).upper()


def _source_scope_rank(
    target: QuestionBlueprint,
    candidate: QuestionBlueprint,
) -> int:
    if (
        target.section_id is not None
        and candidate.section_id
        == target.section_id
    ):
        return 0

    if (
        candidate.evidence.document_id
        == target.evidence.document_id
    ):
        return 1

    return 2


def _lexical_distance(
    target: QuestionBlueprint,
    candidate: QuestionBlueprint,
) -> tuple[int, int]:
    target_tokens = _tokens(
        target.correct_answer
    )
    candidate_tokens = _tokens(
        candidate.correct_answer
    )

    overlap = len(
        target_tokens
        & candidate_tokens
    )

    length_delta = abs(
        len(
            target.correct_answer
        )
        - len(
            candidate.correct_answer
        )
    )

    # Prefer comparable-looking options, but avoid near-duplicates.
    return (
        -min(
            overlap,
            3,
        ),
        length_delta,
    )


def _candidate_rank(
    target: QuestionBlueprint,
    candidate: QuestionBlueprint,
) -> tuple:
    return (
        _source_scope_rank(
            target,
            candidate,
        ),
        0
        if candidate.blueprint_type
        == target.blueprint_type
        else 1,
        *_lexical_distance(
            target,
            candidate,
        ),
        -float(
            candidate.quality_score
        ),
        candidate.id,
    )


def _year_variants(
    answer: str,
) -> list[str]:
    match = re.fullmatch(
        r"\s*(\d{3,4})\s*",
        answer,
    )

    if match is None:
        return []

    year = int(
        match.group(1)
    )

    offsets = (
        -10,
        10,
        -20,
        20,
        -5,
        5,
        -1,
        1,
    )

    return [
        str(
            year + offset
        )
        for offset in offsets
        if year + offset > 0
    ]


def _slash_date_variants(
    answer: str,
) -> list[str]:
    match = re.fullmatch(
        r"\s*(\d{1,2})([/-])(\d{1,2})\2(\d{2,4})\s*",
        answer,
    )

    if match is None:
        return []

    day = int(
        match.group(1)
    )
    sep = match.group(2)
    month = int(
        match.group(3)
    )
    year_text = match.group(4)
    year = int(
        year_text
    )

    values = []

    for delta in (-1, 1, -2, 2):
        new_day = day + delta
        if 1 <= new_day <= 28:
            values.append(
                f"{new_day}{sep}{month}{sep}{year_text}"
            )

    for delta in (-1, 1):
        new_month = month + delta
        if 1 <= new_month <= 12:
            values.append(
                f"{day}{sep}{new_month}{sep}{year_text}"
            )

    for delta in (-1, 1, -5, 5):
        new_year = year + delta
        if new_year > 0:
            if len(year_text) == 2:
                new_year_text = str(
                    new_year
                    % 100
                ).zfill(2)
            else:
                new_year_text = str(
                    new_year
                )

            values.append(
                f"{day}{sep}{month}{sep}{new_year_text}"
            )

    return values


_NUMBER_RE = re.compile(
    r"^\s*"
    r"(?P<number>[+-]?\d+(?:[.,]\d+)?)"
    r"(?P<suffix>\s*.*)"
    r"$"
)


def _format_decimal_like(
    value: Decimal,
    original: str,
) -> str:
    decimal_places = 0

    if "." in original:
        decimal_places = len(
            original.split(
                ".",
                1,
            )[1]
        )
    elif "," in original:
        decimal_places = len(
            original.split(
                ",",
                1,
            )[1]
        )

    if decimal_places <= 0:
        return str(
            int(
                value.to_integral_value()
            )
        )

    quantizer = Decimal(
        "1."
        + (
            "0"
            * decimal_places
        )
    )

    text = format(
        value.quantize(
            quantizer
        ),
        "f",
    )

    if "," in original:
        text = text.replace(
            ".",
            ",",
        )

    return text


def _number_variants(
    answer: str,
) -> list[str]:
    match = _NUMBER_RE.match(
        answer
    )

    if match is None:
        return []

    original_number = (
        match.group(
            "number"
        )
    )
    suffix = (
        match.group(
            "suffix"
        )
        or ""
    )

    try:
        value = Decimal(
            original_number.replace(
                ",",
                ".",
            )
        )
    except InvalidOperation:
        return []

    magnitude = abs(
        value
    )

    if magnitude == 0:
        steps = (
            Decimal("1"),
            Decimal("2"),
            Decimal("5"),
        )
    elif magnitude < 10:
        steps = (
            Decimal("1"),
            Decimal("2"),
            Decimal("0.5"),
        )
    elif magnitude < 100:
        steps = (
            Decimal("5"),
            Decimal("10"),
            Decimal("20"),
        )
    elif magnitude < 1000:
        steps = (
            Decimal("10"),
            Decimal("50"),
            Decimal("100"),
        )
    else:
        power = Decimal(
            str(
                10
                ** max(
                    1,
                    int(
                        math.log10(
                            float(
                                magnitude
                            )
                        )
                    )
                    - 1,
                )
            )
        )

        steps = (
            power,
            power * 2,
            power * 5,
        )

    output = []

    for step in steps:
        for sign in (
            Decimal("-1"),
            Decimal("1"),
        ):
            candidate = (
                value
                + (
                    step
                    * sign
                )
            )

            if (
                value >= 0
                and candidate < 0
            ):
                continue

            formatted = _format_decimal_like(
                candidate,
                original_number,
            )

            output.append(
                f"{formatted}{suffix}"
            )

    return output


def _formula_variants(
    answer: str,
) -> list[str]:
    match = re.fullmatch(
        r"\s*"
        r"(?P<lhs>[A-Za-zΑ-Ωα-ω][A-Za-z0-9_Α-Ωα-ω]{0,12})"
        r"\s*=\s*"
        r"(?P<rhs>.+?)"
        r"\s*",
        answer,
    )

    if match is None:
        return []

    lhs = match.group(
        "lhs"
    )
    rhs = match.group(
        "rhs"
    ).strip()

    output: list[str] = []

    operator_pairs = [
        ("/", "*"),
        ("*", "/"),
        ("+", "-"),
        ("-", "+"),
    ]

    for old, new in operator_pairs:
        if old in rhs:
            output.append(
                f"{lhs} = "
                + rhs.replace(
                    old,
                    new,
                    1,
                )
            )

    binary = re.fullmatch(
        r"\s*(?P<a>[A-Za-z0-9_Α-Ωα-ωπΠ().√]+)"
        r"\s*(?P<op>[/*+\-])\s*"
        r"(?P<b>[A-Za-z0-9_Α-Ωα-ωπΠ().√]+)\s*",
        rhs,
    )

    if binary is not None:
        a = binary.group(
            "a"
        )
        op = binary.group(
            "op"
        )
        b = binary.group(
            "b"
        )

        if a != b:
            output.append(
                f"{lhs} = {b}{op}{a}"
            )

        output.extend(
            [
                f"{lhs} = {a}+{b}",
                f"{lhs} = {a}-{b}",
                f"{lhs} = {a}*{b}",
                f"{lhs} = {a}/{b}",
            ]
        )

    return output


def _structured_variants(
    blueprint: QuestionBlueprint,
) -> list[str]:
    family = _family(
        blueprint.distractor_family
    )

    answer = (
        blueprint.correct_answer
    )

    if family == "DATE":
        return [
            *_year_variants(
                answer
            ),
            *_slash_date_variants(
                answer
            ),
        ]

    if family == "NUMBER":
        return _number_variants(
            answer
        )

    if family == "FORMULA":
        return _formula_variants(
            answer
        )

    return []


def build_distractors(
    target: QuestionBlueprint,
    *,
    candidate_pool: list[QuestionBlueprint],
    forbidden_norms: set[str] | None = None,
) -> tuple[
    tuple[str, str, str] | None,
    tuple[DistractorChoice, ...],
]:
    """
    SSA-QV5-DX-V0.3

    Distractor source priority:
    1. same semantic family + same section;
    2. same semantic family + same document;
    3. same semantic family + other selected documents;
    4. safe deterministic transform for DATE/NUMBER/FORMULA.

    A distractor is never accepted if it equals the target answer or a
    forbidden answer from the currently selected quiz.
    """
    forbidden = {
        _norm(
            value
        )
        for value in (
            forbidden_norms
            or set()
        )
        if _norm(
            value
        )
    }

    target_norm = _norm(
        target.correct_answer
    )
    forbidden.add(
        target_norm
    )

    choices: list[
        DistractorChoice
    ] = []
    seen = set(
        forbidden
    )

    compatible = [
        candidate
        for candidate in candidate_pool
        if (
            candidate.id
            != target.id
            and candidate.knowledge_id
            != target.knowledge_id
            and _family(
                candidate.distractor_family
            )
            == _family(
                target.distractor_family
            )
        )
    ]

    compatible.sort(
        key=lambda item: (
            _candidate_rank(
                target,
                item,
            )
        )
    )

    for candidate in compatible:
        text = str(
            candidate.correct_answer
            or ""
        ).strip()

        key = _norm(
            text
        )

        if (
            not key
            or key in seen
        ):
            continue

        if option_quality_issue(
            text,
            family=target.distractor_family,
        ) is not None:
            continue

        seen.add(
            key
        )

        choices.append(
            DistractorChoice(
                text=text,
                origin="source_blueprint",
                source_blueprint_id=(
                    candidate.id
                ),
                rank=_candidate_rank(
                    target,
                    candidate,
                ),
            )
        )

        if len(choices) >= 3:
            break

    if len(choices) < 3:
        # Avoid generating a structured value that is already a known
        # correct answer anywhere in the available candidate universe.
        known_corrects = {
            _norm(
                item.correct_answer
            )
            for item in candidate_pool
            if _norm(
                item.correct_answer
            )
        }

        for text in _structured_variants(
            target
        ):
            key = _norm(
                text
            )

            if (
                not key
                or key in seen
                or key in known_corrects
            ):
                continue

            if option_quality_issue(
                text,
                family=target.distractor_family,
            ) is not None:
                continue

            seen.add(
                key
            )

            choices.append(
                DistractorChoice(
                    text=text,
                    origin="structured_transform",
                    source_blueprint_id=None,
                    rank=(
                        3,
                        len(
                            choices
                        ),
                        text,
                    ),
                )
            )

            if len(choices) >= 3:
                break

    if len(choices) < 3:
        return (
            None,
            tuple(
                choices
            ),
        )

    return (
        (
            choices[0].text,
            choices[1].text,
            choices[2].text,
        ),
        tuple(
            choices[:3]
        ),
    )


def _build_selected(
    selected: list[QuestionBlueprint],
    *,
    candidate_pool: list[QuestionBlueprint],
) -> tuple[
    list[PlannedQuestion],
    list[str],
    int,
]:
    reserved = {
        _norm(
            item.correct_answer
        )
        for item in selected
        if _norm(
            item.correct_answer
        )
    }

    planned: list[
        PlannedQuestion
    ] = []
    failed: list[str] = []
    structured_count = 0

    for blueprint in selected:
        forbidden = set(
            reserved
        )

        # The target's own correct answer is already rejected by
        # build_distractors; remove it here so the set represents
        # "other selected correct answers".
        forbidden.discard(
            _norm(
                blueprint.correct_answer
            )
        )

        distractors, choices = build_distractors(
            blueprint,
            candidate_pool=candidate_pool,
            forbidden_norms=forbidden,
        )

        if distractors is None:
            failed.append(
                blueprint.id
            )
            continue

        question = PlannedQuestion(
            blueprint=blueprint,
            distractors=distractors,
            validation_score=0.0,
            metadata={
                "distractor_origins": tuple(
                    choice.origin
                    for choice in choices
                ),
                "source_blueprint_ids": tuple(
                    choice.source_blueprint_id
                    for choice in choices
                ),
                "distractor_engine": (
                    SSA_QV5_DISTRACTOR_VERSION
                ),
            },
        )

        validation = validate_planned_question(
            question,
            forbidden_answer_norms=forbidden,
        )

        if not validation.valid:
            failed.append(
                blueprint.id
            )
            continue

        structured_count += sum(
            1
            for choice in choices
            if choice.origin
            == "structured_transform"
        )

        planned.append(
            PlannedQuestion(
                blueprint=question.blueprint,
                distractors=question.distractors,
                validation_score=(
                    validation.score
                ),
                metadata={
                    **question.metadata,
                    "validator_issues": (
                        validation.issues
                    ),
                },
            )
        )

    return (
        planned,
        failed,
        structured_count,
    )


def build_validated_quiz_plan(
    blueprints: list[QuestionBlueprint],
    *,
    target: int,
    max_per_section: int | None = None,
) -> tuple[
    list[PlannedQuestion],
    PlanBuildDiagnostics,
]:
    """
    Select -> build distractors -> validate -> replace failed blueprints.

    One weak blueprint cannot kill the whole quiz. Failed blueprints are
    removed deterministically and the selector is run again over the
    remaining oversampled pool.
    """
    requested = max(
        0,
        int(
            target
        ),
    )

    if requested == 0:
        return (
            [],
            PlanBuildDiagnostics(
                requested=0,
                selected=0,
                exact=True,
                iterations=0,
                rejected_blueprint_ids=(),
                structured_fallback_count=0,
            ),
        )

    available = list(
        blueprints
    )

    rejected: list[str] = []
    iterations = 0
    best: list[
        PlannedQuestion
    ] = []
    best_structured = 0

    while available:
        iterations += 1

        selected, selection_diag = (
            select_diverse_blueprints(
                available,
                target=requested,
                max_per_section=(
                    max_per_section
                ),
            )
        )

        if not selected:
            break

        planned, failed, structured = (
            _build_selected(
                selected,
                candidate_pool=available,
            )
        )

        if (
            len(planned)
            > len(best)
        ):
            best = planned
            best_structured = (
                structured
            )

        if (
            len(planned)
            == requested
        ):
            return (
                planned,
                PlanBuildDiagnostics(
                    requested=requested,
                    selected=len(
                        planned
                    ),
                    exact=True,
                    iterations=iterations,
                    rejected_blueprint_ids=tuple(
                        rejected
                    ),
                    structured_fallback_count=structured,
                ),
            )

        if not failed:
            # Selector could only produce a partial set.
            break

        failed_set = set(
            failed
        )

        rejected.extend(
            item_id
            for item_id in failed
            if item_id not in rejected
        )

        next_available = [
            item
            for item in available
            if item.id
            not in failed_set
        ]

        if (
            len(next_available)
            == len(available)
        ):
            break

        available = (
            next_available
        )

    return (
        best,
        PlanBuildDiagnostics(
            requested=requested,
            selected=len(
                best
            ),
            exact=(
                len(best)
                == requested
            ),
            iterations=iterations,
            rejected_blueprint_ids=tuple(
                rejected
            ),
            structured_fallback_count=(
                best_structured
            ),
        ),
    )
