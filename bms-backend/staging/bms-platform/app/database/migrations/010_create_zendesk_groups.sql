CREATE TABLE IF NOT EXISTS zendesk_groups (
    id SERIAL PRIMARY KEY,
    zendesk_instance_id INT NOT NULL REFERENCES zendesk_instances(id) ON DELETE CASCADE,
    zendesk_group_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(zendesk_instance_id, zendesk_group_id)
);

CREATE INDEX IF NOT EXISTS idx_zendesk_group_instance ON zendesk_groups(zendesk_instance_id);