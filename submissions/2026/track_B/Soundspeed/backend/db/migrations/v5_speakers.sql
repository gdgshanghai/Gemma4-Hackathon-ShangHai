-- v5_speakers.sql: 新增跨 take 声纹台账表
-- 2026-06-03（原 v3，与 2.x v3/v4 撞号，merge 后重排到 v5）

PRAGMA user_version = 5;

CREATE TABLE IF NOT EXISTS speakers (
    speaker_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT    NOT NULL,          -- "说话人1" 或演员姓名（可更新）
    embedding    BLOB,                      -- numpy float32 数组的 bytes，可 NULL
    sample_count INTEGER NOT NULL DEFAULT 1,
    scope_key    TEXT,                      -- 预留：按拍摄/会话分组（当前 NULL = 全局）
    created_at   REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL)),
    updated_at   REAL    NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);
