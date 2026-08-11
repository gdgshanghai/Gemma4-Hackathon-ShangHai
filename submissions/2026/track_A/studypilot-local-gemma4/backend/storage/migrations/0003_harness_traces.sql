CREATE TABLE harness_traces (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL UNIQUE,
    session_id TEXT,
    workflow_phase TEXT NOT NULL CHECK (workflow_phase IN (
        'intake_save', 'coverage_compare', 'inventory_confirm', 'context_read',
        'candidates_build', 'plan_commit', 'profile_propose', 'profile_commit',
        'evening_close', 'final_narration'
    )),
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    expected_version INTEGER NOT NULL CHECK (expected_version >= 0),
    caller_idempotency_sha256 TEXT CHECK (
        caller_idempotency_sha256 IS NULL
        OR length(caller_idempotency_sha256) = 64
    ),
    harness_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    final_error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    model_calls INTEGER NOT NULL DEFAULT 0 CHECK (model_calls >= 0),
    tool_rounds INTEGER NOT NULL DEFAULT 0 CHECK (tool_rounds >= 0),
    handler_executions INTEGER NOT NULL DEFAULT 0 CHECK (handler_executions >= 0),
    cache_hits INTEGER NOT NULL DEFAULT 0 CHECK (cache_hits >= 0),
    schema_repair_used INTEGER NOT NULL DEFAULT 0
        CHECK (schema_repair_used IN (0, 1))
);

INSERT INTO harness_traces (
    id, trace_id, session_id, workflow_phase, actor, role, expected_version,
    caller_idempotency_sha256, harness_version, status, final_error_code,
    started_at, completed_at, model_calls, tool_rounds, handler_executions,
    cache_hits, schema_repair_used
)
SELECT
    'legacy-llm-' || llm.id,
    'legacy-llm-' || llm.id,
    llm.session_id,
    'final_narration',
    'legacy',
    'system',
    0,
    NULL,
    'legacy-v0',
    CASE
        WHEN llm.status = 'failed' OR EXISTS (
            SELECT 1 FROM tool_runs tool
            WHERE tool.llm_run_id = llm.id AND tool.status = 'failed'
        ) THEN 'failed'
        WHEN llm.status = 'started' OR EXISTS (
            SELECT 1 FROM tool_runs tool
            WHERE tool.llm_run_id = llm.id AND tool.status = 'started'
        ) THEN 'started'
        ELSE 'completed'
    END,
    CASE
        WHEN llm.status = 'failed' THEN llm.error_code
        ELSE (
            SELECT tool.error_code FROM tool_runs tool
            WHERE tool.llm_run_id = llm.id AND tool.status = 'failed'
            ORDER BY tool.started_at, tool.id LIMIT 1
        )
    END,
    llm.started_at,
    CASE
        WHEN llm.status = 'started' OR EXISTS (
            SELECT 1 FROM tool_runs tool
            WHERE tool.llm_run_id = llm.id AND tool.status = 'started'
        ) THEN NULL
        ELSE CASE
            WHEN llm.completed_at IS NULL THEN (
                SELECT MAX(tool.completed_at) FROM tool_runs tool
                WHERE tool.llm_run_id = llm.id
            )
            WHEN (
                SELECT MAX(tool.completed_at) FROM tool_runs tool
                WHERE tool.llm_run_id = llm.id
            ) IS NULL THEN llm.completed_at
            WHEN (
                SELECT MAX(tool.completed_at) FROM tool_runs tool
                WHERE tool.llm_run_id = llm.id
            ) > llm.completed_at THEN (
                SELECT MAX(tool.completed_at) FROM tool_runs tool
                WHERE tool.llm_run_id = llm.id
            )
            ELSE llm.completed_at
        END
    END,
    1,
    (SELECT COUNT(*) FROM tool_runs tool WHERE tool.llm_run_id = llm.id),
    (SELECT COUNT(*) FROM tool_runs tool
     WHERE tool.llm_run_id = llm.id AND tool.status = 'completed'),
    0,
    0
FROM llm_runs llm;

INSERT INTO harness_traces (
    id, trace_id, session_id, workflow_phase, actor, role, expected_version,
    caller_idempotency_sha256, harness_version, status, final_error_code,
    started_at, completed_at, model_calls, tool_rounds, handler_executions,
    cache_hits, schema_repair_used
)
SELECT
    'legacy-tool-' || tool.id,
    'legacy-tool-' || tool.id,
    tool.session_id,
    'final_narration',
    'legacy',
    'system',
    0,
    NULL,
    'legacy-v0',
    tool.status,
    tool.error_code,
    tool.started_at,
    tool.completed_at,
    0,
    1,
    CASE WHEN tool.status = 'completed' THEN 1 ELSE 0 END,
    0,
    0
FROM tool_runs tool
WHERE tool.llm_run_id IS NULL;

CREATE TABLE llm_runs_v3 (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES harness_traces(trace_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
    session_id TEXT,
    model TEXT NOT NULL,
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    generation_parameters_json TEXT NOT NULL CHECK (json_valid(generation_parameters_json)),
    response_json TEXT CHECK (response_json IS NULL OR json_valid(response_json)),
    finish_reason TEXT,
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    latency_ms INTEGER CHECK (latency_ms >= 0),
    UNIQUE (trace_id, ordinal)
);

INSERT INTO llm_runs_v3 (
    id, trace_id, ordinal, session_id, model, request_sha256,
    generation_parameters_json, response_json, finish_reason, status,
    error_code, started_at, completed_at, latency_ms
)
SELECT
    id, 'legacy-llm-' || id, 1, session_id, model, request_sha256,
    '{}', response_json, NULL, status, error_code, started_at, completed_at, latency_ms
FROM llm_runs;

CREATE TABLE tool_runs_v3 (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES harness_traces(trace_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
    session_id TEXT,
    llm_run_id TEXT REFERENCES llm_runs_v3(id) ON DELETE RESTRICT,
    tool_name TEXT NOT NULL,
    call_id TEXT NOT NULL,
    arguments_json TEXT NOT NULL CHECK (json_valid(arguments_json)),
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    cache_hit INTEGER NOT NULL DEFAULT 0 CHECK (cache_hit IN (0, 1)),
    handler_executed INTEGER NOT NULL DEFAULT 0 CHECK (handler_executed IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    latency_ms INTEGER CHECK (latency_ms >= 0),
    UNIQUE (trace_id, ordinal),
    UNIQUE (llm_run_id, call_id)
);

INSERT INTO tool_runs_v3 (
    id, trace_id, ordinal, session_id, llm_run_id, tool_name, call_id,
    arguments_json, result_json, cache_hit, handler_executed, status,
    error_code, started_at, completed_at, latency_ms
)
SELECT
    tool.id,
    CASE
        WHEN tool.llm_run_id IS NULL THEN 'legacy-tool-' || tool.id
        ELSE 'legacy-llm-' || tool.llm_run_id
    END,
    ROW_NUMBER() OVER (
        PARTITION BY CASE
            WHEN tool.llm_run_id IS NULL THEN 'legacy-tool-' || tool.id
            ELSE 'legacy-llm-' || tool.llm_run_id
        END
        ORDER BY tool.started_at, tool.id
    ),
    tool.session_id,
    tool.llm_run_id,
    tool.tool_name,
    tool.call_id,
    tool.arguments_json,
    tool.result_json,
    0,
    CASE WHEN tool.status = 'completed' THEN 1 ELSE 0 END,
    tool.status,
    tool.error_code,
    tool.started_at,
    tool.completed_at,
    tool.latency_ms
FROM tool_runs tool;

DROP TABLE tool_runs;
DROP TABLE llm_runs;
ALTER TABLE llm_runs_v3 RENAME TO llm_runs;
ALTER TABLE tool_runs_v3 RENAME TO tool_runs;

CREATE TABLE harness_trace_events (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES harness_traces(trace_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
    event_kind TEXT NOT NULL CHECK (event_kind IN ('llm', 'tool')),
    llm_run_id TEXT REFERENCES llm_runs(id) ON DELETE RESTRICT,
    tool_run_id TEXT REFERENCES tool_runs(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    UNIQUE (trace_id, ordinal),
    CHECK (
        (event_kind = 'llm' AND llm_run_id IS NOT NULL AND tool_run_id IS NULL)
        OR
        (event_kind = 'tool' AND tool_run_id IS NOT NULL AND llm_run_id IS NULL)
    )
);

WITH all_events AS (
    SELECT trace_id, 'llm' AS event_kind, id AS run_id, started_at AS created_at,
           id AS llm_run_id, NULL AS tool_run_id, 0 AS kind_rank
    FROM llm_runs
    UNION ALL
    SELECT trace_id, 'tool' AS event_kind, id AS run_id, started_at AS created_at,
           NULL AS llm_run_id, id AS tool_run_id, 1 AS kind_rank
    FROM tool_runs
), numbered AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY trace_id
        ORDER BY created_at, kind_rank, run_id
    ) AS event_ordinal
    FROM all_events
)
INSERT INTO harness_trace_events (
    id, trace_id, ordinal, event_kind, llm_run_id, tool_run_id, created_at
)
SELECT
    'legacy-event-' || trace_id || '-' || printf('%04d', event_ordinal),
    trace_id,
    event_ordinal,
    event_kind,
    llm_run_id,
    tool_run_id,
    created_at
FROM numbered;

CREATE INDEX idx_harness_traces_session ON harness_traces(session_id, started_at);
CREATE INDEX idx_harness_trace_events_trace
    ON harness_trace_events(trace_id, ordinal);
CREATE INDEX idx_llm_runs_session ON llm_runs(session_id, started_at);
CREATE INDEX idx_llm_runs_trace ON llm_runs(trace_id, ordinal);
CREATE INDEX idx_tool_runs_session ON tool_runs(session_id, started_at);
CREATE INDEX idx_tool_runs_trace ON tool_runs(trace_id, ordinal);
