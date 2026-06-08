-- 迁移 v2：scenes 表加 slugline 结构化列
-- 三列均 nullable TEXT，无 CHECK（值开放，前端自由文本）

ALTER TABLE scenes ADD COLUMN int_ext     TEXT;  -- 内外景：室内 / 室外
ALTER TABLE scenes ADD COLUMN time_of_day TEXT;  -- 时间：日 / 夜 / 晨 …
ALTER TABLE scenes ADD COLUMN location    TEXT;  -- 场景地点：街道 / 咖啡馆 …

PRAGMA user_version = 2;
