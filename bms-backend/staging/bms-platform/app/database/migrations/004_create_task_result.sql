-- Task results table (Celery task outcomes)

CREATE TABLE IF NOT EXISTS task_results (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    result JSONB,
    error TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The below index will be used to optimize query performance for the task_results table. It allows for efficient retrieval of tasks by their ID and status.
CREATE INDEX IF NOT EXISTS idx_task_results_task_id ON task_results (task_id);
CREATE INDEX IF NOT EXISTS idx_task_results_status ON task_results (status);
