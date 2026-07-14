CREATE TABLE IF NOT EXISTS zendesk_instances (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    subdomain VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    encrypted_api_token TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- List queries filter by is_deleted
CREATE INDEX IF NOT EXISTS idx_zendesk_instances_not_deleted ON zendesk_instances(id) WHERE is_deleted = FALSE;