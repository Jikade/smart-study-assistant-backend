from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.services.quiz_v5.models import BlueprintType, QuestionBlueprint


SSA_QV5_SELECTOR_VERSION = "SSA-QV5-SEL-V0.1"
SSA_QV5_SELECTOR_HARDENING_VERSION = "SSA-QV5-SEL-V0.5"
SSA_QV5_SELECTOR_ADAPTIVE_VERSION = "SSA-QV5-SEL-V0.6"
SSA_QV5_SELECTOR_SECTION_VERSION = "SSA-QV5-SEL-V0.8"


@dataclass(frozen=True)
class SelectionDiagnostics:
    requested: int
    available: int
    selected: int
    exact: bool
    distinct_blueprint_types: int
    distinct_sections: int
    total_quality: float
    explored_nodes: int
    effective_max_per_section: int | None = None


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _candidate_key(item: QuestionBlueprint) -> tuple:
    return (
        -float(item.quality_score),
        str(item.blueprint_type.value),
        int(item.section_id or -1),
        str(item.id),
    )


def _objective(selected: list[QuestionBlueprint]) -> tuple:
    blueprint_types = {item.blueprint_type for item in selected}
    sections = {
        int(item.section_id)
        for item in selected
        if item.section_id is not None
    }
    total_quality = round(
        sum(float(item.quality_score) for item in selected),
        8,
    )
    return (
        len(selected),
        len(blueprint_types),
        len(sections),
        total_quality,
    )


def _adaptive_section_cap(
    ordered: list[QuestionBlueprint],
    *,
    target: int,
    requested_cap: int | None,
) -> int | None:
    """
    Treat section diversity as a soft cap.

    Raise the cap only when the current candidate pool cannot mathematically
    fill the requested target under the requested cap. Unsectioned candidates
    are uncapped, so they contribute directly to capacity.
    """
    if requested_cap is None:
        return None

    cap = max(
        1,
        int(requested_cap),
    )

    section_counts: dict[int, int] = {}
    uncapped_count = 0

    for item in ordered:
        if item.section_id is None:
            uncapped_count += 1
            continue

        sid = int(
            item.section_id
        )

        section_counts[sid] = (
            section_counts.get(
                sid,
                0,
            )
            + 1
        )

    def capacity(
        value: int,
    ) -> int:
        return (
            uncapped_count
            + sum(
                min(
                    count,
                    value,
                )
                for count
                in section_counts.values()
            )
        )

    while (
        cap < target
        and capacity(cap) < target
    ):
        cap += 1

    return cap


def select_diverse_blueprints(
    candidates: list[QuestionBlueprint],
    *,
    target: int,
    max_per_blueprint_type: int | None = None,
    max_per_section: int | None = None,
) -> tuple[list[QuestionBlueprint], SelectionDiagnostics]:
    target = max(0, int(target))

    by_id: dict[str, QuestionBlueprint] = {}
    for item in sorted(candidates, key=_candidate_key):
        by_id.setdefault(str(item.id), item)
    ordered = list(by_id.values())

    effective_max_per_section = _adaptive_section_cap(
        ordered,
        target=target,
        requested_cap=max_per_section,
    )

    if target == 0:
        return [], SelectionDiagnostics(
            requested=0,
            available=len(ordered),
            selected=0,
            exact=True,
            distinct_blueprint_types=0,
            distinct_sections=0,
            total_quality=0.0,
            explored_nodes=1,
            effective_max_per_section=(
                effective_max_per_section
            ),
        )

    if max_per_blueprint_type is None:
        available_types = {
            item.blueprint_type
            for item in ordered
        }

        if len(available_types) <= 1:
            max_per_blueprint_type = target
        else:
            max_per_blueprint_type = max(
                1,
                (target + 1) // 2,
            )

    best: list[QuestionBlueprint] = []
    best_objective = _objective(best)
    explored_nodes = 0

    current: list[QuestionBlueprint] = []
    used_knowledge: set[str] = set()
    used_answers: set[str] = set()
    used_stems: set[str] = set()
    type_counts: dict[BlueprintType, int] = {}
    section_counts: dict[int, int] = {}

    def allowed(item: QuestionBlueprint) -> bool:
        if item.knowledge_id in used_knowledge:
            return False

        answer_key = _norm(item.correct_answer)
        if not answer_key or answer_key in used_answers:
            return False

        stem_key = _norm(item.stem)
        if not stem_key or stem_key in used_stems:
            return False

        if (
            max_per_blueprint_type is not None
            and type_counts.get(item.blueprint_type, 0)
            >= max_per_blueprint_type
        ):
            return False

        if (
            effective_max_per_section is not None
            and item.section_id is not None
            and section_counts.get(int(item.section_id), 0)
            >= effective_max_per_section
        ):
            return False

        return True

    def push(item: QuestionBlueprint) -> None:
        current.append(item)
        used_knowledge.add(item.knowledge_id)
        used_answers.add(_norm(item.correct_answer))
        used_stems.add(_norm(item.stem))
        type_counts[item.blueprint_type] = (
            type_counts.get(item.blueprint_type, 0) + 1
        )
        if item.section_id is not None:
            sid = int(item.section_id)
            section_counts[sid] = section_counts.get(sid, 0) + 1

    def pop(item: QuestionBlueprint) -> None:
        current.pop()
        used_knowledge.remove(item.knowledge_id)
        used_answers.remove(_norm(item.correct_answer))
        used_stems.remove(_norm(item.stem))

        type_counts[item.blueprint_type] -= 1
        if type_counts[item.blueprint_type] == 0:
            del type_counts[item.blueprint_type]

        if item.section_id is not None:
            sid = int(item.section_id)
            section_counts[sid] -= 1
            if section_counts[sid] == 0:
                del section_counts[sid]

    def visit(index: int) -> None:
        nonlocal best, best_objective, explored_nodes
        explored_nodes += 1

        objective = _objective(current)
        if objective > best_objective:
            best = list(current)
            best_objective = objective

        if len(current) >= target or index >= len(ordered):
            return

        remaining = len(ordered) - index
        if len(current) + remaining < len(best):
            return

        item = ordered[index]

        if allowed(item):
            push(item)
            visit(index + 1)
            pop(item)

        visit(index + 1)

    visit(0)

    selected = sorted(best, key=_candidate_key)

    diagnostics = SelectionDiagnostics(
        requested=target,
        available=len(ordered),
        selected=len(selected),
        exact=len(selected) == target,
        distinct_blueprint_types=len(
            {item.blueprint_type for item in selected}
        ),
        distinct_sections=len(
            {
                int(item.section_id)
                for item in selected
                if item.section_id is not None
            }
        ),
        total_quality=round(
            sum(float(item.quality_score) for item in selected),
            4,
        ),
        explored_nodes=explored_nodes,
        effective_max_per_section=(
            effective_max_per_section
        ),
    )

    return selected, diagnostics
