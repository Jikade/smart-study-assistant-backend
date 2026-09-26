from __future__ import annotations

from app.services.quiz_v5 import (
    BlueprintType,
    EvidenceRef,
    QuestionBlueprint,
    SSA_QV5_SELECTOR_VERSION,
    select_diverse_blueprints,
)


def bp(
    ident: str,
    *,
    kind: BlueprintType,
    knowledge: str,
    answer: str,
    score: float,
    section: int,
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=ident,
        blueprint_type=kind,
        knowledge_id=knowledge,
        stem=f"Question {ident}?",
        correct_answer=answer,
        distractor_family=kind.value,
        section_id=section,
        quality_score=score,
        evidence=EvidenceRef(
            document_id=1,
            chunk_id=100 + section,
            section_id=section,
            text=f"Evidence {ident}",
        ),
    )


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    print()
    print("=" * 96)
    print("QUIZ V5 FOUNDATION V0.1 REGRESSION")
    print("=" * 96)

    candidates = [
        bp("date-1", kind=BlueprintType.EVENT_DATE, knowledge="k1",
           answer="1945", score=99, section=1),
        bp("date-2", kind=BlueprintType.EVENT_DATE, knowledge="k2",
           answer="1954", score=98, section=1),
        bp("date-3", kind=BlueprintType.EVENT_DATE, knowledge="k3",
           answer="1975", score=97, section=1),
        bp("definition-1", kind=BlueprintType.TERM_FROM_DEFINITION,
           knowledge="k4", answer="Phân công lao động xã hội",
           score=90, section=2),
        bp("function-1", kind=BlueprintType.CONCEPT_FUNCTION,
           knowledge="k5", answer="Thước đo giá trị",
           score=89, section=2),
        bp("cause-1", kind=BlueprintType.CAUSE_EFFECT,
           knowledge="k6", answer="Nguyên nhân A",
           score=88, section=3),
        bp("dup-answer", kind=BlueprintType.PROPERTY_RECALL,
           knowledge="k7", answer="1945",
           score=96, section=4),
        bp("dup-knowledge", kind=BlueprintType.PROPERTY_RECALL,
           knowledge="k4", answer="Khái niệm phụ",
           score=95, section=4),
    ]

    selected, diag = select_diverse_blueprints(
        candidates,
        target=5,
    )

    must(
        "Selector version exposed",
        SSA_QV5_SELECTOR_VERSION == "SSA-QV5-SEL-V0.1",
    )
    must(
        "Exact target selected",
        len(selected) == 5 and diag.exact,
    )
    must(
        "Correct answers are globally unique",
        len({item.correct_answer.casefold() for item in selected})
        == len(selected),
    )
    must(
        "Knowledge objects are globally unique",
        len({item.knowledge_id for item in selected})
        == len(selected),
    )
    must(
        "Selection spans multiple blueprint types",
        diag.distinct_blueprint_types >= 3,
    )
    must(
        "Selection spans multiple sections",
        diag.distinct_sections >= 2,
    )
    must(
        "Default family cap prevents one-family monopoly",
        max(
            sum(
                1
                for item in selected
                if item.blueprint_type == family
            )
            for family in BlueprintType
        ) <= 3,
    )

    partial, partial_diag = select_diverse_blueprints(
        candidates[:2],
        target=5,
    )
    must(
        "Impossible target returns safe partial set",
        len(partial) == 2 and not partial_diag.exact,
    )

    selected_again, _ = select_diverse_blueprints(
        list(reversed(candidates)),
        target=5,
    )
    must(
        "Selection is deterministic independent of input order",
        [item.id for item in selected]
        == [item.id for item in selected_again],
    )

    print("-" * 96)
    print("RESULT: PASS")
    print("=" * 96)


if __name__ == "__main__":
    main()
