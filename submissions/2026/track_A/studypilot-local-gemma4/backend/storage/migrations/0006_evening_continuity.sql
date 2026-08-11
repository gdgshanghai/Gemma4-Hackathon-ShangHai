ALTER TABLE evening_sessions
ADD COLUMN planning_date TEXT;

UPDATE evening_sessions
SET planning_date = session_date
WHERE planning_date IS NULL;

CREATE TABLE assignment_obligations (
    id TEXT PRIMARY KEY,
    origin_session_id TEXT NOT NULL
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    subject TEXT,
    task_type TEXT,
    deadline_text TEXT,
    due_at TEXT,
    latest_safe_evening TEXT,
    planned_evening_date TEXT,
    remaining_percent INTEGER NOT NULL DEFAULT 100
        CHECK (remaining_percent BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'completed')),
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX assignment_obligations_open_schedule_idx
ON assignment_obligations(status, planned_evening_date, due_at);

CREATE TABLE assignment_schedule_events (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL
        REFERENCES assignment_obligations(id) ON DELETE RESTRICT,
    session_id TEXT NOT NULL
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    from_evening_date TEXT,
    to_evening_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX assignment_schedule_events_assignment_idx
ON assignment_schedule_events(assignment_id, created_at);

ALTER TABLE task_items
ADD COLUMN assignment_id TEXT
    REFERENCES assignment_obligations(id) ON DELETE RESTRICT;

ALTER TABLE task_items
ADD COLUMN deadline_text TEXT;

ALTER TABLE task_items
ADD COLUMN remaining_percent INTEGER NOT NULL DEFAULT 100
    CHECK (remaining_percent BETWEEN 0 AND 100);

ALTER TABLE task_items
ADD COLUMN planning_bucket TEXT NOT NULL DEFAULT 'tonight_required'
    CHECK (planning_bucket IN (
        'tonight_required', 'tonight_advance', 'future_scheduled'
    ));

