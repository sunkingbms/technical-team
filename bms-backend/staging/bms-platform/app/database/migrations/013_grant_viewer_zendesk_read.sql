-- Parity with the old Zendesk module: viewers could see instances/processes/
-- operations read-only. seed.sql already grants zendesk:read to superadmin
-- (via the blanket superadmin grant) but not to viewer.

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'viewer' AND p.codename = 'zendesk:read'
ON CONFLICT DO NOTHING;
