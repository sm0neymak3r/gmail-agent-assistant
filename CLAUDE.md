# Gmail Agent Assistant - Development Guide

This document provides guidance for AI assistants working on the Gmail Agent project.

## Project Overview

A multi-agent Gmail inbox management system built with:
- **Infrastructure**: Terraform on GCP (Cloud Run, Cloud SQL, Secret Manager)
- **AI/ML**: LangGraph with Anthropic Claude models
- **Authentication**: OAuth 2.0 for personal Gmail access

## Key Files to Check

| File | Purpose |
|------|---------|
| `README.md` | Project status and next steps |
| `infrastructure/CLAUDE.md` | Infrastructure-specific guidance |
| `infrastructure/REFERENCE.md` | Complete Terraform resource dictionary |

## Before Starting Work

1. **Check current status** in `README.md` under "Current Status" and "Next Steps"
2. **Update the checklist** as tasks are completed
3. **Review infrastructure** if making changes that affect GCP resources

## Working with Next Steps

The `README.md` contains a "Next Steps" section with checkboxes. When working on tasks:

### Marking Tasks Complete

When a task is finished, update the checkbox:
```markdown
# Before
- [ ] Create LangGraph agent architecture

# After
- [x] Create LangGraph agent architecture
```

### Adding New Tasks

Add new tasks under the appropriate section:
```markdown
### 1. Develop the Gmail Agent Application
- [x] Create LangGraph agent architecture
- [x] Implement email fetching from Gmail API
- [ ] NEW: Add rate limiting for API calls    # <-- New task
```

### Moving Tasks Between Sections

If a task belongs in a different phase, move it to the appropriate section.

## Project Conventions

### Directory Structure

```
src/                    # Application code goes here
├── agents/             # LangGraph agent definitions
├── services/           # External service integrations (Gmail, Anthropic)
├── models/             # Database models
└── utils/              # Shared utilities

tests/                  # Test files mirror src/ structure
├── agents/
├── services/
└── models/

config/                 # Configuration files
```

### Environment Variables

Application code should read from environment variables (set by Cloud Run):
```python
import os

PROJECT_ID = os.environ.get('PROJECT_ID')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
DATABASE_HOST = os.environ.get('DATABASE_HOST')
# etc.
```

### Gmail OAuth Handling

OAuth credentials are provided as JSON strings in environment variables:
```python
import os
import json

oauth_client = json.loads(os.environ.get('GMAIL_OAUTH_CLIENT'))
user_token = json.loads(os.environ.get('GMAIL_USER_TOKEN'))
```

### Claude Model Selection

Use different Claude models based on task complexity:
- **Claude Haiku** (`claude-3-haiku-20240307`): Fast/cheap for classification, routing
- **Claude Sonnet** (`claude-3-5-sonnet-20241022`): Balanced for most tasks
- **Claude Opus** (`claude-3-opus-20240229`): Complex reasoning (use sparingly)

```python
import anthropic

client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

# Fast classification
response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=100,
    messages=[{"role": "user", "content": "Classify this email..."}]
)

# Complex analysis
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Analyze this email thread..."}]
)
```

## Database Schema

The database has these tables (see `infrastructure/REFERENCE.md` for full schema):

| Table | Purpose |
|-------|---------|
| `emails` | Processed email storage |
| `checkpoints` | LangGraph state persistence |
| `feedback` | User feedback for training |
| `importance_rules` | Learned classification rules |
| `unsubscribe_queue` | Pending unsubscribe actions |
| `processing_log` | Audit log for all actions |

## Common Tasks

### Adding a New Agent

1. Create agent file in `src/agents/`
2. Define state schema using Pydantic or TypedDict
3. Implement node functions
4. Build graph with LangGraph
5. Add tests in `tests/agents/`
6. Update README.md checklist

### Adding a New API Integration

1. Create service file in `src/services/`
2. Handle authentication (use env vars)
3. Implement retry logic for resilience
4. Add to `requirements.txt`
5. Update Dockerfile if needed

### Modifying Infrastructure

1. Read `infrastructure/CLAUDE.md` first
2. Make changes to `.tf` files
3. Run `terraform plan` to preview
4. Update `infrastructure/REFERENCE.md` if adding resources
5. Apply with `terraform apply`

## Testing

### Local Development

```bash
# Set up environment variables
export ANTHROPIC_API_KEY="sk-ant-..."
export DATABASE_HOST="localhost"
# ... etc

# Run tests
pytest tests/
```

### Database Access (via Bastion)

```bash
gcloud compute ssh gmail-agent-bastion-dev \
  --zone=us-central1-a \
  --tunnel-through-iap

# On bastion:
DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password-dev")
PGPASSWORD=$DB_PASSWORD psql -h <DB_IP> -U agent_user -d email_agent
```

## Deployment

### Build and Push Image

```bash
docker build -t us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v1 .
docker push us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v1
```

### Deploy to Cloud Run

```bash
gcloud run deploy gmail-agent-dev \
  --image=us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v1 \
  --region=us-central1
```

## Checklist for Completing Work

Before finishing a session, ensure:

- [ ] Code is tested and working
- [ ] `README.md` "Next Steps" updated with completed tasks
- [ ] New files follow project conventions
- [ ] Documentation updated if needed
- [ ] No secrets or credentials in code (use env vars)
