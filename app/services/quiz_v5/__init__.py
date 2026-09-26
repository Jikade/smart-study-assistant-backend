from app.services.quiz_v5.models import (
    BlueprintType,
    EvidenceRef,
    KnowledgeKind,
    KnowledgeObject,
    PlannedQuestion,
    QuestionBlueprint,
)
from app.services.quiz_v5.selector import (
    SSA_QV5_SELECTOR_VERSION,
    SSA_QV5_SELECTOR_ADAPTIVE_VERSION,
    SelectionDiagnostics,
    select_diverse_blueprints,
)
from app.services.quiz_v5.extractor import (
    SSA_QV5_EXTRACTOR_VERSION,
    SSA_QV5_EXTRACTOR_BOUNDARY_VERSION,
    ChunkInput,
    extract_knowledge_objects,
)
from app.services.quiz_v5.planner import (
    SSA_QV5_PLANNER_VERSION,
    blueprint_quality_score,
    blueprints_for_knowledge,
    plan_blueprints,
)

__all__ = [
    "BlueprintType",
    "EvidenceRef",
    "KnowledgeKind",
    "KnowledgeObject",
    "PlannedQuestion",
    "QuestionBlueprint",
    "SSA_QV5_SELECTOR_VERSION",
    "SSA_QV5_SELECTOR_ADAPTIVE_VERSION",
    "SelectionDiagnostics",
    "select_diverse_blueprints",
    "SSA_QV5_EXTRACTOR_VERSION",
    "SSA_QV5_EXTRACTOR_BOUNDARY_VERSION",
    "ChunkInput",
    "extract_knowledge_objects",
    "SSA_QV5_PLANNER_VERSION",
    "blueprint_quality_score",
    "blueprints_for_knowledge",
    "plan_blueprints",
]

from app.services.quiz_v5.distractors import (
    SSA_QV5_DISTRACTOR_VERSION,
    SSA_QV5_DISTRACTOR_BOUNDARY_VERSION,
    DistractorChoice,
    PlanBuildDiagnostics,
    build_distractors,
    build_validated_quiz_plan,
)
from app.services.quiz_v5.validators import (
    SSA_QV5_VALIDATOR_VERSION,
    SSA_QV5_VALIDATOR_BOUNDARY_VERSION,
    ValidationResult,
    validate_planned_question,
)

__all__ += [
    "SSA_QV5_DISTRACTOR_VERSION",
    "SSA_QV5_DISTRACTOR_BOUNDARY_VERSION",
    "DistractorChoice",
    "PlanBuildDiagnostics",
    "build_distractors",
    "build_validated_quiz_plan",
    "SSA_QV5_VALIDATOR_VERSION",
    "SSA_QV5_VALIDATOR_BOUNDARY_VERSION",
    "ValidationResult",
    "validate_planned_question",
]

from app.services.quiz_v5.shadow import (
    SSA_QV5_SHADOW_VERSION,
    ReadyDocumentSummary,
    ShadowQuestionReport,
    ShadowReport,
    list_ready_documents,
    load_document_chunks,
    report_as_dict,
    shadow_documents,
    shadow_from_chunks,
)

__all__ += [
    "SSA_QV5_SHADOW_VERSION",
    "ReadyDocumentSummary",
    "ShadowQuestionReport",
    "ShadowReport",
    "list_ready_documents",
    "load_document_chunks",
    "report_as_dict",
    "shadow_documents",
    "shadow_from_chunks",
]
