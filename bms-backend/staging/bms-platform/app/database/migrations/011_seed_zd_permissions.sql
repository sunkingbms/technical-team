-- Add Zendesk module permissions

INSERT INTO permissions (codename, description) VALUES
('zendesk:admin',   'Full Zendesk module management (instances, processes)'),
('zendesk:create',  'Submit bulk ticket creation operations'),
('zendesk:delete',  'Submit bulk ticket deletion operations'),
('zendesk:read',    'View Zendesk instances, processes and operation status')
ON CONFLICT (codename) DO NOTHING;

-- Grant all zendesk permissions to superadmin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'superadmin'
  AND p.codename LIKE 'zendesk:%'
ON CONFLICT DO NOTHING;

-- Grant zendesk:read to viewer
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'viewer' AND p.codename = 'zendesk:read'
ON CONFLICT DO NOTHING;
