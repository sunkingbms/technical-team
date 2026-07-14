create table if not exists zendesk_fields (
    id SERIAL PRIMARY KEY,
    zendesk_instance_id INT NOT NULL REFERENCES zendesk_instances(id) ON DELETE CASCADE,
    zendesk_field_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    type VARCHAR(100),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(zendesk_instance_id, zendesk_field_id)
);

CREATE INDEX IF NOT EXISTS idx_zendesk_field_instance ON zendesk_fields(zendesk_instance_id);