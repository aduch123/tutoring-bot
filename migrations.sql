-- ================================================================
-- EduConnect Bot — Database Migrations
-- Run these in order against your PostgreSQL database
-- psql -U postgres -d tutoring_bot -f migrations.sql
-- ================================================================

-- Users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS agreed_terms_at TIMESTAMP;

-- Students table
ALTER TABLE students ADD COLUMN IF NOT EXISTS subjects TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS days_per_week INTEGER DEFAULT 3;
ALTER TABLE students ADD COLUMN IF NOT EXISTS next_payment_due TIMESTAMP;
ALTER TABLE students ADD COLUMN IF NOT EXISTS payment_notified_days INTEGER DEFAULT 0;

-- Tutors table
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS primary_subjects TEXT;
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS secondary_subjects TEXT;
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS max_teaching_days INTEGER DEFAULT 3;
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS payment_accounts TEXT;
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS is_blacklisted BOOLEAN DEFAULT FALSE;
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS approval_status VARCHAR(30) DEFAULT 'pending_documents';
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS video_file_id VARCHAR(200);
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS cv_file_ids TEXT;

-- Remove old columns if they exist
ALTER TABLE tutors DROP COLUMN IF EXISTS cv_file_id;
ALTER TABLE tutors DROP COLUMN IF EXISTS transcript_file_id;
ALTER TABLE tutors DROP COLUMN IF EXISTS id_photo_file_id;
ALTER TABLE tutors DROP COLUMN IF EXISTS subjects;
ALTER TABLE tutors DROP COLUMN IF EXISTS is_active;

-- Sessions table
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS tutor_start_confirmed BOOLEAN DEFAULT FALSE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS student_start_confirmed BOOLEAN DEFAULT FALSE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS start_confirmed_at TIMESTAMP;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS end_confirmed_at TIMESTAMP;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS recording_approved BOOLEAN DEFAULT FALSE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS recording_approved_by VARCHAR(20);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS replacement_tutor_id VARCHAR(20);

-- Payments table
ALTER TABLE payments ADD COLUMN IF NOT EXISTS screenshot_file_id VARCHAR(200);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS screenshot_uploaded_at TIMESTAMP;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS claimed_by_user_id VARCHAR(20);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS claimed_by_telegram_id BIGINT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMP;

-- Emergencies table
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS claimed_by_user_id VARCHAR(20);
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS claimed_by_telegram_id BIGINT;
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP;
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS resolution_notes TEXT;

-- New tables
CREATE TABLE IF NOT EXISTS blacklist (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    reason TEXT,
    blacklisted_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_log (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(20) UNIQUE NOT NULL,
    from_admin_id VARCHAR(20) NOT NULL,
    to_user_id VARCHAR(20) NOT NULL,
    message_text TEXT NOT NULL,
    response_type VARCHAR(30) NOT NULL,
    response_options TEXT,
    user_response TEXT,
    responded_at TIMESTAMP,
    sent_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_student ON sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tutor ON sessions(tutor_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(scheduled_start);
CREATE INDEX IF NOT EXISTS idx_schedules_student ON schedules(student_id);
CREATE INDEX IF NOT EXISTS idx_schedules_tutor ON schedules(tutor_id);
CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id);
CREATE INDEX IF NOT EXISTS idx_emergencies_status ON emergencies(status);

-- Done
SELECT 'Migrations completed successfully.' AS result;

-- ── Improvement Area 3 migrations ─────────────────────────────────────────
-- Tutor: replace max_teaching_days with max_teaching_hours
ALTER TABLE tutors ADD COLUMN IF NOT EXISTS max_teaching_hours INTEGER DEFAULT 3;
ALTER TABLE tutors DROP COLUMN IF EXISTS max_teaching_days;
