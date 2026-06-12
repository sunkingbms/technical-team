-- Zendesk metadata cached from the Zendesk API per instance

CREATE TABLE IF NOT EXISTS zd_fields (
    id                      SERIAL PRIMARY KEY,
    zendesk_instance_id     INTEGER NOT NULL REFERENCES zd_instances(id) ON DELETE CASCADE,
    -- Zendesk field attributes
    zendesk_field_id        BIGINT NOT NULL,
    title                   VARCHAR(500),
    raw_title               VARCHAR(500),
    title_in_portal         VARCHAR(500),
    raw_title_in_portal     VARCHAR(500),
    type                    VARCHAR(100),
    description             TEXT,
    raw_description         TEXT,
    agent_description       TEXT,
    position                INTEGER,
    active                  BOOLEAN DEFAULT TRUE,
    required                BOOLEAN DEFAULT FALSE,
    required_in_portal      BOOLEAN DEFAULT FALSE,
    visible_in_portal       BOOLEAN DEFAULT FALSE,
    editable_in_portal      BOOLEAN DEFAULT FALSE,
    removable               BOOLEAN DEFAULT FALSE,
    collapsed_for_agents    BOOLEAN DEFAULT FALSE,
    regexp_for_validation   TEXT,
    tag                     VARCHAR(255),
    url                     TEXT,
    key                     VARCHAR(255),
    sub_type_id             INTEGER,
    relationship_target_type VARCHAR(100),
    relationship_filter     JSONB,
    custom_field_options    JSONB,
    custom_statuses         JSONB,
    system_field_options    JSONB,
    creator_user_id         BIGINT,
    creator_app_name        VARCHAR(255),
    created_at              TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ,
    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zd_fields_instance ON zd_fields(zendesk_instance_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zd_fields_instance_field ON zd_fields(zendesk_instance_id, zendesk_field_id);


CREATE TABLE IF NOT EXISTS zd_forms (
    id                  SERIAL PRIMARY KEY,
    zendesk_instance_id INTEGER NOT NULL REFERENCES zd_instances(id) ON DELETE CASCADE,
    form_id             BIGINT NOT NULL,
    form_name           VARCHAR(500),
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zd_forms_instance ON zd_forms(zendesk_instance_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zd_forms_instance_form ON zd_forms(zendesk_instance_id, form_id);


CREATE TABLE IF NOT EXISTS zd_groups (
    id                  SERIAL PRIMARY KEY,
    zendesk_instance_id INTEGER NOT NULL REFERENCES zd_instances(id) ON DELETE CASCADE,
    group_id            BIGINT NOT NULL,
    group_name          VARCHAR(500),
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zd_groups_instance ON zd_groups(zendesk_instance_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zd_groups_instance_group ON zd_groups(zendesk_instance_id, group_id);
