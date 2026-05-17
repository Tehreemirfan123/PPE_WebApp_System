-- ============================================================
--  PPE Detection System — Database Schema
--  001_init_schema.sql
-- ============================================================

-- Enable pgvector for face embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────
--  USERS  (admin & security_officer accounts)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    full_name   VARCHAR(255)        NOT NULL,
    hashed_password TEXT            NOT NULL,
    role        VARCHAR(50)         NOT NULL CHECK (role IN ('admin', 'security_officer')),
    is_active   BOOLEAN             NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
--  SITES  (4 seeded defaults + user-created)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sites (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) UNIQUE NOT NULL,
    location    VARCHAR(500),
    description TEXT,
    is_default  BOOLEAN             NOT NULL DEFAULT FALSE,
    is_active   BOOLEAN             NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

-- Soft delete site
UPDATE sites
SET is_active = FALSE
WHERE id = <site_id>;

-- ─────────────────────────────────────────────────────────────
--  SITE_REQUIREMENTS  (which PPE items are required per site)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS site_requirements (
    id          SERIAL PRIMARY KEY,
    site_id     INT  NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    ppe_item    VARCHAR(100) NOT NULL,   -- e.g. 'helmet', 'gloves'
    UNIQUE (site_id, ppe_item)
);

-- ─────────────────────────────────────────────────────────────
--  CAMERAS  (CCTV / camera info per site)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cameras (
    id           SERIAL PRIMARY KEY,
    site_id      INT          NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    camera_name  VARCHAR(255) NOT NULL,
    location     VARCHAR(500),
    stream_url   VARCHAR(500),           -- RTSP or HTTP stream URL
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
--  WORKERS  (registered employees with face embedding)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workers (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(100) UNIQUE NOT NULL,
    full_name       VARCHAR(255)        NOT NULL,
    department      VARCHAR(255),
    site_id         INT REFERENCES sites(id) ON DELETE SET NULL,
    face_image_path TEXT,                -- path to registered face photo
    face_embedding  vector(512),         -- pgvector face embedding (written by ML pipeline)
    is_active       BOOLEAN             NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

-- Soft delete worker
UPDATE workers
SET is_active = FALSE,
    updated_at = NOW()
WHERE id = <worker_id>;

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS workers_face_embedding_idx
    ON workers USING ivfflat (face_embedding vector_cosine_ops)
    WITH (lists = 100);

-- ─────────────────────────────────────────────────────────────
--  DETECTION_EVENTS  (one row per violation event — NOT every frame)
-- ─────────────────────────────────────────────────────────────
CREATE TYPE detection_status AS ENUM ('open', 'resolved');

CREATE TABLE IF NOT EXISTS detection_events (
    id              SERIAL PRIMARY KEY,
    camera_id       INT REFERENCES cameras(id) ON DELETE SET NULL,
    site_id         INT REFERENCES sites(id)   ON DELETE SET NULL,
    worker_id       INT REFERENCES workers(id) ON DELETE SET NULL, -- nullable: unknown face
    detected_by     VARCHAR(255),              -- YOLO model version string
    image_path      TEXT,                      -- saved violation frame (saved_violations/)
    confidence_score NUMERIC(5,4),             -- overall detection confidence
    detected_ppe    TEXT[],                    -- array of PPE items detected
    missing_ppe     TEXT[],                    -- array of PPE items missing
    event_status    detection_status NOT NULL DEFAULT 'open',
    timestamp       TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
--  VIOLATIONS  (one row per missing PPE item per event)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS violations (
    id              SERIAL PRIMARY KEY,
    event_id        INT         NOT NULL REFERENCES detection_events(id) ON DELETE CASCADE,
    worker_id       INT REFERENCES workers(id) ON DELETE SET NULL,
    site_id         INT REFERENCES sites(id)   ON DELETE SET NULL,
    camera_id       INT REFERENCES cameras(id) ON DELETE SET NULL,
    missing_item    VARCHAR(100) NOT NULL,      -- e.g. 'helmet'
    confidence_score NUMERIC(5,4),
    status          detection_status NOT NULL DEFAULT 'open',
    resolved_at     TIMESTAMPTZ,
    resolved_by     INT REFERENCES users(id) ON DELETE SET NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
--  INDEXES for common queries
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_detection_events_timestamp  ON detection_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_detection_events_site_id    ON detection_events(site_id);
CREATE INDEX IF NOT EXISTS idx_detection_events_status     ON detection_events(event_status);
CREATE INDEX IF NOT EXISTS idx_violations_timestamp        ON violations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_violations_site_id          ON violations(site_id);
CREATE INDEX IF NOT EXISTS idx_violations_status           ON violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_worker_id        ON violations(worker_id);
