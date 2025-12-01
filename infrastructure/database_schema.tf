# Null resource to initialize database schema
resource "null_resource" "db_schema" {
  depends_on = [
    google_sql_database.main,
    google_sql_user.agent
  ]

  provisioner "local-exec" {
    command = <<-EOT
      cat > /tmp/schema.sql <<'EOF'
      -- Email processing tables
      CREATE TABLE IF NOT EXISTS emails (
          email_id VARCHAR(255) PRIMARY KEY,
          message_id VARCHAR(255) UNIQUE NOT NULL,
          thread_id VARCHAR(255),
          from_email VARCHAR(255) NOT NULL,
          to_emails TEXT[],
          subject TEXT,
          date TIMESTAMP NOT NULL,
          body TEXT,
          category VARCHAR(255),
          confidence FLOAT,
          importance_level VARCHAR(20),
          status VARCHAR(50) DEFAULT 'unread',
          processed_at TIMESTAMP DEFAULT NOW(),
          created_at TIMESTAMP DEFAULT NOW(),
          updated_at TIMESTAMP DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date);
      CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category);
      CREATE INDEX IF NOT EXISTS idx_emails_from ON emails(from_email);
      CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);

      -- Checkpoint tracking for recovery
      CREATE TABLE IF NOT EXISTS checkpoints (
          checkpoint_id SERIAL PRIMARY KEY,
          email_id VARCHAR(255) REFERENCES emails(email_id),
          step VARCHAR(100) NOT NULL,
          state_json JSONB NOT NULL,
          created_at TIMESTAMP DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_checkpoints_email_id ON checkpoints(email_id);
      CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON checkpoints(created_at);

      -- User feedback for training
      CREATE TABLE IF NOT EXISTS feedback (
          feedback_id SERIAL PRIMARY KEY,
          email_id VARCHAR(255) REFERENCES emails(email_id),
          user_action VARCHAR(50) NOT NULL,
          proposed_category VARCHAR(255),
          final_category VARCHAR(255),
          timestamp TIMESTAMP DEFAULT NOW()
      );

      -- Importance rules
      CREATE TABLE IF NOT EXISTS importance_rules (
          rule_id SERIAL PRIMARY KEY,
          rule_type VARCHAR(50) NOT NULL,
          pattern TEXT NOT NULL,
          priority VARCHAR(20) NOT NULL,
          confidence FLOAT DEFAULT 0.8,
          approved BOOLEAN DEFAULT FALSE,
          created_at TIMESTAMP DEFAULT NOW(),
          updated_at TIMESTAMP DEFAULT NOW()
      );

      -- Unsubscribe queue
      CREATE TABLE IF NOT EXISTS unsubscribe_queue (
          queue_id SERIAL PRIMARY KEY,
          email_id VARCHAR(255) REFERENCES emails(email_id),
          sender VARCHAR(255) NOT NULL,
          method VARCHAR(50) NOT NULL,
          unsubscribe_link TEXT,
          status VARCHAR(50) DEFAULT 'pending',
          user_action VARCHAR(50),
          created_at TIMESTAMP DEFAULT NOW(),
          executed_at TIMESTAMP
      );

      -- Processing log for monitoring
      CREATE TABLE IF NOT EXISTS processing_log (
          log_id SERIAL PRIMARY KEY,
          email_id VARCHAR(255),
          agent VARCHAR(100),
          action VARCHAR(100),
          status VARCHAR(50),
          error TEXT,
          latency_ms INTEGER,
          timestamp TIMESTAMP DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_processing_log_email_id ON processing_log(email_id);
      CREATE INDEX IF NOT EXISTS idx_processing_log_timestamp ON processing_log(timestamp);
      EOF

      echo "Schema file created. Apply manually after infrastructure is deployed."
    EOT
  }
}
