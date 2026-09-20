BEGIN;

ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS chunk_set_id varchar(80);
ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS chunking_algorithm varchar(50);
ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS is_active boolean;
ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS superseded_at timestamptz;

UPDATE public.document_chunks
SET
    chunk_set_id = COALESCE(chunk_set_id, 'legacy-v1'),
    chunking_algorithm = COALESCE(chunking_algorithm, 'legacy-v1'),
    is_active = COALESCE(is_active, TRUE);

ALTER TABLE public.document_chunks
    ALTER COLUMN chunk_set_id SET DEFAULT 'legacy-v1';
ALTER TABLE public.document_chunks
    ALTER COLUMN chunk_set_id SET NOT NULL;

ALTER TABLE public.document_chunks
    ALTER COLUMN chunking_algorithm SET DEFAULT 'legacy-v1';
ALTER TABLE public.document_chunks
    ALTER COLUMN chunking_algorithm SET NOT NULL;

ALTER TABLE public.document_chunks
    ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE public.document_chunks
    ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE public.document_chunks
    DROP CONSTRAINT IF EXISTS
        document_chunks_document_id_chunk_index_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid =
            'public.document_chunks'::regclass
          AND conname =
            'document_chunks_document_set_index_key'
    ) THEN
        ALTER TABLE public.document_chunks
            ADD CONSTRAINT
            document_chunks_document_set_index_key
            UNIQUE (
                document_id,
                chunk_set_id,
                chunk_index
            );
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_document_chunks_active_document_index
ON public.document_chunks (
    document_id,
    chunk_index
)
WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS
    ix_document_chunks_active_document
ON public.document_chunks (
    document_id,
    is_active,
    chunk_index
);

CREATE INDEX IF NOT EXISTS
    ix_document_chunks_active_section
ON public.document_chunks (
    section_id,
    is_active
);

COMMIT;

SELECT
    chunk_set_id,
    chunking_algorithm,
    is_active,
    COUNT(*) AS chunk_count
FROM public.document_chunks
GROUP BY
    chunk_set_id,
    chunking_algorithm,
    is_active
ORDER BY
    chunk_set_id,
    is_active DESC;
