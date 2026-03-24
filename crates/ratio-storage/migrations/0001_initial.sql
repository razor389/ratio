CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    display_name TEXT,
    sector TEXT,
    industry TEXT,
    description TEXT,
    is_tracked INTEGER NOT NULL DEFAULT 1,
    is_published INTEGER NOT NULL DEFAULT 0,
    visibility TEXT NOT NULL DEFAULT 'draft_only',
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    source_type TEXT NOT NULL,
    external_source_id TEXT,
    title TEXT,
    body_text TEXT NOT NULL,
    author_email TEXT,
    source_timestamp TEXT,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT,
    updated_by TEXT,
    published_by TEXT,
    as_of_date TEXT,
    public_comment TEXT,
    is_public_comment_enabled INTEGER NOT NULL DEFAULT 0,
    internal_notes TEXT,
    llm_provider TEXT,
    llm_model TEXT,
    llm_prompt_version TEXT,
    llm_assumptions_json TEXT NOT NULL DEFAULT '[]',
    llm_confidence TEXT,
    raw_response TEXT,
    calculation_version TEXT NOT NULL,
    aggregate_score INTEGER NOT NULL,
    relative_score REAL NOT NULL,
    beta_like_score REAL NOT NULL,
    base_position_size REAL NOT NULL,
    suggested_position_size REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT,
    UNIQUE(company_id, version_number)
);

CREATE TABLE IF NOT EXISTS assessment_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id),
    factor_key TEXT NOT NULL,
    factor_label TEXT NOT NULL,
    score INTEGER NOT NULL,
    score_min INTEGER NOT NULL,
    score_max INTEGER NOT NULL,
    internal_rationale TEXT,
    public_rationale_override TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assessment_evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id),
    factor_key TEXT,
    source_document_id INTEGER NOT NULL REFERENCES source_documents(id),
    relevance_rank INTEGER NOT NULL DEFAULT 0,
    evidence_note TEXT,
    used_by_llm INTEGER NOT NULL DEFAULT 0,
    used_in_final_review INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    password_hash TEXT,
    auth_provider_subject TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES admin_users(id),
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    assessment_id INTEGER NOT NULL REFERENCES assessments(id),
    published_by TEXT,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
