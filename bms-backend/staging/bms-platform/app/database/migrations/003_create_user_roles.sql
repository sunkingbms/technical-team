-- User-Roles junction (many-to-many)

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_by INT REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- The below index will be used to optimize query performance for the user_roles table. It allows reverse lookup by role
CREATE INDEX IF NOT EXISTS idx_users_roles_role_id ON user_roles (role_id);
