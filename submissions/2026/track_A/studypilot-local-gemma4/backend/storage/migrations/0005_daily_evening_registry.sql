CREATE TABLE daily_evening_sessions (
    session_date TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE
        REFERENCES evening_sessions(id) ON DELETE RESTRICT,
    registered_at TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO daily_evening_sessions (
    session_date,
    session_id,
    registered_at
)
SELECT
    candidate.session_date,
    candidate.id,
    candidate.created_at
FROM evening_sessions AS candidate
WHERE candidate.rowid = (
    SELECT winner.rowid
    FROM evening_sessions AS winner
    WHERE winner.session_date = candidate.session_date
    ORDER BY winner.created_at DESC, winner.rowid DESC
    LIMIT 1
);
