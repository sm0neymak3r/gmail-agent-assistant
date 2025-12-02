# Gmail Agent: Multi-Agent Email Classification System

**Author:** Martin Hyman
**Date:** December 2025
**Status:** Phase 1 & 2 Complete | Production Deployed

---

## Executive Summary

I designed and built a **production-grade multi-agent email processing system** that processes emails using LLM-powered workflows on GCP. The system demonstrates expertise in **agentic AI orchestration**, **enterprise cloud deployment**, and **reliable distributed processing**—capabilities directly applicable to deploying autonomous coding agents in customer environments.

**Key Outcomes:**
- **65K emails processed** through autonomous batch execution
- **99.2% success rate** with robust error handling
- **80% cost reduction** via intelligent model escalation
- **36 Terraform-managed resources** with IaC discipline
- **Zero manual intervention** during 11-year inbox backfill (AUTHOR NOTE: excluding manual approval CLI for low confidence scores)
- **Phase 2 multi-agent workflow** with importance scoring, calendar extraction, and unsubscribe management

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TRIGGER LAYER                                 │
│   ┌─────────────────┐         ┌─────────────────────────────────────┐   │
│   │ Cloud Scheduler │         │ Cloud Tasks Queue                   │   │
│   │  (Hourly Cron)  │         │  • OIDC authentication              │   │
│   └────────┬────────┘         │  • 4 retries, exponential backoff   │   │
│            │                  │  • Self-continuation pattern        │   │
│            │                  └──────────────┬──────────────────────┘   │
└────────────┼─────────────────────────────────┼──────────────────────────┘
             │ POST + OIDC                     │ POST /batch-worker
             ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          COMPUTE LAYER                                  │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    Cloud Run (Serverless)                       │   │
│   │   ┌───────────────────────────────────────────────────────────┐ │   │
│   │   │          LangGraph Multi-Agent Workflow (Phase 2)         │ │   │
│   │   │                                                           │ │   │
│   │   │  ┌────────┐   ┌───────────┐   ┌────────────┐              │ │   │
│   │   │  │ Fetch  │──►│Categorize │──►│ Importance │              │ │   │
│   │   │  │ Email  │   │(Haiku→    │   │   Agent    │              │ │   │
│   │   │  │        │   │ Sonnet)   │   │ (6 factors)│              │ │   │
│   │   │  └────────┘   └───────────┘   └─────┬──────┘              │ │   │
│   │   │                                     │                     │ │   │
│   │   │               ┌─────────────────────┼─────────────────┐   │ │   │
│   │   │               ▼                     ▼                 ▼   │ │   │
│   │   │        ┌───────────┐         ┌───────────┐     ┌────────┐ │ │   │
│   │   │        │ Calendar  │         │Unsubscribe│     │Finalize│ │ │   │
│   │   │        │   Agent   │         │   Agent   │     │(bypass)│ │ │   │
│   │   │        │┌─────────┐│         │ RFC 2369  │     └────┬───┘ │ │   │
│   │   │        ││FreeBusy ││         │ RFC 8058  │          │     │ │   │
│   │   │        ││  Tool   ││         │ Headers   │          │     │ │   │
│   │   │        │└─────────┘│         └─────┬─────┘          │     │ │   │
│   │   │        └─────┬─────┘               │                │     │ │   │
│   │   │              └─────────────────────┴────────────────┘     │ │   │
│   │   │                                    │                      │ │   │
│   │   │                    ┌───────────────┴───────────────┐      │ │   │
│   │   │                    │   Finalize → Route Decision   │      │ │   │
│   │   │                    │  ┌─────────┐    ┌──────────┐  │      │ │   │
│   │   │                    │  │ Apply   │    │  Queue   │  │      │ │   │
│   │   │                    │  │ Label   │    │ Approval │  │      │ │   │
│   │   │                    │  └─────────┘    └──────────┘  │      │ │   │
│   │   │                    └───────────────────────────────┘      │ │   │
│   │   └───────────────────────────────────────────────────────────┘ │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                    │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐    │
│   │       Cloud SQL             │    │       External APIs         │    │
│   │   (Private IP Only)         │    │                             │    │
│   │   • PostgreSQL 15           │    │   ┌───────────────────┐     │    │
│   │   • emails, checkpoints     │    │   │    Gmail API      │     │    │
│   │   • calendar_events         │◄───┼───│    (OAuth 2.0)    │     │    │
│   │   • unsubscribe_queue       │    │   └───────────────────┘     │    │
│   └─────────────────────────────┘    │   ┌───────────────────┐     │    │
│                                      │   │  Google Calendar  │     │    │
│   ┌─────────────────────────────┐    │   │  (FreeBusy API)   │     │    │
│   │     VPC + NAT Gateway       │    │   └───────────────────┘     │    │
│   │   No public DB exposure     │◄───┼───┌───────────────────┐     │    │
│   └─────────────────────────────┘    │   │  Anthropic API    │     │    │
│                                      │   │  (Haiku/Sonnet)   │     │    │
│                                      │   └───────────────────┘     │    │
│                                      └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics

| Metric | Value | Significance |
|--------|-------|--------------|
| Emails Processed | ~65K | 11 years of inbox history |
| Categorized & Labeled | 24,679 | Automated classification |
| Success Rate | 99.2% | Robust error handling |
| Pending Human Review | 314 | Appropriate escalation |
| Terraform Resources | 36 | Full IaC coverage |
| Processing Cost | ~$22 | Cost-effective at scale |
| Batch Duration | ~10 hours | Autonomous, unattended |

---

## Technical Decisions Mapped to FDE Capabilities

| Challenge | Decision | Rationale | FDE Relevance |
|-----------|----------|-----------|---------------|
| **Agent orchestration** | LangGraph StateGraph with conditional routing | Checkpointing, state persistence, graph-based flows | Same patterns as multi-agent retrieval systems |
| **Reliable batch processing** | Cloud Tasks with OIDC auth and self-continuation | Handles 465K items without timeout/retry issues | Enterprise-grade reliability for customer deployments |
| **Cost optimization** | Haiku→Sonnet escalation (confidence < 0.7) | 80% cost reduction vs. always using quality model | Production cost management at scale |
| **Security posture** | VPC + Private Service Connect | No public DB exposure, all traffic via NAT | VPC deployment expertise for on-prem/hybrid |
| **Infrastructure discipline** | Terraform with workspaces (dev/staging/prod) | Reproducible, environment-separated, auditable | IaC discipline for rapid customer deployments |
| **Concurrent processing** | Database-level optimistic locking | Prevents duplicate processing without distributed locks | Patterns for multi-worker distributed systems |
| **Agent tooling** | Calendar FreeBusy API integration | Agents use external tools (conflict detection) | Tool-use patterns for agentic systems |

---

## Challenges Overcome

### 1. Cloud Tasks IAM Complexity
**Problem:** Auto-dispatch failed silently despite correct-looking configuration.
**Root Cause:** Cloud Tasks service agent requires `serviceAccountUser` role (not `serviceAccountTokenCreator`) to generate OIDC tokens.
**Solution:** Documented the specific IAM binding pattern; created troubleshooting runbook.
**Learning:** Enterprise integrations often have non-obvious permission requirements that require deep debugging.

### 2. Batch Processing State Management
**Problem:** 11-year inbox processing required autonomous execution across multiple days.
**Solution:** Implemented:
- 2-month chunk granularity for predictable memory usage
- Database-level locking with stale lock detection (30-min timeout)
- Cloud Tasks self-continuation pattern (each chunk enqueues the next)
- Checkpoint tracking for resume-from-failure capability

**Result:** Zero manual intervention during 48-hour processing run.

### 3. Confidence Calibration for Human-in-the-Loop
**Problem:** LLM confidence scores didn't correlate well with actual accuracy.
**Solution:** Two-tier escalation with conservative thresholds:
- Haiku at confidence < 0.7 → Escalate to Sonnet
- Sonnet at confidence < 0.8 → Queue for human review

**Result:** Only 1.3% of emails require human review while maintaining high accuracy.

---

## Phase 2 Implementation (Complete)

| Component | Implementation | Status |
|-----------|---------------|--------|
| **Importance Agent** | 6-factor weighted scoring (sender authority, urgency keywords, deadline detection, financial signals, thread activity, recipient position) | ✅ Complete |
| **Calendar Agent** | LLM event extraction + Google Calendar FreeBusy conflict detection | ✅ Complete |
| **Unsubscribe Agent** | RFC 2369/8058 header parsing with CLI batch review | ✅ Complete |
| **Multi-Agent Workflow** | LangGraph conditional routing with parallel agent execution | ✅ Complete |

## Phase 3 Roadmap (Demonstrates Product Thinking)

| Priority | Feature | Purpose |
|----------|---------|---------|
| 1 | **Obsidian Integration** | RAG context index for cross-thread awareness |
| 2 | **Reply Draft Generation** | Context-aware response suggestions |
| 3 | **Active Learning Pipeline** | Continuous improvement from feedback |

---

## Technology Stack

**Infrastructure:**
- GCP: Cloud Run, Cloud SQL (PostgreSQL 15), Cloud Tasks, Secret Manager
- Networking: VPC, Private Service Connect, Cloud NAT
- IaC: Terraform with remote state (GCS backend)

**Application:**
- Framework: FastAPI + LangGraph (StateGraph)
- LLM: Anthropic Claude (Haiku for speed, Sonnet for quality)
- ORM: SQLAlchemy with async support
- Auth: OAuth 2.0 (Gmail), OIDC (internal services)

**Observability:**
- Logging: Cloud Logging with structured JSON
- Alerting: Cloud Monitoring (>10% error rate threshold)
- Archival: Log sink to Cloud Storage (90-day retention)

---

## Code Samples

### LangGraph Multi-Agent Workflow (Phase 2)
```python
# src/workflows/email_processor.py:298-423
def create_workflow() -> StateGraph:
    workflow = StateGraph(EmailState)

    # Phase 1 nodes
    workflow.add_node("categorize", categorize_email)
    workflow.add_node("apply_label", apply_label_node)
    workflow.add_node("queue_approval", queue_approval_node)

    # Phase 2 nodes - specialized agents
    workflow.add_node("check_importance", check_importance)
    workflow.add_node("extract_calendar", extract_calendar_event)
    workflow.add_node("detect_unsubscribe", detect_unsubscribe)
    workflow.add_node("finalize", finalize_processing_node)

    # Build graph: categorize → importance → specialized agents → finalize
    workflow.add_edge(START, "categorize")
    workflow.add_edge("categorize", "check_importance")
    workflow.add_conditional_edges(
        "check_importance",
        route_after_importance,  # Routes to calendar, unsubscribe, or finalize
        {"extract_calendar": "extract_calendar",
         "detect_unsubscribe": "detect_unsubscribe",
         "finalize": "finalize"}
    )
    workflow.add_conditional_edges("finalize", route_final, {...})

    return workflow.compile()
```

### Model Escalation Pattern
```python
# src/services/anthropic_client.py
def classify_with_escalation(self, ..., confidence_threshold=0.7):
    # Fast model first
    result = self.classify_email(..., use_quality_model=False)

    # Escalate if uncertain
    if result.confidence < confidence_threshold:
        result = self.classify_email(..., use_quality_model=True)

    return result
```

### Calendar Agent Tool: FreeBusy Conflict Detection
```python
# src/services/google_calendar.py:168-229
def check_conflicts(self, start: datetime, end: datetime) -> list[CalendarConflict]:
    """Check for conflicting events using Google Calendar FreeBusy API.

    Uses FreeBusy for efficient conflict detection (privacy-preserving,
    returns only busy/free status without event details).
    """
    body = {
        "timeMin": start.isoformat() + "Z",
        "timeMax": end.isoformat() + "Z",
        "items": [{"id": "primary"}],
    }

    result = self.service.freebusy().query(body=body).execute()
    busy_times = result.get("calendars", {}).get("primary", {}).get("busy", [])

    return [CalendarConflict(
        start=datetime.fromisoformat(busy["start"]),
        end=datetime.fromisoformat(busy["end"]),
    ) for busy in busy_times]
```

### Distributed Lock Acquisition
```python
# src/services/batch_processor.py
async def _try_acquire_lock(self, session, job, lock_id) -> bool:
    lock_timeout = datetime.utcnow() - timedelta(minutes=30)

    if job.processing_lock_time and job.processing_lock_time > lock_timeout:
        return False  # Lock held by another worker

    job.processing_lock_id = lock_id
    await session.commit()

    # Verify acquisition (race condition check)
    await session.refresh(job)
    return job.processing_lock_id == lock_id
```

---

## Why This Project Demonstrates FDE Readiness

1. **Agentic Systems Expertise:** Built a production multi-agent workflow with LangGraph—4 specialized agents (Categorization, Importance, Calendar, Unsubscribe) with conditional routing and tool integration.

2. **Tool-Using Agents:** Implemented Calendar Agent with Google Calendar FreeBusy API tool for conflict detection—demonstrating the agent-tool pattern used in autonomous coding systems.

3. **Enterprise Deployment Skills:** Designed for VPC deployment with no public exposure, managed via Terraform—ready for customer on-prem/hybrid environments.

4. **Reliability Engineering:** Implemented autonomous batch processing that ran unattended for 48 hours, handling retries and failures gracefully.

5. **Cost-Conscious Architecture:** Achieved 80% cost reduction through intelligent model routing—critical for production AI systems at scale.

6. **Documentation & Reproducibility:** Created comprehensive technical documentation (PRD, architecture diagrams, deployment guides) for knowledge transfer.

---

*Source code and documentation available upon request.*
