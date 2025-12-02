# Gmail Agent Assistant

A multi-agent Gmail inbox management system using LangGraph on GCP infrastructure. Uses OAuth 2.0 for personal Gmail access with Anthropic Claude models for AI processing.

## Project Structure

```
gmail-agent-assistant/
├── infrastructure/          # Terraform IaC for GCP
│   ├── *.tf                 # Terraform configurations
│   ├── README.md            # Infrastructure documentation
│   ├── REFERENCE.md         # Comprehensive resource dictionary
│   └── CLAUDE.md            # AI assistant guide for infrastructure
├── src/                     # Application source code
│   ├── agents/              # LangGraph agent definitions
│   ├── cli/                 # CLI approval interface
│   ├── models/              # SQLAlchemy database models
│   ├── services/            # External service integrations
│   ├── workflows/           # LangGraph workflow definitions
│   ├── config.py            # Configuration management
│   └── main.py              # FastAPI application
├── tests/                   # Test files
├── scripts/                 # Deployment and utility scripts
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Current Status

### Phase 1: Completed
- [x] GCP project setup (`gmail-agent-prod`)
- [x] Terraform infrastructure deployed (dev environment)
  - Cloud Run service with application deployed (v12)
  - Cloud SQL PostgreSQL database with schema
  - VPC with private connectivity
  - Secret Manager (OAuth, Anthropic API key, DB password)
  - Cloud Scheduler for hourly processing
  - Cloud Tasks queue for reliable batch processing
  - Bastion host for secure database access
  - Monitoring and logging
- [x] Application code (Phase 1)
  - FastAPI application with health, process, and batch endpoints
  - Gmail API client with OAuth 2.0
  - Anthropic Claude client (Haiku for fast, Sonnet for quality)
  - LangGraph categorization workflow
  - CLI approval interface
  - SQLAlchemy models for all database tables
- [x] Batch processing for full inbox
  - Cloud Tasks-based reliable processing
  - Database-level locking for concurrency protection
  - Automatic retry with exponential backoff
  - Progress tracking and pause/resume support
- [x] Historical processing complete (464,757 emails)

### Phase 2: Completed
- [x] Importance Agent with 6-factor weighted scoring
  - Sender authority (VIP list), urgency keywords, deadline detection
  - Financial signals, thread activity, recipient position
  - LLM-based action item extraction
- [x] Calendar Agent with Google Calendar integration
  - LLM-based event extraction from meeting/reservation emails
  - Virtual meeting link detection (Zoom, Meet, Teams)
  - FreeBusy API conflict detection
- [x] Unsubscribe Agent with RFC 2369/8058 support
  - List-Unsubscribe header parsing
  - One-click, mailto, and HTTP link detection
  - CLI for batch review and browser-based execution
- [x] Multi-agent workflow with conditional routing
- [x] Phase 2 database migrations
- [x] VIP sender configuration (config/vip_senders.yaml)

### In Progress
- [ ] Deploy and test Phase 2 workflow on live emails

## Next Steps

### 1. Local Integration Testing (Recommended First)

Use the test harness to validate the pipeline before deployment:

```bash
# Set up credentials
export GMAIL_OAUTH_CLIENT='<oauth-client-json>'
export GMAIL_USER_TOKEN='<user-token-json>'
export ANTHROPIC_API_KEY='sk-ant-...'

# Dry run - analyze emails without processing (no API cost)
python scripts/test_batch.py \
  --query "after:2024/11/01 before:2025/02/01" \
  --dry-run

# Process a sample of 10 emails
python scripts/test_batch.py \
  --query "after:2024/11/01 before:2025/02/01" \
  --sample 10

# Save results to file
python scripts/test_batch.py \
  --query "after:2024/11/01 before:2025/02/01" \
  --sample 10 \
  --output results.json
```

The test harness provides:
- Email count and date distribution
- Cost estimation before processing
- Sample processing with real Claude API
- Category distribution and confidence metrics

### 2. Build and Deploy Container
```bash
# Authenticate Docker with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build the Docker image
docker build -t us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v1 .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v1

# Update Cloud Run
gcloud run deploy gmail-agent-dev \
  --image=us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v1 \
  --region=us-central1
```

### 3. Test the Deployed Application
```bash
# Check health endpoint
curl https://gmail-agent-dev-<hash>.run.app/health

# Trigger manual processing
curl -X POST https://gmail-agent-dev-<hash>.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"trigger": "manual", "query": "is:unread", "max_emails": 10}'
```

### 4. Use CLI Approval Interface
```bash
# Set up SSH tunnel through bastion
gcloud compute ssh gmail-agent-bastion-dev \
  --zone=us-central1-a \
  --tunnel-through-iap \
  -- -L 5432:<DB_PRIVATE_IP>:5432 -N &

# Set environment variables
export DATABASE_HOST=localhost
export DATABASE_PASSWORD=$(gcloud secrets versions access latest --secret="db-password-dev")

# Run approval CLI
python -m src.cli.approval
```

### 5. Use Unsubscribe CLI
```bash
# Set up SSH tunnel through bastion
gcloud compute ssh gmail-agent-bastion-dev \
  --zone=us-central1-a \
  --tunnel-through-iap \
  -- -L 5432:<DB_PRIVATE_IP>:5432 -N &

# Run unsubscribe CLI for batch review
python -m src.cli.unsubscribe
```

### 6. Phase 3 Features (Future)
- [ ] Obsidian knowledge base integration
- [ ] Draft reply generation
- [ ] Dynamic category creation
- [ ] Active learning from feedback

### 7. Production Readiness
- [ ] Enable Cloud SQL deletion protection
- [ ] Configure alert notification channels
- [ ] Set up CI/CD pipeline
- [ ] Add integration tests
- [ ] Performance optimization
- [ ] Add Redis/Memorystore for LLM response caching

## Quick Start

### Prerequisites
- GCP project with billing enabled
- Terraform installed
- gcloud CLI authenticated
- Docker installed
- Python 3+

### Deploy Infrastructure
```bash
cd infrastructure/
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gmail-agent-keys/terraform-sa-key.json"
terraform apply
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (for local testing)
export PROJECT_ID=gmail-agent-prod
export ENVIRONMENT=dev
export ANTHROPIC_API_KEY=sk-ant-...
export DATABASE_HOST=localhost  # Via SSH tunnel
export DATABASE_NAME=email_agent
export DATABASE_USER=agent_user
export DATABASE_PASSWORD=...

# Run the application
uvicorn src.main:app --reload --port 8080
```

### Connect to Database (via Bastion)
```bash
# SSH to bastion with port forwarding
gcloud compute ssh gmail-agent-bastion-dev \
  --zone=us-central1-a \
  --tunnel-through-iap \
  -- -L 5432:<DB_PRIVATE_IP>:5432

# In another terminal, connect with psql
PGPASSWORD=$DB_PASSWORD psql -h localhost -U agent_user -d email_agent
```

## Batch Processing (Full Inbox)

Process your entire Gmail inbox reliably. Start the job and close your laptop - processing continues on Cloud Run.

### Start Processing
```bash
curl -X POST https://gmail-agent-dev-621335261494.us-central1.run.app/process-all \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2015-01-01", "chunk_months": 2}'
```

### Check Progress
```bash
curl https://gmail-agent-dev-621335261494.us-central1.run.app/process-status
```

### Pause/Resume
```bash
# Pause
curl -X POST https://gmail-agent-dev-621335261494.us-central1.run.app/process-pause/{job_id}

# Resume
curl -X POST https://gmail-agent-dev-621335261494.us-central1.run.app/process-continue/{job_id}
```

### How It Works
1. Job created in database, first task enqueued to Cloud Tasks
2. Cloud Tasks dispatches to `/batch-worker` endpoint
3. Worker processes one 2-month chunk (~500 emails)
4. Progress saved, next task enqueued automatically
5. If worker fails, Cloud Tasks retries (4 attempts, exponential backoff)

### Monitoring
- **Cloud Tasks Console**: https://console.cloud.google.com/cloudtasks/queue/us-central1/gmail-agent-batch-dev?project=gmail-agent-prod
- **Debug endpoint**: `GET /process-debug/{job_id}` - raw job data with lock status

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check (DB, Gmail, Anthropic) |
| `/process` | POST | Process emails (batch or single) |
| `/pending` | GET | Get emails pending approval |
| `/approve/{email_id}` | POST | Approve/correct categorization |
| `/process-all` | POST | Start batch processing entire inbox |
| `/process-status` | GET | Get latest batch job status |
| `/process-status/{job_id}` | GET | Get specific batch job status |
| `/process-pause/{job_id}` | POST | Pause a running batch job |
| `/process-continue/{job_id}` | POST | Resume a paused/failed batch job |
| `/batch-worker` | POST | Called by Cloud Tasks (internal) |

## Environment Variables

The application has access to these environment variables in Cloud Run:

| Variable | Description |
|----------|-------------|
| `PROJECT_ID` | GCP project ID |
| `PROJECT_NUMBER` | GCP project number |
| `ENVIRONMENT` | Environment name (dev/staging/prod) |
| `REGION` | GCP region (us-central1) |
| `DATABASE_HOST` | Cloud SQL private IP |
| `DATABASE_NAME` | Database name |
| `DATABASE_USER` | Database username |
| `DATABASE_PASSWORD` | Database password |
| `GMAIL_OAUTH_CLIENT` | OAuth client credentials JSON |
| `GMAIL_USER_TOKEN` | User access/refresh tokens JSON |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `CLOUD_TASKS_QUEUE` | Cloud Tasks queue path for batch processing |
| `SERVICE_ACCOUNT_EMAIL` | Service account for Cloud Tasks OIDC auth |

## Email Categories (Phase 1)

| Category | Description |
|----------|-------------|
| Important | Time-sensitive or critical emails |
| Personal/Friends | Emails from friends |
| Personal/Family | Emails from family |
| Professional/Recruiters | Job-related emails |
| Professional/Work | Work correspondence |
| Purchases/Orders | Order confirmations, shipping |
| Newsletters/Subscriptions | Newsletter emails |
| Marketing/Promotions | Promotional emails |

## Importance Levels (Phase 2)

| Level | Score Range | Gmail Label | Description |
|-------|-------------|-------------|-------------|
| Critical | ≥ 0.9 | `Agent/Priority/Critical` | Immediate attention needed |
| High | 0.7 - 0.9 | `Agent/Priority/High` | Prioritize today |
| Normal | 0.4 - 0.7 | (none) | Standard processing |
| Low | < 0.4 | (none) | FYI, newsletters |

## Documentation

- [Infrastructure README](infrastructure/README.md) - Deployment and operations guide
- [Infrastructure Reference](infrastructure/REFERENCE.md) - Complete resource dictionary
- [Infrastructure CLAUDE.md](infrastructure/CLAUDE.md) - AI assistant guide for infrastructure
- [GCP Architecture](infrastructure/gcp_architecture.md) - Architecture diagram

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Gmail API     │────▶│   Cloud Run     │────▶│  Cloud SQL      │
│                 │     │                 │     │                 │
│   (OAuth 2.0)   │     │  (LangGraph)    │     │  (PostgreSQL)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────▼────────┐
                        │  Anthropic API  │
                        │  (Claude)       │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │  Cloud Tasks    │
                        │  (Batch Queue)  │
                        └─────────────────┘
```

### Processing Flow (Hourly) - Phase 2 Multi-Agent

1. **Cloud Scheduler** triggers `/process` endpoint hourly
2. **Gmail Client** fetches unread emails (batch of 100)
3. **Categorization Agent** classifies using Claude Haiku (fast) with escalation to Sonnet (quality)
4. **Importance Agent** scores using 6-factor weighted analysis, extracts action items
5. **Calendar Agent** (conditional) extracts events from meeting/reservation emails, checks conflicts
6. **Unsubscribe Agent** (conditional) detects unsubscribe options for newsletters/marketing
7. High-confidence emails get **labeled automatically** in Gmail (category + priority)
8. Low-confidence or conflicting emails go to **approval queue** in PostgreSQL
9. **CLI or API** allows human review and correction
10. **Feedback** stored for future model improvement

### Batch Processing Flow (Full Inbox)

1. User calls `POST /process-all` to start batch job
2. **Cloud Tasks** receives first task and dispatches to `/batch-worker`
3. Worker processes one chunk (2-month date range, ~500 emails)
4. Progress saved to **Cloud SQL**, next task enqueued
5. **Cloud Tasks** handles retries on failure (4 attempts, exponential backoff)
6. User can check progress, pause, or resume anytime

## License

Private - All rights reserved
