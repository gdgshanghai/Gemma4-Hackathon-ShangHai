-- 迁移 v4：takes 表 shot 列改 NOT NULL DEFAULT ''，唯一约束扩成四元
-- UNIQUE(scene_id, take_number, take_suffix) → UNIQUE(scene_id, shot, take_number, take_suffix)
-- 旧 NULL shot → '' (COALESCE)；原有行全部仍合法，不需要重新编号。
-- 整表重建套路（12 步）：PRAGMA OFF → 建新表 → copy → DROP → RENAME → check → ON
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
        CHECK (status IN ('keeper', 'ng', 'hold', 'tbd')),
    performer_issues TEXT,
    audio_quality    TEXT,
    script_diff      TEXT,
    notes            TEXT,
    deleted_at       REAL,
    created_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    updated_at       REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    UNIQUE (scene_id, shot, take_number, take_suffix)
);

INSERT INTO takes_new (
    take_id, scene_id, shot, take_number, take_suffix, start_ts, end_ts,
    status, performer_issues, audio_quality, script_diff, notes,
    deleted_at, created_at, updated_at
)
SELECT
    take_id, scene_id, COALESCE(shot, ''), take_number, take_suffix, start_ts, end_ts,
    status, performer_issues, audio_quality, script_diff, notes,
    deleted_at, created_at, updated_at
FROM takes;

DROP TABLE takes;
ALTER TABLE takes_new RENAME TO takes;

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;

PRAGMA user_version = 4;
