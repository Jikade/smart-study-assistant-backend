from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class OptionCreate(BaseModel):
    option_key: str = Field(pattern="^[ABCD]$")
    option_text: str = Field(min_length=1)
    is_correct: bool = False
    explanation: str | None = None
    position: int = Field(ge=1, le=4)


class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD)$")
    explanation: str | None = None
    points: Decimal = Field(default=Decimal("1.00"), gt=0)
    source_chunk_id: int | None = None
    options: list[OptionCreate]

    @model_validator(mode="after")
    def validate_options(self):
        if len(self.options) != 4:
            raise ValueError("Each question must contain exactly 4 options")
        if sum(1 for option in self.options if option.is_correct) != 1:
            raise ValueError("Each question must contain exactly one correct option")
        if {o.option_key for o in self.options} != {"A", "B", "C", "D"}:
            raise ValueError("Options must use keys A, B, C and D")
        return self


class QuizCreate(BaseModel):
    subject_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD|MIXED)$")
    duration_minutes: int | None = Field(default=None, gt=0)
    visibility: str = Field(default="PRIVATE", pattern="^(PRIVATE|UNLISTED|PUBLIC)$")
    document_ids: list[int] = []
    questions: list[QuestionCreate] = []


class QuizGenerateRequest(BaseModel):
    subject_id: int | None = None
    document_ids: list[int] = []
    title: str = Field(min_length=1, max_length=300)
    question_count: int = Field(default=10, ge=1, le=50)
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD|MIXED)$")
    duration_minutes: int | None = Field(default=None, gt=0)



class QuizV5PreviewRequest(BaseModel):
    subject_id: int | None = None
    document_ids: list[int] = Field(
        default_factory=list,
        min_length=1,
        max_length=20,
    )
    question_count: int = Field(
        default=5,
        ge=1,
        le=50,
    )
    subject_family: str = Field(
        default="general",
        pattern=(
            "^(general|history|economics|biology|"
            "physics|geography)$"
        ),
    )
    max_per_section: int | None = Field(
        default=2,
        ge=1,
        le=50,
    )


class QuizV5PreviewQuestion(BaseModel):
    order: int
    blueprint_id: str
    blueprint_type: str
    knowledge_id: str
    stem: str
    correct_answer: str
    distractors: list[str]
    source_document_id: int
    source_chunk_id: int
    source_section_id: int | None = None
    evidence: str
    quality_score: float
    validation_score: float
    distractor_origins: list[str]


class QuizV5PreviewOut(BaseModel):
    engine_version: str
    subject_family: str
    requested: int
    generated: int
    exact: bool
    source_chars: int
    knowledge_count: int
    blueprint_count: int
    replacement_iterations: int
    structured_fallback_count: int
    rejected_blueprint_ids: list[str]
    questions: list[QuizV5PreviewQuestion]


class OptionOut(ORMModel):
    id: int
    question_id: int
    option_key: str
    option_text: str
    is_correct: bool
    explanation: str | None = None
    position: int


class QuestionOut(ORMModel):
    id: int
    quiz_id: int
    source_chunk_id: int | None = None
    question_order: int
    question_text: str
    difficulty: str
    explanation: str | None = None
    points: Decimal
    options: list[OptionOut] = []


class QuizOut(ORMModel):
    id: int
    owner_id: int
    subject_id: int | None = None
    source_quiz_id: int | None = None
    title: str
    description: str | None = None
    generation_mode: str
    difficulty: str
    duration_minutes: int | None = None
    question_count: int
    status: str
    visibility: str
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AnswerSubmit(BaseModel):
    question_id: int
    selected_option_id: int | None = None


class AttemptSubmit(BaseModel):
    answers: list[AnswerSubmit]


class AttemptOut(ORMModel):
    id: int
    quiz_id: int
    user_id: int
    status: str
    score: Decimal
    max_score: Decimal
    correct_count: int
    wrong_count: int
    unanswered_count: int
    percentage: Decimal | None = None
    started_at: datetime
    submitted_at: datetime | None = None
