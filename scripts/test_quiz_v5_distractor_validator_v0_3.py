from __future__ import annotations

from app.services.quiz_v5 import (
    BlueprintType,
    EvidenceRef,
    PlannedQuestion,
    QuestionBlueprint,
    SSA_QV5_DISTRACTOR_VERSION,
    SSA_QV5_VALIDATOR_VERSION,
    build_distractors,
    build_validated_quiz_plan,
    validate_planned_question,
)


def bp(
    ident: str,
    *,
    kind: BlueprintType,
    answer: str,
    family: str,
    section: int,
    document: int,
    score: float = 90.0,
    knowledge: str | None = None,
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=ident,
        blueprint_type=kind,
        knowledge_id=(
            knowledge
            or f"k-{ident}"
        ),
        stem=f"Câu hỏi chuẩn cho {ident}?",
        correct_answer=answer,
        distractor_family=family,
        section_id=section,
        quality_score=score,
        evidence=EvidenceRef(
            document_id=document,
            chunk_id=(
                1000
                + len(ident)
                + section
            ),
            section_id=section,
            text=(
                f"Evidence supporting {ident} "
                f"with answer {answer}."
            ),
        ),
    )


def must(
    label: str,
    condition: bool,
) -> None:
    if not condition:
        raise AssertionError(
            label
        )
    print(
        f"[PASS] {label}"
    )


def main() -> None:
    print()
    print("=" * 108)
    print(
        "QUIZ V5 DISTRACTOR ENGINE + "
        "FINAL VALIDATOR V0.3 REGRESSION"
    )
    print("=" * 108)

    pool = [
        # DATE family: target + source alternatives.
        bp(
            "date-target",
            kind=BlueprintType.EVENT_DATE,
            answer="938",
            family="DATE",
            section=1,
            document=1,
            score=99,
        ),
        bp(
            "date-extra-1",
            kind=BlueprintType.EVENT_DATE,
            answer="1945",
            family="DATE",
            section=1,
            document=1,
            score=88,
        ),
        bp(
            "date-extra-2",
            kind=BlueprintType.EVENT_DATE,
            answer="1954",
            family="DATE",
            section=2,
            document=1,
            score=87,
        ),
        bp(
            "date-extra-3",
            kind=BlueprintType.EVENT_DATE,
            answer="1975",
            family="DATE",
            section=3,
            document=2,
            score=86,
        ),
        # TERM family: one intentionally sparse high-quality target.
        # It cannot build three distractors and must be replaceable.
        bp(
            "term-sparse",
            kind=BlueprintType.TERM_FROM_DEFINITION,
            answer="Phân công lao động xã hội",
            family="TERM",
            section=4,
            document=3,
            score=100,
        ),
        # FUNCTION family with four alternatives.
        bp(
            "func-target",
            kind=BlueprintType.CONCEPT_FUNCTION,
            answer="Đo lường và biểu hiện giá trị hàng hóa",
            family="FUNCTION",
            section=5,
            document=3,
            score=98,
        ),
        bp(
            "func-extra-1",
            kind=BlueprintType.CONCEPT_FUNCTION,
            answer="Làm môi giới trong trao đổi hàng hóa",
            family="FUNCTION",
            section=5,
            document=3,
            score=80,
        ),
        bp(
            "func-extra-2",
            kind=BlueprintType.CONCEPT_FUNCTION,
            answer="Thực hiện nghĩa vụ thanh toán",
            family="FUNCTION",
            section=6,
            document=3,
            score=79,
        ),
        bp(
            "func-extra-3",
            kind=BlueprintType.CONCEPT_FUNCTION,
            answer="Cất trữ giá trị",
            family="FUNCTION",
            section=7,
            document=3,
            score=78,
        ),
        # NUMBER family uses structured fallback if source pool is sparse.
        bp(
            "number-target",
            kind=BlueprintType.PROPERTY_RECALL,
            answer="3143 m",
            family="NUMBER",
            section=8,
            document=4,
            score=97,
        ),
        # FORMULA family also supports structured fallback.
        bp(
            "formula-target",
            kind=BlueprintType.FORMULA_APPLICATION,
            answer="P = A/t",
            family="FORMULA",
            section=9,
            document=5,
            score=96,
        ),
        # EFFECT family with enough source alternatives.
        bp(
            "effect-target",
            kind=BlueprintType.CAUSE_EFFECT,
            answer="Gió",
            family="EFFECT",
            section=10,
            document=4,
            score=95,
        ),
        bp(
            "effect-extra-1",
            kind=BlueprintType.CAUSE_EFFECT,
            answer="Mưa lớn",
            family="EFFECT",
            section=10,
            document=4,
            score=77,
        ),
        bp(
            "effect-extra-2",
            kind=BlueprintType.CAUSE_EFFECT,
            answer="Xói mòn đất",
            family="EFFECT",
            section=11,
            document=4,
            score=76,
        ),
        bp(
            "effect-extra-3",
            kind=BlueprintType.CAUSE_EFFECT,
            answer="Nhiệt độ giảm",
            family="EFFECT",
            section=12,
            document=4,
            score=75,
        ),
    ]

    must(
        "Distractor version exposed",
        SSA_QV5_DISTRACTOR_VERSION
        == "SSA-QV5-DX-V0.3",
    )

    must(
        "Validator version exposed",
        SSA_QV5_VALIDATOR_VERSION
        == "SSA-QV5-VAL-V0.3",
    )

    date_target = next(
        item
        for item in pool
        if item.id
        == "date-target"
    )

    distractors, choices = (
        build_distractors(
            date_target,
            candidate_pool=pool,
        )
    )

    must(
        "DATE distractors are built",
        distractors is not None
        and len(distractors) == 3,
    )

    must(
        "Same-section DATE is ranked first",
        choices[0].text == "1945",
    )

    must(
        "Source DATE alternatives are preferred before transforms",
        all(
            choice.origin
            == "source_blueprint"
            for choice in choices
        ),
    )

    number_target = next(
        item
        for item in pool
        if item.id
        == "number-target"
    )

    number_distractors, number_choices = (
        build_distractors(
            number_target,
            candidate_pool=pool,
        )
    )

    must(
        "NUMBER structured fallback creates three options",
        number_distractors is not None
        and len(number_distractors) == 3,
    )

    must(
        "NUMBER transforms preserve unit",
        all(
            value.endswith(" m")
            for value in number_distractors
        ),
    )

    formula_target = next(
        item
        for item in pool
        if item.id
        == "formula-target"
    )

    formula_distractors, formula_choices = (
        build_distractors(
            formula_target,
            candidate_pool=pool,
        )
    )

    must(
        "FORMULA structured fallback creates three options",
        formula_distractors is not None
        and len(formula_distractors) == 3,
    )

    must(
        "Structured fallback is explicitly tagged",
        any(
            choice.origin
            == "structured_transform"
            for choice in (
                *number_choices,
                *formula_choices,
            )
        ),
    )

    sparse_term = next(
        item
        for item in pool
        if item.id
        == "term-sparse"
    )

    sparse_distractors, _ = (
        build_distractors(
            sparse_term,
            candidate_pool=pool,
        )
    )

    must(
        "Unsupported sparse TERM is skipped instead of invented",
        sparse_distractors is None,
    )

    # Direct validator negative checks.
    invalid = PlannedQuestion(
        blueprint=date_target,
        distractors=(
            "938",
            "1945",
            "1954",
        ),
        validation_score=0.0,
    )

    invalid_result = (
        validate_planned_question(
            invalid
        )
    )

    must(
        "Validator rejects duplicated correct answer",
        not invalid_result.valid
        and "duplicate_options"
        in invalid_result.issues,
    )

    # Full replacement flow: sparse top-scoring TERM must not kill plan.
    planned, diag = (
        build_validated_quiz_plan(
            pool,
            target=5,
            max_per_section=2,
        )
    )

    must(
        "Weak blueprint does not kill whole quiz",
        len(planned) == 5
        and diag.exact,
    )

    must(
        "Sparse TERM was rejected and replaced",
        "term-sparse"
        in diag.rejected_blueprint_ids,
    )

    selected_corrects = {
        item.blueprint.correct_answer.casefold()
        for item in planned
    }

    must(
        "No distractor equals another selected correct answer",
        all(
            distractor.casefold()
            not in (
                selected_corrects
                - {
                    question.blueprint.correct_answer.casefold()
                }
            )
            for question in planned
            for distractor in question.distractors
        ),
    )

    must(
        "Every final question passes validator",
        all(
            validate_planned_question(
                question,
                forbidden_answer_norms=(
                    selected_corrects
                    - {
                        question.blueprint.correct_answer.casefold()
                    }
                ),
            ).valid
            for question in planned
        ),
    )

    must(
        "Every final question has exactly four unique options",
        all(
            len(
                {
                    question.blueprint.correct_answer.casefold(),
                    *(
                        value.casefold()
                        for value
                        in question.distractors
                    ),
                }
            )
            == 4
            for question in planned
        ),
    )

    # Determinism independent of input order.
    planned_again, diag_again = (
        build_validated_quiz_plan(
            list(
                reversed(
                    pool
                )
            ),
            target=5,
            max_per_section=2,
        )
    )

    must(
        "Plan build is deterministic independent of input order",
        [
            (
                item.blueprint.id,
                item.distractors,
            )
            for item in planned
        ]
        == [
            (
                item.blueprint.id,
                item.distractors,
            )
            for item in planned_again
        ],
    )

    # Impossible target returns best safe partial instead of raising.
    partial, partial_diag = (
        build_validated_quiz_plan(
            [
                sparse_term,
                number_target,
            ],
            target=5,
        )
    )

    must(
        "Impossible quiz returns safe partial plan",
        len(partial) <= 1
        and not partial_diag.exact,
    )

    print()
    print(
        f"Final questions             : {len(planned)}"
    )
    print(
        f"Replacement iterations      : {diag.iterations}"
    )
    print(
        f"Rejected blueprints         : "
        f"{list(diag.rejected_blueprint_ids)}"
    )
    print(
        f"Structured distractors used : "
        f"{diag.structured_fallback_count}"
    )

    print("-" * 108)
    print("RESULT: PASS")
    print("=" * 108)


if __name__ == "__main__":
    main()
