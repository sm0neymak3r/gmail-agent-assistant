-- Phase 2 Database Migration
-- Creates tables for VIP senders, calendar events, and updates unsubscribe_queue
--
-- Run with:
-- PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U agent_user -d email_agent -f scripts/migrations/002_phase2_tables.sql

-- ============================================================================
-- VIP Senders Table
-- Stores email patterns for importance scoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS vip_senders (
    id SERIAL PRIMARY KEY,
    email_pattern VARCHAR(255) NOT NULL,  -- SQL LIKE pattern: exact or %@domain.com
    name VARCHAR(255),                     -- Human-readable name
    importance_boost FLOAT DEFAULT 0.3,   -- Score boost (0.0-1.0)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email_pattern)
);

COMMENT ON TABLE vip_senders IS 'VIP sender patterns for importance scoring boost';
COMMENT ON COLUMN vip_senders.email_pattern IS 'SQL LIKE pattern: exact email or %@domain.com for domain matching';
COMMENT ON COLUMN vip_senders.importance_boost IS 'Additional importance score (0.0-1.0) added for matching senders';

-- ============================================================================
-- Calendar Events Table
-- Stores extracted calendar events from emails
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) REFERENCES emails(email_id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_minutes INTEGER,
    location VARCHAR(500),
    is_virtual BOOLEAN DEFAULT FALSE,
    virtual_link VARCHAR(1000),
    attendees TEXT[],                      -- Array of email addresses
    description TEXT,                      -- Confirmation numbers, details
    confidence FLOAT,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, created, conflict, dismissed, error
    conflicts JSONB,                       -- Conflicting events as JSON array
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_email_id ON calendar_events(email_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);

COMMENT ON TABLE calendar_events IS 'Calendar events extracted from emails by Calendar Agent';
COMMENT ON COLUMN calendar_events.status IS 'Event status: pending (awaiting action), created (added to calendar), conflict (has conflicts), dismissed (user declined), error (creation failed)';
COMMENT ON COLUMN calendar_events.conflicts IS 'JSON array of conflicting calendar events with start/end times';

-- ============================================================================
-- Update Unsubscribe Queue Table
-- Add sender_domain for batch grouping
-- ============================================================================
DO $$
BEGIN
    -- Add sender_domain column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'unsubscribe_queue' AND column_name = 'sender_domain'
    ) THEN
        ALTER TABLE unsubscribe_queue ADD COLUMN sender_domain VARCHAR(255);
    END IF;

    -- Add unsubscribe_email column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'unsubscribe_queue' AND column_name = 'unsubscribe_email'
    ) THEN
        ALTER TABLE unsubscribe_queue ADD COLUMN unsubscribe_email VARCHAR(255);
    END IF;

    -- Add confidence column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'unsubscribe_queue' AND column_name = 'confidence'
    ) THEN
        ALTER TABLE unsubscribe_queue ADD COLUMN confidence FLOAT DEFAULT 0.9;
    END IF;
END $$;

-- Create indexes for unsubscribe queue
CREATE INDEX IF NOT EXISTS idx_unsubscribe_sender_domain ON unsubscribe_queue(sender_domain);
CREATE INDEX IF NOT EXISTS idx_unsubscribe_status ON unsubscribe_queue(status);

-- ============================================================================
-- Update Emails Table
-- Add Phase 2 columns for importance and action items
-- ============================================================================
DO $$
BEGIN
    -- Add importance_score column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'emails' AND column_name = 'importance_score'
    ) THEN
        ALTER TABLE emails ADD COLUMN importance_score FLOAT;
    END IF;

    -- Add action_items column if it doesn't exist (JSONB array)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'emails' AND column_name = 'action_items'
    ) THEN
        ALTER TABLE emails ADD COLUMN action_items JSONB DEFAULT '[]'::JSONB;
    END IF;

    -- Add has_calendar_event column for quick filtering
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'emails' AND column_name = 'has_calendar_event'
    ) THEN
        ALTER TABLE emails ADD COLUMN has_calendar_event BOOLEAN DEFAULT FALSE;
    END IF;

    -- Add has_unsubscribe column for quick filtering
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'emails' AND column_name = 'has_unsubscribe'
    ) THEN
        ALTER TABLE emails ADD COLUMN has_unsubscribe BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Create index on importance_level for filtering
CREATE INDEX IF NOT EXISTS idx_emails_importance ON emails(importance_level);

-- ============================================================================
-- Seed initial VIP senders (examples - customize as needed)
-- ============================================================================
-- INSERT INTO vip_senders (email_pattern, name, importance_boost) VALUES
-- ('ceo@yourcompany.com', 'CEO', 0.4),
-- ('%@important-client.com', 'Important Client', 0.3)
-- ON CONFLICT (email_pattern) DO NOTHING;

-- ============================================================================
-- Migration Complete
-- ============================================================================
SELECT 'Phase 2 migration complete' AS status;
