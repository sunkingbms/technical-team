-- Zendesk business processes (create or delete tickets, per instance)

CREATE TABLE IF NOT EXISTS zendesk_processes (
    id                  SERIAL PRIMARY KEY,
    zendesk_instance_id INTEGER NOT NULL REFERENCES zendesk_instances(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_zendesk_processes_instance     ON zendesk_processes(zendesk_instance_id);
CREATE INDEX IF NOT EXISTS idx_zendesk_processes_not_deleted  ON zendesk_processes(id) WHERE is_deleted = FALSE;


-- Field configuration for a process (which Zendesk fields to use + defaults)

CREATE TABLE IF NOT EXISTS zendesk_process_fields (
    id              SERIAL PRIMARY KEY,
    process_id      INTEGER NOT NULL REFERENCES zendesk_processes(id) ON DELETE CASCADE,
    field_id        INTEGER NOT NULL REFERENCES zendesk_fields(id) ON DELETE CASCADE,
    default_value   TEXT,
    user_visible    BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE = user maps from sheet column
    UNIQUE (process_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_zendesk_process_fields_process ON zendesk_process_fields(process_id);


-- Tags applied to every ticket created by a process

CREATE TABLE IF NOT EXISTS zendesk_process_tags (
    id          SERIAL PRIMARY KEY,
    process_id  INTEGER NOT NULL REFERENCES zendesk_processes(id) ON DELETE CASCADE UNIQUE,
    tags        JSONB NOT NULL DEFAULT '[]'
);
