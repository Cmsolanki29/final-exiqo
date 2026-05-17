-- ============================================================================
-- 031: extraction_results — audit trail for every document extraction attempt
-- Apply: cd backend && python -m scripts.apply_migrations
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_results (
    id SERIAL PRIMARY KEY,
    uploaded_document_id INTEGER REFERENCES uploaded_documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,

    file_type VARCHAR(20),
    file_size_bytes INTEGER,
    page_count INTEGER,

    raw_extracted_text TEXT,
    extraction_method VARCHAR(50),

    quality_score INTEGER,
    quality_checks JSONB,
    attempt_number INTEGER DEFAULT 1,

    llm_raw_response TEXT,
    llm_model_used VARCHAR(50),

    transactions_extracted INTEGER,
    transactions_after_validation INTEGER,
    validation_issues JSONB,

    categorization_method VARCHAR(50),

    transactions_stored INTEGER,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_extraction_results_doc
    ON extraction_results(uploaded_document_id);

CREATE INDEX IF NOT EXISTS idx_extraction_results_user
    ON extraction_results(user_id);
