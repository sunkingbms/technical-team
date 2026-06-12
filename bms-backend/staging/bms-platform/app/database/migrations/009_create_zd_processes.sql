-- Zendesk business processes (create or delete tickets, per instance)

CREATE TABLE IF NOT EXISTS zd_processes (
    id                  SERIAL PRIMARY KEY,
    instance_id         INTEGER NOT NULL REFERENCES zd_instances(id) ON DELETE CASCADE,
    process_name        VARCHAR(255) NOT NULL,
    process_description TEXT,
    operation           VARCHAR(50) NOT NULL CHECK (operation IN ('create', 'delete')),
    status              VARCHAR(50) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    ticket_form_id      BIGINT,                -- optional Zendesk form override
    ticket_group_id     BIGINT,                -- optional Zendesk group override
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zd_processes_instance ON zd_processes(instance_id);
CREATE INDEX IF NOT EXISTS idx_zd_processes_deleted  ON zd_processes(is_deleted);


-- Field configuration for a process (which Zendesk fields to use + defaults)

CREATE TABLE IF NOT EXISTS zd_process_fields (
    id              SERIAL PRIMARY KEY,
    process_id      INTEGER NOT NULL REFERENCES zd_processes(id) ON DELETE CASCADE,
    field_id        INTEGER NOT NULL REFERENCES zd_fields(id) ON DELETE CASCADE,
    default_value   TEXT,
    user_visible    BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE = user maps from sheet column
    UNIQUE (process_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_zd_process_fields_process ON zd_process_fields(process_id);


-- Tags applied to every ticket created by a process

CREATE TABLE IF NOT EXISTS zd_process_tags (
    id          SERIAL PRIMARY KEY,
    process_id  INTEGER NOT NULL REFERENCES zd_processes(id) ON DELETE CASCADE UNIQUE,
    tags        JSONB NOT NULL DEFAULT '[]'
);
