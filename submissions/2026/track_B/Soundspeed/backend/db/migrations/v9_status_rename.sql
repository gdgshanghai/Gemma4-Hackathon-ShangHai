-- 迁移 v9：take.status / note.category 枚举正名 keeper→keep、hold→pass
-- 语义对齐 UI Mark：keep=「保」(KEEP)、pass=「过」(PASS)。
-- 旧名拧巴：keeper 是「保/KEEP」却叫 keeper、hold 是「过/PASS」却叫 hold（hold 字面又像 keep）。
-- 本次扶正名字、**不改含义**：原 keeper(保)→keep、原 hold(过)→pass。ng / tbd 不变。
-- CHECK 约束不能 ALTER，故整表重建（同 v4 的 12 步套路）；
-- 历史 take_events payload（manual.mark.status / manual.note.category）+ takes.notes 聚合串一并映射。
-- per-connection PRAGMA（foreign_keys / journal_mode / busy_timeout）由 Python 代码管理，不放此文件。

PRAGMA foreign_keys = OFF;

CREATE TABLE takes_new (
    take_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id         INTEGER NOT NULL
        REFERENCES scenes (scene_id) ON DELETE RESTRICT,
    shot             TEXT    NOT NULL DEFAULT '',
    take_number      INTEGER NOT NULL,
    take_suffix      TEXT    NOT NULL DEFAULT '',
    start_ts         REAL    NOT NULL,
    end_ts           REAL,
    status           TEXT    NOT NULL DEFAULT 'tbd'
        CHECK (status IN ('pass', 'ng', 'keep', 'tbd')),
    performer_issues TEXT,
    audio_quality    TEXT,
    script_diff      TEXT,
    notes            TEXT,
    deleted_at       REAL,
    created_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    updated_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    structured_transcript TEXT,
    UNIQUE (scene_id, shot, take_number, take_suffix)
);

INSERT INTO takes_new (
    take_id, scene_id, shot, take_number, take_suffix, start_ts, end_ts,
    status, performer_issues, audio_quality, script_diff, notes,
    deleted_at, created_at, updated_at, structured_transcript
)
SELECT
    take_id, scene_id, shot, take_number, take_suffix, start_ts, end_ts,
    CASE status WHEN 'keeper' THEN 'keep' WHEN 'hold' THEN 'pass' ELSE status END,
    performer_issues, audio_quality, script_diff,
    -- notes 聚合串里的 @keeper/@hold（insert_note 重建格式 "[ts] @cat …"）一并正名
    REPLACE(REPLACE(notes, '@keeper', '@keep'), '@hold', '@pass'),
    deleted_at, created_at, updated_at, structured_transcript
FROM takes;

DROP TABLE takes;
ALTER TABLE takes_new RENAME TO takes;

-- 历史 take_events payload：JSON 文本里精确匹配 "status"/"category" 值（json.dumps 默认 ": " 分隔），
-- 用 REPLACE 字符串替换，不依赖 SQLite json1 扩展。keeper→keep、hold→pass，二者无重叠。
UPDATE take_events SET payload =
    REPLACE(REPLACE(payload, '"status": "keeper"', '"status": "keep"'), '"status": "hold"', '"status": "pass"')
    WHERE event_type = 'manual.mark';
UPDATE take_events SET payload =
    REPLACE(REPLACE(payload, '"category": "keeper"', '"category": "keep"'), '"category": "hold"', '"category": "pass"')
    WHERE event_type = 'manual.note';

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;

PRAGMA user_version = 9;
