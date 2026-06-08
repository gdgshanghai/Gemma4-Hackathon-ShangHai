-- Soundspeed SQLite schema v1
-- 9 张表 + FTS5 虚拟表 + 三个同步触发器
-- timestamp DEFAULT 使用 CAST(strftime('%s', 'now') AS REAL)（整数秒精度），
-- 兼容 Python 3.11 自带的 SQLite 3.39.4。
-- 若运行环境 sqlite3.sqlite_version >= 3.42，可改为 unixepoch('now', 'subsec') 获得小数秒精度。
-- per-connection PRAGMA (foreign_keys / journal_mode / busy_timeout) 由 Python 代码管理，不放此文件。

-- ── scenes 表 ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scenes (
    scene_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_code  TEXT    NOT NULL,                   -- 场次编号，如 "Scene_3A"
    description TEXT,                               -- 场次说明（可选）
    shoot_date  TEXT,                               -- 拍摄日期，ISO 8601 格式（YYYY-MM-DD）
    is_active   INTEGER NOT NULL DEFAULT 0          -- 1 = 当前活跃场次，0 = 非活跃
        CHECK (is_active IN (0, 1)),
    created_at  REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    int_ext     TEXT,                               -- 内外景：室内 / 室外（slugline 结构化，v2）
    time_of_day TEXT,                               -- 时间：日 / 夜 / 晨 …（slugline 结构化，v2）
    location    TEXT                                -- 场景地点：街道 / 咖啡馆 …（slugline 结构化，v2）
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_scenes_scene_code
    ON scenes (scene_code);

CREATE INDEX IF NOT EXISTS ix_scenes_is_active
    ON scenes (is_active);

-- ── takes 表 ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS takes (
    take_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id         INTEGER NOT NULL
        REFERENCES scenes (scene_id) ON DELETE RESTRICT,
    shot             TEXT    NOT NULL DEFAULT '',    -- 镜次编号，如 "Shot_2B"；'' 表示无镜（v4）
    take_number      INTEGER NOT NULL,               -- 本场次内的 take 编号，从 1 起
    take_suffix      TEXT    NOT NULL DEFAULT '',    -- 后缀，冲突时追加 '+' / '++'（v3）
    start_ts         REAL    NOT NULL,               -- take 开始 Unix 时间戳（秒，含小数）
    end_ts           REAL,                           -- take 结束 Unix 时间戳，进行中时为 NULL
    status           TEXT    NOT NULL DEFAULT 'tbd'
        CHECK (status IN ('pass', 'ng', 'keep', 'tbd')),
    performer_issues TEXT,                           -- NP 解析输出，JSON 文本，可选
    audio_quality    TEXT,                           -- NP 解析输出，如 'clean' / 'noisy' / 'clipped'
    script_diff      TEXT,                           -- L2 输出，JSON 文本，剧本偏差报告
    notes            TEXT,                           -- Ch2 原文拼接 + 候补 note，可选
    deleted_at       REAL,                           -- 软删时间戳，NULL 表示未删除（v3）
    created_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    updated_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    UNIQUE (scene_id, shot, take_number, take_suffix)
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
    event_type  TEXT    NOT NULL,                   -- 事件类型，见约定值
    ts          REAL    NOT NULL,                   -- 事件发生时间戳（Unix 秒，含小数）
    payload     TEXT    NOT NULL DEFAULT '{}'       -- JSON 文本，事件结构化载荷
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
    raw_text    TEXT    NOT NULL,                   -- 剧本原文（纯文本或分行文本）
    version     INTEGER NOT NULL DEFAULT 1,         -- 同场次版本号，从 1 起递增
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
    line_no         INTEGER NOT NULL,               -- 行号，同 script 内从 1 起
    character       TEXT,                           -- 角色名（NULL 表示舞台指示行）
    text            TEXT    NOT NULL,               -- 台词文本
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
    diff_type       TEXT    NOT NULL                -- 偏差类型
        CHECK (diff_type IN ('match', 'missing', 'substitution', 'insertion')),
    payload         TEXT    NOT NULL DEFAULT '{}'   -- JSON 文本，偏差明细
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
    take_id         INTEGER NOT NULL                -- 必须关联到 take
        REFERENCES takes (take_id) ON DELETE CASCADE,
    ch              INTEGER NOT NULL                -- 声道，1 或 2（一基命名）
        CHECK (ch IN (1, 2)),
    speaker         TEXT,                           -- 说话人标签，NULL 表示未知或未分离
    text            TEXT    NOT NULL,               -- 转录文本
    start_frame     INTEGER NOT NULL,               -- 毫秒（秒 × 1000 取整）⚠ 字段名沿用历史命名
    end_frame       INTEGER NOT NULL,               -- 毫秒（秒 × 1000 取整）⚠ 字段名沿用历史命名
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
    actor       TEXT    NOT NULL,                   -- 操作发起方，如 'orchestrator' / 'user'
    action      TEXT    NOT NULL,                   -- 操作描述，如 'take.start' / 'script.upload'
    payload     TEXT    NOT NULL DEFAULT '{}'       -- JSON 文本，操作明细
        CHECK (json_valid(payload)),
    ts          REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

CREATE INDEX IF NOT EXISTS ix_audit_log_actor
    ON audit_log (actor);

CREATE INDEX IF NOT EXISTS ix_audit_log_ts
    ON audit_log (ts);

-- ── active_observers 表 ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS active_observers (
    connection_id   TEXT    PRIMARY KEY,            -- WebSocket 连接 ID（UUID 或 session token）
    name            TEXT    NOT NULL,               -- 观察者自填名字（导演 / 场记）
    joined_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

-- ── FTS5 虚拟表 ──────────────────────────────────────────────────────────────

CREATE VIRTUAL TABLE IF NOT EXISTS script_lines_fts
    USING fts5(
        text,                           -- 被索引的列，对应 script_lines.text
        character UNINDEXED,            -- 不参与检索，只做 retrieve
        content='script_lines',         -- content table 模式，不重复存文本
        content_rowid='line_id',        -- 关联 script_lines 主键
        tokenize='trigram'
    );

-- ── FTS5 同步触发器 ──────────────────────────────────────────────────────────

-- INSERT 触发器
CREATE TRIGGER IF NOT EXISTS tg_script_lines_fts_insert
    AFTER INSERT ON script_lines
BEGIN
    INSERT INTO script_lines_fts (rowid, text, character)
        VALUES (NEW.line_id, NEW.text, NEW.character);
END;

-- DELETE 触发器
CREATE TRIGGER IF NOT EXISTS tg_script_lines_fts_delete
    BEFORE DELETE ON script_lines
BEGIN
    INSERT INTO script_lines_fts (script_lines_fts, rowid, text, character)
        VALUES ('delete', OLD.line_id, OLD.text, OLD.character);
END;

-- UPDATE 触发器（先删旧 FTS 行，再插新 FTS 行）
CREATE TRIGGER IF NOT EXISTS tg_script_lines_fts_update
    AFTER UPDATE ON script_lines
BEGIN
    INSERT INTO script_lines_fts (script_lines_fts, rowid, text, character)
        VALUES ('delete', OLD.line_id, OLD.text, OLD.character);
    INSERT INTO script_lines_fts (rowid, text, character)
        VALUES (NEW.line_id, NEW.text, NEW.character);
END;

PRAGMA user_version = 4;
