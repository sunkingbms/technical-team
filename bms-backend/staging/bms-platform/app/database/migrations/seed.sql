-- seed permissions and roles tables with few permissions and roles

INSERT INTO permissions (codename, description) values
('users:write', 'Create and update users'),
('users:read', 'View users list and details'),
('users:delete', 'Delete users'),
('rbac:admin', 'Full RBAC management'),
('zendesk:create', 'Trigger Zendesk ticket creation'),
('zendesk:delete', 'Trigger Zendesk tickets bulk deletion')
ON CONFLICT (codename) DO NOTHING;


INSERT INTO roles (name, description) values
('superadmin', 'Full access to all features'),
('viewer', 'View only access to all features')
ON CONFLICT (name) DO NOTHING;


--- Assigning all permissions to superadmin role ---
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

--- Assigning viewer permissions to viewer role ---
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'viewer' AND p.codename = 'users:read'
ON CONFLICT DO NOTHING;