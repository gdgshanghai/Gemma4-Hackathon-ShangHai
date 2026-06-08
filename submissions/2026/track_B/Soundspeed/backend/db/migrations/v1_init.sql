-- Soundspeed 迁移 v1：初始化全量 schema
-- 内容与 backend/db/schema.sql 相同，供 migration runner 执行。
-- timestamp DEFAULT 使用 CAST(strftime('%s', 'now') AS REAL)（整数秒精度），
-- 兼容 Python 3.11 自带的 SQLite 3.39.4。
-- 若运行环境 sqlite3.sqlite_version >= 3.42，可改为 unixepoch('now', 'subsec') 获得小数秒精度。
-- per-connection PRAGMA 由 Python 代码管理，不放此文件。

-- ── scenes 表 ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scenes (
    scene_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_code  TEXT    NOT NULL,
    description TEXT,
    shoot_date  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 0
        CHECK (is_active IN (0, 1)),
    created_at  REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_scenes_scene_code
    ON scenes (scene_code);

CREATE INDEX IF NOT EXISTS ix_scenes_is_active
    ON scenes (is_active);

-- ── takes 表 ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS takes (
    take_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id        INTEGER NOT NULL
        REFERENCES scenes (scene_id) ON DELETE RESTRICT,
    take_number     INTEGER NOT NULL,
    shot            TEXT,
    start_ts        REAL    NOT NULL,
    end_ts          REAL,
    status          TEXT    NOT NULL DEFAULT 'tbd'
        CHECK (status IN ('keeper', 'ng', 'hold', 'tbd')),
    performer_issues TEXT,
    audio_quality   TEXT,
    script_diff     TEXT,
    notes           TEXT,
    created_at      REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    updated_at      REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    UNIQUE (scene_id, take_number)
);

CREATE INDEX IF NOT EXISTS ix_takes_scene_id
    ON takes (scene_id);

CREATE INDEX IF NOT EXISTS ix_takes_scene_take
    ON takes (scene_id, take_number);

CREATE INDEX IF NOT EXISTS ix_takes_status
    ON takes (status);

-- ── take_events 表 ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS take_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    take_id     INTEGER NOT NULL
        REFERENCES takes (take_id) ON DELETE CASCADE,
    event_type  TEXT    NOT NULL,
    ts          REAL    NOT NULL,
    payload     TEXT    NOT NULL DEFAULT '{}'
        CHECK (json_valid(payload)),
    created_at  REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

CREATE INDEX IF NOT EXISTS ix_take_events_take_id
    ON take_events (take_id);

CREATE INDEX IF NOT EXISTS ix_take_events_take_type_ts
    ON take_events (take_id, event_type, ts);

-- ── scripts 表 ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scripts (
    script_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id    INTEGER NOT NULL
        REFERENCES scenes (scene_id) ON DELETE RESTRICT,
    raw_text    TEXT    NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

CREATE INDEX IF NOT EXISTS ix_scripts_scene_id
    ON scripts (scene_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_scripts_scene_version
    ON scripts (scene_id, version);

-- ── script_lines 表 ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS script_lines (
    line_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id       INTEGER NOT NULL
        REFERENCES scripts (script_id) ON DELETE CASCADE,
    line_no         INTEGER NOT NULL,
    character       TEXT,
    text            TEXT    NOT NULL,
    created_at      REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    UNIQUE (script_id, line_no)
);

CREATE INDEX IF NOT EXISTS ix_script_lines_script_id
    ON script_lines (script_id);

CREATE INDEX IF NOT EXISTS ix_script_lines_character
    ON script_lines (character);

-- ── take_line_matches 表 ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS take_line_matches (
    match_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    take_id         INTEGER NOT NULL
        REFERENCES takes (take_id) ON DELETE CASCADE,
    line_id         INTEGER NOT NULL
        REFERENCES script_lines (line_id) ON DELETE CASCADE,
    diff_type       TEXT    NOT NULL
        CHECK (diff_type IN ('match', 'missing', 'substitution', 'insertion')),
    payload         TEXT    NOT NULL DEFAULT '{}'
        CHECK (json_valid(payload)),
    created_at      REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

CREATE INDEX IF NOT EXISTS ix_take_line_matches_take_id
    ON take_line_matches (take_id);

CREATE INDEX IF NOT EXISTS ix_take_line_matches_line_id
    ON take_line_matches (line_id);

-- ── transcript_segments 表 ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS transcript_segments (
    segment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    take_id         INTEGER NOT NULL
        REFERENCES takes (take_id) ON DELETE CASCADE,
    ch              INTEGER NOT NULL
        CHECK (ch IN (1, 2)),
    speaker         TEXT,
    text            TEXT    NOT NULL,
    start_frame     INTEGER NOT NULL,
    end_frame       INTEGER NOT NULL,
    created_at      REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    CHECK (end_frame > start_frame)
);

CREATE INDEX IF NOT EXISTS ix_transcript_take_ch
    ON transcript_segments (take_id, ch);

CREATE INDEX IF NOT EXISTS ix_transcript_take_speaker
    ON transcript_segments (take_id, speaker);

CREATE INDEX IF NOT EXISTS ix_transcript_frames
    ON transcript_segments (start_frame, end_frame);

-- ── audit_log 表 ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    payload     TEXT    NOT NULL DEFAULT '{}'
        CHECK (json_valid(payload)),
    ts          REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

CREATE INDEX IF NOT EXISTS ix_audit_log_actor
    ON audit_log (actor);

CREATE INDEX IF NOT EXISTS ix_audit_log_ts
    ON audit_log (ts);

-- ── active_observers 表 ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS active_observers (
    connection_id   TEXT    PRIMARY KEY,
    name            TEXT    NOT NULL,
    joined_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

-- ── FTS5 虚拟表 ──────────────────────────────────────────────────────────────

CREATE VIRTUAL TABLE IF NOT EXISTS script_lines_fts
    USING fts5(
        text,
        character UNINDEXED,
        content='script_lines',
        content_rowid='line_id',
        tokenize='trigram'
    );

-- ── FTS5 同步触发器 ──────────────────────────────────────────────────────────

CREATE TRIGGER IF NOT EXISTS tg_script_lines_fts_insert
    AFTER INSERT ON script_lines
BEGIN
    INSERT INTO script_lines_fts (rowid, text, character)
        VALUES (NEW.line_id, NEW.text, NEW.character);
END;

CREATE TRIGGER IF NOT EXISTS tg_script_lines_fts_delete
    BEFORE DELETE ON script_lines
BEGIN
    INSERT INTO script_lines_fts (script_lines_fts, rowid, text, character)
        VALUES ('delete', OLD.line_id, OLD.text, OLD.character);
END;

CREATE TRIGGER IF NOT EXISTS tg_script_lines_fts_update
    AFTER UPDATE ON script_lines
BEGIN
    INSERT INTO script_lines_fts (script_lines_fts, rowid, text, character)
        VALUES ('delete', OLD.line_id, OLD.text, OLD.character);
    INSERT INTO script_lines_fts (rowid, text, character)
        VALUES (NEW.line_id, NEW.text, NEW.character);
END;

PRAGMA user_version = 1;
