CREATE TABLE IF NOT EXISTS zendesk_forms (
    id SERIAL PRIMARY KEY,
    zendesk_instance_id INT NOT NULL REFERENCES zendesk_instances(id) ON DELETE CASCADE,
    zendesk_form_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(zendesk_instance_id, zendesk_form_id)
);

CREATE INDEX IF NOT EXISTS idx_zendesk_form_instance ON zendesk_forms(zendesk_instance_id);