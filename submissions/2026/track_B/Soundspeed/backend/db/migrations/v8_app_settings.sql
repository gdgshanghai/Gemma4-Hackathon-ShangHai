-- v8: app_settings KV 表（设备持久化等应用级设置）
PRAGMA user_version = 8;

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
