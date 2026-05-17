-- ============================================================
--  PPE Detection System — Seed Defaults
--  002_seed_defaults.sql
-- ============================================================

-- ─────────────────────────────────────────────────────────────
--  DEFAULT USERS  (admin & security officer)
--  Passwords are bcrypt hashes of:
--    admin123   →  admin@ppe.com
--    officer123 →  officer@ppe.com
-- ─────────────────────────────────────────────────────────────
INSERT INTO users (email, full_name, hashed_password, role) VALUES
(
    'admin@ppe.com',
    'System Administrator',
    '$2b$12$mmJe2RacLhOKWMc8k7q7Z.h6hcsm10WJpIGw.vN7ZVLD3aTELQ3NW',  -- admin123
    'admin'
),
(
    'officer@ppe.com',
    'Security Officer',
    '$2b$12$oiPsGhqebXewooP/Q8A9AewtNrpUgzqLx1RRXrF4RZZRN83kFsgyq',  -- officer123
    'security_officer'
)
ON CONFLICT (email) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
--  DEFAULT SITES  (protected — is_default = TRUE)
-- ─────────────────────────────────────────────────────────────
INSERT INTO sites (name, location, description, is_default) VALUES
('Construction Site', 'Zone A – North Campus',    'Active construction area with heavy machinery', TRUE),
('Chemical Lab',      'Building B – Floor 2',      'Chemical processing and research laboratory',   TRUE),
('Factory',           'Industrial Block C',         'Main manufacturing and assembly factory floor', TRUE),
('Warehouse',         'South Wing – Storage Block', 'Goods storage and logistics warehouse',         TRUE)
ON CONFLICT (name) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
--  SITE REQUIREMENTS  (required PPE per default site)
-- ─────────────────────────────────────────────────────────────

-- Construction Site
INSERT INTO site_requirements (site_id, ppe_item)
SELECT s.id, req.item
FROM sites s,
     (VALUES ('hardhat'), ('safety_vest'), ('gloves'), ('safety_shoes')) AS req(item)
WHERE s.name = 'Construction Site'
ON CONFLICT DO NOTHING;

-- Chemical Lab
INSERT INTO site_requirements (site_id, ppe_item)
SELECT s.id, req.item
FROM sites s,
     (VALUES ('gloves'), ('face_mask'), ('lab_coat'), ('goggles')) AS req(item)
WHERE s.name = 'Chemical Lab'
ON CONFLICT DO NOTHING;

-- Factory
INSERT INTO site_requirements (site_id, ppe_item)
SELECT s.id, req.item
FROM sites s,
     (VALUES ('hardhat'), ('earmuffs'), ('safety_vest'), ('gloves')) AS req(item)
WHERE s.name = 'Factory'
ON CONFLICT DO NOTHING;

-- Warehouse
INSERT INTO site_requirements (site_id, ppe_item)
SELECT s.id, req.item
FROM sites s,
     (VALUES ('safety_vest'), ('hardhat'), ('gloves')) AS req(item)
WHERE s.name = 'Warehouse'
ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────
--  DEFAULT CAMERAS  (one camera per default site)
-- ─────────────────────────────────────────────────────────────
INSERT INTO cameras (site_id, camera_name, location, stream_url)
SELECT s.id, cam.name, cam.loc, cam.url
FROM sites s
JOIN (VALUES
    ('Construction Site', 'CAM-001-CONSTRUCTION', 'Main Gate',       'rtsp://localhost:8554/construction_cam1'),
    ('Chemical Lab',      'CAM-002-CHEMLAB',      'Lab Entrance',    'rtsp://localhost:8554/chemlab_cam1'),
    ('Factory',           'CAM-003-FACTORY',       'Production Floor','rtsp://localhost:8554/factory_cam1'),
    ('Warehouse',         'CAM-004-WAREHOUSE',     'Loading Bay',     'rtsp://localhost:8554/warehouse_cam1')
) AS cam(site_name, name, loc, url) ON s.name = cam.site_name
ON CONFLICT DO NOTHING;
