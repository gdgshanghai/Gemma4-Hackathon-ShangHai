ALTER TABLE task_items
ADD COLUMN task_type TEXT;

ALTER TABLE task_items
ADD COLUMN must_do_tonight INTEGER NOT NULL DEFAULT 0
    CHECK (must_do_tonight IN (0, 1));

ALTER TABLE task_items
ADD COLUMN child_estimate_minutes INTEGER
    CHECK (child_estimate_minutes >= 0);

ALTER TABLE task_items
ADD COLUMN estimate_source TEXT NOT NULL DEFAULT 'domain_default'
    CHECK (estimate_source IN (
        'history_p80',
        'parent_range',
        'child_adjusted',
        'domain_default'
    ));

ALTER TABLE task_items
ADD COLUMN estimate_confidence TEXT NOT NULL DEFAULT 'low'
    CHECK (estimate_confidence IN ('low', 'medium', 'high'));

ALTER TABLE task_items
ADD COLUMN avoidance_score INTEGER NOT NULL DEFAULT 0
    CHECK (avoidance_score BETWEEN 0 AND 3);

ALTER TABLE task_items
ADD COLUMN preference_score INTEGER NOT NULL DEFAULT 0
    CHECK (preference_score BETWEEN 0 AND 3);
