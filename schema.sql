PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    cadence_seconds INTEGER,
    rights_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    terms_memo TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    collector_id TEXT REFERENCES collector_registry(collector_id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    requested_count INTEGER NOT NULL DEFAULT 0,
    received_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    raw_path TEXT,
    raw_sha256 TEXT,
    health_json TEXT
);

CREATE TABLE IF NOT EXISTS raw_payloads (
    payload_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    run_id INTEGER REFERENCES collection_runs(run_id),
    collected_at TEXT NOT NULL,
    source_url TEXT NOT NULL,
    query_params_json TEXT NOT NULL DEFAULT '{}',
    source_timestamp TEXT,
    content_hash TEXT NOT NULL,
    raw_path TEXT,
    byte_count INTEGER NOT NULL DEFAULT 0,
    mime_type TEXT,
    is_duplicate INTEGER NOT NULL DEFAULT 0 CHECK (is_duplicate IN (0, 1)),
    previous_payload_id INTEGER REFERENCES raw_payloads(payload_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_payload_hash ON raw_payloads(source_id, content_hash);

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    external_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    title TEXT NOT NULL,
    description TEXT,
    provider TEXT,
    category TEXT,
    public_status TEXT NOT NULL DEFAULT 'OPEN',
    expected_release_year INTEGER,
    api_available INTEGER NOT NULL DEFAULT 0 CHECK (api_available IN (0, 1)),
    file_available INTEGER NOT NULL DEFAULT 0 CHECK (file_available IN (0, 1)),
    update_frequency TEXT,
    license TEXT,
    terms TEXT,
    registered_at TEXT,
    modified_at TEXT,
    source_url TEXT NOT NULL,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    machine_format TEXT,
    cost_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    rights_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    historical_availability TEXT NOT NULL DEFAULT 'UNKNOWN',
    current_hash TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    raw_payload_id INTEGER REFERENCES raw_payloads(payload_id),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_datasets_provider ON datasets(provider);
CREATE INDEX IF NOT EXISTS idx_datasets_modified ON datasets(modified_at);

CREATE TABLE IF NOT EXISTS dataset_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
    event_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    observed_run_id INTEGER REFERENCES collection_runs(run_id),
    raw_payload_id INTEGER REFERENCES raw_payloads(payload_id)
);

CREATE INDEX IF NOT EXISTS idx_dataset_events_time ON dataset_events(event_at);
CREATE INDEX IF NOT EXISTS idx_dataset_events_dataset ON dataset_events(dataset_id);

CREATE TABLE IF NOT EXISTS pre_release_signals (
    signal_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    buyer_org TEXT,
    posted_at TEXT,
    notice_type TEXT,
    source_url TEXT NOT NULL,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    entities_json TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    raw_payload_id INTEGER REFERENCES raw_payloads(payload_id),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, external_id)
);

CREATE TABLE IF NOT EXISTS signal_dataset_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL REFERENCES pre_release_signals(signal_id),
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    method TEXT NOT NULL,
    matched_terms_json TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'AUTO',
    created_at TEXT NOT NULL,
    UNIQUE(signal_id, dataset_id)
);

CREATE TABLE IF NOT EXISTS score_overrides (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_type TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    score_kind TEXT NOT NULL,
    dimension TEXT NOT NULL,
    rating REAL NOT NULL CHECK (rating >= 0 AND rating <= 10),
    source_type TEXT NOT NULL CHECK (source_type IN ('HUMAN', 'AI')),
    source_name TEXT NOT NULL,
    rationale TEXT,
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_score_override_candidate
ON score_overrides(candidate_type, candidate_id, score_kind, active);

CREATE TABLE IF NOT EXISTS scoring_dimensions (
    score_dimension_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_type TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    score_kind TEXT NOT NULL,
    dimension TEXT NOT NULL,
    weight REAL NOT NULL,
    auto_rating REAL NOT NULL,
    override_rating REAL,
    override_source_type TEXT,
    override_source_name TEXT,
    effective_rating REAL NOT NULL,
    effective_points REAL NOT NULL,
    rationale TEXT,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    calculated_at TEXT NOT NULL,
    UNIQUE(candidate_type, candidate_id, score_kind, dimension)
);

CREATE TABLE IF NOT EXISTS alpha_scores (
    candidate_type TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    pra_score REAL,
    seed_score REAL,
    ephemeral_score REAL,
    rights_gate TEXT NOT NULL,
    cost_gate TEXT NOT NULL,
    accumulation_gate TEXT NOT NULL,
    review_status TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    PRIMARY KEY(candidate_type, candidate_id)
);

CREATE TABLE IF NOT EXISTS collector_registry (
    collector_id TEXT PRIMARY KEY,
    dataset_id TEXT REFERENCES datasets(dataset_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    name TEXT NOT NULL,
    module TEXT NOT NULL,
    endpoint_template TEXT NOT NULL,
    schedule_cron TEXT,
    cadence_seconds INTEGER NOT NULL,
    entity_key TEXT NOT NULL,
    snapshot_strategy TEXT NOT NULL,
    storage_estimate_bytes_day INTEGER,
    legal_memo TEXT NOT NULL,
    terms_checked_at TEXT,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
    auth_env TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seed_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_type TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    dataset_id TEXT REFERENCES datasets(dataset_id),
    seed_score REAL NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    rights_ok INTEGER NOT NULL CHECK (rights_ok IN (0, 1)),
    low_cost INTEGER NOT NULL CHECK (low_cost IN (0, 1)),
    collector_id TEXT REFERENCES collector_registry(collector_id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(candidate_type, candidate_id)
);

CREATE TABLE IF NOT EXISTS place_registry (
    place_id TEXT PRIMARY KEY,
    area_code TEXT,
    area_name TEXT NOT NULL UNIQUE,
    cohort TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    commercial_available INTEGER NOT NULL DEFAULT 1 CHECK (commercial_available IN (0, 1)),
    rationale TEXT NOT NULL,
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_id TEXT NOT NULL REFERENCES collector_registry(collector_id),
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    source_timestamp TEXT,
    source_url TEXT NOT NULL,
    query_params_json TEXT NOT NULL DEFAULT '{}',
    payload_hash TEXT NOT NULL,
    raw_path TEXT,
    raw_payload_id INTEGER REFERENCES raw_payloads(payload_id),
    normalized_json TEXT NOT NULL,
    missing_sections_json TEXT NOT NULL DEFAULT '[]',
    quality_status TEXT NOT NULL,
    UNIQUE(collector_id, entity_key, source_timestamp, payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_entity_time
ON snapshots(collector_id, entity_key, observed_at);

CREATE TABLE IF NOT EXISTS snapshot_features (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    namespace TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    numeric_value REAL,
    text_value TEXT,
    feature_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE(snapshot_id, namespace, feature_name, feature_version)
);

CREATE TABLE IF NOT EXISTS event_annotations (
    annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT,
    confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
    notes TEXT,
    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collector_health_logs (
    health_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_id TEXT NOT NULL REFERENCES collector_registry(collector_id),
    run_id INTEGER REFERENCES collection_runs(run_id),
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER,
    http_status INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    entities_expected INTEGER NOT NULL DEFAULT 0,
    entities_succeeded INTEGER NOT NULL DEFAULT 0,
    new_snapshots INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    missing_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS data_gap_events (
    gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_id TEXT NOT NULL REFERENCES collector_registry(collector_id),
    entity_key TEXT NOT NULL,
    expected_at TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    severity TEXT NOT NULL,
    reason TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE(collector_id, entity_key, expected_at)
);
