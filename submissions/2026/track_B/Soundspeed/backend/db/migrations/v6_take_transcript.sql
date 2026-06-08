-- v6_take_transcript.sql: takes 增加结构化转录列（ASR + 说话人 整合后的合并 JSON）
-- 2026-06-03（原 v4，与 2.x v3/v4 撞号，merge 后重排到 v6；必须排在 2.x v4 重建 takes 之后）
-- diarization 回填完成后，把 ch1 对白（带 speaker + 时间戳）整合成结构化 JSON 写入此列，
-- 作为导出 / 场记单的统一来源。ch2 note 区与 L2 接入留后续 ticket。

PRAGMA user_version = 6;

ALTER TABLE takes ADD COLUMN structured_transcript TEXT;
