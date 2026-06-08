-- v7_take_speakers.sql: take ↔ 已注册演员(speaker) 关联表
-- 2026-06-03（原 v5，与 2.x v3/v4 撞号，merge 后重排到 v7）
-- 建 take 时挂"本 take 在场演员"列表；diarization 回填只在这些演员里匹配声纹。
-- 空关联（没挂演员）→ diarization 全部出匿名"说话人N"。

PRAGMA user_version = 7;

CREATE TABLE IF NOT EXISTS take_speakers (
    take_id    INTEGER NOT NULL REFERENCES takes (take_id) ON DELETE CASCADE,
    speaker_id INTEGER NOT NULL REFERENCES speakers (speaker_id) ON DELETE CASCADE,
    PRIMARY KEY (take_id, speaker_id)
);

CREATE INDEX IF NOT EXISTS ix_take_speakers_take ON take_speakers (take_id);
