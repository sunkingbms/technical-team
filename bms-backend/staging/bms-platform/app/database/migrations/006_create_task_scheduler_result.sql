-- Task scheduler results table (Celery Beat schedules)

CREATE TABLE IF NOT EXISTS task_scheduler_results (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) NOT NULL,
    job JSONB NOT NULL,
    next_run TIMESTAMPTZ NOT NULL,
    last_run TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The below index will be used to optimize query performance for the task_scheduler_results table. It allows for efficient retrieval of tasks by their ID.
CREATE INDEX IF NOT EXISTS idx_task_scheduler_results_task_id ON task_scheduler_results (task_id);
