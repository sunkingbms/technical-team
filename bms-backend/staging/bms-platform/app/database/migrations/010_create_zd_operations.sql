-- An operation is one run of a process (submitted data + execution lifecycle)

CREATE TABLE IF NOT EXISTS zd_operations (
    id                  SERIAL PRIMARY KEY,
    zendesk_instance_id INTEGER NOT NULL REFERENCES zd_instances(id),
    process_id          INTEGER NOT NULL REFERENCES zd_processes(id),
    status              VARCHAR(50) NOT NULL DEFAULT 'Pending'
                            CHECK (status IN ('Pending', 'queued', 'working', 'completed', 'failed')),
    item_count          INTEGER NOT NULL DEFAULT 0,
    processed_count     INTEGER NOT NULL DEFAULT 0,
    mappings            JSONB,          -- {field_id: col_index} or {delete_column: col_index}
    headers             JSONB,          -- ordered list of column names from the sheet
    start_date          DATE,
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zd_operations_status     ON zd_operations(status);
CREATE INDEX IF NOT EXISTS idx_zd_operations_start_date ON zd_operations(start_date);
CREATE INDEX IF NOT EXISTS idx_zd_operations_instance   ON zd_operations(zendesk_instance_id);


-- Row-level data imported from Google Sheets (up to 20 columns, generic col_0..col_19)

CREATE TABLE IF NOT EXISTS zd_operation_rows (
    id          SERIAL PRIMARY KEY,
    operation_id INTEGER NOT NULL REFERENCES zd_operations(id) ON DELETE CASCADE,
    process_id  INTEGER NOT NULL REFERENCES zd_processes(id),
    status      VARCHAR(100) NOT NULL DEFAULT 'Pending',
    job_id      VARCHAR(200),           -- Zendesk bulk job ID once submitted
    job_index   INTEGER NOT NULL DEFAULT 0,
    ticket_id   BIGINT,                 -- populated after successful creation
    col_0       TEXT, col_1  TEXT, col_2  TEXT, col_3  TEXT, col_4  TEXT,
    col_5       TEXT, col_6  TEXT, col_7  TEXT, col_8  TEXT, col_9  TEXT,
    col_10      TEXT, col_11 TEXT, col_12 TEXT, col_13 TEXT, col_14 TEXT,
    col_15      TEXT, col_16 TEXT, col_17 TEXT, col_18 TEXT, col_19 TEXT
);

CREATE INDEX IF NOT EXISTS idx_zd_rows_operation ON zd_operation_rows(operation_id);
CREATE INDEX IF NOT EXISTS idx_zd_rows_job_id    ON zd_operation_rows(job_id);
CREATE INDEX IF NOT EXISTS idx_zd_rows_status    ON zd_operation_rows(status);


-- Zendesk bulk job tracker (one Zendesk job = up to 90 tickets)

CREATE TABLE IF NOT EXISTS zd_jobs (
    id              SERIAL PRIMARY KEY,
    operation_id    INTEGER NOT NULL REFERENCES zd_operations(id) ON DELETE CASCADE,
    zendesk_job_id  VARCHAR(200) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',
    url             TEXT NOT NULL,      -- Zendesk job status URL to poll
    progress        INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    created_at      DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE INDEX IF NOT EXISTS idx_zd_jobs_operation ON zd_jobs(operation_id);
CREATE INDEX IF NOT EXISTS idx_zd_jobs_status    ON zd_jobs(status);
