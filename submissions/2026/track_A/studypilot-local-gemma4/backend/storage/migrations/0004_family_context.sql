CREATE TABLE profile_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    profile_version INTEGER NOT NULL DEFAULT 0 CHECK (profile_version >= 0)
);

INSERT INTO profile_state (singleton, profile_version) VALUES (1, 0);

CREATE TABLE calibration_sessions (
    id TEXT PRIMARY KEY,
    calibration_version INTEGER NOT NULL CHECK (calibration_version >= 1),
    state TEXT NOT NULL CHECK (state IN (
        'input_saved', 'model_unavailable', 'needs_confirmation',
        'retry_pending', 'committed', 'abandoned'
    )),
    base_profile_version INTEGER NOT NULL CHECK (base_profile_version >= 0),
    profile_version INTEGER NOT NULL CHECK (profile_version >= 0),
    input_receipt_id TEXT,
    pending_kind TEXT CHECK (
        pending_kind IS NULL OR pending_kind IN ('profile_patch', 'model_retry')
    ),
    pending_entity_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE calibration_turn_receipts (
    id TEXT PRIMARY KEY,
    calibration_id TEXT NOT NULL
        REFERENCES calibration_sessions(id) ON DELETE RESTRICT,
    operation TEXT NOT NULL,
    key_hash TEXT NOT NULL CHECK (length(key_hash) = 64),
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    raw_text TEXT NOT NULL,
    base_profile_version INTEGER NOT NULL CHECK (base_profile_version >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (operation, key_hash)
);

CREATE TABLE calibration_drafts (
    id TEXT PRIMARY KEY,
    calibration_id TEXT NOT NULL
        REFERENCES calibration_sessions(id) ON DELETE RESTRICT,
    receipt_id TEXT NOT NULL
        REFERENCES calibration_turn_receipts(id) ON DELETE RESTRICT,
    base_profile_version INTEGER NOT NULL CHECK (base_profile_version >= 0),
    proposal_digest TEXT NOT NULL CHECK (length(proposal_digest) = 64),
    draft_digest TEXT NOT NULL CHECK (length(draft_digest) = 64),
    operations_json TEXT NOT NULL CHECK (json_valid(operations_json)),
    result_json TEXT NOT NULL CHECK (json_valid(result_json)),
    revises_draft_id TEXT
        REFERENCES calibration_drafts(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL
);

CREATE TABLE calibration_commits (
    id TEXT PRIMARY KEY,
    calibration_id TEXT NOT NULL
        REFERENCES calibration_sessions(id) ON DELETE RESTRICT,
    draft_id TEXT NOT NULL UNIQUE
        REFERENCES calibration_drafts(id) ON DELETE RESTRICT,
    resulting_profile_version INTEGER NOT NULL UNIQUE
        CHECK (resulting_profile_version >= 1),
    accepted_operation_ids_json TEXT NOT NULL
        CHECK (json_valid(accepted_operation_ids_json)),
    confirmed_by TEXT NOT NULL,
    committed_at TEXT NOT NULL
);

CREATE TABLE profile_versions (
    profile_version INTEGER PRIMARY KEY CHECK (profile_version >= 1),
    commit_id TEXT NOT NULL UNIQUE
        REFERENCES calibration_commits(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    committed_at TEXT NOT NULL
);

CREATE TABLE profile_observation_events (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL
        REFERENCES profile_versions(profile_version) ON DELETE RESTRICT,
    canonical_order INTEGER NOT NULL CHECK (canonical_order >= 0),
    action TEXT NOT NULL CHECK (action IN ('assert', 'supersede', 'revoke')),
    category TEXT NOT NULL CHECK (category IN (
        'subject_performance', 'task_speed', 'behavior', 'environment'
    )),
    subject TEXT,
    task_type TEXT,
    metric TEXT NOT NULL,
    value_text TEXT,
    value_number REAL,
    unit TEXT,
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    sample_count INTEGER CHECK (sample_count IS NULL OR sample_count >= 1),
    observed_at TEXT NOT NULL,
    target_event_id TEXT
        REFERENCES profile_observation_events(id) ON DELETE RESTRICT,
    source TEXT NOT NULL CHECK (source IN (
        'child', 'school', 'both', 'parent', 'system'
    )),
    evidence_level TEXT NOT NULL CHECK (evidence_level IN (
        'parent_confirmed', 'system_observed', 'inferred_by_exclusion'
    )),
    confirmed_by TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    UNIQUE (profile_version, canonical_order),
    CHECK (
        (action = 'assert' AND target_event_id IS NULL)
        OR (action IN ('supersede', 'revoke') AND target_event_id IS NOT NULL)
    ),
    CHECK (
        action <> 'revoke'
        OR (
            value_text IS NULL AND value_number IS NULL
            AND unit IS NULL AND sample_count IS NULL
        )
    )
);

CREATE TABLE calibration_checkpoints (
    id TEXT PRIMARY KEY,
    calibration_id TEXT NOT NULL
        REFERENCES calibration_sessions(id) ON DELETE RESTRICT,
    calibration_version INTEGER NOT NULL CHECK (calibration_version >= 1),
    profile_version INTEGER NOT NULL CHECK (profile_version >= 0),
    state TEXT NOT NULL CHECK (state IN (
        'input_saved', 'model_unavailable', 'needs_confirmation',
        'retry_pending', 'committed', 'abandoned'
    )),
    resume_stage TEXT,
    pending_kind TEXT CHECK (
        pending_kind IS NULL OR pending_kind IN ('profile_patch', 'model_retry')
    ),
    pending_entity_id TEXT,
    last_stable_calibration_version INTEGER NOT NULL
        CHECK (last_stable_calibration_version >= 0),
    last_stable_profile_version INTEGER NOT NULL
        CHECK (last_stable_profile_version >= 0),
    input_receipt_id TEXT
        REFERENCES calibration_turn_receipts(id) ON DELETE RESTRICT,
    trace_id TEXT,
    outcome_json TEXT CHECK (outcome_json IS NULL OR json_valid(outcome_json)),
    occurred_at TEXT NOT NULL,
    UNIQUE (calibration_id, calibration_version)
);

CREATE TABLE calibration_audit_events (
    id TEXT PRIMARY KEY,
    calibration_id TEXT NOT NULL
        REFERENCES calibration_sessions(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    profile_version INTEGER NOT NULL CHECK (profile_version >= 0),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    trace_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE school_brief_revisions (
    id TEXT PRIMARY KEY,
    brief_date TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    raw_text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual-paste'
        CHECK (source = 'manual-paste'),
    created_at TEXT NOT NULL,
    UNIQUE (brief_date, revision)
);

CREATE INDEX idx_profile_events_projection
    ON profile_observation_events(profile_version, canonical_order);
CREATE INDEX idx_profile_events_target
    ON profile_observation_events(target_event_id);
CREATE INDEX idx_calibration_sessions_recovery
    ON calibration_sessions(id, calibration_version, state);
CREATE INDEX idx_calibration_receipts_replay
    ON calibration_turn_receipts(operation, key_hash);
CREATE INDEX idx_calibration_receipts_session
    ON calibration_turn_receipts(calibration_id, created_at);
CREATE INDEX idx_calibration_drafts_session
    ON calibration_drafts(calibration_id, created_at);
CREATE INDEX idx_calibration_checkpoints_history
    ON calibration_checkpoints(calibration_id, calibration_version);
CREATE INDEX idx_school_revisions_date
    ON school_brief_revisions(brief_date, revision);

CREATE TRIGGER calibration_turn_receipts_no_update
BEFORE UPDATE ON calibration_turn_receipts
BEGIN
    SELECT RAISE(ABORT, 'calibration_turn_receipts are append-only');
END;

CREATE TRIGGER calibration_turn_receipts_no_delete
BEFORE DELETE ON calibration_turn_receipts
BEGIN
    SELECT RAISE(ABORT, 'calibration_turn_receipts are append-only');
END;

CREATE TRIGGER calibration_drafts_no_update
BEFORE UPDATE ON calibration_drafts
BEGIN
    SELECT RAISE(ABORT, 'calibration_drafts are append-only');
END;

CREATE TRIGGER calibration_drafts_no_delete
BEFORE DELETE ON calibration_drafts
BEGIN
    SELECT RAISE(ABORT, 'calibration_drafts are append-only');
END;

CREATE TRIGGER calibration_commits_no_update
BEFORE UPDATE ON calibration_commits
BEGIN
    SELECT RAISE(ABORT, 'calibration_commits are append-only');
END;

CREATE TRIGGER calibration_commits_no_delete
BEFORE DELETE ON calibration_commits
BEGIN
    SELECT RAISE(ABORT, 'calibration_commits are append-only');
END;

CREATE TRIGGER profile_versions_no_update
BEFORE UPDATE ON profile_versions
BEGIN
    SELECT RAISE(ABORT, 'profile_versions are append-only');
END;

CREATE TRIGGER profile_versions_no_delete
BEFORE DELETE ON profile_versions
BEGIN
    SELECT RAISE(ABORT, 'profile_versions are append-only');
END;

CREATE TRIGGER profile_observation_events_no_update
BEFORE UPDATE ON profile_observation_events
BEGIN
    SELECT RAISE(ABORT, 'profile_observation_events are append-only');
END;

CREATE TRIGGER profile_observation_events_no_delete
BEFORE DELETE ON profile_observation_events
BEGIN
    SELECT RAISE(ABORT, 'profile_observation_events are append-only');
END;

CREATE TRIGGER school_brief_revisions_no_update
BEFORE UPDATE ON school_brief_revisions
BEGIN
    SELECT RAISE(ABORT, 'school_brief_revisions are append-only');
END;

CREATE TRIGGER school_brief_revisions_no_delete
BEFORE DELETE ON school_brief_revisions
BEGIN
    SELECT RAISE(ABORT, 'school_brief_revisions are append-only');
END;

CREATE TRIGGER calibration_checkpoints_no_update
BEFORE UPDATE ON calibration_checkpoints
BEGIN
    SELECT RAISE(ABORT, 'calibration_checkpoints are append-only');
END;

CREATE TRIGGER calibration_checkpoints_no_delete
BEFORE DELETE ON calibration_checkpoints
BEGIN
    SELECT RAISE(ABORT, 'calibration_checkpoints are append-only');
END;

CREATE TRIGGER calibration_audit_events_no_update
BEFORE UPDATE ON calibration_audit_events
BEGIN
    SELECT RAISE(ABORT, 'calibration_audit_events are append-only');
END;

CREATE TRIGGER calibration_audit_events_no_delete
BEFORE DELETE ON calibration_audit_events
BEGIN
    SELECT RAISE(ABORT, 'calibration_audit_events are append-only');
END;
