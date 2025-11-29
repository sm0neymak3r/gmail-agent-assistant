# Gmail Agent Infrastructure

## Architecture Overview
- **Compute**: Cloud Run (serverless containers)
- **Database**: Cloud SQL PostgreSQL (Private Service Connect)
- **Networking**: VPC with NAT for external API calls
- **Secrets**: Secret Manager for API keys and OAuth credentials
- **Scheduling**: Cloud Scheduler for hourly processing
- **Batch Processing**: Cloud Tasks for reliable historical inbox processing
- **Storage**: Cloud Storage for log archival
- **LLM Provider**: Anthropic (Claude Haiku/Sonnet/Opus)

## Prerequisites
1. GCP project with billing enabled
2. Terraform service account key at `~/gmail-agent-keys/terraform-sa-key.json`
3. Required APIs enabled (see REFERENCE.md for full list)
4. Gmail OAuth credentials configured (see Secrets Setup below)

## Deployment

### First-time setup
```bash
# Deploy dev environment
./scripts/deploy-infrastructure.sh dev

# Deploy staging environment
./scripts/deploy-infrastructure.sh staging

# Deploy production environment
./scripts/deploy-infrastructure.sh prod
```

### Secrets Setup

The infrastructure requires these secrets in Secret Manager:

| Secret | Purpose | Format |
|--------|---------|--------|
| `gmail-oauth-token` | OAuth client credentials (app identity) | JSON |
| `gmail-user-token` | User access/refresh tokens | JSON |
| `anthropic-api-key-{env}` | Anthropic API key | String |
| `db-password-{env}` | Database password (auto-generated) | String |

#### Gmail OAuth Setup

1. **Client credentials** (`gmail-oauth-token`):
   ```bash
   # Upload OAuth client secret from Google Cloud Console
   gcloud secrets versions add gmail-oauth-token \
     --data-file="$HOME/gmail-agent-keys/oauth_client_secret.json"
   ```

2. **User tokens** (`gmail-user-token`):
   ```bash
   # First, generate tokens using OAuth flow (creates token.pickle)
   # Then convert to JSON and upload:
   python3 << 'EOF'
   import pickle, json
   with open('token.pickle', 'rb') as f:
       creds = pickle.load(f)
   token_data = {
       'token': creds.token,
       'refresh_token': creds.refresh_token,
       'token_uri': creds.token_uri,
       'client_id': creds.client_id,
       'client_secret': creds.client_secret,
       'scopes': list(creds.scopes) if creds.scopes else []
   }
   with open('/tmp/gmail_token.json', 'w') as f:
       json.dump(token_data, f)
   EOF

   gcloud secrets create gmail-user-token --replication-policy="automatic"
   gcloud secrets versions add gmail-user-token --data-file=/tmp/gmail_token.json
   rm /tmp/gmail_token.json
   ```

3. **Anthropic API key**:
   ```bash
   echo -n "sk-ant-your-anthropic-key" | \
     gcloud secrets versions add anthropic-api-key-dev --data-file=-
   ```

### Initialize Database Schema

The database uses a private IP (no public access) for security. Connect via the bastion host:

**Step 1: Deploy the bastion host** (if not already deployed)
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gmail-agent-keys/terraform-sa-key.json"
terraform apply
```

**Step 2: SSH to the bastion via IAP**
```bash
gcloud compute ssh gmail-agent-bastion-dev \
  --zone=us-central1-a \
  --tunnel-through-iap
```

**Step 3: On the bastion, connect to the database**
```bash
# Get the database private IP (run this locally first, note the IP)
# gcloud sql instances describe gmail-agent-db-dev --format='value(ipAddresses[0].ipAddress)'

# On the bastion:
DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password-dev")
PGPASSWORD=$DB_PASSWORD psql -h <DATABASE_PRIVATE_IP> -U agent_user -d email_agent
```

**Step 4: Run the schema SQL**

Once connected to psql, paste the schema (see `database_schema.tf` for the full SQL) or run:
```sql
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

-- Additional tables: checkpoints, feedback, importance_rules, unsubscribe_queue, processing_log
-- See database_schema.tf or REFERENCE.md for complete schema
```

## Environment Variables

Your application will have access to these environment variables:

| Variable | Description |
|----------|-------------|
| `PROJECT_ID` | GCP project ID |
| `ENVIRONMENT` | Environment name (dev/staging/prod) |
| `DATABASE_HOST` | Cloud SQL private IP |
| `DATABASE_NAME` | Database name (`email_agent`) |
| `DATABASE_USER` | Database username (`agent_user`) |
| `DATABASE_PASSWORD` | Database password (from Secret Manager) |
| `GMAIL_OAUTH_CLIENT` | OAuth client credentials JSON |
| `GMAIL_USER_TOKEN` | User access/refresh tokens JSON |
| `ANTHROPIC_API_KEY` | Anthropic API key |

## Workspace Management
```bash
# List workspaces
terraform workspace list

# Switch workspace
terraform workspace select staging

# Create new workspace
terraform workspace new prod
```

## Running Terraform Commands

Always authenticate before running Terraform:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gmail-agent-keys/terraform-sa-key.json"

# Plan changes
terraform plan

# Apply changes
terraform apply

# Destroy infrastructure (careful!)
terraform destroy
```

## Cost Optimization
- **Dev**: Minimal resources (db-f1-micro, 0 min instances, scale to zero)
- **Staging**: Medium resources for testing
- **Prod**: Full resources with high availability

## Security Notes
1. Database uses Private Service Connect (no public IP)
2. Cloud Run uses VPC connector for private access
3. All secrets managed through Secret Manager
4. Service account with minimal permissions (principle of least privilege)
5. OAuth 2.0 for personal Gmail access (not domain-wide delegation)

## Batch Processing with Cloud Tasks

Cloud Tasks provides reliable, autonomous batch processing for historical inbox analysis. This enables processing thousands of emails without requiring an active client connection.

### How It Works

1. **Batch Job Initiation**: User starts a batch job via `/batch-process` endpoint
2. **Chunk Creation**: System divides date range into 2-month chunks
3. **Task Chaining**: Each chunk completion enqueues the next chunk via Cloud Tasks
4. **Automatic Retries**: Cloud Tasks handles failures with exponential backoff
5. **Autonomous Execution**: Processing continues even when user closes their laptop

### Queue Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| Queue Name | `gmail-agent-batch-v3` | Unique queue for batch processing |
| Max Concurrent | 1 | Serial processing (one chunk at a time) |
| Dispatch Rate | 1/sec | Faster processing with rate limiting |
| Max Attempts | 4 | Original + 3 retries |
| Max Backoff | 600s | 10-minute max retry delay |
| Logging | 100% | Full task operation logging for debugging |

### IAM Requirements

Cloud Tasks auto-dispatch requires specific IAM configuration:

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe gmail-agent-prod --format='value(projectNumber)')

# Cloud Tasks service agent needs serviceAccountUser (not serviceAccountTokenCreator!)
gcloud iam service-accounts add-iam-policy-binding \
  email-agent-runtime@gmail-agent-prod.iam.gserviceaccount.com \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

**Critical**: The `serviceAccountUser` role provides `iam.serviceAccounts.actAs` permission, which Cloud Tasks needs to generate OIDC tokens for authenticated requests. The `serviceAccountTokenCreator` role does NOT work for Cloud Tasks auto-dispatch.

### Monitoring Batch Jobs

```bash
# Check batch job status
curl https://gmail-agent-dev-621335261494.us-central1.run.app/process-status

# View queue status
gcloud tasks queues describe gmail-agent-batch-v3 --location=us-central1

# List pending tasks
gcloud tasks list --queue=gmail-agent-batch-v3 --location=us-central1

# View Cloud Tasks logs
gcloud logging read 'resource.type="cloud_tasks_queue"' --limit=20
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Tasks stuck at 0 dispatch attempts | Missing `serviceAccountUser` role | Add IAM binding (see above) |
| Manual dispatch works, auto fails | IAM misconfiguration | Verify service agent has `actAs` permission |
| Queue corrupted/stuck | Unknown GCP issue | Create new queue (v3, v4, etc.) |

## Documentation

- **REFERENCE.md**: Comprehensive dictionary of all Terraform resources
- **CLAUDE.md**: AI assistant guide for working with this infrastructure
- **gcp_architecture.md**: Visual architecture diagrams
- **terraform_deployment.md**: Deployment sequence and dependencies
