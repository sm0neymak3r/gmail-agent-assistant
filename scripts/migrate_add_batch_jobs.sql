-- Migration: Add batch_jobs table for batch processing
-- Run this via bastion host or Cloud SQL Studio

CREATE TABLE IF NOT EXISTS batch_jobs (
    job_id VARCHAR(255) PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    query_template TEXT NOT NULL,
    start_date VARCHAR(20) NOT NULL,
    end_date VARCHAR(20) NOT NULL,
    chunk_size INTEGER DEFAULT 500,
    chunk_months INTEGER DEFAULT 2,

    -- Progress tracking
    status VARCHAR(50) DEFAULT 'pending',
    current_chunk_start VARCHAR(20),
    current_chunk_end VARCHAR(20),
    chunks_completed INTEGER DEFAULT 0,
    chunks_total INTEGER DEFAULT 0,

    -- Email counts
    emails_processed INTEGER DEFAULT 0,
    emails_categorized INTEGER DEFAULT 0,
    emails_labeled INTEGER DEFAULT 0,
    emails_pending_approval INTEGER DEFAULT 0,
    emails_errors INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_activity TIMESTAMP DEFAULT NOW(),

    -- Cost tracking
    estimated_cost FLOAT DEFAULT 0.0,

    -- Error tracking
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Processing lock (prevents concurrent chunk processing)
    processing_lock_id VARCHAR(36),
    processing_lock_time TIMESTAMP,

    -- Completed date ranges (JSON array of [start, end] pairs)
    completed_ranges JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_last_activity ON batch_jobs(last_activity);
