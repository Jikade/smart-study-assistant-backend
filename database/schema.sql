--
-- PostgreSQL database dump
--

\restrict bUX7q1RdSbHHuPnU2Jm83h596ygpvBmIvJrqaTg1H0dRJL7aoWu2g3G2QnP7WrE

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: validate_quiz_before_publish(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.validate_quiz_before_publish() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_question_count INTEGER;
    v_invalid_count  INTEGER;
BEGIN
    IF NEW.status = 'PUBLISHED'
       AND OLD.status IS DISTINCT FROM 'PUBLISHED' THEN

        SELECT COUNT(*)
        INTO v_question_count
        FROM public.questions q
        WHERE q.quiz_id = NEW.id;

        IF v_question_count = 0 THEN
            RAISE EXCEPTION 'Cannot publish quiz %: quiz has no questions.', NEW.id;
        END IF;

        SELECT COUNT(*)
        INTO v_invalid_count
        FROM (
            SELECT q.id
            FROM public.questions q
            LEFT JOIN public.question_options o ON o.question_id = q.id
            WHERE q.quiz_id = NEW.id
            GROUP BY q.id
            HAVING COUNT(o.id) <> 4
                OR COUNT(o.id) FILTER (WHERE o.is_correct = TRUE) <> 1
        ) invalid_questions;

        IF v_invalid_count > 0 THEN
            RAISE EXCEPTION 'Cannot publish quiz %: % question(s) do not have exactly 4 options and 1 correct answer.',
                NEW.id, v_invalid_count;
        END IF;

        NEW.question_count := v_question_count;
        NEW.published_at := COALESCE(NEW.published_at, CURRENT_TIMESTAMP);
    END IF;

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id bigint NOT NULL,
    user_id bigint,
    action character varying(100) NOT NULL,
    entity_type character varying(100),
    entity_id bigint,
    ip_address inet,
    user_agent text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.audit_logs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.audit_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: badges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.badges (
    id bigint NOT NULL,
    code character varying(60) NOT NULL,
    name character varying(150) NOT NULL,
    description text,
    icon_url text,
    criteria jsonb DEFAULT '{}'::jsonb NOT NULL,
    xp_reward integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT badges_xp_reward_check CHECK ((xp_reward >= 0))
);


--
-- Name: badges_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.badges ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.badges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: chunk_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunk_embeddings (
    id bigint NOT NULL,
    chunk_id bigint NOT NULL,
    embedding_model character varying(150) NOT NULL,
    embedding_dimension integer NOT NULL,
    embedding_json jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    embedding public.vector,
    CONSTRAINT chunk_embeddings_embedding_dimension_check CHECK ((embedding_dimension > 0))
);


--
-- Name: chunk_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.chunk_embeddings ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.chunk_embeddings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: community_posts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.community_posts (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    quiz_id bigint,
    flashcard_deck_id bigint,
    title character varying(300),
    description text,
    status character varying(20) DEFAULT 'PUBLISHED'::character varying NOT NULL,
    published_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT community_posts_check CHECK ((((quiz_id IS NOT NULL) AND (flashcard_deck_id IS NULL)) OR ((quiz_id IS NULL) AND (flashcard_deck_id IS NOT NULL)))),
    CONSTRAINT community_posts_status_check CHECK (((status)::text = ANY ((ARRAY['PUBLISHED'::character varying, 'HIDDEN'::character varying, 'REMOVED'::character varying])::text[])))
);


--
-- Name: community_posts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.community_posts ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.community_posts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: community_reactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.community_reactions (
    post_id bigint NOT NULL,
    user_id bigint NOT NULL,
    reaction_type character varying(20) DEFAULT 'LIKE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT community_reactions_reaction_type_check CHECK (((reaction_type)::text = 'LIKE'::text))
);


--
-- Name: community_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.community_reports (
    id bigint NOT NULL,
    post_id bigint NOT NULL,
    reporter_user_id bigint NOT NULL,
    reason_code character varying(50) NOT NULL,
    description text,
    status character varying(20) DEFAULT 'OPEN'::character varying NOT NULL,
    reviewed_by bigint,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT community_reports_status_check CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'REVIEWING'::character varying, 'RESOLVED'::character varying, 'REJECTED'::character varying])::text[])))
);


--
-- Name: community_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.community_reports ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.community_reports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: community_saves; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.community_saves (
    post_id bigint NOT NULL,
    user_id bigint NOT NULL,
    saved_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: conversation_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_documents (
    conversation_id bigint NOT NULL,
    document_id bigint NOT NULL,
    added_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    subject_id bigint,
    title character varying(300),
    is_archived boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.conversations ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.conversations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: daily_learning_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.daily_learning_stats (
    user_id bigint NOT NULL,
    activity_date date NOT NULL,
    study_seconds integer DEFAULT 0 NOT NULL,
    quiz_attempts integer DEFAULT 0 NOT NULL,
    questions_answered integer DEFAULT 0 NOT NULL,
    correct_answers integer DEFAULT 0 NOT NULL,
    flashcards_reviewed integer DEFAULT 0 NOT NULL,
    xp_earned integer DEFAULT 0 NOT NULL,
    CONSTRAINT daily_learning_stats_correct_answers_check CHECK ((correct_answers >= 0)),
    CONSTRAINT daily_learning_stats_flashcards_reviewed_check CHECK ((flashcards_reviewed >= 0)),
    CONSTRAINT daily_learning_stats_questions_answered_check CHECK ((questions_answered >= 0)),
    CONSTRAINT daily_learning_stats_quiz_attempts_check CHECK ((quiz_attempts >= 0)),
    CONSTRAINT daily_learning_stats_study_seconds_check CHECK ((study_seconds >= 0))
);


--
-- Name: document_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_chunks (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    section_id bigint,
    chunk_index integer NOT NULL,
    chunk_set_id character varying(80) DEFAULT 'legacy-v1'::character varying NOT NULL,
    chunking_algorithm character varying(50) DEFAULT 'legacy-v1'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    superseded_at timestamp with time zone,
    content text NOT NULL,
    token_count integer,
    char_count integer,
    page_start integer,
    page_end integer,
    content_hash character varying(64),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, COALESCE(content, ''::text))) STORED,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT document_chunks_char_count_check CHECK (((char_count IS NULL) OR (char_count >= 0))),
    CONSTRAINT document_chunks_check CHECK (((page_start IS NULL) OR (page_end IS NULL) OR (page_end >= page_start))),
    CONSTRAINT document_chunks_chunk_index_check CHECK ((chunk_index >= 0)),
    CONSTRAINT document_chunks_page_end_check CHECK (((page_end IS NULL) OR (page_end >= 1))),
    CONSTRAINT document_chunks_page_start_check CHECK (((page_start IS NULL) OR (page_start >= 1))),
    CONSTRAINT document_chunks_token_count_check CHECK (((token_count IS NULL) OR (token_count >= 0)))
);


--
-- Name: document_chunks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_chunks ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.document_chunks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: document_processing_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_processing_jobs (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    stage character varying(30) NOT NULL,
    status character varying(20) DEFAULT 'PENDING'::character varying NOT NULL,
    progress_pct numeric(5,2) DEFAULT 0 NOT NULL,
    error_message text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT document_processing_jobs_progress_pct_check CHECK (((progress_pct >= (0)::numeric) AND (progress_pct <= (100)::numeric))),
    CONSTRAINT document_processing_jobs_stage_check CHECK (((stage)::text = ANY ((ARRAY['EXTRACT'::character varying, 'CLEAN'::character varying, 'STRUCTURE'::character varying, 'CHUNK'::character varying, 'EMBED'::character varying, 'COMPLETE'::character varying])::text[]))),
    CONSTRAINT document_processing_jobs_status_check CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'RUNNING'::character varying, 'SUCCEEDED'::character varying, 'FAILED'::character varying])::text[])))
);


--
-- Name: document_processing_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_processing_jobs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.document_processing_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: document_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_sections (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    parent_section_id bigint,
    title character varying(500),
    section_level smallint DEFAULT 1 NOT NULL,
    section_order integer DEFAULT 0 NOT NULL,
    page_start integer,
    page_end integer,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT document_sections_check CHECK (((page_start IS NULL) OR (page_end IS NULL) OR (page_end >= page_start))),
    CONSTRAINT document_sections_page_end_check CHECK (((page_end IS NULL) OR (page_end >= 1))),
    CONSTRAINT document_sections_page_start_check CHECK (((page_start IS NULL) OR (page_start >= 1))),
    CONSTRAINT document_sections_section_level_check CHECK ((section_level >= 1))
);


--
-- Name: document_sections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_sections ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.document_sections_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    subject_id bigint,
    original_name character varying(500) NOT NULL,
    stored_name character varying(500),
    storage_url text,
    mime_type character varying(150),
    file_extension character varying(20),
    file_size_bytes bigint,
    checksum_sha256 character varying(64),
    language_code character varying(20) DEFAULT 'vi'::character varying,
    page_count integer,
    status character varying(30) DEFAULT 'UPLOADED'::character varying NOT NULL,
    visibility character varying(20) DEFAULT 'PRIVATE'::character varying NOT NULL,
    processing_error text,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT documents_file_size_bytes_check CHECK (((file_size_bytes IS NULL) OR (file_size_bytes >= 0))),
    CONSTRAINT documents_page_count_check CHECK (((page_count IS NULL) OR (page_count >= 0))),
    CONSTRAINT documents_status_check CHECK (((status)::text = ANY ((ARRAY['UPLOADED'::character varying, 'PROCESSING'::character varying, 'READY'::character varying, 'FAILED'::character varying, 'ARCHIVED'::character varying])::text[]))),
    CONSTRAINT documents_visibility_check CHECK (((visibility)::text = ANY ((ARRAY['PRIVATE'::character varying, 'UNLISTED'::character varying, 'PUBLIC'::character varying])::text[])))
);


--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.documents ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: export_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.export_jobs (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    resource_type character varying(30) NOT NULL,
    resource_id bigint NOT NULL,
    file_format character varying(10) NOT NULL,
    status character varying(20) DEFAULT 'PENDING'::character varying NOT NULL,
    file_url text,
    error_message text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT export_jobs_file_format_check CHECK (((file_format)::text = ANY ((ARRAY['PDF'::character varying, 'DOCX'::character varying])::text[]))),
    CONSTRAINT export_jobs_resource_type_check CHECK (((resource_type)::text = ANY ((ARRAY['QUIZ'::character varying, 'FLASHCARD_DECK'::character varying, 'STUDY_PLAN'::character varying])::text[]))),
    CONSTRAINT export_jobs_status_check CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'PROCESSING'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[])))
);


--
-- Name: export_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.export_jobs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.export_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: flashcard_deck_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flashcard_deck_documents (
    deck_id bigint NOT NULL,
    document_id bigint NOT NULL
);


--
-- Name: flashcard_decks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flashcard_decks (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    subject_id bigint,
    source_deck_id bigint,
    title character varying(300) NOT NULL,
    description text,
    generation_mode character varying(20) DEFAULT 'AI'::character varying NOT NULL,
    visibility character varying(20) DEFAULT 'PRIVATE'::character varying NOT NULL,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    published_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT flashcard_decks_generation_mode_check CHECK (((generation_mode)::text = ANY ((ARRAY['AI'::character varying, 'MANUAL'::character varying, 'IMPORTED'::character varying, 'FORKED'::character varying])::text[]))),
    CONSTRAINT flashcard_decks_status_check CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'ARCHIVED'::character varying])::text[]))),
    CONSTRAINT flashcard_decks_visibility_check CHECK (((visibility)::text = ANY ((ARRAY['PRIVATE'::character varying, 'UNLISTED'::character varying, 'PUBLIC'::character varying])::text[])))
);


--
-- Name: flashcard_decks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.flashcard_decks ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.flashcard_decks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: flashcard_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flashcard_progress (
    user_id bigint NOT NULL,
    flashcard_id bigint NOT NULL,
    repetitions integer DEFAULT 0 NOT NULL,
    interval_days integer DEFAULT 0 NOT NULL,
    ease_factor numeric(5,2) DEFAULT 2.50 NOT NULL,
    lapse_count integer DEFAULT 0 NOT NULL,
    last_rating smallint,
    last_reviewed_at timestamp with time zone,
    next_review_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT flashcard_progress_ease_factor_check CHECK ((ease_factor > (0)::numeric)),
    CONSTRAINT flashcard_progress_interval_days_check CHECK ((interval_days >= 0)),
    CONSTRAINT flashcard_progress_lapse_count_check CHECK ((lapse_count >= 0)),
    CONSTRAINT flashcard_progress_last_rating_check CHECK (((last_rating >= 0) AND (last_rating <= 3))),
    CONSTRAINT flashcard_progress_repetitions_check CHECK ((repetitions >= 0))
);


--
-- Name: flashcard_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flashcard_reviews (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    flashcard_id bigint NOT NULL,
    rating smallint NOT NULL,
    response_time_ms integer,
    previous_interval integer,
    next_interval integer,
    previous_ease numeric(5,2),
    next_ease numeric(5,2),
    reviewed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT flashcard_reviews_next_interval_check CHECK (((next_interval IS NULL) OR (next_interval >= 0))),
    CONSTRAINT flashcard_reviews_previous_interval_check CHECK (((previous_interval IS NULL) OR (previous_interval >= 0))),
    CONSTRAINT flashcard_reviews_rating_check CHECK (((rating >= 0) AND (rating <= 3))),
    CONSTRAINT flashcard_reviews_response_time_ms_check CHECK (((response_time_ms IS NULL) OR (response_time_ms >= 0)))
);


--
-- Name: flashcard_reviews_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.flashcard_reviews ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.flashcard_reviews_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: flashcards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flashcards (
    id bigint NOT NULL,
    deck_id bigint NOT NULL,
    source_chunk_id bigint,
    front_text text NOT NULL,
    back_text text NOT NULL,
    hint text,
    card_order integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT flashcards_card_order_check CHECK ((card_order >= 1))
);


--
-- Name: flashcards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.flashcards ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.flashcards_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: message_citations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_citations (
    id bigint NOT NULL,
    message_id bigint NOT NULL,
    chunk_id bigint NOT NULL,
    rank_order integer,
    similarity_score numeric(8,6),
    excerpt text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT message_citations_rank_order_check CHECK (((rank_order IS NULL) OR (rank_order >= 1)))
);


--
-- Name: message_citations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.message_citations ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.message_citations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id bigint NOT NULL,
    conversation_id bigint NOT NULL,
    parent_message_id bigint,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    input_mode character varying(20) DEFAULT 'TEXT'::character varying NOT NULL,
    audio_url text,
    model_name character varying(150),
    prompt_tokens integer,
    completion_tokens integer,
    latency_ms integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT messages_completion_tokens_check CHECK (((completion_tokens IS NULL) OR (completion_tokens >= 0))),
    CONSTRAINT messages_input_mode_check CHECK (((input_mode)::text = ANY ((ARRAY['TEXT'::character varying, 'VOICE'::character varying])::text[]))),
    CONSTRAINT messages_latency_ms_check CHECK (((latency_ms IS NULL) OR (latency_ms >= 0))),
    CONSTRAINT messages_prompt_tokens_check CHECK (((prompt_tokens IS NULL) OR (prompt_tokens >= 0))),
    CONSTRAINT messages_role_check CHECK (((role)::text = ANY ((ARRAY['SYSTEM'::character varying, 'USER'::character varying, 'ASSISTANT'::character varying])::text[])))
);


--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.messages ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    notification_type character varying(50) NOT NULL,
    title character varying(300) NOT NULL,
    message text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_read boolean DEFAULT false NOT NULL,
    read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.notifications ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.notifications_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.password_reset_tokens ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.password_reset_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: question_options; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.question_options (
    id bigint NOT NULL,
    question_id bigint NOT NULL,
    option_key character(1) NOT NULL,
    option_text text NOT NULL,
    is_correct boolean DEFAULT false NOT NULL,
    explanation text,
    "position" smallint NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT question_options_option_key_check CHECK ((option_key = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar, 'D'::bpchar]))),
    CONSTRAINT question_options_position_check CHECK ((("position" >= 1) AND ("position" <= 4)))
);


--
-- Name: question_options_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.question_options ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.question_options_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.questions (
    id bigint NOT NULL,
    quiz_id bigint NOT NULL,
    source_chunk_id bigint,
    question_order integer NOT NULL,
    question_text text NOT NULL,
    difficulty character varying(20) DEFAULT 'MEDIUM'::character varying NOT NULL,
    explanation text,
    points numeric(8,2) DEFAULT 1.00 NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT questions_difficulty_check CHECK (((difficulty)::text = ANY ((ARRAY['EASY'::character varying, 'MEDIUM'::character varying, 'HARD'::character varying])::text[]))),
    CONSTRAINT questions_points_check CHECK ((points > (0)::numeric)),
    CONSTRAINT questions_question_order_check CHECK ((question_order >= 1))
);


--
-- Name: questions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.questions ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.questions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: quiz_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_attempts (
    id bigint NOT NULL,
    quiz_id bigint NOT NULL,
    user_id bigint NOT NULL,
    status character varying(20) DEFAULT 'IN_PROGRESS'::character varying NOT NULL,
    started_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    submitted_at timestamp with time zone,
    time_spent_seconds integer,
    score numeric(10,2) DEFAULT 0 NOT NULL,
    max_score numeric(10,2) DEFAULT 0 NOT NULL,
    correct_count integer DEFAULT 0 NOT NULL,
    wrong_count integer DEFAULT 0 NOT NULL,
    unanswered_count integer DEFAULT 0 NOT NULL,
    percentage numeric(6,2),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT quiz_attempts_correct_count_check CHECK ((correct_count >= 0)),
    CONSTRAINT quiz_attempts_max_score_check CHECK ((max_score >= (0)::numeric)),
    CONSTRAINT quiz_attempts_percentage_check CHECK (((percentage IS NULL) OR ((percentage >= (0)::numeric) AND (percentage <= (100)::numeric)))),
    CONSTRAINT quiz_attempts_score_check CHECK ((score >= (0)::numeric)),
    CONSTRAINT quiz_attempts_status_check CHECK (((status)::text = ANY ((ARRAY['IN_PROGRESS'::character varying, 'SUBMITTED'::character varying, 'ABANDONED'::character varying])::text[]))),
    CONSTRAINT quiz_attempts_time_spent_seconds_check CHECK (((time_spent_seconds IS NULL) OR (time_spent_seconds >= 0))),
    CONSTRAINT quiz_attempts_unanswered_count_check CHECK ((unanswered_count >= 0)),
    CONSTRAINT quiz_attempts_wrong_count_check CHECK ((wrong_count >= 0))
);


--
-- Name: quiz_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.quiz_attempts ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.quiz_attempts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: quiz_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_documents (
    quiz_id bigint NOT NULL,
    document_id bigint NOT NULL
);


--
-- Name: quizzes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quizzes (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    subject_id bigint,
    source_quiz_id bigint,
    title character varying(300) NOT NULL,
    description text,
    generation_mode character varying(20) DEFAULT 'AI'::character varying NOT NULL,
    difficulty character varying(20) DEFAULT 'MEDIUM'::character varying NOT NULL,
    duration_minutes integer,
    question_count integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'DRAFT'::character varying NOT NULL,
    visibility character varying(20) DEFAULT 'PRIVATE'::character varying NOT NULL,
    ai_model_name character varying(150),
    generation_prompt text,
    published_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT quizzes_difficulty_check CHECK (((difficulty)::text = ANY ((ARRAY['EASY'::character varying, 'MEDIUM'::character varying, 'HARD'::character varying, 'MIXED'::character varying])::text[]))),
    CONSTRAINT quizzes_duration_minutes_check CHECK (((duration_minutes IS NULL) OR (duration_minutes > 0))),
    CONSTRAINT quizzes_generation_mode_check CHECK (((generation_mode)::text = ANY ((ARRAY['AI'::character varying, 'MANUAL'::character varying, 'IMPORTED'::character varying, 'FORKED'::character varying, 'V5_DETERMINISTIC'::character varying])::text[]))),
    CONSTRAINT quizzes_question_count_check CHECK ((question_count >= 0)),
    CONSTRAINT quizzes_status_check CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'PUBLISHED'::character varying, 'ARCHIVED'::character varying])::text[]))),
    CONSTRAINT quizzes_visibility_check CHECK (((visibility)::text = ANY ((ARRAY['PRIVATE'::character varying, 'UNLISTED'::character varying, 'PUBLIC'::character varying])::text[])))
);


--
-- Name: quizzes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.quizzes ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.quizzes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rag_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rag_evaluations (
    id bigint NOT NULL,
    message_id bigint NOT NULL,
    faithfulness numeric(6,5),
    answer_relevancy numeric(6,5),
    context_precision numeric(6,5),
    context_recall numeric(6,5),
    evaluator_model character varying(150),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    evaluated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT rag_evaluations_answer_relevancy_check CHECK (((answer_relevancy IS NULL) OR ((answer_relevancy >= (0)::numeric) AND (answer_relevancy <= (1)::numeric)))),
    CONSTRAINT rag_evaluations_context_precision_check CHECK (((context_precision IS NULL) OR ((context_precision >= (0)::numeric) AND (context_precision <= (1)::numeric)))),
    CONSTRAINT rag_evaluations_context_recall_check CHECK (((context_recall IS NULL) OR ((context_recall >= (0)::numeric) AND (context_recall <= (1)::numeric)))),
    CONSTRAINT rag_evaluations_faithfulness_check CHECK (((faithfulness IS NULL) OR ((faithfulness >= (0)::numeric) AND (faithfulness <= (1)::numeric))))
);


--
-- Name: rag_evaluations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rag_evaluations ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.rag_evaluations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    user_agent text,
    ip_address inet,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.refresh_tokens ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id smallint NOT NULL,
    code character varying(30) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.roles ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.roles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: study_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.study_plans (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    subject_id bigint,
    title character varying(300) NOT NULL,
    start_date date NOT NULL,
    exam_date date,
    daily_minutes integer DEFAULT 60 NOT NULL,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    generated_by_ai boolean DEFAULT true NOT NULL,
    generation_notes text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT study_plans_check CHECK (((exam_date IS NULL) OR (exam_date >= start_date))),
    CONSTRAINT study_plans_daily_minutes_check CHECK ((daily_minutes > 0)),
    CONSTRAINT study_plans_status_check CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'ACTIVE'::character varying, 'COMPLETED'::character varying, 'ARCHIVED'::character varying])::text[])))
);


--
-- Name: study_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.study_plans ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.study_plans_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: study_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.study_tasks (
    id bigint NOT NULL,
    plan_id bigint NOT NULL,
    document_id bigint,
    section_id bigint,
    quiz_id bigint,
    flashcard_deck_id bigint,
    task_date date NOT NULL,
    task_type character varying(30) NOT NULL,
    title character varying(300) NOT NULL,
    description text,
    estimated_minutes integer DEFAULT 30 NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'PENDING'::character varying NOT NULL,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT study_tasks_estimated_minutes_check CHECK ((estimated_minutes > 0)),
    CONSTRAINT study_tasks_status_check CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'IN_PROGRESS'::character varying, 'COMPLETED'::character varying, 'SKIPPED'::character varying])::text[]))),
    CONSTRAINT study_tasks_task_type_check CHECK (((task_type)::text = ANY ((ARRAY['STUDY'::character varying, 'REVIEW'::character varying, 'QUIZ'::character varying, 'FLASHCARD'::character varying])::text[])))
);


--
-- Name: study_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.study_tasks ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.study_tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: subject_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subject_members (
    subject_id bigint NOT NULL,
    user_id bigint NOT NULL,
    member_role character varying(20) DEFAULT 'VIEWER'::character varying NOT NULL,
    joined_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT subject_members_member_role_check CHECK (((member_role)::text = ANY ((ARRAY['OWNER'::character varying, 'EDITOR'::character varying, 'VIEWER'::character varying])::text[])))
);


--
-- Name: subjects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subjects (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    name character varying(150) NOT NULL,
    description text,
    color_hex character varying(7),
    is_archived boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: subjects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.subjects ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.subjects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: topic_mastery; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topic_mastery (
    user_id bigint NOT NULL,
    subject_id bigint NOT NULL,
    section_id bigint NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    correct_answers integer DEFAULT 0 NOT NULL,
    wrong_answers integer DEFAULT 0 NOT NULL,
    mastery_score numeric(6,2) DEFAULT 0 NOT NULL,
    last_practiced_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT topic_mastery_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT topic_mastery_correct_answers_check CHECK ((correct_answers >= 0)),
    CONSTRAINT topic_mastery_mastery_score_check CHECK (((mastery_score >= (0)::numeric) AND (mastery_score <= (100)::numeric))),
    CONSTRAINT topic_mastery_wrong_answers_check CHECK ((wrong_answers >= 0))
);


--
-- Name: user_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_answers (
    id bigint NOT NULL,
    attempt_id bigint NOT NULL,
    question_id bigint NOT NULL,
    selected_option_id bigint,
    is_correct boolean,
    points_awarded numeric(8,2) DEFAULT 0 NOT NULL,
    answered_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT user_answers_points_awarded_check CHECK ((points_awarded >= (0)::numeric))
);


--
-- Name: user_answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.user_answers ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.user_answers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: user_badges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_badges (
    user_id bigint NOT NULL,
    badge_id bigint NOT NULL,
    earned_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: user_gamification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_gamification (
    user_id bigint NOT NULL,
    xp_total bigint DEFAULT 0 NOT NULL,
    level_no integer DEFAULT 1 NOT NULL,
    current_streak integer DEFAULT 0 NOT NULL,
    longest_streak integer DEFAULT 0 NOT NULL,
    last_study_date date,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT user_gamification_current_streak_check CHECK ((current_streak >= 0)),
    CONSTRAINT user_gamification_level_no_check CHECK ((level_no >= 1)),
    CONSTRAINT user_gamification_longest_streak_check CHECK ((longest_streak >= 0)),
    CONSTRAINT user_gamification_xp_total_check CHECK ((xp_total >= 0))
);


--
-- Name: user_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_preferences (
    user_id bigint NOT NULL,
    theme character varying(20) DEFAULT 'SYSTEM'::character varying NOT NULL,
    default_language character varying(20) DEFAULT 'vi-VN'::character varying NOT NULL,
    tts_enabled boolean DEFAULT false NOT NULL,
    tts_rate numeric(4,2) DEFAULT 1.00 NOT NULL,
    study_reminder_time time without time zone,
    email_notifications boolean DEFAULT true NOT NULL,
    push_notifications boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT user_preferences_theme_check CHECK (((theme)::text = ANY ((ARRAY['SYSTEM'::character varying, 'LIGHT'::character varying, 'DARK'::character varying])::text[]))),
    CONSTRAINT user_preferences_tts_rate_check CHECK ((tts_rate > (0)::numeric))
);


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    user_id bigint NOT NULL,
    role_id smallint NOT NULL,
    assigned_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: user_subject_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_subject_progress (
    user_id bigint NOT NULL,
    subject_id bigint NOT NULL,
    total_study_seconds bigint DEFAULT 0 NOT NULL,
    quizzes_completed integer DEFAULT 0 NOT NULL,
    average_score numeric(6,2),
    accuracy_rate numeric(6,2),
    mastery_score numeric(6,2),
    last_activity_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT user_subject_progress_accuracy_rate_check CHECK (((accuracy_rate IS NULL) OR ((accuracy_rate >= (0)::numeric) AND (accuracy_rate <= (100)::numeric)))),
    CONSTRAINT user_subject_progress_average_score_check CHECK (((average_score IS NULL) OR ((average_score >= (0)::numeric) AND (average_score <= (100)::numeric)))),
    CONSTRAINT user_subject_progress_mastery_score_check CHECK (((mastery_score IS NULL) OR ((mastery_score >= (0)::numeric) AND (mastery_score <= (100)::numeric)))),
    CONSTRAINT user_subject_progress_quizzes_completed_check CHECK ((quizzes_completed >= 0)),
    CONSTRAINT user_subject_progress_total_study_seconds_check CHECK ((total_study_seconds >= 0))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    email character varying(320) NOT NULL,
    password_hash text NOT NULL,
    full_name character varying(150) NOT NULL,
    avatar_url text,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    timezone character varying(64) DEFAULT 'Asia/Ho_Chi_Minh'::character varying NOT NULL,
    locale character varying(20) DEFAULT 'vi-VN'::character varying NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT users_status_check CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'INACTIVE'::character varying, 'SUSPENDED'::character varying])::text[])))
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.users ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: vw_due_flashcards; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_due_flashcards AS
 SELECT fp.user_id,
    fp.flashcard_id,
    f.deck_id,
    f.front_text,
    f.back_text,
    fp.repetitions,
    fp.interval_days,
    fp.ease_factor,
    fp.next_review_at
   FROM (public.flashcard_progress fp
     JOIN public.flashcards f ON ((f.id = fp.flashcard_id)))
  WHERE (fp.next_review_at <= CURRENT_TIMESTAMP);


--
-- Name: vw_public_community_resources; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_public_community_resources AS
 SELECT cp.id AS post_id,
    cp.owner_id,
    u.full_name AS owner_name,
    cp.quiz_id,
    cp.flashcard_deck_id,
    cp.title,
    cp.description,
    cp.published_at,
    COALESCE(r.reaction_count, (0)::bigint) AS like_count,
    COALESCE(s.save_count, (0)::bigint) AS save_count
   FROM (((public.community_posts cp
     JOIN public.users u ON ((u.id = cp.owner_id)))
     LEFT JOIN ( SELECT community_reactions.post_id,
            count(*) AS reaction_count
           FROM public.community_reactions
          GROUP BY community_reactions.post_id) r ON ((r.post_id = cp.id)))
     LEFT JOIN ( SELECT community_saves.post_id,
            count(*) AS save_count
           FROM public.community_saves
          GROUP BY community_saves.post_id) s ON ((s.post_id = cp.id)))
  WHERE ((cp.status)::text = 'PUBLISHED'::text);


--
-- Name: vw_quiz_attempt_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_quiz_attempt_summary AS
 SELECT qa.id AS attempt_id,
    qa.user_id,
    qa.quiz_id,
    q.title AS quiz_title,
    qa.status,
    qa.started_at,
    qa.submitted_at,
    qa.score,
    qa.max_score,
    qa.percentage,
    qa.correct_count,
    qa.wrong_count,
    qa.unanswered_count
   FROM (public.quiz_attempts qa
     JOIN public.quizzes q ON ((q.id = qa.quiz_id)));


--
-- Name: vw_user_topic_performance; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_user_topic_performance AS
 SELECT qa.user_id,
    d.subject_id,
    dc.document_id,
    dc.section_id,
    ds.title AS section_title,
    count(ua.id) AS answered_count,
    count(ua.id) FILTER (WHERE (ua.is_correct = true)) AS correct_count,
    count(ua.id) FILTER (WHERE (ua.is_correct = false)) AS wrong_count,
    round(((100.0 * (count(ua.id) FILTER (WHERE (ua.is_correct = true)))::numeric) / (NULLIF(count(ua.id), 0))::numeric), 2) AS accuracy_percent
   FROM (((((public.user_answers ua
     JOIN public.quiz_attempts qa ON ((qa.id = ua.attempt_id)))
     JOIN public.questions qn ON ((qn.id = ua.question_id)))
     JOIN public.document_chunks dc ON ((dc.id = qn.source_chunk_id)))
     JOIN public.documents d ON ((d.id = dc.document_id)))
     LEFT JOIN public.document_sections ds ON ((ds.id = dc.section_id)))
  WHERE ((qa.status)::text = 'SUBMITTED'::text)
  GROUP BY qa.user_id, d.subject_id, dc.document_id, dc.section_id, ds.title;


--
-- Name: xp_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.xp_transactions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    amount integer NOT NULL,
    source_type character varying(40) NOT NULL,
    source_id bigint,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: xp_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.xp_transactions ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.xp_transactions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: badges badges_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.badges
    ADD CONSTRAINT badges_code_key UNIQUE (code);


--
-- Name: badges badges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.badges
    ADD CONSTRAINT badges_pkey PRIMARY KEY (id);


--
-- Name: chunk_embeddings chunk_embeddings_chunk_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_embeddings
    ADD CONSTRAINT chunk_embeddings_chunk_id_key UNIQUE (chunk_id);


--
-- Name: chunk_embeddings chunk_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_embeddings
    ADD CONSTRAINT chunk_embeddings_pkey PRIMARY KEY (id);


--
-- Name: community_posts community_posts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_posts
    ADD CONSTRAINT community_posts_pkey PRIMARY KEY (id);


--
-- Name: community_reactions community_reactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reactions
    ADD CONSTRAINT community_reactions_pkey PRIMARY KEY (post_id, user_id);


--
-- Name: community_reports community_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reports
    ADD CONSTRAINT community_reports_pkey PRIMARY KEY (id);


--
-- Name: community_reports community_reports_post_id_reporter_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reports
    ADD CONSTRAINT community_reports_post_id_reporter_user_id_key UNIQUE (post_id, reporter_user_id);


--
-- Name: community_saves community_saves_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_saves
    ADD CONSTRAINT community_saves_pkey PRIMARY KEY (post_id, user_id);


--
-- Name: conversation_documents conversation_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_documents
    ADD CONSTRAINT conversation_documents_pkey PRIMARY KEY (conversation_id, document_id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: daily_learning_stats daily_learning_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_learning_stats
    ADD CONSTRAINT daily_learning_stats_pkey PRIMARY KEY (user_id, activity_date);


--
-- Name: document_chunks document_chunks_document_id_chunk_index_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT uq_document_chunks_set_index UNIQUE (document_id, chunk_set_id, chunk_index);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: document_processing_jobs document_processing_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_jobs
    ADD CONSTRAINT document_processing_jobs_pkey PRIMARY KEY (id);


--
-- Name: document_sections document_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_sections
    ADD CONSTRAINT document_sections_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: export_jobs export_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.export_jobs
    ADD CONSTRAINT export_jobs_pkey PRIMARY KEY (id);


--
-- Name: flashcard_deck_documents flashcard_deck_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_deck_documents
    ADD CONSTRAINT flashcard_deck_documents_pkey PRIMARY KEY (deck_id, document_id);


--
-- Name: flashcard_decks flashcard_decks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_decks
    ADD CONSTRAINT flashcard_decks_pkey PRIMARY KEY (id);


--
-- Name: flashcard_progress flashcard_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_progress
    ADD CONSTRAINT flashcard_progress_pkey PRIMARY KEY (user_id, flashcard_id);


--
-- Name: flashcard_reviews flashcard_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_reviews
    ADD CONSTRAINT flashcard_reviews_pkey PRIMARY KEY (id);


--
-- Name: flashcards flashcards_deck_id_card_order_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcards
    ADD CONSTRAINT flashcards_deck_id_card_order_key UNIQUE (deck_id, card_order);


--
-- Name: flashcards flashcards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcards
    ADD CONSTRAINT flashcards_pkey PRIMARY KEY (id);


--
-- Name: message_citations message_citations_message_id_chunk_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_citations
    ADD CONSTRAINT message_citations_message_id_chunk_id_key UNIQUE (message_id, chunk_id);


--
-- Name: message_citations message_citations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_citations
    ADD CONSTRAINT message_citations_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: question_options question_options_id_question_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.question_options
    ADD CONSTRAINT question_options_id_question_id_key UNIQUE (id, question_id);


--
-- Name: question_options question_options_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.question_options
    ADD CONSTRAINT question_options_pkey PRIMARY KEY (id);


--
-- Name: question_options question_options_question_id_option_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.question_options
    ADD CONSTRAINT question_options_question_id_option_key_key UNIQUE (question_id, option_key);


--
-- Name: question_options question_options_question_id_position_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.question_options
    ADD CONSTRAINT question_options_question_id_position_key UNIQUE (question_id, "position");


--
-- Name: questions questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_pkey PRIMARY KEY (id);


--
-- Name: questions questions_quiz_id_question_order_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_quiz_id_question_order_key UNIQUE (quiz_id, question_order);


--
-- Name: quiz_attempts quiz_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_pkey PRIMARY KEY (id);


--
-- Name: quiz_documents quiz_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_documents
    ADD CONSTRAINT quiz_documents_pkey PRIMARY KEY (quiz_id, document_id);


--
-- Name: quizzes quizzes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_pkey PRIMARY KEY (id);


--
-- Name: rag_evaluations rag_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_evaluations
    ADD CONSTRAINT rag_evaluations_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: roles roles_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_code_key UNIQUE (code);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: study_plans study_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plans
    ADD CONSTRAINT study_plans_pkey PRIMARY KEY (id);


--
-- Name: study_tasks study_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_tasks
    ADD CONSTRAINT study_tasks_pkey PRIMARY KEY (id);


--
-- Name: subject_members subject_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject_members
    ADD CONSTRAINT subject_members_pkey PRIMARY KEY (subject_id, user_id);


--
-- Name: subjects subjects_owner_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT subjects_owner_id_name_key UNIQUE (owner_id, name);


--
-- Name: subjects subjects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT subjects_pkey PRIMARY KEY (id);


--
-- Name: topic_mastery topic_mastery_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topic_mastery
    ADD CONSTRAINT topic_mastery_pkey PRIMARY KEY (user_id, section_id);


--
-- Name: user_answers user_answers_attempt_id_question_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_answers
    ADD CONSTRAINT user_answers_attempt_id_question_id_key UNIQUE (attempt_id, question_id);


--
-- Name: user_answers user_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_answers
    ADD CONSTRAINT user_answers_pkey PRIMARY KEY (id);


--
-- Name: user_badges user_badges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_badges
    ADD CONSTRAINT user_badges_pkey PRIMARY KEY (user_id, badge_id);


--
-- Name: user_gamification user_gamification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gamification
    ADD CONSTRAINT user_gamification_pkey PRIMARY KEY (user_id);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (user_id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: user_subject_progress user_subject_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subject_progress
    ADD CONSTRAINT user_subject_progress_pkey PRIMARY KEY (user_id, subject_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: xp_transactions xp_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_transactions
    ADD CONSTRAINT xp_transactions_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_logs_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_entity ON public.audit_logs USING btree (entity_type, entity_id);


--
-- Name: ix_audit_logs_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_user ON public.audit_logs USING btree (user_id, created_at DESC);


--
-- Name: ix_chunk_embeddings_model; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chunk_embeddings_model ON public.chunk_embeddings USING btree (embedding_model);


--
-- Name: ix_community_posts_published; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_community_posts_published ON public.community_posts USING btree (status, published_at DESC);


--
-- Name: ix_community_reports_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_community_reports_status ON public.community_reports USING btree (status, created_at);


--
-- Name: ix_conversations_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_user ON public.conversations USING btree (user_id, created_at DESC);


--
-- Name: ix_daily_learning_stats_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_daily_learning_stats_date ON public.daily_learning_stats USING btree (activity_date);


--
-- Name: ix_document_chunks_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_chunks_document ON public.document_chunks USING btree (document_id, chunk_index);


--
-- Name: uq_document_chunks_active_document_index; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_document_chunks_active_document_index ON public.document_chunks USING btree (document_id, chunk_index) WHERE (is_active = true);


--
-- Name: ix_document_chunks_active_section; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_chunks_active_section ON public.document_chunks USING btree (document_id, section_id, chunk_index) WHERE (is_active = true);


--
-- Name: ix_document_chunks_metadata; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_chunks_metadata ON public.document_chunks USING gin (metadata);


--
-- Name: ix_document_chunks_search_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_chunks_search_vector ON public.document_chunks USING gin (search_vector);


--
-- Name: ix_document_chunks_section; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_chunks_section ON public.document_chunks USING btree (section_id);


--
-- Name: ix_document_processing_jobs_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_processing_jobs_document ON public.document_processing_jobs USING btree (document_id, created_at DESC);


--
-- Name: ix_document_processing_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_processing_jobs_status ON public.document_processing_jobs USING btree (status);


--
-- Name: ix_document_sections_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_sections_document ON public.document_sections USING btree (document_id, section_order);


--
-- Name: ix_document_sections_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_sections_parent ON public.document_sections USING btree (parent_section_id);


--
-- Name: ix_documents_checksum; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_checksum ON public.documents USING btree (checksum_sha256);


--
-- Name: ix_documents_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_owner_id ON public.documents USING btree (owner_id);


--
-- Name: ix_documents_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_status ON public.documents USING btree (status);


--
-- Name: ix_documents_subject_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_subject_id ON public.documents USING btree (subject_id);


--
-- Name: ix_documents_visibility; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_visibility ON public.documents USING btree (visibility);


--
-- Name: ix_export_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_export_jobs_status ON public.export_jobs USING btree (status);


--
-- Name: ix_export_jobs_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_export_jobs_user ON public.export_jobs USING btree (user_id, created_at DESC);


--
-- Name: ix_flashcard_decks_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcard_decks_owner ON public.flashcard_decks USING btree (owner_id, created_at DESC);


--
-- Name: ix_flashcard_decks_public; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcard_decks_public ON public.flashcard_decks USING btree (visibility, published_at DESC);


--
-- Name: ix_flashcard_decks_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcard_decks_subject ON public.flashcard_decks USING btree (subject_id);


--
-- Name: ix_flashcard_progress_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcard_progress_due ON public.flashcard_progress USING btree (user_id, next_review_at);


--
-- Name: ix_flashcard_reviews_card; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcard_reviews_card ON public.flashcard_reviews USING btree (flashcard_id, reviewed_at DESC);


--
-- Name: ix_flashcard_reviews_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcard_reviews_user ON public.flashcard_reviews USING btree (user_id, reviewed_at DESC);


--
-- Name: ix_flashcards_deck; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcards_deck ON public.flashcards USING btree (deck_id, card_order);


--
-- Name: ix_flashcards_source_chunk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flashcards_source_chunk ON public.flashcards USING btree (source_chunk_id);


--
-- Name: ix_message_citations_chunk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_citations_chunk ON public.message_citations USING btree (chunk_id);


--
-- Name: ix_messages_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_messages_conversation ON public.messages USING btree (conversation_id, created_at);


--
-- Name: ix_messages_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_messages_parent ON public.messages USING btree (parent_message_id);


--
-- Name: ix_notifications_user_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_unread ON public.notifications USING btree (user_id, is_read, created_at DESC);


--
-- Name: ix_questions_quiz; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_questions_quiz ON public.questions USING btree (quiz_id, question_order);


--
-- Name: ix_questions_source_chunk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_questions_source_chunk ON public.questions USING btree (source_chunk_id);


--
-- Name: ix_quiz_attempts_quiz; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_attempts_quiz ON public.quiz_attempts USING btree (quiz_id, started_at DESC);


--
-- Name: ix_quiz_attempts_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_attempts_status ON public.quiz_attempts USING btree (status);


--
-- Name: ix_quiz_attempts_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_attempts_user ON public.quiz_attempts USING btree (user_id, started_at DESC);


--
-- Name: ix_quizzes_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_owner ON public.quizzes USING btree (owner_id, created_at DESC);


--
-- Name: ix_quizzes_public; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_public ON public.quizzes USING btree (visibility, status, published_at DESC);


--
-- Name: ix_quizzes_source_quiz; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_source_quiz ON public.quizzes USING btree (source_quiz_id);


--
-- Name: ix_quizzes_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_subject ON public.quizzes USING btree (subject_id);


--
-- Name: ix_rag_evaluations_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rag_evaluations_message ON public.rag_evaluations USING btree (message_id);


--
-- Name: ix_refresh_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_expires_at ON public.refresh_tokens USING btree (expires_at);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_study_plans_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_study_plans_subject ON public.study_plans USING btree (subject_id);


--
-- Name: ix_study_plans_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_study_plans_user ON public.study_plans USING btree (user_id, created_at DESC);


--
-- Name: ix_study_tasks_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_study_tasks_due ON public.study_tasks USING btree (task_date, status);


--
-- Name: ix_study_tasks_plan_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_study_tasks_plan_date ON public.study_tasks USING btree (plan_id, task_date, sort_order);


--
-- Name: ix_subjects_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subjects_owner_id ON public.subjects USING btree (owner_id);


--
-- Name: ix_topic_mastery_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_topic_mastery_subject ON public.topic_mastery USING btree (user_id, subject_id, mastery_score);


--
-- Name: ix_user_answers_attempt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_answers_attempt ON public.user_answers USING btree (attempt_id);


--
-- Name: ix_user_answers_incorrect; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_answers_incorrect ON public.user_answers USING btree (question_id) WHERE (is_correct = false);


--
-- Name: ix_user_answers_question; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_answers_question ON public.user_answers USING btree (question_id);


--
-- Name: ix_xp_transactions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_xp_transactions_user ON public.xp_transactions USING btree (user_id, created_at DESC);


--
-- Name: ux_community_post_deck; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_community_post_deck ON public.community_posts USING btree (flashcard_deck_id) WHERE (flashcard_deck_id IS NOT NULL);


--
-- Name: ux_community_post_quiz; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_community_post_quiz ON public.community_posts USING btree (quiz_id) WHERE (quiz_id IS NOT NULL);


--
-- Name: ux_question_only_one_correct_option; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_question_only_one_correct_option ON public.question_options USING btree (question_id) WHERE (is_correct = true);


--
-- Name: ux_users_email_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_users_email_lower ON public.users USING btree (lower((email)::text));


--
-- Name: chunk_embeddings trg_chunk_embeddings_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_chunk_embeddings_updated_at BEFORE UPDATE ON public.chunk_embeddings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: community_posts trg_community_posts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_community_posts_updated_at BEFORE UPDATE ON public.community_posts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: conversations trg_conversations_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversations_updated_at BEFORE UPDATE ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: documents trg_documents_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: flashcard_decks trg_flashcard_decks_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_flashcard_decks_updated_at BEFORE UPDATE ON public.flashcard_decks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: flashcard_progress trg_flashcard_progress_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_flashcard_progress_updated_at BEFORE UPDATE ON public.flashcard_progress FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: flashcards trg_flashcards_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_flashcards_updated_at BEFORE UPDATE ON public.flashcards FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: questions trg_questions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_questions_updated_at BEFORE UPDATE ON public.questions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: quizzes trg_quizzes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_quizzes_updated_at BEFORE UPDATE ON public.quizzes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: study_plans trg_study_plans_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_study_plans_updated_at BEFORE UPDATE ON public.study_plans FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: study_tasks trg_study_tasks_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_study_tasks_updated_at BEFORE UPDATE ON public.study_tasks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: subjects trg_subjects_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_subjects_updated_at BEFORE UPDATE ON public.subjects FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: topic_mastery trg_topic_mastery_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_topic_mastery_updated_at BEFORE UPDATE ON public.topic_mastery FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: user_gamification trg_user_gamification_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_user_gamification_updated_at BEFORE UPDATE ON public.user_gamification FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: user_subject_progress trg_user_subject_progress_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_user_subject_progress_updated_at BEFORE UPDATE ON public.user_subject_progress FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: users trg_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: quizzes trg_validate_quiz_before_publish; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_validate_quiz_before_publish BEFORE UPDATE OF status ON public.quizzes FOR EACH ROW EXECUTE FUNCTION public.validate_quiz_before_publish();


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: chunk_embeddings chunk_embeddings_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_embeddings
    ADD CONSTRAINT chunk_embeddings_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id) ON DELETE CASCADE;


--
-- Name: community_posts community_posts_flashcard_deck_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_posts
    ADD CONSTRAINT community_posts_flashcard_deck_id_fkey FOREIGN KEY (flashcard_deck_id) REFERENCES public.flashcard_decks(id) ON DELETE CASCADE;


--
-- Name: community_posts community_posts_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_posts
    ADD CONSTRAINT community_posts_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: community_posts community_posts_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_posts
    ADD CONSTRAINT community_posts_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: community_reactions community_reactions_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reactions
    ADD CONSTRAINT community_reactions_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.community_posts(id) ON DELETE CASCADE;


--
-- Name: community_reactions community_reactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reactions
    ADD CONSTRAINT community_reactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: community_reports community_reports_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reports
    ADD CONSTRAINT community_reports_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.community_posts(id) ON DELETE CASCADE;


--
-- Name: community_reports community_reports_reporter_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reports
    ADD CONSTRAINT community_reports_reporter_user_id_fkey FOREIGN KEY (reporter_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: community_reports community_reports_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_reports
    ADD CONSTRAINT community_reports_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: community_saves community_saves_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_saves
    ADD CONSTRAINT community_saves_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.community_posts(id) ON DELETE CASCADE;


--
-- Name: community_saves community_saves_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.community_saves
    ADD CONSTRAINT community_saves_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: conversation_documents conversation_documents_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_documents
    ADD CONSTRAINT conversation_documents_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: conversation_documents conversation_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_documents
    ADD CONSTRAINT conversation_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE SET NULL;


--
-- Name: conversations conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: daily_learning_stats daily_learning_stats_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_learning_stats
    ADD CONSTRAINT daily_learning_stats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.document_sections(id) ON DELETE SET NULL;


--
-- Name: document_processing_jobs document_processing_jobs_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_jobs
    ADD CONSTRAINT document_processing_jobs_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: document_sections document_sections_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_sections
    ADD CONSTRAINT document_sections_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: document_sections document_sections_parent_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_sections
    ADD CONSTRAINT document_sections_parent_section_id_fkey FOREIGN KEY (parent_section_id) REFERENCES public.document_sections(id) ON DELETE CASCADE;


--
-- Name: documents documents_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: documents documents_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE SET NULL;


--
-- Name: export_jobs export_jobs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.export_jobs
    ADD CONSTRAINT export_jobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_answers fk_user_answer_selected_option; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_answers
    ADD CONSTRAINT fk_user_answer_selected_option FOREIGN KEY (selected_option_id, question_id) REFERENCES public.question_options(id, question_id) ON DELETE RESTRICT;


--
-- Name: flashcard_deck_documents flashcard_deck_documents_deck_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_deck_documents
    ADD CONSTRAINT flashcard_deck_documents_deck_id_fkey FOREIGN KEY (deck_id) REFERENCES public.flashcard_decks(id) ON DELETE CASCADE;


--
-- Name: flashcard_deck_documents flashcard_deck_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_deck_documents
    ADD CONSTRAINT flashcard_deck_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: flashcard_decks flashcard_decks_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_decks
    ADD CONSTRAINT flashcard_decks_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: flashcard_decks flashcard_decks_source_deck_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_decks
    ADD CONSTRAINT flashcard_decks_source_deck_id_fkey FOREIGN KEY (source_deck_id) REFERENCES public.flashcard_decks(id) ON DELETE SET NULL;


--
-- Name: flashcard_decks flashcard_decks_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_decks
    ADD CONSTRAINT flashcard_decks_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE SET NULL;


--
-- Name: flashcard_progress flashcard_progress_flashcard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_progress
    ADD CONSTRAINT flashcard_progress_flashcard_id_fkey FOREIGN KEY (flashcard_id) REFERENCES public.flashcards(id) ON DELETE CASCADE;


--
-- Name: flashcard_progress flashcard_progress_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_progress
    ADD CONSTRAINT flashcard_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: flashcard_reviews flashcard_reviews_flashcard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_reviews
    ADD CONSTRAINT flashcard_reviews_flashcard_id_fkey FOREIGN KEY (flashcard_id) REFERENCES public.flashcards(id) ON DELETE CASCADE;


--
-- Name: flashcard_reviews flashcard_reviews_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcard_reviews
    ADD CONSTRAINT flashcard_reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: flashcards flashcards_deck_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcards
    ADD CONSTRAINT flashcards_deck_id_fkey FOREIGN KEY (deck_id) REFERENCES public.flashcard_decks(id) ON DELETE CASCADE;


--
-- Name: flashcards flashcards_source_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flashcards
    ADD CONSTRAINT flashcards_source_chunk_id_fkey FOREIGN KEY (source_chunk_id) REFERENCES public.document_chunks(id) ON DELETE SET NULL;


--
-- Name: message_citations message_citations_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_citations
    ADD CONSTRAINT message_citations_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id) ON DELETE CASCADE;


--
-- Name: message_citations message_citations_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_citations
    ADD CONSTRAINT message_citations_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: messages messages_parent_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_parent_message_id_fkey FOREIGN KEY (parent_message_id) REFERENCES public.messages(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: question_options question_options_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.question_options
    ADD CONSTRAINT question_options_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.questions(id) ON DELETE CASCADE;


--
-- Name: questions questions_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: questions questions_source_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_source_chunk_id_fkey FOREIGN KEY (source_chunk_id) REFERENCES public.document_chunks(id) ON DELETE SET NULL;


--
-- Name: quiz_attempts quiz_attempts_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quiz_attempts quiz_attempts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quiz_documents quiz_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_documents
    ADD CONSTRAINT quiz_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: quiz_documents quiz_documents_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_documents
    ADD CONSTRAINT quiz_documents_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_source_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_source_quiz_id_fkey FOREIGN KEY (source_quiz_id) REFERENCES public.quizzes(id) ON DELETE SET NULL;


--
-- Name: quizzes quizzes_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE SET NULL;


--
-- Name: rag_evaluations rag_evaluations_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_evaluations
    ADD CONSTRAINT rag_evaluations_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: study_plans study_plans_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plans
    ADD CONSTRAINT study_plans_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE SET NULL;


--
-- Name: study_plans study_plans_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plans
    ADD CONSTRAINT study_plans_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: study_tasks study_tasks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_tasks
    ADD CONSTRAINT study_tasks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: study_tasks study_tasks_flashcard_deck_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_tasks
    ADD CONSTRAINT study_tasks_flashcard_deck_id_fkey FOREIGN KEY (flashcard_deck_id) REFERENCES public.flashcard_decks(id) ON DELETE SET NULL;


--
-- Name: study_tasks study_tasks_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_tasks
    ADD CONSTRAINT study_tasks_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.study_plans(id) ON DELETE CASCADE;


--
-- Name: study_tasks study_tasks_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_tasks
    ADD CONSTRAINT study_tasks_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE SET NULL;


--
-- Name: study_tasks study_tasks_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_tasks
    ADD CONSTRAINT study_tasks_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.document_sections(id) ON DELETE SET NULL;


--
-- Name: subject_members subject_members_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject_members
    ADD CONSTRAINT subject_members_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE CASCADE;


--
-- Name: subject_members subject_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject_members
    ADD CONSTRAINT subject_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: subjects subjects_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT subjects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: topic_mastery topic_mastery_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topic_mastery
    ADD CONSTRAINT topic_mastery_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.document_sections(id) ON DELETE CASCADE;


--
-- Name: topic_mastery topic_mastery_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topic_mastery
    ADD CONSTRAINT topic_mastery_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE CASCADE;


--
-- Name: topic_mastery topic_mastery_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topic_mastery
    ADD CONSTRAINT topic_mastery_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_answers user_answers_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_answers
    ADD CONSTRAINT user_answers_attempt_id_fkey FOREIGN KEY (attempt_id) REFERENCES public.quiz_attempts(id) ON DELETE CASCADE;


--
-- Name: user_answers user_answers_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_answers
    ADD CONSTRAINT user_answers_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.questions(id) ON DELETE CASCADE;


--
-- Name: user_badges user_badges_badge_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_badges
    ADD CONSTRAINT user_badges_badge_id_fkey FOREIGN KEY (badge_id) REFERENCES public.badges(id) ON DELETE CASCADE;


--
-- Name: user_badges user_badges_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_badges
    ADD CONSTRAINT user_badges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_gamification user_gamification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gamification
    ADD CONSTRAINT user_gamification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_preferences user_preferences_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE RESTRICT;


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_subject_progress user_subject_progress_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subject_progress
    ADD CONSTRAINT user_subject_progress_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id) ON DELETE CASCADE;


--
-- Name: user_subject_progress user_subject_progress_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subject_progress
    ADD CONSTRAINT user_subject_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: xp_transactions xp_transactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_transactions
    ADD CONSTRAINT xp_transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict bUX7q1RdSbHHuPnU2Jm83h596ygpvBmIvJrqaTg1H0dRJL7aoWu2g3G2QnP7WrE

-- Active versioned-chunk lookup index.
CREATE INDEX IF NOT EXISTS ix_document_chunks_active_document
ON public.document_chunks
USING btree (document_id, is_active, chunk_index);

