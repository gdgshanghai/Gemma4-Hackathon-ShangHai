CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL CHECK (length(checksum) = 64),
    applied_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE school_briefs (
    id TEXT PRIMARY KEY,
    brief_date TEXT NOT NULL,
    source_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    raw_text TEXT NOT NULL,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (brief_date, content_sha256)
);

CREATE TABLE evening_sessions (
    id TEXT PRIMARY KEY,
    session_date TEXT NOT NULL,
    timezone TEXT NOT NULL,
    sleep_time TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN (
        'created',
        'intake_draft',
        'coverage_pending',
        'inventory_confirmed',
        'plan_draft',
        'committed',
        'closed',
        'capacity_conflict',
        'needs_confirmation',
        'model_unavailable'
    )),
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    available_minutes INTEGER NOT NULL CHECK (available_minutes >= 0),
    school_brief_id TEXT REFERENCES school_briefs(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE task_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    school_brief_id TEXT REFERENCES school_briefs(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    subject TEXT,
    source TEXT NOT NULL CHECK (source IN (
        'child', 'school', 'both', 'parent', 'system'
    )),
    completion_state TEXT NOT NULL CHECK (completion_state IN (
        'pending', 'partial', 'completed', 'uncertain', 'no_task'
    )),
    estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes >= 0),
    conservative_minutes INTEGER NOT NULL CHECK (conservative_minutes >= 0),
    priority INTEGER NOT NULL CHECK (priority >= 0),
    due_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE coverage_diffs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    school_task_id TEXT REFERENCES task_items(id) ON DELETE RESTRICT,
    reported_task_id TEXT REFERENCES task_items(id) ON DELETE RESTRICT,
    mode TEXT NOT NULL CHECK (mode IN ('school_verified', 'child_reported')),
    source TEXT NOT NULL CHECK (source IN (
        'child', 'school', 'both', 'parent', 'system'
    )),
    summary TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
    resolved_at TEXT,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (resolved = 1 OR resolved_at IS NULL)
);

CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (version >= 1),
    stage TEXT NOT NULL CHECK (stage IN (
        'created',
        'intake_draft',
        'coverage_pending',
        'inventory_confirmed',
        'plan_draft',
        'committed',
        'closed',
        'capacity_conflict',
        'needs_confirmation',
        'model_unavailable'
    )),
    capacity_json TEXT NOT NULL CHECK (json_valid(capacity_json)),
    reason TEXT NOT NULL,
    committed INTEGER NOT NULL DEFAULT 0 CHECK (committed IN (0, 1)),
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (session_id, version)
);

CREATE TABLE plan_blocks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    task_id TEXT REFERENCES task_items(id) ON DELETE RESTRICT,
    block_type TEXT NOT NULL CHECK (block_type IN (
        'task', 'fixed', 'buffer', 'break'
    )),
    label TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (plan_id, ordinal),
    CHECK (ends_at > starts_at)
);

CREATE TABLE task_outcomes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    task_id TEXT NOT NULL REFERENCES task_items(id) ON DELETE RESTRICT,
    completion_state TEXT NOT NULL CHECK (completion_state IN (
        'pending', 'partial', 'completed', 'uncertain', 'no_task'
    )),
    actual_minutes INTEGER CHECK (actual_minutes >= 0),
    note TEXT,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (session_id, task_id)
);

CREATE TABLE calibration_events (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    source TEXT NOT NULL CHECK (source IN (
        'child', 'school', 'both', 'parent', 'system'
    )),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    confirmed INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0, 1)),
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE observation_events (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'child', 'school', 'both', 'parent', 'system'
    )),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE llm_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    model TEXT NOT NULL,
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    response_json TEXT CHECK (response_json IS NULL OR json_valid(response_json)),
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    latency_ms INTEGER CHECK (latency_ms >= 0)
);

CREATE TABLE tool_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    llm_run_id TEXT REFERENCES llm_runs(id) ON DELETE RESTRICT,
    tool_name TEXT NOT NULL,
    call_id TEXT NOT NULL,
    arguments_json TEXT NOT NULL CHECK (json_valid(arguments_json)),
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    latency_ms INTEGER CHECK (latency_ms >= 0),
    UNIQUE (llm_run_id, call_id)
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    actor_source TEXT NOT NULL CHECK (actor_source IN (
        'child', 'school', 'both', 'parent', 'system'
    )),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    trace_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE idempotency_records (
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    response_json TEXT NOT NULL CHECK (json_valid(response_json)),
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (operation, idempotency_key)
);

CREATE INDEX idx_task_items_session ON task_items(session_id);
CREATE INDEX idx_coverage_diffs_session ON coverage_diffs(session_id);
CREATE INDEX idx_plans_session ON plans(session_id, version);
CREATE INDEX idx_observation_events_session
    ON observation_events(session_id, occurred_at);
CREATE INDEX idx_audit_events_session ON audit_events(session_id, occurred_at);
CREATE INDEX idx_llm_runs_session ON llm_runs(session_id, started_at);
CREATE INDEX idx_tool_runs_session ON tool_runs(session_id, started_at);

CREATE TRIGGER observation_events_no_update
BEFORE UPDATE ON observation_events
BEGIN
    SELECT RAISE(ABORT, 'observation_events are append-only');
END;

CREATE TRIGGER observation_events_no_delete
BEFORE DELETE ON observation_events
BEGIN
    SELECT RAISE(ABORT, 'observation_events are append-only');
END;

CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;
