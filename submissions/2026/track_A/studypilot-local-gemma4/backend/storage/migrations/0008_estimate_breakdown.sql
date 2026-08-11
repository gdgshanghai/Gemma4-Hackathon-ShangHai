ALTER TABLE task_items
ADD COLUMN estimate_breakdown_json TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(estimate_breakdown_json));

ALTER TABLE task_items
ADD COLUMN estimate_signature TEXT;

ALTER TABLE assignment_obligations
ADD COLUMN estimate_breakdown_json TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(estimate_breakdown_json));

ALTER TABLE assignment_obligations
ADD COLUMN estimate_signature TEXT;
