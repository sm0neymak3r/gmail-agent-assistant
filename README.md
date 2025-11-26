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

### Completed
- [x] GCP project setup (`gmail-agent-prod`)
- [x] Terraform infrastructure deployed (dev environment)
  - Cloud Run service (placeholder image)
  - Cloud SQL PostgreSQL database with schema
  - VPC with private connectivity
  - Secret Manager (OAuth, Anthropic API key, DB password)
  - Cloud Scheduler for hourly processing
  - Bastion host for secure database access
  - Monitoring and logging
- [x] Application code (Phase 1)
  - FastAPI application with `/health` and `/process` endpoints
  - Gmail API client with OAuth 2.0
  - Anthropic Claude client (Haiku for fast, Sonnet for quality)
  - LangGraph categorization workflow
  - CLI approval interface
  - SQLAlchemy models for all database tables

### In Progress
- [ ] Build, push, and deploy container to Cloud Run
- [ ] Test end-to-end email processing

## Next Steps

### 1. Build and Deploy Container
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

### 2. Test the Application
```bash
# Check health endpoint
curl https://gmail-agent-dev-<hash>.run.app/health

# Trigger manual processing
curl -X POST https://gmail-agent-dev-<hash>.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"trigger": "manual", "query": "is:unread", "max_emails": 10}'
```

### 3. Use CLI Approval Interface
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

### 4. Phase 2 Features (Future)
- [ ] Importance detection agent
- [ ] Calendar event extraction
- [ ] Unsubscribe management
- [ ] Active learning from feedback

### 5. Phase 3 Features (Future)
- [ ] Obsidian knowledge base integration
- [ ] Draft reply generation
- [ ] Dynamic category creation
- [ ] Batch CLI operations

### 6. Production Readiness
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
- Python 3.11+

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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check (DB, Gmail, Anthropic) |
| `/process` | POST | Process emails (batch or single) |
| `/pending` | GET | Get emails pending approval |
| `/approve/{email_id}` | POST | Approve/correct categorization |

## Environment Variables

The application has access to these environment variables in Cloud Run:

| Variable | Description |
|----------|-------------|
| `PROJECT_ID` | GCP project ID |
| `ENVIRONMENT` | Environment name (dev/staging/prod) |
| `DATABASE_HOST` | Cloud SQL private IP |
| `DATABASE_NAME` | Database name |
| `DATABASE_USER` | Database username |
| `DATABASE_PASSWORD` | Database password |
| `GMAIL_OAUTH_CLIENT` | OAuth client credentials JSON |
| `GMAIL_USER_TOKEN` | User access/refresh tokens JSON |
| `ANTHROPIC_API_KEY` | Anthropic API key |

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
                        └─────────────────┘
```

### Processing Flow

1. **Cloud Scheduler** triggers `/process` endpoint hourly
2. **Gmail Client** fetches unread emails (batch of 100)
3. **Categorization Agent** classifies using Claude Haiku (fast) with escalation to Sonnet (quality)
4. High-confidence emails get **labeled automatically** in Gmail
5. Low-confidence emails go to **approval queue** in PostgreSQL
6. **CLI or API** allows human review and correction
7. **Feedback** stored for future model improvement

## License

Private - All rights reserved
