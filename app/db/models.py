from __future__ import annotations

from sqlalchemy import (BigInteger, Boolean, CHAR, Computed, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, Time, text)
from sqlalchemy.dialects.postgresql import INET, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    """ORM mapping for the existing PostgreSQL schema.

    The authoritative schema remains database/schema.sql because it also contains
    triggers, partial indexes, pgvector setup, and views.
    """
    pass


class Role(Base):
    __tablename__ = "roles"
    id = mapped_column(SmallInteger, primary_key=True)
    code = mapped_column(String(30), nullable=False, unique=True)
    name = mapped_column(String(100), nullable=False)
    description = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class User(Base):
    __tablename__ = "users"
    id = mapped_column(BigInteger, primary_key=True)
    email = mapped_column(String(320), nullable=False)
    password_hash = mapped_column(Text, nullable=False)
    full_name = mapped_column(String(150), nullable=False)
    avatar_url = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    timezone = mapped_column(String(64), nullable=False, server_default=text("'Asia/Ho_Chi_Minh'"))
    locale = mapped_column(String(20), nullable=False, server_default=text("'vi-VN'"))
    last_login_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = mapped_column(SmallInteger, ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)
    assigned_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = mapped_column(Text, nullable=False, unique=True)
    user_agent = mapped_column(Text, nullable=True)
    ip_address = mapped_column(INET, nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = mapped_column(Text, nullable=False, unique=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    used_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme = mapped_column(String(20), nullable=False, server_default=text("'SYSTEM'"))
    default_language = mapped_column(String(20), nullable=False, server_default=text("'vi-VN'"))
    tts_enabled = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    tts_rate = mapped_column(Numeric(4, 2), nullable=False, server_default=text('1.00'))
    study_reminder_time = mapped_column(Time, nullable=True)
    email_notifications = mapped_column(Boolean, nullable=False, server_default=text('TRUE'))
    push_notifications = mapped_column(Boolean, nullable=False, server_default=text('TRUE'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class Subject(Base):
    __tablename__ = "subjects"
    id = mapped_column(BigInteger, primary_key=True)
    owner_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = mapped_column(String(150), nullable=False)
    description = mapped_column(Text, nullable=True)
    color_hex = mapped_column(String(7), nullable=True)
    is_archived = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class SubjectMember(Base):
    __tablename__ = "subject_members"
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    member_role = mapped_column(String(20), nullable=False, server_default=text("'VIEWER'"))
    joined_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class Document(Base):
    __tablename__ = "documents"
    id = mapped_column(BigInteger, primary_key=True)
    owner_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    original_name = mapped_column(String(500), nullable=False)
    stored_name = mapped_column(String(500), nullable=True)
    storage_url = mapped_column(Text, nullable=True)
    mime_type = mapped_column(String(150), nullable=True)
    file_extension = mapped_column(String(20), nullable=True)
    file_size_bytes = mapped_column(BigInteger, nullable=True)
    checksum_sha256 = mapped_column(String(64), nullable=True)
    language_code = mapped_column(String(20), nullable=True, server_default=text("'vi'"))
    page_count = mapped_column(Integer, nullable=True)
    status = mapped_column(String(30), nullable=False, server_default=text("'UPLOADED'"))
    visibility = mapped_column(String(20), nullable=False, server_default=text("'PRIVATE'"))
    processing_error = mapped_column(Text, nullable=True)
    processed_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    id = mapped_column(BigInteger, primary_key=True)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    stage = mapped_column(String(30), nullable=False)
    status = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    progress_pct = mapped_column(Numeric(5, 2), nullable=False, server_default=text('0'))
    error_message = mapped_column(Text, nullable=True)
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class DocumentSection(Base):
    __tablename__ = "document_sections"
    id = mapped_column(BigInteger, primary_key=True)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    parent_section_id = mapped_column(BigInteger, ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=True)
    title = mapped_column(String(500), nullable=True)
    section_level = mapped_column(SmallInteger, nullable=False, server_default=text('1'))
    section_order = mapped_column(Integer, nullable=False, server_default=text('0'))
    page_start = mapped_column(Integer, nullable=True)
    page_end = mapped_column(Integer, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = mapped_column(BigInteger, primary_key=True)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    section_id = mapped_column(BigInteger, ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True)
    chunk_index = mapped_column(Integer, nullable=False)
    chunk_set_id = mapped_column(
        String(80),
        nullable=False,
        server_default=text("'legacy-v1'"),
    )
    chunking_algorithm = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'legacy-v1'"),
    )
    is_active = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    superseded_at = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    content = mapped_column(Text, nullable=False)
    token_count = mapped_column(Integer, nullable=True)
    char_count = mapped_column(Integer, nullable=True)
    page_start = mapped_column(Integer, nullable=True)
    page_end = mapped_column(Integer, nullable=True)
    content_hash = mapped_column(String(64), nullable=True)
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    search_vector = mapped_column(TSVECTOR, Computed("to_tsvector('simple'::regconfig, COALESCE(content, ''))", persisted=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    id = mapped_column(BigInteger, primary_key=True)
    chunk_id = mapped_column(BigInteger, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    embedding_model = mapped_column(String(150), nullable=False)
    embedding_dimension = mapped_column(Integer, nullable=False)
    embedding_json = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class Conversation(Base):
    __tablename__ = "conversations"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    title = mapped_column(String(300), nullable=True)
    is_archived = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class ConversationDocument(Base):
    __tablename__ = "conversation_documents"
    conversation_id = mapped_column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    added_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class Message(Base):
    __tablename__ = "messages"
    id = mapped_column(BigInteger, primary_key=True)
    conversation_id = mapped_column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    parent_message_id = mapped_column(BigInteger, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    role = mapped_column(String(20), nullable=False)
    content = mapped_column(Text, nullable=False)
    input_mode = mapped_column(String(20), nullable=False, server_default=text("'TEXT'"))
    audio_url = mapped_column(Text, nullable=True)
    model_name = mapped_column(String(150), nullable=True)
    prompt_tokens = mapped_column(Integer, nullable=True)
    completion_tokens = mapped_column(Integer, nullable=True)
    latency_ms = mapped_column(Integer, nullable=True)
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class MessageCitation(Base):
    __tablename__ = "message_citations"
    id = mapped_column(BigInteger, primary_key=True)
    message_id = mapped_column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    chunk_id = mapped_column(BigInteger, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    rank_order = mapped_column(Integer, nullable=True)
    similarity_score = mapped_column(Numeric(8, 6), nullable=True)
    excerpt = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class RagEvaluation(Base):
    __tablename__ = "rag_evaluations"
    id = mapped_column(BigInteger, primary_key=True)
    message_id = mapped_column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    faithfulness = mapped_column(Numeric(6, 5), nullable=True)
    answer_relevancy = mapped_column(Numeric(6, 5), nullable=True)
    context_precision = mapped_column(Numeric(6, 5), nullable=True)
    context_recall = mapped_column(Numeric(6, 5), nullable=True)
    evaluator_model = mapped_column(String(150), nullable=True)
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    evaluated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class Quiz(Base):
    __tablename__ = "quizzes"
    id = mapped_column(BigInteger, primary_key=True)
    owner_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    source_quiz_id = mapped_column(BigInteger, ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True)
    title = mapped_column(String(300), nullable=False)
    description = mapped_column(Text, nullable=True)
    generation_mode = mapped_column(String(20), nullable=False, server_default=text("'AI'"))
    difficulty = mapped_column(String(20), nullable=False, server_default=text("'MEDIUM'"))
    duration_minutes = mapped_column(Integer, nullable=True)
    question_count = mapped_column(Integer, nullable=False, server_default=text('0'))
    status = mapped_column(String(20), nullable=False, server_default=text("'DRAFT'"))
    visibility = mapped_column(String(20), nullable=False, server_default=text("'PRIVATE'"))
    ai_model_name = mapped_column(String(150), nullable=True)
    generation_prompt = mapped_column(Text, nullable=True)
    published_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class QuizDocument(Base):
    __tablename__ = "quiz_documents"
    quiz_id = mapped_column(BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), primary_key=True)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)


class Question(Base):
    __tablename__ = "questions"
    id = mapped_column(BigInteger, primary_key=True)
    quiz_id = mapped_column(BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id = mapped_column(BigInteger, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    question_order = mapped_column(Integer, nullable=False)
    question_text = mapped_column(Text, nullable=False)
    difficulty = mapped_column(String(20), nullable=False, server_default=text("'MEDIUM'"))
    explanation = mapped_column(Text, nullable=True)
    points = mapped_column(Numeric(8, 2), nullable=False, server_default=text('1.00'))
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class QuestionOption(Base):
    __tablename__ = "question_options"
    id = mapped_column(BigInteger, primary_key=True)
    question_id = mapped_column(BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    option_key = mapped_column(CHAR(1), nullable=False)
    option_text = mapped_column(Text, nullable=False)
    is_correct = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    explanation = mapped_column(Text, nullable=True)
    position = mapped_column(SmallInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id = mapped_column(BigInteger, primary_key=True)
    quiz_id = mapped_column(BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = mapped_column(String(20), nullable=False, server_default=text("'IN_PROGRESS'"))
    started_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    submitted_at = mapped_column(DateTime(timezone=True), nullable=True)
    time_spent_seconds = mapped_column(Integer, nullable=True)
    score = mapped_column(Numeric(10, 2), nullable=False, server_default=text('0'))
    max_score = mapped_column(Numeric(10, 2), nullable=False, server_default=text('0'))
    correct_count = mapped_column(Integer, nullable=False, server_default=text('0'))
    wrong_count = mapped_column(Integer, nullable=False, server_default=text('0'))
    unanswered_count = mapped_column(Integer, nullable=False, server_default=text('0'))
    percentage = mapped_column(Numeric(6, 2), nullable=True)
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class UserAnswer(Base):
    __tablename__ = "user_answers"
    id = mapped_column(BigInteger, primary_key=True)
    attempt_id = mapped_column(BigInteger, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = mapped_column(BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_option_id = mapped_column(BigInteger, nullable=True)
    is_correct = mapped_column(Boolean, nullable=True)
    points_awarded = mapped_column(Numeric(8, 2), nullable=False, server_default=text('0'))
    answered_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class FlashcardDeck(Base):
    __tablename__ = "flashcard_decks"
    id = mapped_column(BigInteger, primary_key=True)
    owner_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    source_deck_id = mapped_column(BigInteger, ForeignKey("flashcard_decks.id", ondelete="SET NULL"), nullable=True)
    title = mapped_column(String(300), nullable=False)
    description = mapped_column(Text, nullable=True)
    generation_mode = mapped_column(String(20), nullable=False, server_default=text("'AI'"))
    visibility = mapped_column(String(20), nullable=False, server_default=text("'PRIVATE'"))
    status = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    published_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class FlashcardDeckDocument(Base):
    __tablename__ = "flashcard_deck_documents"
    deck_id = mapped_column(BigInteger, ForeignKey("flashcard_decks.id", ondelete="CASCADE"), primary_key=True)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)


class Flashcard(Base):
    __tablename__ = "flashcards"
    id = mapped_column(BigInteger, primary_key=True)
    deck_id = mapped_column(BigInteger, ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id = mapped_column(BigInteger, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    front_text = mapped_column(Text, nullable=False)
    back_text = mapped_column(Text, nullable=False)
    hint = mapped_column(Text, nullable=True)
    card_order = mapped_column(Integer, nullable=False, server_default=text('1'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class FlashcardProgress(Base):
    __tablename__ = "flashcard_progress"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    flashcard_id = mapped_column(BigInteger, ForeignKey("flashcards.id", ondelete="CASCADE"), primary_key=True)
    repetitions = mapped_column(Integer, nullable=False, server_default=text('0'))
    interval_days = mapped_column(Integer, nullable=False, server_default=text('0'))
    ease_factor = mapped_column(Numeric(5, 2), nullable=False, server_default=text('2.50'))
    lapse_count = mapped_column(Integer, nullable=False, server_default=text('0'))
    last_rating = mapped_column(SmallInteger, nullable=True)
    last_reviewed_at = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class FlashcardReview(Base):
    __tablename__ = "flashcard_reviews"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    flashcard_id = mapped_column(BigInteger, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    rating = mapped_column(SmallInteger, nullable=False)
    response_time_ms = mapped_column(Integer, nullable=True)
    previous_interval = mapped_column(Integer, nullable=True)
    next_interval = mapped_column(Integer, nullable=True)
    previous_ease = mapped_column(Numeric(5, 2), nullable=True)
    next_ease = mapped_column(Numeric(5, 2), nullable=True)
    reviewed_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class StudyPlan(Base):
    __tablename__ = "study_plans"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    title = mapped_column(String(300), nullable=False)
    start_date = mapped_column(Date, nullable=False)
    exam_date = mapped_column(Date, nullable=True)
    daily_minutes = mapped_column(Integer, nullable=False, server_default=text('60'))
    status = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    generated_by_ai = mapped_column(Boolean, nullable=False, server_default=text('TRUE'))
    generation_notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class StudyTask(Base):
    __tablename__ = "study_tasks"
    id = mapped_column(BigInteger, primary_key=True)
    plan_id = mapped_column(BigInteger, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False)
    document_id = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    section_id = mapped_column(BigInteger, ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True)
    quiz_id = mapped_column(BigInteger, ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True)
    flashcard_deck_id = mapped_column(BigInteger, ForeignKey("flashcard_decks.id", ondelete="SET NULL"), nullable=True)
    task_date = mapped_column(Date, nullable=False)
    task_type = mapped_column(String(30), nullable=False)
    title = mapped_column(String(300), nullable=False)
    description = mapped_column(Text, nullable=True)
    estimated_minutes = mapped_column(Integer, nullable=False, server_default=text('30'))
    sort_order = mapped_column(Integer, nullable=False, server_default=text('0'))
    status = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class UserSubjectProgress(Base):
    __tablename__ = "user_subject_progress"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    total_study_seconds = mapped_column(BigInteger, nullable=False, server_default=text('0'))
    quizzes_completed = mapped_column(Integer, nullable=False, server_default=text('0'))
    average_score = mapped_column(Numeric(6, 2), nullable=True)
    accuracy_rate = mapped_column(Numeric(6, 2), nullable=True)
    mastery_score = mapped_column(Numeric(6, 2), nullable=True)
    last_activity_at = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class DailyLearningStat(Base):
    __tablename__ = "daily_learning_stats"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    activity_date = mapped_column(Date, primary_key=True)
    study_seconds = mapped_column(Integer, nullable=False, server_default=text('0'))
    quiz_attempts = mapped_column(Integer, nullable=False, server_default=text('0'))
    questions_answered = mapped_column(Integer, nullable=False, server_default=text('0'))
    correct_answers = mapped_column(Integer, nullable=False, server_default=text('0'))
    flashcards_reviewed = mapped_column(Integer, nullable=False, server_default=text('0'))
    xp_earned = mapped_column(Integer, nullable=False, server_default=text('0'))


class TopicMastery(Base):
    __tablename__ = "topic_mastery"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subject_id = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    section_id = mapped_column(BigInteger, ForeignKey("document_sections.id", ondelete="CASCADE"), primary_key=True)
    attempts = mapped_column(Integer, nullable=False, server_default=text('0'))
    correct_answers = mapped_column(Integer, nullable=False, server_default=text('0'))
    wrong_answers = mapped_column(Integer, nullable=False, server_default=text('0'))
    mastery_score = mapped_column(Numeric(6, 2), nullable=False, server_default=text('0'))
    last_practiced_at = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class UserGamification(Base):
    __tablename__ = "user_gamification"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    xp_total = mapped_column(BigInteger, nullable=False, server_default=text('0'))
    level_no = mapped_column(Integer, nullable=False, server_default=text('1'))
    current_streak = mapped_column(Integer, nullable=False, server_default=text('0'))
    longest_streak = mapped_column(Integer, nullable=False, server_default=text('0'))
    last_study_date = mapped_column(Date, nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class Badge(Base):
    __tablename__ = "badges"
    id = mapped_column(BigInteger, primary_key=True)
    code = mapped_column(String(60), nullable=False, unique=True)
    name = mapped_column(String(150), nullable=False)
    description = mapped_column(Text, nullable=True)
    icon_url = mapped_column(Text, nullable=True)
    criteria = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    xp_reward = mapped_column(Integer, nullable=False, server_default=text('0'))
    is_active = mapped_column(Boolean, nullable=False, server_default=text('TRUE'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class UserBadge(Base):
    __tablename__ = "user_badges"
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    badge_id = mapped_column(BigInteger, ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True)
    earned_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class XpTransaction(Base):
    __tablename__ = "xp_transactions"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = mapped_column(Integer, nullable=False)
    source_type = mapped_column(String(40), nullable=False)
    source_id = mapped_column(BigInteger, nullable=True)
    description = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class CommunityPost(Base):
    __tablename__ = "community_posts"
    id = mapped_column(BigInteger, primary_key=True)
    owner_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_id = mapped_column(BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=True)
    flashcard_deck_id = mapped_column(BigInteger, ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=True)
    title = mapped_column(String(300), nullable=True)
    description = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), nullable=False, server_default=text("'PUBLISHED'"))
    published_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class CommunityReaction(Base):
    __tablename__ = "community_reactions"
    post_id = mapped_column(BigInteger, ForeignKey("community_posts.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reaction_type = mapped_column(String(20), nullable=False, server_default=text("'LIKE'"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class CommunitySave(Base):
    __tablename__ = "community_saves"
    post_id = mapped_column(BigInteger, ForeignKey("community_posts.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    saved_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class CommunityReport(Base):
    __tablename__ = "community_reports"
    id = mapped_column(BigInteger, primary_key=True)
    post_id = mapped_column(BigInteger, ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False)
    reporter_user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason_code = mapped_column(String(50), nullable=False)
    description = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), nullable=False, server_default=text("'OPEN'"))
    reviewed_by = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class ExportJob(Base):
    __tablename__ = "export_jobs"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resource_type = mapped_column(String(30), nullable=False)
    resource_id = mapped_column(BigInteger, nullable=False)
    file_format = mapped_column(String(10), nullable=False)
    status = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    file_url = mapped_column(Text, nullable=True)
    error_message = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = mapped_column(String(50), nullable=False)
    title = mapped_column(String(300), nullable=False)
    message = mapped_column(Text, nullable=True)
    payload = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_read = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    read_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = mapped_column(String(100), nullable=False)
    entity_type = mapped_column(String(100), nullable=True)
    entity_id = mapped_column(BigInteger, nullable=True)
    ip_address = mapped_column(INET, nullable=True)
    user_agent = mapped_column(Text, nullable=True)
    metadata_ = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
