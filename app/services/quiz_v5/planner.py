from __future__ import annotations

import hashlib
import re

from app.services.quiz_v5.models import (
    BlueprintType,
    KnowledgeKind,
    KnowledgeObject,
    QuestionBlueprint,
)


SSA_QV5_PLANNER_VERSION = "SSA-QV5-BP-V0.2"


_RELATION_LABELS_VI = {
    "diện_tích": "diện tích",
    "dân_số": "dân số",
    "độ_cao": "độ cao",
    "chiều_dài": "chiều dài",
    "khối_lượng": "khối lượng",
    "nhiệt_độ": "nhiệt độ",
    "vận_tốc": "vận tốc",
    "tốc_độ": "tốc độ",
    "thể_tích": "thể tích",
    "bán_kính": "bán kính",
    "area": "diện tích",
    "population": "dân số",
    "height": "độ cao",
    "length": "chiều dài",
    "mass": "khối lượng",
    "temperature": "nhiệt độ",
    "speed": "tốc độ",
    "volume": "thể tích",
    "radius": "bán kính",
}


def _stable_blueprint_id(
    knowledge_id: str,
    blueprint_type: BlueprintType,
) -> str:
    payload = (
        f"{knowledge_id}|"
        f"{blueprint_type.value}"
    )

    digest = hashlib.sha1(
        payload.encode("utf-8")
    ).hexdigest()[:16]

    return f"bp-{digest}"


def _clean_inline(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip(
        " \t\r\n.;:"
    )


def blueprint_quality_score(
    knowledge: KnowledgeObject,
    blueprint_type: BlueprintType,
) -> float:
    fit = {
        BlueprintType.EVENT_DATE:
            1.00,
        BlueprintType.FORMULA_APPLICATION:
            0.99,
        BlueprintType.CONCEPT_FUNCTION:
            0.97,
        BlueprintType.TERM_FROM_DEFINITION:
            0.97,
        BlueprintType.DEFINITION_FROM_TERM:
            0.94,
        BlueprintType.CAUSE_EFFECT:
            0.95,
        BlueprintType.PROPERTY_RECALL:
            0.96,
    }.get(
        blueprint_type,
        0.80,
    )

    score = (
        float(
            knowledge.confidence
        )
        * fit
        * 100.0
    )

    answer_len = len(
        _clean_inline(
            knowledge.object
        )
    )

    if answer_len > 220:
        score -= 10.0
    elif answer_len > 140:
        score -= 4.0

    subject_len = len(
        _clean_inline(
            knowledge.subject
        )
    )

    if subject_len > 140:
        score -= 6.0

    return round(
        max(
            0.0,
            min(
                100.0,
                score,
            ),
        ),
        2,
    )


def _make(
    knowledge: KnowledgeObject,
    *,
    blueprint_type: BlueprintType,
    stem: str,
    correct_answer: str,
    distractor_family: str,
    tags: tuple[str, ...],
) -> QuestionBlueprint | None:
    stem = _clean_inline(
        stem
    )

    correct_answer = _clean_inline(
        correct_answer
    )

    if (
        len(stem) < 8
        or not correct_answer
    ):
        return None

    return QuestionBlueprint(
        id=_stable_blueprint_id(
            knowledge.id,
            blueprint_type,
        ),
        blueprint_type=blueprint_type,
        knowledge_id=knowledge.id,
        stem=stem,
        correct_answer=correct_answer,
        distractor_family=distractor_family,
        section_id=knowledge.evidence.section_id,
        quality_score=blueprint_quality_score(
            knowledge,
            blueprint_type,
        ),
        evidence=knowledge.evidence,
        tags=(
            "deterministic_blueprint",
            *tags,
        ),
    )


def blueprints_for_knowledge(
    knowledge: KnowledgeObject,
) -> list[QuestionBlueprint]:
    output: list[
        QuestionBlueprint
    ] = []

    subject = _clean_inline(
        knowledge.subject
    )

    obj = _clean_inline(
        knowledge.object
    )

    if (
        knowledge.relation
        == "occurred_in"
        and knowledge.kind
        == KnowledgeKind.DATE
    ):
        item = _make(
            knowledge,
            blueprint_type=(
                BlueprintType.EVENT_DATE
            ),
            stem=(
                f"Sự kiện “{subject}” diễn ra "
                "vào thời gian nào?"
            ),
            correct_answer=obj,
            distractor_family="DATE",
            tags=("event_date",),
        )

        if item:
            output.append(
                item
            )

    elif (
        knowledge.relation
        == "defined_as"
        and knowledge.kind
        == KnowledgeKind.DEFINITION
    ):
        term = _make(
            knowledge,
            blueprint_type=(
                BlueprintType.TERM_FROM_DEFINITION
            ),
            stem=(
                "Khái niệm nào phù hợp với "
                f"mô tả sau: {obj}?"
            ),
            correct_answer=subject,
            distractor_family="TERM",
            tags=("definition_term",),
        )

        if term:
            output.append(
                term
            )

        if len(obj) <= 180:
            definition = _make(
                knowledge,
                blueprint_type=(
                    BlueprintType.DEFINITION_FROM_TERM
                ),
                stem=(
                    f"“{subject}” được hiểu là gì?"
                ),
                correct_answer=obj,
                distractor_family="DEFINITION",
                tags=("term_definition",),
            )

            if definition:
                output.append(
                    definition
                )

    elif (
        knowledge.relation
        == "used_for"
        and knowledge.kind
        == KnowledgeKind.FUNCTION
    ):
        item = _make(
            knowledge,
            blueprint_type=(
                BlueprintType.CONCEPT_FUNCTION
            ),
            stem=(
                "Theo tài liệu, chức năng hoặc "
                f"vai trò của “{subject}” là gì?"
            ),
            correct_answer=obj,
            distractor_family="FUNCTION",
            tags=("concept_function",),
        )

        if item:
            output.append(
                item
            )

    elif (
        knowledge.relation
        == "causes"
        and knowledge.kind
        == KnowledgeKind.CAUSE
    ):
        item = _make(
            knowledge,
            blueprint_type=(
                BlueprintType.CAUSE_EFFECT
            ),
            stem=(
                f"Theo tài liệu, “{subject}” "
                "dẫn đến kết quả nào?"
            ),
            correct_answer=obj,
            distractor_family="EFFECT",
            tags=("cause_effect",),
        )

        if item:
            output.append(
                item
            )

    elif (
        knowledge.relation
        == "formula"
        and knowledge.kind
        == KnowledgeKind.FORMULA
    ):
        item = _make(
            knowledge,
            blueprint_type=(
                BlueprintType.FORMULA_APPLICATION
            ),
            stem=(
                f"Biểu thức nào mô tả đại lượng "
                f"“{subject}” theo tài liệu?"
            ),
            correct_answer=obj,
            distractor_family="FORMULA",
            tags=("formula_recall",),
        )

        if item:
            output.append(
                item
            )

    elif (
        knowledge.kind
        == KnowledgeKind.PROPERTY
    ):
        label = (
            _RELATION_LABELS_VI.get(
                knowledge.relation,
                knowledge.relation.replace(
                    "_",
                    " ",
                ),
            )
        )

        item = _make(
            knowledge,
            blueprint_type=(
                BlueprintType.PROPERTY_RECALL
            ),
            stem=(
                f"Theo tài liệu, {label} của "
                f"“{subject}” là bao nhiêu?"
            ),
            correct_answer=obj,
            distractor_family="NUMBER",
            tags=("numeric_property",),
        )

        if item:
            output.append(
                item
            )

    return output


def plan_blueprints(
    knowledge_objects: list[KnowledgeObject],
) -> list[QuestionBlueprint]:
    output: list[
        QuestionBlueprint
    ] = []

    for knowledge in knowledge_objects:
        output.extend(
            blueprints_for_knowledge(
                knowledge
            )
        )

    by_id: dict[
        str,
        QuestionBlueprint,
    ] = {}

    for item in sorted(
        output,
        key=lambda value: (
            -float(
                value.quality_score
            ),
            value.blueprint_type.value,
            value.id,
        ),
    ):
        by_id.setdefault(
            item.id,
            item,
        )

    return list(
        by_id.values()
    )
