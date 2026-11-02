-- Create Jobs Table
CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(64) PRIMARY KEY,
    mode VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    bucket VARCHAR(128) NOT NULL,
    object_key VARCHAR(256) NOT NULL,
    result JSONB,
    error_reason VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

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
