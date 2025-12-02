# Gmail Agent Assistant - Next Steps Roadmap

> **Last Updated**: December 2025
> **Phase 1 Status**: Complete (Historical processing finished)
> **Phase 2 Status**: Complete (Multi-agent workflow implemented)
> **Current Focus**: Phase 3 Development (Obsidian Integration)

---

## Executive Summary

With Phase 2 complete (multi-agent workflow with importance scoring, calendar extraction, and unsubscribe detection), the system now has a robust foundation for intelligent email processing. The next focus is **Obsidian integration** as a context index for multi-agent reasoning, enabling cross-thread context for intelligent email responses.

---

## Completed Work (Phase 1)

| Component | Status | Documentation |
|-----------|--------|---------------|
| GCP Infrastructure | ✅ Complete | [infrastructure/REFERENCE.md](infrastructure/REFERENCE.md) |
| Cloud Tasks Batch Processing | ✅ Complete | [infrastructure/gcp_architecture.md](infrastructure/gcp_architecture.md) |
| Categorization Agent | ✅ Complete | [langgraph_workflow.md](langgraph_workflow.md) |
| Gmail OAuth Integration | ✅ Complete | [src/services/gmail_client.py](src/services/gmail_client.py) |
| CLI Approval Interface | ✅ Complete | [src/cli/approval.py](src/cli/approval.py) |
| Database Schema | ✅ Complete | [data_flow_state.md](data_flow_state.md) |
| Historical Processing | ✅ Complete | 464,757 emails processed |

### Historical Processing Results

```
Emails Processed:     464,757
Emails Categorized:    24,679
Emails Labeled:        24,365
Pending Approval:         314
Error Rate:             0.8%
Total Cost:          $576.30
```

---

## Completed Work (Phase 2)

| Component | Status | Documentation |
|-----------|--------|---------------|
| Importance Agent | ✅ Complete | [src/agents/importance.py](src/agents/importance.py) |
| Calendar Agent | ✅ Complete | [src/agents/calendar.py](src/agents/calendar.py) |
| Unsubscribe Agent | ✅ Complete | [src/agents/unsubscribe.py](src/agents/unsubscribe.py) |
| Google Calendar Client | ✅ Complete | [src/services/google_calendar.py](src/services/google_calendar.py) |
| Multi-Agent Workflow | ✅ Complete | [langgraph_workflow.md](langgraph_workflow.md) |
| Unsubscribe CLI | ✅ Complete | [src/cli/unsubscribe.py](src/cli/unsubscribe.py) |
| Phase 2 Database Schema | ✅ Complete | [scripts/migrations/002_phase2_tables.sql](scripts/migrations/002_phase2_tables.sql) |
| VIP Sender Config | ✅ Complete | [config/vip_senders.yaml](config/vip_senders.yaml) |

### Phase 2 Features

**Importance Agent** (6-factor weighted scoring):
- Sender authority (VIP list), urgency keywords, deadline detection
- Financial signals, thread activity, recipient position
- Extracts action items using LLM
- Labels: critical, high, normal, low

**Calendar Agent**:
- Extracts events from meeting/reservation emails
- Detects virtual meeting links (Zoom, Meet, Teams)
- Conflict detection using Google Calendar FreeBusy API
- Queues events for human approval if uncertain

**Unsubscribe Agent**:
- Header-based detection (RFC 2369, RFC 8058)
- One-click, mailto, and HTTP link support
- Batch review CLI with browser-based execution

---

## Phase 3: Prioritized Roadmap

### Priority 1: Obsidian Knowledge Base Integration

**Rationale**: Obsidian serves as a **context index for multi-agent reasoning**, not just a knowledge archive. When generating email replies, agents can retrieve relevant context from past conversations, contacts, and topics stored in Obsidian notes.

#### Use Cases

1. **Reply Context Retrieval**: When drafting a reply to an email about "Project Alpha", the Reply Agent queries Obsidian for:
   - Previous emails about Project Alpha
   - Notes on the sender's communication style
   - Related project documentation

2. **Contact Intelligence**: Build sender profiles linking:
   - Communication history
   - Topics discussed
   - Response patterns
   - Relationship context (colleague, client, vendor)

3. **Topic Clustering**: Automatically link related emails via:
   - WikiLinks (`[[Project Alpha]]`, `[[John Smith]]`)
   - Tags (`#urgent`, `#followup`, `#waiting-response`)
   - Backlinks for bidirectional discovery

#### Implementation Plan

```
src/
├── agents/
│   └── obsidian.py          # NEW: Obsidian Agent
├── services/
│   └── obsidian_client.py   # NEW: Obsidian file operations
└── workflows/
    └── email_processor.py   # UPDATE: Add Obsidian node
```

**Database Additions**:
```sql
-- Track Obsidian note paths
ALTER TABLE emails ADD COLUMN obsidian_note_path VARCHAR(500);

-- Index for quick lookups
CREATE INDEX idx_emails_obsidian ON emails(obsidian_note_path) WHERE obsidian_note_path IS NOT NULL;
```

**Note Structure** (per PRD Section 3.7):
```markdown
---
email_id: abc123
message_id: <msg-id@gmail.com>
thread_id: thread-xyz
from: john@company.com
to: [me@gmail.com]
date: 2025-11-28
labels: [Professional/Work]
category: Professional/Work
confidence: 0.92
---

# Subject Line Here

## Summary
AI-generated summary of email content...

## Key Points
- Point 1
- Point 2

## Related
- [[John Smith]] - Sender profile
- [[Project Alpha]] - Related project
- [[Previous Thread]] - Earlier discussion

## Original Content
> Quoted email body...
```

**Reference**: [gmail_inbox_management_system.md](gmail_inbox_management_system.md) Section 3.7 (FR-OBS-001 through FR-OBS-006)

---

### Priority 2: Draft Reply Generation

**Rationale**: Highest user time-savings potential. Leverages Obsidian context for personalized, contextually-aware responses.

#### Context Flow

```
1. User receives email from john@company.com about "Project Alpha"
2. Reply Agent queries Obsidian:
   - [[John Smith]] note → communication style, past interactions
   - [[Project Alpha]] note → project status, key decisions
   - Related thread notes → conversation history
3. Claude Sonnet generates draft with full context
4. Draft saved to Gmail (user reviews before sending)
```

**Implementation**:
```python
# src/agents/reply.py

class ReplyAgent:
    def __init__(self, obsidian_client: ObsidianClient):
        self.obsidian = obsidian_client
        self.model = ChatAnthropic(model="claude-sonnet-4-20250514")

    def generate_draft(self, email: EmailState) -> str:
        # 1. Retrieve context from Obsidian
        sender_profile = self.obsidian.get_contact_note(email.from_email)
        related_notes = self.obsidian.search_related(email.subject, email.body)

        # 2. Build context-rich prompt
        context = self._build_context(sender_profile, related_notes)

        # 3. Generate reply
        return self.model.invoke(self._build_prompt(email, context))
```

**Reference**: [gmail_inbox_management_system.md](gmail_inbox_management_system.md) Section 3.6 (FR-REPLY-001 through FR-REPLY-006)

---

### Priority 3: Active Learning from Feedback

**Rationale**: Improves accuracy over time. Requires research before implementation (see [ACTIVE_LEARNING_RESEARCH.md](ACTIVE_LEARNING_RESEARCH.md)).

#### Current State

- Feedback table exists: [src/models/feedback.py](src/models/feedback.py)
- Records `user_action`, `proposed_category`, `final_category`
- 314 emails pending approval (source of training data)

#### Research Questions

1. What active learning strategy best fits our use case?
2. How to balance exploration vs exploitation?
3. When to retrain vs use few-shot examples?
4. How to handle concept drift over time?

**Reference**: [ACTIVE_LEARNING_RESEARCH.md](ACTIVE_LEARNING_RESEARCH.md) for detailed research prompt

---

### Priority 4: Future Enhancements

#### Calendar Agent Enhancements
- Recurring event detection and creation
- All-day event support
- Attendee invitation sending
- Body-based event extraction (for emails without structured data)

#### Unsubscribe Agent Enhancements
- Body-based link scanning (with low-confidence manual review)
- Automated one-click unsubscribe execution (no browser confirmation)
- Unsubscribe success verification

---

## Deferred Work

| Feature | Reason | Phase |
|---------|--------|-------|
| Real-time Pub/Sub | Hourly processing sufficient for personal use | Phase 4 |
| Dynamic Category Creation | 8 categories adequate; focus on accuracy first | Phase 3 |
| Redis LLM Caching | Optimize after core features complete | Phase 3 |

---

## Implementation Sequence

```mermaid
gantt
    title Phase 3 Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Priority 1
    Obsidian Agent Design     :a1, 2025-12-01, 3d
    Obsidian File Operations  :a2, after a1, 4d
    Note Generation Logic     :a3, after a2, 3d
    Workflow Integration      :a4, after a3, 2d
    section Priority 2
    Reply Agent               :b1, after a4, 5d
    Context Retrieval         :b2, after b1, 3d
    section Priority 3
    Active Learning Research  :c1, 2025-12-01, 7d
    Implementation            :c2, after b2, 5d
```

---

## File References

### Core Documentation
| File | Purpose |
|------|---------|
| [gmail_inbox_management_system.md](gmail_inbox_management_system.md) | PRD & Technical Specification |
| [README.md](README.md) | Project overview and quick start |
| [CLAUDE.md](CLAUDE.md) | AI assistant development guide |

### Architecture Diagrams
| File | Purpose |
|------|---------|
| [langgraph_workflow.md](langgraph_workflow.md) | LangGraph workflow diagrams |
| [data_flow_state.md](data_flow_state.md) | Data flow and state transitions |
| [categorization_hierarchy.md](categorization_hierarchy.md) | Email category definitions |

### Infrastructure
| File | Purpose |
|------|---------|
| [infrastructure/README.md](infrastructure/README.md) | Infrastructure operations guide |
| [infrastructure/REFERENCE.md](infrastructure/REFERENCE.md) | Complete Terraform resource dictionary |
| [infrastructure/gcp_architecture.md](infrastructure/gcp_architecture.md) | GCP architecture diagram |
| [infrastructure/terraform_deployment.md](infrastructure/terraform_deployment.md) | Deployment sequence |
| [infrastructure/CLAUDE.md](infrastructure/CLAUDE.md) | Infrastructure AI guide |

### Source Code
| File | Purpose |
|------|---------|
| [src/main.py](src/main.py) | FastAPI application |
| [src/config.py](src/config.py) | Configuration and categories |
| [src/agents/categorization.py](src/agents/categorization.py) | Categorization agent |
| [src/agents/importance.py](src/agents/importance.py) | Importance scoring agent (Phase 2) |
| [src/agents/calendar.py](src/agents/calendar.py) | Calendar extraction agent (Phase 2) |
| [src/agents/unsubscribe.py](src/agents/unsubscribe.py) | Unsubscribe detection agent (Phase 2) |
| [src/services/anthropic_client.py](src/services/anthropic_client.py) | Claude API client |
| [src/services/gmail_client.py](src/services/gmail_client.py) | Gmail API client |
| [src/services/google_calendar.py](src/services/google_calendar.py) | Google Calendar client (Phase 2) |
| [src/workflows/email_processor.py](src/workflows/email_processor.py) | LangGraph multi-agent workflow |
| [src/cli/unsubscribe.py](src/cli/unsubscribe.py) | Unsubscribe review CLI (Phase 2) |
| [src/models/email.py](src/models/email.py) | Email database model |
| [src/models/calendar_event.py](src/models/calendar_event.py) | Calendar event model (Phase 2) |
| [src/models/vip_sender.py](src/models/vip_sender.py) | VIP sender model (Phase 2) |
| [src/models/feedback.py](src/models/feedback.py) | Feedback model for active learning |
| [config/vip_senders.yaml](config/vip_senders.yaml) | VIP sender configuration (Phase 2) |

---

## Success Metrics (Phase 3)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Importance Detection | <5% false negatives | Track missed urgent emails |
| Calendar Extraction | 90% accuracy on meeting emails | Compare extracted vs actual events |
| Unsubscribe Detection | 95% header detection rate | Audit sample of newsletter emails |
| Reply Draft Acceptance | 80% with minor edits | User feedback on drafts |
| Obsidian Note Quality | Useful for context retrieval | Manual review of generated notes |
| Active Learning | 5% accuracy improvement/month | Compare monthly categorization accuracy |

---

## Next Actions

1. **Immediate**: Run database migration `002_phase2_tables.sql` to create Phase 2 tables
2. **Immediate**: Configure VIP senders in `config/vip_senders.yaml`
3. **Test**: Deploy Phase 2 workflow and validate importance scoring on live emails
4. **Review**: Process pending approvals via CLI to generate training data
5. **Development**: Begin Obsidian agent implementation (Priority 1)
