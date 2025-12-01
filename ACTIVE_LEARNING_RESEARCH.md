# Active Learning Research for Email Classification System

> **Purpose**: This document is designed to be uploaded to Claude for researching the best active learning approach for improving email classification accuracy over time.

---

## Project Context

I'm building a multi-agent Gmail inbox management system that classifies emails into categories and learns from user feedback. I need your help researching the best active learning strategies for this specific use case.

### System Overview

```
Architecture: LangGraph multi-agent system on GCP
LLM Provider: Anthropic Claude (Haiku for fast, Sonnet for quality)
Database: PostgreSQL on Cloud SQL
Processing: Batch (hourly) and historical (bulk)
```

### Current Classification Flow

```
1. Email arrives → Gmail API fetch
2. Claude Haiku classifies → {category, confidence, reasoning}
3. If confidence < 0.7 → Escalate to Claude Sonnet
4. If confidence < 0.8 → Queue for human approval
5. Human approves/corrects → Feedback recorded
6. Gmail label applied
```

### Data Available

**Processed Emails** (464,757 total):
- `email_id`, `message_id`, `thread_id`
- `from_email`, `to_emails`, `subject`, `body`, `date`
- `category` (assigned), `confidence` (0.0-1.0)
- `status` (processing, pending_approval, labeled, failed)

**Feedback Table** (growing):
- `email_id` (FK)
- `user_action` (approved, corrected, denied)
- `proposed_category` (what the model suggested)
- `final_category` (what the user chose)
- `timestamp`

**Categories** (8 total):
1. Important
2. Personal/Friends
3. Personal/Family
4. Professional/Recruiters
5. Professional/Work
6. Purchases/Orders
7. Newsletters/Subscriptions
8. Marketing/Promotions

### Current Categorization Results

```
Emails Categorized: 24,679
Pending Approval: 314 (low-confidence)
Error Rate: 0.8%
```

---

## Research Questions

### 1. Active Learning Strategy Selection

Given our system characteristics:
- **LLM-based classifier** (not traditional ML)
- **Human-in-the-loop** for low-confidence cases
- **Feedback available** but potentially sparse
- **No model fine-tuning** (using Claude API, not self-hosted)

**Questions**:
1. What active learning strategies work best with LLM classifiers that can't be fine-tuned?
2. Should we use **few-shot learning** (include examples in prompts) or **retrieval-augmented generation** (RAG)?
3. How do we handle the cold-start problem when we have limited feedback?

### 2. Sample Selection Strategy

We need to decide which emails to prioritize for human review:

**Options**:
- **Uncertainty sampling**: Select emails where model confidence is lowest
- **Query-by-committee**: Use multiple prompt variants, select where they disagree
- **Diversity sampling**: Select emails that represent different patterns
- **Expected model change**: Select emails that would most improve the model

**Questions**:
1. Which sampling strategy maximizes learning per human review?
2. How do we balance **exploration** (new patterns) vs **exploitation** (refining known patterns)?
3. Should we combine strategies? If so, how?

### 3. Feedback Integration Approaches

Since we can't fine-tune Claude, we need alternative approaches:

**Option A: Dynamic Few-Shot Examples**
```python
# Include recent corrections in the prompt
examples = get_recent_corrections(category, limit=5)
prompt = f"""
Previous corrections for this category:
{format_examples(examples)}

Now classify this email:
{email_content}
"""
```

**Option B: RAG with Feedback Store**
```python
# Retrieve similar past emails with known-correct labels
similar_emails = vector_search(email_embedding, top_k=5)
prompt = f"""
Similar emails and their correct categories:
{format_similar(similar_emails)}

Classify this email:
{email_content}
"""
```

**Option C: Rule Extraction**
```python
# Analyze corrections to extract explicit rules
rules = analyze_corrections(feedback_data)
# e.g., "Emails from @greenhouse.io are always Professional/Recruiters"
prompt = f"""
Classification rules:
{format_rules(rules)}

Apply these rules to classify:
{email_content}
"""
```

**Option D: Confidence Calibration**
```python
# Adjust confidence thresholds based on historical accuracy
category_calibration = compute_calibration(feedback_data)
# e.g., "Marketing/Promotions" confidence tends to be overestimated
adjusted_confidence = calibrate(raw_confidence, category_calibration)
```

**Questions**:
1. Which approach yields the best accuracy improvement per feedback item?
2. Can/should we combine multiple approaches?
3. How do we evaluate which approach is working?

### 4. Concept Drift Handling

User preferences may change over time:
- New senders become important
- Newsletter subscriptions change
- Work projects shift priorities

**Questions**:
1. How do we detect concept drift in email classification?
2. Should we weight recent feedback higher than older feedback?
3. How often should we re-evaluate classification rules?

### 5. Feedback Loop Architecture

**Current Flow**:
```
Email → Classify → [Auto-label OR Human Review] → Feedback → ???
```

**Proposed Options**:

**Option A: Batch Reprocessing**
- Weekly: Analyze all feedback, update prompt templates
- Re-classify emails that might have been wrong

**Option B: Continuous Learning**
- After each feedback: Immediately update examples/rules
- Next classification uses updated context

**Option C: Hybrid**
- Immediate: Add to few-shot example cache
- Weekly: Analyze patterns, extract rules, calibrate confidence

**Questions**:
1. What's the optimal feedback loop cadence?
2. How do we avoid catastrophic forgetting (losing good patterns)?
3. How do we measure if the feedback loop is improving accuracy?

---

## Technical Constraints

1. **No Model Fine-Tuning**: Using Claude API, can't train custom model
2. **Cost Sensitivity**: ~$0.05/email target, can't add expensive operations
3. **Latency Requirements**: <5 seconds per email classification
4. **Storage**: PostgreSQL available, can add vector store if needed
5. **Compute**: Cloud Run serverless, no persistent GPU

---

## Existing Research to Consider

Please research and compare:

1. **LLM-specific active learning** papers/approaches
2. **Few-shot learning optimization** for classification
3. **RAG for classification** vs traditional few-shot
4. **Confidence calibration** techniques for LLMs
5. **Online learning** with LLM APIs (not fine-tuning)
6. **Human-in-the-loop** design patterns for classification

---

## Desired Output

Please provide:

### 1. Strategy Recommendation
- Which active learning approach best fits our constraints?
- Concrete implementation steps
- Expected accuracy improvement

### 2. Architecture Design
- How should feedback flow through the system?
- What data structures do we need?
- How do we store and retrieve examples/rules?

### 3. Evaluation Framework
- How do we measure if active learning is working?
- What metrics should we track?
- How do we A/B test different approaches?

### 4. Implementation Roadmap
- What to build first?
- How to iterate and improve?
- When to add complexity vs keep simple?

### 5. Risk Analysis
- What could go wrong?
- How do we prevent feedback loops from degrading quality?
- How do we handle adversarial or inconsistent feedback?

---

## Code Context

### Current Classification Prompt

```python
# src/services/anthropic_client.py (simplified)

SYSTEM_PROMPT = """You are an expert email classifier.

Categories:
{categories}

Classify the email into EXACTLY ONE category.

Response Format (JSON only):
{{
  "category": "<CATEGORY_PATH>",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>",
  "key_phrases": ["<phrase1>", "<phrase2>"]
}}"""

def classify_email(self, subject, from_email, body, categories):
    response = self.client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Subject: {subject}\nFrom: {from_email}\nBody: {body}"}],
        system=SYSTEM_PROMPT.format(categories=format_categories(categories)),
    )
    return parse_response(response)
```

### Feedback Recording

```python
# src/models/feedback.py

class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[str] = mapped_column(String(255), ForeignKey("emails.email_id"))
    user_action: Mapped[str] = mapped_column(String(50))  # approved, corrected, denied
    proposed_category: Mapped[str] = mapped_column(String(255))
    final_category: Mapped[str] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP)

    @property
    def was_corrected(self) -> bool:
        return self.proposed_category != self.final_category
```

### Category Definitions

```python
# src/config.py

CATEGORIES = {
    "Important": {
        "description": "Time-sensitive or critical emails requiring immediate attention",
        "keywords": ["urgent", "deadline", "interview", "offer", "critical", "ASAP"],
    },
    "Personal/Friends": {
        "description": "Emails from friends with informal tone",
        "domains": ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"],
    },
    "Personal/Family": {
        "description": "Emails from family members",
        "keywords": ["family", "mom", "dad", "sister", "brother"],
    },
    "Professional/Recruiters": {
        "description": "Job-related emails from recruiters",
        "domains": ["linkedin.com", "greenhouse.io", "lever.co"],
        "keywords": ["opportunity", "position", "interview", "role", "hiring"],
    },
    "Professional/Work": {
        "description": "Work-related professional correspondence",
        "keywords": ["meeting", "project", "deadline", "deliverable"],
    },
    "Purchases/Orders": {
        "description": "Order confirmations and shipping notifications",
        "domains": ["amazon.com", "etsy.com", "ebay.com", "shopify.com"],
        "keywords": ["order", "shipped", "delivery", "tracking", "receipt"],
    },
    "Newsletters/Subscriptions": {
        "description": "Newsletter and subscription emails",
        "domains": ["substack.com"],
        "keywords": ["unsubscribe", "newsletter", "digest", "weekly"],
    },
    "Marketing/Promotions": {
        "description": "Promotional and marketing emails",
        "keywords": ["sale", "discount", "promo", "offer", "deal", "limited time"],
    },
}
```

---

## Additional Context

### Why Active Learning Matters

1. **Accuracy Target**: 95% categorization accuracy (currently ~91% estimated)
2. **Personalization**: Each user's "Important" definition is different
3. **Evolving Patterns**: New senders, topics, and communication styles emerge
4. **Sparse Feedback**: Users won't review every email; must learn efficiently

### Integration with Obsidian (Future)

Active learning insights will also feed into the Obsidian knowledge base:
- Contact profiles will include learned preferences
- Topic notes will include classification patterns
- This enables the Reply Agent to use learned context when drafting responses

---

## Summary Request

Given all the above context, please research and recommend:

1. **The best active learning strategy** for our LLM-based email classifier
2. **Concrete implementation approach** with code structure
3. **Evaluation methodology** to measure improvement
4. **Risks and mitigations** for the feedback loop

Focus on practical, implementable solutions that work within our constraints (no fine-tuning, cost-sensitive, serverless architecture).
