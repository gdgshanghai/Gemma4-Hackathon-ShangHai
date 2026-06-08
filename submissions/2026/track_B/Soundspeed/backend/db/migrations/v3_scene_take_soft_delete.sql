-- 迁移 v3：takes 表加软删（deleted_at）+ 后缀（take_suffix）+ 三元 UNIQUE
-- 原 UNIQUE(scene_id, take_number) 是内联约束，SQLite 不支持 ALTER DROP CONSTRAINT，
-- 必须整表重建（标准 12 步）。
-- per-connection PRAGMA（foreign_keys / journal_mode / busy_timeout）由 Python 代码管理，不放此文件。

PRAGMA foreign_keys = OFF;

CREATE TABLE takes_new (
    take_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id         INTEGER NOT NULL
        REFERENCES scenes (scene_id) ON DELETE RESTRICT,
    take_number      INTEGER NOT NULL,
    take_suffix      TEXT    NOT NULL DEFAULT '',
    shot             TEXT,
    start_ts         REAL    NOT NULL,
    end_ts           REAL,
    status           TEXT    NOT NULL DEFAULT 'tbd'
        CHECK (status IN ('keeper', 'ng', 'hold', 'tbd')),
    performer_issues TEXT,
    audio_quality    TEXT,
    script_diff      TEXT,
    notes            TEXT,
    deleted_at       REAL,
    created_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    updated_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    UNIQUE (scene_id, take_number, take_suffix)
);

INSERT INTO takes_new (
    take_id, scene_id, take_number, take_suffix, shot, start_ts, end_ts,
    status, performer_issues, audio_quality, script_diff, notes,
    deleted_at, created_at, updated_at
)
SELECT
    take_id, scene_id, take_number, '', shot, start_ts, end_ts,
    status, performer_issues, audio_quality, script_diff, notes,
    NULL, created_at, updated_at
FROM takes;

DROP TABLE takes;
ALTER TABLE takes_new RENAME TO takes;

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;

PRAGMA user_version = 3;
