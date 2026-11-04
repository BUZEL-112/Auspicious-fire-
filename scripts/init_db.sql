-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128),
    default_city VARCHAR(128),
    default_style VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Jobs Table
CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(64) PRIMARY KEY,
    mode VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    bucket VARCHAR(128) NOT NULL,
    object_key VARCHAR(256) NOT NULL,
    user_id VARCHAR(64) REFERENCES users(user_id) ON DELETE SET NULL,
    item_id VARCHAR(64),
    result JSONB,
    error_reason VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);

-- Create Wardrobe Items Table
CREATE TABLE IF NOT EXISTS wardrobe_items (
    item_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    job_id VARCHAR(64) UNIQUE REFERENCES jobs(id) ON DELETE SET NULL,
    bucket VARCHAR(128) NOT NULL,
    object_key VARCHAR(256) NOT NULL,
    source_url VARCHAR(512),
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING_TAGS',
    slot VARCHAR(32),
    category VARCHAR(64),
    color VARCHAR(64),
    fabric VARCHAR(64),
    pattern VARCHAR(64),
    neckline VARCHAR(64),
    sleeve VARCHAR(64),
    fit VARCHAR(64),
    tags_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wardrobe_items_user_id ON wardrobe_items(user_id);
CREATE INDEX IF NOT EXISTS idx_wardrobe_items_status ON wardrobe_items(status);
CREATE INDEX IF NOT EXISTS idx_wardrobe_items_slot ON wardrobe_items(slot);

-- Trigger function for Postgres NOTIFY on Job updates
CREATE OR REPLACE FUNCTION notify_job_update()
RETURNS TRIGGER AS $$
DECLARE
    payload JSON;
BEGIN
    payload = json_build_object(
        'job_id', NEW.id,
        'status', NEW.status,
        'mode', NEW.mode,
        'error_reason', NEW.error_reason,
        'updated_at', NEW.updated_at
    );
    PERFORM pg_notify('job_updates', payload::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_job_update ON jobs;
CREATE TRIGGER trg_notify_job_update
AFTER UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION notify_job_update();

-- Grant full permissions to fashion_user
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fashion_user') THEN
        ALTER TABLE users OWNER TO fashion_user;
        ALTER TABLE jobs OWNER TO fashion_user;
        ALTER TABLE wardrobe_items OWNER TO fashion_user;
        GRANT ALL PRIVILEGES ON TABLE users TO fashion_user;
        GRANT ALL PRIVILEGES ON TABLE jobs TO fashion_user;
        GRANT ALL PRIVILEGES ON TABLE wardrobe_items TO fashion_user;
        GRANT ALL ON SCHEMA public TO fashion_user;
    END IF;
END
$$;
