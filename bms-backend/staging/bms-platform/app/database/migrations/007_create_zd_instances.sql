-- Zendesk instances (connection credentials per Zendesk account)

CREATE TABLE IF NOT EXISTS zd_instances (
    id          SERIAL PRIMARY KEY,
    instance_name VARCHAR(255) NOT NULL,
    subdomain   VARCHAR(255) NOT NULL,          -- e.g. mycompany.zendesk.com
    email       VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,                 -- API token (store encrypted in prod)
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zd_instances_deleted ON zd_instances(is_deleted);
