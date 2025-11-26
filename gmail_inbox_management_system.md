# COMPREHENSIVE GMAIL INBOX MANAGEMENT SYSTEM
## Product Requirements Document (PRD) &amp; Technical Specification

---

# **PRODUCT REQUIREMENTS DOCUMENT (PRD)**

## **Executive Summary**

An intelligent, multi-agent Gmail management system built with LangGraph and LangChain that autonomously categorizes emails, generates draft replies, creates calendar events, manages unsubscriptions, and maintains an Obsidian knowledge base—all while keeping humans in the loop for critical decisions. The system processes up to 100 emails daily initially, scaling to real-time processing, with model-agnostic implementation for cost optimization.

**Key Success Metrics:**
- **95% categorization accuracy** within 30 days
- **70% reduction** in email management time
- **<5 seconds** email-to-categorization latency
- **<$50/month** operational cost for 1000 emails/day
- **99.9% uptime** with zero duplicate processing

---

## **1. Product Vision and Goals**

### **Vision**
Transform Gmail from a reactive inbox into an intelligent, automated workspace assistant that understands context, learns from user preferences, and handles routine email management tasks autonomously while maintaining human oversight for important decisions.

### **Core Objectives**
1. **Intelligent Categorization**: Hierarchical email organization with 91% baseline accuracy
2. **Proactive Importance Detection**: Multi-factor scoring prevents missed critical emails
3. **Automated Knowledge Capture**: Obsidian integration creates linked, searchable records
4. **Smart Unsubscribe**: Bulk newsletter management with one-click execution
5. **Calendar Intelligence**: Automatic event extraction from reservations and invitations
6. **Cost-Optimized Processing**: Tiered LLM usage reduces costs by 80-95%

---

## **2. User Personas**

### **Primary: Knowledge Worker**
- **Volume**: 50-150 emails/day
- **Pain Points**: Important emails buried, 30-60 min daily filing, newsletter overload
- **Needs**: Automated organization, instant action items, conversation tracking

### **Secondary: Executive**
- **Volume**: 200+ emails/day
- **Pain Points**: Can't keep up, critical emails mixed with noise
- **Needs**: Ultra-accurate importance detection, delegable workflows, quick context

---

## **3. Core Features**

### **3.1 Intelligent Email Categorization**

**Requirements:**
- **FR-CAT-001**: Hierarchical categories (Personal/Friends, Professional/Recruiters, Purchases/Amazon, Reservations/Hotels, Newsletters/Substacks, Marketing, Important)
- **FR-CAT-002**: Dynamic folder creation when taxonomy insufficient
- **FR-CAT-003**: Confidence scoring (0-1.0) with <0.8 triggering human approval
- **FR-CAT-004**: Active learning from user corrections
- **FR-CAT-005**: 91% accuracy baseline, 95% target within 30 days

**User Stories:**
- "As a user, I want newsletters sorted by publication so I can read them on my schedule"
- "As a user, I want new categories suggested when patterns emerge so my taxonomy stays current"

### **3.2 Historical Email Processing**

**Requirements:**
- **FR-HIST-001**: One-time sweep with date range selection
- **FR-HIST-002**: Batch processing (100 emails) with checkpoint recovery
- **FR-HIST-003**: Progress tracking and pause/resume capability
- **FR-HIST-004**: Idempotency—no duplicate processing on retry
- **FR-HIST-005**: Process 10,000 emails in <6 hours

### **3.3 Importance Detection**

**Requirements:**
- **FR-IMP-001**: Multi-factor scoring (sender authority, urgency keywords, deadlines, financial impact, operational criticality)
- **FR-IMP-002**: Extract action items (task, assignee, deadline, priority)
- **FR-IMP-003**: Propose new importance rules based on patterns
- **FR-IMP-004**: <5% false negatives, <15% false positives
- **FR-IMP-005**: Flag important emails within 5 seconds

### **3.4 Smart Unsubscribe Management**

**Requirements:**
- **FR-UNSUB-001**: Detect List-Unsubscribe headers, mailto/HTTP links
- **FR-UNSUB-002**: RFC 8058 one-click unsubscribe support
- **FR-UNSUB-003**: Batch recommendations (Approve/Deny/Snooze)
- **FR-UNSUB-004**: Auto-execute within 2 days (Gmail compliance)
- **FR-UNSUB-005**: 95% successful execution rate

### **3.5 Calendar Event Creation**

**Requirements:**
- **FR-CAL-001**: Extract title, date/time, duration, location, attendees, virtual links
- **FR-CAL-002**: Support meetings, reservations (hotel/restaurant/flight), appointments
- **FR-CAL-003**: User approval before creation
- **FR-CAL-004**: 90% date/time extraction accuracy
- **FR-CAL-005**: Timezone detection and ISO 8601 formatting

### **3.6 Draft Reply Generation**

**Requirements:**
- **FR-REPLY-001**: Contextually appropriate drafts for common email types
- **FR-REPLY-002**: Configurable styles (Professional, Friendly, Formal)
- **FR-REPLY-003**: Personalization (user name, role, signature)
- **FR-REPLY-004**: Address all questions in multi-point emails
- **FR-REPLY-005**: 80% acceptance with minor edits
- **FR-REPLY-006**: <8 seconds generation time

### **3.7 Obsidian Knowledge Base**

**Requirements:**
- **FR-OBS-001**: Separate notes per company/topic with automatic linking
- **FR-OBS-002**: YAML frontmatter (email_id, message_id, thread_id, from, to, date, labels, category, confidence)
- **FR-OBS-003**: Folder structure (inbox/, projects/, archive/, _system/)
- **FR-OBS-004**: WikiLink syntax for relationships ([[Company Name]], [[Project]])
- **FR-OBS-005**: Tags for categories (#work, #personal, #purchase)
- **FR-OBS-006**: Dataview-compatible metadata

### **3.8 CLI Approval Interface**

**Requirements:**
- **FR-CLI-001**: Terminal interface for approval workflows
- **FR-CLI-002**: Single-key actions (A/D/S/E/V for Approve/Deny/Snooze/Edit/View)
- **FR-CLI-003**: Context display (email snippet, sender, confidence, similar decisions)
- **FR-CLI-004**: Color-coded status (Green/Red/Yellow/Blue)
- **FR-CLI-005**: Batch operations ("Approve all >0.9 confidence")
- **FR-CLI-006**: <2 minutes daily for typical workflows
- **FR-CLI-007**: Keyboard-only navigation

---

## **4. System Architecture**

### **4.1 Technology Stack**

**Core Framework:**
- Python 3.11+, LangGraph 0.2+, LangChain, FastAPI

**LLM Provider (Anthropic):**
- Claude Haiku: High-volume categorization, fast/cheap tasks
- Claude Sonnet: Complex reasoning, drafts, quality tasks

**Infrastructure (GCP):**
- Cloud Run: Serverless containers (4 vCPU, 8GB RAM, 60min timeout)
- Cloud Scheduler: Hourly triggers → Gmail Pub/Sub (real-time)
- Cloud SQL (PostgreSQL): State/checkpoints
- Secret Manager: API keys, credentials
- Artifact Registry: Docker images
- Terraform: Infrastructure as Code

**APIs:**
- Gmail API, Google Calendar API, Google Cloud Pub/Sub

### **4.2 Multi-Agent Architecture**

**Agents:**
1. Categorization Agent: Email → Category + Confidence
2. Importance Agent: Email → Priority + Action Items
3. Calendar Agent: Email → Event Details
4. Unsubscribe Agent: Email → Recommendation
5. Reply Agent: Email → Draft Response
6. Obsidian Agent: Email → Knowledge Base Entry

**Orchestration:** LangGraph StateGraph with conditional routing

---

## **5. User Workflows**

### **5.1 Initial Setup**
1. OAuth2 domain-wide delegation
2. Define category taxonomy
3. Historical processing (select date range)
4. Configure importance rules
5. Set preferences (reply style, Obsidian paths)

### **5.2 Daily Operations**

**Hourly Automated (Phase 1-3):**
- Cloud Scheduler triggers processing
- Multi-agent workflow processes each email
- Uncertain decisions queued for CLI approval
- User notified when approvals pending

**Real-Time (Phase 4):**
- Gmail Push via Pub/Sub
- Sub-second latency
- Immediate important email alerts

### **5.3 CLI Approval Workflow**

```
┌─────────────────────────────────────────────────┐
│ Pending Approvals: 12 items                    │
├─────────────────────────────────────────────────┤
│ [1/12] Categorization: Professional > Recruiter│
│ From: jane@techcorp.com                        │
│ Subject: Senior Engineer Position              │
│ Confidence: 0.75                               │
│ Reasoning: Job-related keywords, recruiter     │
│ Similar past: 3 approved, 0 denied             │
│ [A]pprove [D]eny [S]nooze [V]iew [N]ext       │
└─────────────────────────────────────────────────┘
```

---

## **6. Security & Privacy**

**Security:**
- OAuth2 service account with minimal scopes
- Secret Manager for credentials (90-day rotation)
- Cloud Audit Logs, TLS 1.3, RBAC

**Privacy:**
- Email content not stored permanently
- LLM APIs don't train on data
- Obsidian notes stored locally
- GDPR-compliant, SOC 2 Type II controls

---

## **7. Performance & Scalability**

**Targets:**
- <5s latency (email receipt to categorization)
- 100 emails/day → 1000 emails/day scalability
- 99.9% uptime
- <$50/month for 1000 emails/day

**Optimization:**
- Horizontal scaling (Cloud Run 1-10 instances)
- Async processing (Celery + Redis)
- Batch API operations (100 emails/request)
- Tiered LLM usage (80% cheap, 20% premium)

---

## **8. Release Roadmap**

### **Phase 1: MVP (Weeks 1-4)**
- Basic categorization (4-6 categories)
- Historical processing
- CLI approval interface
- PostgreSQL state management
- Cloud Run deployment with hourly scheduler
- **Success:** 85% accuracy, <10s per email

### **Phase 2: Enhanced Intelligence (Weeks 5-8)**
- Importance detection + action items
- Calendar event creation
- Unsubscribe management
- Tiered model usage
- Active learning feedback
- **Success:** 90% accuracy, <5% missed important emails

### **Phase 3: Knowledge Management (Weeks 9-12)**
- Obsidian integration
- Draft reply generation
- Dynamic category creation
- Batch CLI operations
- Monitoring dashboard
- **Success:** 95% accuracy, 80% draft acceptance

### **Phase 4: Real-Time (Weeks 13-16)**
- Gmail Pub/Sub push notifications
- <5s real-time processing
- Advanced error recovery
- Load testing
- Cost optimization
- **Success:** 1000 emails/day, <$50/month

---

## **9. Risks & Mitigation**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gmail API rate limits | High | Exponential backoff, quota monitoring, batch operations |
| LLM hallucination | Medium | Confidence thresholds, human approval, feedback loop |
| Service account key leak | High | Secret Manager, 90-day rotation, audit logs |
| Too many approvals | Medium | Aggressive thresholds, batch approvals, active learning |
| Cost overruns | High | Model tiering, caching, budget alerts |

---

## **10. Success Metrics**

**Accuracy:**
- Categorization: 91% baseline → 95% target
- Importance detection: <5% false negatives
- Calendar extraction: 90% accuracy

**Performance:**
- Latency: <5 seconds
- Throughput: 1000 emails/day
- Uptime: 99.9%

**User Experience:**
- Approval time: <2 minutes/day
- Draft acceptance: 80%
- User satisfaction: >80%

**Cost:**
- <$0.05 per email
- <$50/month at 1000 emails/day

---

# **TECHNICAL SPECIFICATION DOCUMENT**

## **1. System Architecture**

### **1.1 High-Level Architecture**

```
┌─────────────────────────────────────────────────────────┐
│                    TRIGGER LAYER                        │
│  Cloud Scheduler (Hourly) │ Gmail Pub/Sub (Real-time)  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              CLOUD RUN SERVICE (FastAPI)                │
│  ┌───────────────────────────────────────────────────┐  │
│  │     LangGraph Multi-Agent Orchestrator            │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐     │  │
│  │  │Categorize│→│Importance│→│  Calendar    │     │  │
│  │  └──────────┘ └──────────┘ └──────────────┘     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐     │  │
│  │  │Unsubscribe│ │  Reply   │ │   Obsidian   │     │  │
│  │  └──────────┘ └──────────┘ └──────────────┘     │  │
│  └───────────────────────────────────────────────────┘  │
└────────────┬────────────┬────────────┬──────────────────┘
             │            │            │
             ▼            ▼            ▼
       ┌─────────┐  ┌─────────┐  ┌─────────┐
       │ Gmail   │  │Calendar │  │Obsidian │
       │  API    │  │   API   │  │ (Local) │
       └─────────┘  └─────────┘  └─────────┘

┌─────────────────────────────────────────────────────────┐
│               PERSISTENCE LAYER                         │
│  PostgreSQL  │  Redis Cache  │  Cloud Storage          │
│  (State)     │  (LLM Cache)  │  (Logs/Backups)         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               LLM PROVIDER LAYER                        │
│  Anthropic (Claude Haiku + Claude Sonnet)               │
└─────────────────────────────────────────────────────────┘
```

---

## **2. LangGraph Agent Implementation**

### **2.1 State Definition**

```python
from typing import Annotated, TypedDict, Literal
from langgraph.graph.message import add_messages

class EmailState(TypedDict):
    # Email metadata
    email_id: str
    message_id: str
    thread_id: str
    from_email: str
    to_emails: list[str]
    subject: str
    date: str
    body: str
    headers: dict
    
    # Processing state
    messages: Annotated[list, add_messages]
    processing_step: str
    
    # Agent outputs
    category: str
    confidence: float
    reasoning: str
    importance_level: Literal["critical", "high", "normal", "low"]
    action_items: list[dict]
    calendar_event: dict | None
    unsubscribe_recommendation: dict | None
    draft_reply: str | None
    obsidian_note_path: str | None
    
    # Control flow
    needs_human_approval: bool
    approval_type: Literal["categorization", "importance_rule", "unsubscribe", "calendar"]
    error: str | None
```

### **2.2 LangGraph Workflow**

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

# Create workflow
workflow = StateGraph(EmailState)

# Add nodes
workflow.add_node("fetch_email", fetch_email_node)
workflow.add_node("categorize", categorization_agent)
workflow.add_node("importance", importance_agent)
workflow.add_node("calendar", calendar_agent)
workflow.add_node("unsubscribe", unsubscribe_agent)
workflow.add_node("obsidian", obsidian_agent)
workflow.add_node("reply", reply_agent)
workflow.add_node("apply_labels", apply_gmail_labels)
workflow.add_node("human_approval", human_approval_node)

# Conditional routing
def should_check_calendar(state: EmailState) -> str:
    if any(kw in state["body"].lower() 
           for kw in ["meeting", "appointment", "reservation"]):
        return "calendar"
    return "unsubscribe"

def needs_approval(state: EmailState) -> str:
    if state["confidence"] < 0.8 or state["needs_human_approval"]:
        return "human_approval"
    return "apply_labels"

# Build graph
workflow.add_edge(START, "fetch_email")
workflow.add_edge("fetch_email", "categorize")
workflow.add_edge("categorize", "importance")
workflow.add_conditional_edges("importance", should_check_calendar)
workflow.add_edge("calendar", "unsubscribe")
workflow.add_edge("unsubscribe", "obsidian")
workflow.add_conditional_edges("obsidian", needs_approval)
workflow.add_edge("human_approval", "apply_labels")
workflow.add_edge("apply_labels", "reply")
workflow.add_edge("reply", END)

# Compile with checkpointing
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
app = workflow.compile(checkpointer=checkpointer)
```

### **2.3 Categorization Agent**

```python
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

class CategorizationAgent:
    def __init__(self):
        self.fast_model = ChatAnthropic(model="claude-3-haiku-20240307", temperature=0)
        self.smart_model = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert email classifier.

Categories:
{categories}

Classify the email into EXACTLY ONE category.

Response Format (JSON only):
{{
  "category": "<CATEGORY_PATH>",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>",
  "key_phrases": ["<phrase1>", "<phrase2>"]
}}"""),
            ("human", "Subject: {subject}\nFrom: {from_email}\nBody: {body}")
        ])
    
    def __call__(self, state: EmailState) -> EmailState:
        # First pass: Fast model
        chain = self.prompt | self.fast_model
        result = chain.invoke({
            "categories": self.format_categories(),
            "subject": state["subject"],
            "from_email": state["from_email"],
            "body": state["body"][:10000]
        })
        
        classification = json.loads(result.content)
        
        # Second pass: Smart model if uncertain
        if classification["confidence"] < 0.7:
            chain = self.prompt | self.smart_model
            result = chain.invoke({...})
            classification = json.loads(result.content)
        
        state["category"] = classification["category"]
        state["confidence"] = classification["confidence"]
        state["reasoning"] = classification["reasoning"]
        state["needs_human_approval"] = classification["confidence"] < 0.8
        
        return state
```

---

## **3. Gmail API Integration**

### **3.1 Service Account Setup**

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.events'
]

def get_delegated_credentials(user_email: str):
    credentials = service_account.Credentials.from_service_account_file(
        'service-account-key.json',
        scopes=SCOPES
    )
    return credentials.with_subject(user_email)

def build_gmail_service(user_email: str):
    creds = get_delegated_credentials(user_email)
    return build('gmail', 'v1', credentials=creds)
```

### **3.2 Rate-Limited Email Fetching**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class GmailClient:
    def __init__(self, user_email: str):
        self.service = build_gmail_service(user_email)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
    def list_messages(self, query: str = '', max_results: int = 100):
        response = self.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        return response.get('messages', [])
    
    def batch_get_messages(self, message_ids: list[str]):
        batch = self.service.new_batch_http_request()
        messages = []
        
        def callback(request_id, response, exception):
            if not exception:
                messages.append(response)
        
        for msg_id in message_ids[:100]:  # Gmail limit: 100/batch
            batch.add(self.service.users().messages().get(
                userId='me', id=msg_id, format='full'), callback=callback)
        
        batch.execute()
        return messages
```

### **3.3 Label Management**

```python
class GmailLabelManager:
    def get_or_create_label(self, label_path: str) -> str:
        # Check cache
        if label_path in self._cache:
            return self._cache[label_path]
        
        # Check existing
        labels = self.service.users().labels().list(userId='me').execute()
        for label in labels.get('labels', []):
            if label['name'] == label_path:
                return label['id']
        
        # Create new
        created = self.service.users().labels().create(
            userId='me',
            body={'name': label_path, 'labelListVisibility': 'labelShow'}
        ).execute()
        return created['id']
    
    def apply_label(self, message_id: str, label_path: str):
        label_id = self.get_or_create_label(label_path)
        self.service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'addLabelIds': [label_id]}
        ).execute()
```

### **3.4 Pub/Sub Real-Time Processing**

```python
from google.cloud import pubsub_v1

class GmailPushHandler:
    def setup_watch(self, user_email: str):
        service = build_gmail_service(user_email)
        watch_request = {
            'topicName': f'projects/{PROJECT_ID}/topics/gmail-notifications',
            'labelIds': ['INBOX']
        }
        response = service.users().watch(userId='me', body=watch_request).execute()
        return response['historyId']
    
    def handle_notification(self, message_data: str):
        decoded = base64.b64decode(message_data).decode('utf-8')
        notification = json.loads(decoded)
        
        email_address = notification['emailAddress']
        history_id = notification['historyId']
        
        # Fetch new messages
        changes = self.fetch_history(email_address, history_id)
        for change in changes:
            if 'messagesAdded' in change:
                for msg in change['messagesAdded']:
                    self.process_email(email_address, msg['message']['id'])
```

---

## **4. GCP Infrastructure (Terraform)**

### **4.1 Complete Terraform Configuration**

```hcl
# terraform/main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com"
  ])
  service = each.value
}

# Artifact Registry
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "email-agent"
  format        = "DOCKER"
}

# Service Account
resource "google_service_account" "agent" {
  account_id   = "email-agent-sa"
  display_name = "Email Agent Service Account"
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "agent" {
  name     = "email-agent"
  location = var.region
  
  template {
    timeout = "3600s"
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/email-agent/app:latest"
      
      resources {
        limits = {
          cpu    = "4"
          memory = "8Gi"
        }
        cpu_idle = false
        startup_cpu_boost = true
      }
      
      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_key.secret_id
            version = "latest"
          }
        }
      }
    }
    
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
    
    service_account = google_service_account.agent.email
  }
}

# Cloud SQL (PostgreSQL)
resource "google_sql_database_instance" "postgres" {
  name             = "email-agent-db"
  database_version = "POSTGRES_15"
  region           = var.region
  
  settings {
    tier = "db-f1-micro"
    
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "cloud-run"
        value = "0.0.0.0/0"
      }
    }
    
    backup_configuration {
      enabled = true
      start_time = "03:00"
    }
  }
}

resource "google_sql_database" "database" {
  name     = "email_agent"
  instance = google_sql_database_instance.postgres.name
}

# Secret Manager
resource "google_secret_manager_secret" "anthropic_key" {
  secret_id = "anthropic-api-key"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_iam_member" "agent_access" {
  secret_id = google_secret_manager_secret.anthropic_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}

# Cloud Scheduler
resource "google_cloud_scheduler_job" "hourly_processor" {
  name      = "hourly-email-processor"
  schedule  = "0 * * * *"
  time_zone = "America/New_York"
  
  http_target {
    http_method = "POST"
    uri         = google_cloud_run_v2_service.agent.uri
    
    oidc_token {
      service_account_email = google_service_account.agent.email
    }
  }
  
  retry_config {
    retry_count = 3
  }
}

# Pub/Sub Topic (for Gmail push)
resource "google_pubsub_topic" "gmail_notifications" {
  name = "gmail-notifications"
}

resource "google_pubsub_subscription" "gmail_push" {
  name  = "gmail-push-sub"
  topic = google_pubsub_topic.gmail_notifications.name
  
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.agent.uri}/webhook"
    
    oidc_token {
      service_account_email = google_service_account.agent.email
    }
  }
}
```

---

## **5. Database Schema**

```sql
-- PostgreSQL Schema

CREATE TABLE emails (
    email_id VARCHAR(255) PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    thread_id VARCHAR(255),
    from_email VARCHAR(255) NOT NULL,
    to_emails TEXT[],
    subject TEXT,
    date TIMESTAMP NOT NULL,
    category VARCHAR(255),
    confidence FLOAT,
    importance_level VARCHAR(20),
    processed_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_date (date),
    INDEX idx_category (category),
    INDEX idx_from (from_email)
);

CREATE TABLE checkpoints (
    checkpoint_id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) REFERENCES emails(email_id),
    step VARCHAR(100) NOT NULL,
    state_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feedback (
    feedback_id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) REFERENCES emails(email_id),
    user_action VARCHAR(50) NOT NULL,
    proposed_category VARCHAR(255),
    final_category VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE importance_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_type VARCHAR(50) NOT NULL,
    pattern TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE unsubscribe_queue (
    queue_id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) REFERENCES emails(email_id),
    sender VARCHAR(255) NOT NULL,
    method VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    user_action VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE processing_log (
    log_id SERIAL PRIMARY KEY,
    email_id VARCHAR(255),
    agent VARCHAR(100),
    action VARCHAR(100),
    status VARCHAR(50),
    error TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

---

## **6. Deployment Process**

### **6.1 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY config/ ./config/

# Non-root user
RUN useradd -m agent && chown -R agent:agent /app
USER agent

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### **6.2 GitHub Actions CI/CD**

```yaml
name: Deploy Email Agent

on:
  push:
    branches: [main]

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1
  SERVICE: email-agent

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/ --cov=src

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      
      - name: Build and push
        run: |
          gcloud auth configure-docker $REGION-docker.pkg.dev
          docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/email-agent/app:${{ github.sha }} .
          docker push $REGION-docker.pkg.dev/$PROJECT_ID/email-agent/app:${{ github.sha }}
      
      - uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE }}
          region: ${{ env.REGION }}
          image: ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/email-agent/app:${{ github.sha }}
```

---

## **7. CLI Interface Implementation**

```python
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

class ApprovalCLI:
    def __init__(self):
        self.console = Console()
    
    def show_pending_approvals(self, approvals: list[dict]):
        for idx, approval in enumerate(approvals, 1):
            self.console.clear()
            
            # Header
            self.console.print(f"[bold]Pending Approvals: {idx}/{len(approvals)}[/bold]\n")
            
            # Approval details
            table = Table(show_header=False, box=None)
            table.add_row("[bold]Type:[/bold]", approval['type'])
            table.add_row("[bold]From:[/bold]", approval['from_email'])
            table.add_row("[bold]Subject:[/bold]", approval['subject'])
            table.add_row("[bold]Confidence:[/bold]", f"{approval['confidence']:.2f}")
            table.add_row("[bold]Category:[/bold]", approval['category'])
            table.add_row("[bold]Reasoning:[/bold]", approval['reasoning'])
            
            self.console.print(table)
            
            # Action prompt
            action = Prompt.ask(
                "\n[bold][A]pprove [D]eny [S]nooze [V]iew Full [N]ext[/bold]",
                choices=["a", "d", "s", "v", "n"],
                default="a"
            )
            
            if action == "a":
                self.approve(approval)
            elif action == "d":
                self.deny(approval)
            elif action == "s":
                self.snooze(approval)
            elif action == "v":
                self.view_full(approval)
            elif action == "n":
                continue
    
    def approve(self, approval: dict):
        # Apply categorization
        apply_gmail_label(approval['email_id'], approval['category'])
        # Record feedback
        record_feedback(approval['email_id'], 'approved', approval['category'])
        self.console.print("[green]✓ Approved[/green]")
        time.sleep(0.5)
    
    def deny(self, approval: dict):
        correct_category = Prompt.ask("Enter correct category")
        apply_gmail_label(approval['email_id'], correct_category)
        record_feedback(approval['email_id'], 'denied', correct_category)
        self.console.print("[red]✗ Denied - Corrected[/red]")
        time.sleep(0.5)
```

---

## **8. Error Handling & Recovery**

### **8.1 Retry with Exponential Backoff**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((RateLimitError, TimeoutError))
)
def process_with_retry(email_id: str):
    try:
        return agent_workflow.invoke({"email_id": email_id})
    except Exception as e:
        log_error(email_id, str(e))
        raise
```

### **8.2 Circuit Breaker**

```python
from pybreaker import CircuitBreaker

gmail_breaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=60,
    name="gmail_api"
)

@gmail_breaker
def call_gmail_api():
    return gmail_client.list_messages()
```

### **8.3 Dead Letter Queue**

```python
def process_email(email_id: str):
    try:
        result = agent_workflow.invoke({"email_id": email_id})
    except PermanentError as e:
        # Move to DLQ for manual review
        dead_letter_queue.add(email_id, error=str(e))
        alert_admin(f"Email {email_id} moved to DLQ")
    except TransientError:
        # Retry later
        retry_queue.add(email_id, delay=300)
```

---

## **9. Monitoring & Observability**

### **9.1 Logging**

```python
import structlog

logger = structlog.get_logger()

def process_email(email_id: str):
    logger.info("processing_started", email_id=email_id)
    
    try:
        result = agent_workflow.invoke({"email_id": email_id})
        logger.info("processing_completed", 
                   email_id=email_id,
                   category=result['category'],
                   confidence=result['confidence'],
                   latency_ms=result['latency'])
    except Exception as e:
        logger.error("processing_failed",
                    email_id=email_id,
                    error=str(e),
                    exc_info=True)
        raise
```

### **9.2 Metrics**

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
emails_processed = Counter('emails_processed_total', 'Total emails processed', ['category', 'status'])
api_calls = Counter('api_calls_total', 'Total API calls', ['provider', 'model'])

# Histograms
processing_latency = Histogram('processing_latency_seconds', 'Processing latency')
llm_latency = Histogram('llm_latency_seconds', 'LLM API latency', ['provider'])

# Gauges
approval_queue_size = Gauge('approval_queue_size', 'Pending approvals')
```

### **9.3 Alerts**

```yaml
# Cloud Monitoring Alert Policies
alerts:
  - name: high_error_rate
    condition: error_rate > 10% over 5 minutes
    notification: email, slack
  
  - name: api_quota_exceeded
    condition: gmail_api_quota > 90%
    notification: pagerduty
  
  - name: processing_latency_high
    condition: p95_latency > 10 seconds
    notification: email
  
  - name: approval_queue_growing
    condition: approval_queue_size > 50
    notification: email
```

---

## **10. Testing Strategy**

### **10.1 Unit Tests**

```python
import pytest
from src.agents.categorization import CategorizationAgent

def test_categorization_agent():
    agent = CategorizationAgent()
    
    state = {
        "subject": "Job Opportunity at Tech Corp",
        "from_email": "recruiter@techcorp.com",
        "body": "We have an exciting position..."
    }
    
    result = agent(state)
    
    assert result['category'] == "Professional/Recruiters"
    assert result['confidence'] > 0.8
    assert 'job' in result['reasoning'].lower()

def test_idempotency():
    email_id = "test-123"
    
    # Process twice
    result1 = process_email(email_id)
    result2 = process_email(email_id)
    
    # Should only process once
    assert result2 == "already_processed"
    assert db.count_where(email_id=email_id) == 1
```

### **10.2 Integration Tests**

```python
def test_gmail_to_obsidian_flow():
    # Mock Gmail API
    with patch('gmail_client.get_message') as mock_gmail:
        mock_gmail.return_value = sample_email
        
        # Run workflow
        result = agent_workflow.invoke({"email_id": "test-123"})
        
        # Verify Obsidian note created
        assert Path(result['obsidian_note_path']).exists()
        
        # Verify note content
        note = Path(result['obsidian_note_path']).read_text()
        assert sample_email['subject'] in note
        assert f"[[{sample_email['company']}]]" in note
```

### **10.3 Load Testing**

```python
# locustfile.py
from locust import HttpUser, task, between

class EmailProcessingUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def process_email(self):
        self.client.post("/process", json={
            "trigger": "manual",
            "email_ids": [f"test-{random.randint(1, 1000)}"]
        })
```

---

## **11. Cost Optimization**

### **11.1 Model Tiering Strategy**

```python
class CostOptimizedLLMRouter:
    def select_model(self, task: str, confidence_required: float) -> str:
        if task == "simple_categorization":
            return "claude-3-haiku-20240307"  # Fast/cheap
        elif task == "complex_reasoning" and confidence_required > 0.9:
            return "claude-sonnet-4-20250514"  # Quality
        elif task == "draft_reply":
            return "claude-sonnet-4-20250514"  # Best quality
        else:
            return "claude-3-haiku-20240307"  # Default to fast

    def estimate_cost(self, tokens: int, model: str) -> float:
        prices = {
            "claude-3-haiku-20240307": 0.25 / 1_000_000,
            "claude-sonnet-4-20250514": 3.00 / 1_000_000,
        }
        return tokens * prices.get(model, 0)
```

### **11.2 Caching Strategy**

```python
import hashlib
from functools import lru_cache

class LLMCacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def get_cached_response(self, prompt: str, model: str) -> str | None:
        cache_key = f"llm:{model}:{hashlib.md5(prompt.encode()).hexdigest()}"
        return self.redis.get(cache_key)
    
    def cache_response(self, prompt: str, model: str, response: str, ttl: int = 86400):
        cache_key = f"llm:{model}:{hashlib.md5(prompt.encode()).hexdigest()}"
        self.redis.setex(cache_key, ttl, response)
```

---

## **12. Security Best Practices**

### **12.1 Secret Management**

```python
from google.cloud import secretmanager

def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Usage
ANTHROPIC_API_KEY = get_secret("anthropic-api-key")
```

### **12.2 Service Account Key Rotation**

```bash
#!/bin/bash
# rotate-service-account-key.sh

# Create new key
gcloud iam service-accounts keys create new-key.json \
  --iam-account=email-agent-sa@PROJECT.iam.gserviceaccount.com

# Update Secret Manager
gcloud secrets versions add service-account-key \
  --data-file=new-key.json

# Delete old keys (keep only latest 2)
gcloud iam service-accounts keys list \
  --iam-account=email-agent-sa@PROJECT.iam.gserviceaccount.com \
  --filter="validAfterTime<$(date -d '90 days ago' -Iminutes)" \
  --format="value(name)" | \
  xargs -I {} gcloud iam service-accounts keys delete {}
```

---

## **13. Development Guidelines**

### **13.1 Project Structure**

```
email-agent/
├── src/
│   ├── main.py                 # FastAPI application
│   ├── agents/
│   │   ├── categorization.py
│   │   ├── importance.py
│   │   ├── calendar.py
│   │   ├── unsubscribe.py
│   │   ├── reply.py
│   │   └── obsidian.py
│   ├── services/
│   │   ├── gmail_client.py
│   │   ├── calendar_client.py
│   │   └── llm_router.py
│   ├── workflows/
│   │   └── email_workflow.py
│   ├── cli/
│   │   └── approval_interface.py
│   └── utils/
│       ├── database.py
│       ├── cache.py
│       └── logging.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── load/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── modules/
├── config/
│   ├── categories.yaml
│   └── importance_rules.yaml
├── Dockerfile
├── requirements.txt
└── README.md
```

### **13.2 Configuration Management**

```yaml
# config/categories.yaml
categories:
  - id: 1
    name: "Personal"
    description: "Emails from friends and family"
    children:
      - id: 11
        name: "Friends"
      - id: 12
        name: "Family"
  
  - id: 2
    name: "Professional"
    description: "Work-related emails"
    children:
      - id: 21
        name: "Recruiters"
      - id: 22
        name: "School"
  
  - id: 3
    name: "Purchases"
    children:
      - id: 31
        name: "Amazon"
      - id: 32
        name: "Etsy"
```

---

## **14. Implementation Checklist**

### **Phase 1: MVP (Weeks 1-4)**
- [ ] Set up GCP project and enable APIs
- [ ] Create service account with domain-wide delegation
- [ ] Implement Gmail API client with rate limiting
- [ ] Build basic categorization agent (Claude Haiku)
- [ ] Set up PostgreSQL database and schema
- [ ] Implement LangGraph workflow with checkpointing
- [ ] Create CLI approval interface
- [ ] Deploy to Cloud Run with Cloud Scheduler
- [ ] Implement historical email processing
- [ ] Add basic monitoring and logging

### **Phase 2: Enhanced Intelligence (Weeks 5-8)**
- [ ] Implement importance detection agent
- [ ] Add action item extraction
- [ ] Build calendar event creation agent
- [ ] Implement unsubscribe detection and management
- [ ] Add tiered model usage (Claude Haiku + Claude Sonnet)
- [ ] Implement feedback loop and active learning
- [ ] Add Redis caching for LLM responses
- [ ] Create monitoring dashboard

### **Phase 3: Knowledge Management (Weeks 9-12)**
- [ ] Implement Obsidian agent with note creation
- [ ] Add WikiLink generation and automatic linking
- [ ] Build draft reply generation agent
- [ ] Implement dynamic category creation
- [ ] Add batch CLI operations
- [ ] Implement rule suggestion system
- [ ] Add comprehensive error handling (circuit breaker, DLQ)

### **Phase 4: Real-Time Processing (Weeks 13-16)**
- [ ] Set up Gmail Push Notifications via Pub/Sub
- [ ] Implement real-time webhook handler
- [ ] Add auto-renewal for Gmail watch mechanism
- [ ] Optimize for <5s latency
- [ ] Implement advanced recovery patterns
- [ ] Conduct load testing (1000 emails/day)
- [ ] Optimize costs (<$50/month target)
- [ ] Complete documentation

---

## **15. Key Technical Decisions**

### **Decision 1: LangGraph vs Custom Orchestration**
**Choice:** LangGraph  
**Rationale:** Built-in state management, checkpointing, human-in-the-loop support, reduces custom code

### **Decision 2: Cloud Run vs GKE**
**Choice:** Cloud Run  
**Rationale:** Simpler ops, 60min timeout sufficient, auto-scaling, pay-per-use cost model

### **Decision 3: Service Account vs OAuth User**
**Choice:** Service Account with Domain-Wide Delegation  
**Rationale:** No user consent screens, centralized management, suitable for automation

### **Decision 4: PostgreSQL vs NoSQL**
**Choice:** PostgreSQL  
**Rationale:** ACID transactions, complex queries, relational data (emails ↔ feedback ↔ rules)

### **Decision 5: Tiered Models vs Single Model**
**Choice:** Tiered (Claude Haiku + Claude Sonnet)
**Rationale:** 80-95% cost savings, 95% tasks don't need premium models

---

## **16. Success Criteria**

### **Technical Metrics**
- ✓ 95% categorization accuracy
- ✓ <5 seconds processing latency (p95)
- ✓ 99.9% uptime (43 min downtime/month)
- ✓ Zero duplicate processing (100% idempotency)
- ✓ <$50/month at 1000 emails/day

### **User Metrics**
- ✓ <2 minutes daily approval time
- ✓ 80% draft reply acceptance rate
- ✓ <5% missed important emails
- ✓ >80% user satisfaction

### **Operational Metrics**
- ✓ <10 minutes deployment time
- ✓ <1 hour recovery time (RTO)
- ✓ Zero data loss (RPO = 0)
- ✓ 100% audit trail coverage

---

**This comprehensive PRD and Technical Specification provides a complete blueprint for implementing a production-ready Gmail inbox management system with multi-agent AI, combining the research findings on Gmail APIs, LangGraph architecture, GCP infrastructure, email processing strategies, and integration patterns into actionable specifications for development.**