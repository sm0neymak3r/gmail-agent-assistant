# GCP Infrastructure Architecture

```mermaid
flowchart TB
    subgraph Triggers["Trigger Layer"]
        CS[Cloud Scheduler<br/>Hourly 0 * * * *]
        CT[Cloud Tasks<br/>Batch Processing Queue<br/>gmail-agent-batch-v3]
    end

    subgraph GCP["GCP Project"]
        subgraph VPC["VPC Network<br/>gmail-agent-vpc-ENV"]
            subgraph Subnet["Subnet 10.0.1.0/24"]
                BASTION[Bastion Host<br/>e2-micro<br/>Debian 12]
            end

            subgraph Connector["VPC Access Connector<br/>10.8.0.0/28"]
                VPCC[Serverless VPC Connector<br/>2-3 instances]
            end

            subgraph NAT["Cloud NAT"]
                ROUTER[Cloud Router]
                NATGW[NAT Gateway<br/>Auto IP Allocation]
            end
        end

        subgraph Compute["Compute Layer"]
            CR[Cloud Run Service<br/>0-5 instances<br/>2 vCPU / 4Gi RAM<br/>3600s timeout]
        end

        subgraph Registry["Container Registry"]
            AR[Artifact Registry<br/>Docker Images<br/>7-day cleanup policy]
        end

        subgraph Secrets["Secret Manager"]
            SM_OAUTH[gmail-oauth-token<br/>OAuth Client Credentials]
            SM_TOKEN[gmail-user-token<br/>User Access/Refresh Tokens]
            SM_ANTH["anthropic-api-key-ENV<br/>Anthropic API Key"]
            SM_DB["db-password-ENV<br/>Auto-generated"]
        end

        subgraph IAM["Service Accounts"]
            SA_RUNTIME[email-agent-runtime<br/>Cloud Run Identity]
            SA_BASTION["bastion-ENV<br/>Bastion Identity"]
        end

        subgraph Observability["Monitoring & Logging"]
            CL[Cloud Logging]
            CM[Cloud Monitoring]
            ALERT[Alert Policy<br/>Error Rate > 10%]
            SINK[Log Sink<br/>gmail-agent-archive]
        end
    end

    subgraph Storage["Storage Layer"]
        subgraph PrivateNetwork["Private Service Connect"]
            SQL[(Cloud SQL<br/>PostgreSQL 15<br/>Private IP Only<br/>7-day backups)]
        end
        GCS[(Cloud Storage<br/>Logs Bucket<br/>90-day retention)]
    end

    subgraph External["External APIs"]
        GMAIL[Gmail API]
        ANTHROPIC[Anthropic API<br/>Claude Models]
    end

    subgraph Admin["Administrative Access"]
        IAP[Identity-Aware Proxy<br/>35.235.240.0/20]
    end

    %% Scheduler Trigger Flow
    CS -->|"HTTP POST<br/>+ OIDC Token"| CR

    %% Cloud Tasks Trigger Flow
    CT -->|"HTTP POST /batch-worker<br/>+ OIDC Token"| CR
    CR -->|"Enqueue next chunk"| CT

    %% Container Setup
    AR -.->|"Pull Image<br/>on Deploy"| CR

    %% Secret Access
    SM_OAUTH -->|"secretAccessor"| SA_RUNTIME
    SM_TOKEN -->|"secretAccessor"| SA_RUNTIME
    SM_ANTH -->|"secretAccessor"| SA_RUNTIME
    SM_DB -->|"secretAccessor"| SA_RUNTIME
    SM_DB -->|"secretAccessor"| SA_BASTION

    %% Cloud Run → VPC → Database
    CR -->|"VPC Access"| VPCC
    VPCC -->|"Private IP"| SQL

    %% Cloud Run → External APIs (via NAT)
    CR -->|"VPC Connector"| VPCC
    VPCC --> ROUTER
    ROUTER --> NATGW
    NATGW -->|"Public Internet<br/>TLS 1.3"| GMAIL
    NATGW -->|"Public Internet<br/>TLS 1.3"| ANTHROPIC

    %% Bastion Access Path
    IAP -->|"SSH Port 22"| BASTION
    BASTION -->|"Port 5432"| SQL

    %% Observability
    CR -->|"Stdout/Stderr"| CL
    CL -->|"Metrics"| CM
    CM --> ALERT
    CL --> SINK
    SINK -->|"Archive"| GCS

    %% Styling
    classDef trigger fill:#4285F4,stroke:#1967D2,color:#fff
    classDef compute fill:#34A853,stroke:#1E8E3E,color:#fff
    classDef storage fill:#FBBC04,stroke:#F9AB00,color:#000
    classDef external fill:#EA4335,stroke:#C5221F,color:#fff
    classDef security fill:#9334E6,stroke:#7627BB,color:#fff
    classDef monitoring fill:#FF6D01,stroke:#E65100,color:#fff
    classDef network fill:#00ACC1,stroke:#00838F,color:#fff
    classDef admin fill:#78909C,stroke:#546E7A,color:#fff

    class CS,CT trigger
    class CR,AR compute
    class SQL,GCS storage
    class GMAIL,ANTHROPIC external
    class SM_OAUTH,SM_TOKEN,SM_ANTH,SM_DB,SA_RUNTIME,SA_BASTION security
    class CL,CM,ALERT,SINK monitoring
    class VPCC,ROUTER,NATGW,BASTION network
    class IAP admin
```

## Component Summary

### Networking

| Component | Resource | Purpose |
|-----------|----------|---------|
| VPC | `gmail-agent-vpc-{env}` | Private network for all resources |
| Subnet | `cloudrun-subnet-{env}` (10.0.1.0/24) | IP range for Cloud Run connector |
| VPC Connector | `gmail-agent-connector-{env}` (10.8.0.0/28) | Bridge Cloud Run to VPC |
| Cloud Router | `gmail-agent-router-{env}` | Dynamic routing for NAT |
| Cloud NAT | `gmail-agent-nat-{env}` | Outbound internet access for VPC resources |
| Private Service Connect | `sql-private-ip-{env}` (/16 range) | VPC peering for Cloud SQL |

### Compute

| Component | Resource | Specs |
|-----------|----------|-------|
| Cloud Run | `gmail-agent-{env}` | 0-5 instances, 2 vCPU, 4Gi RAM, 3600s timeout |
| Bastion | `gmail-agent-bastion-{env}` | e2-micro, Debian 12, preemptible (non-prod) |

### Task Queues

| Component | Resource | Configuration |
|-----------|----------|---------------|
| Cloud Scheduler | `gmail-agent-processor-{env}` | Hourly cron (0 * * * *), OIDC auth |
| Cloud Tasks | `gmail-agent-batch-v3` | Serial (1 concurrent), 4 retries, 10min max backoff |

### Database

| Component | Resource | Details |
|-----------|----------|---------|
| Cloud SQL | `gmail-agent-db-{env}` | PostgreSQL 15, private IP only, ZONAL (REGIONAL in prod) |
| Database | `email_agent` | Application database |
| User | `agent_user` | Application credentials |

### Secrets

| Secret | ID | Purpose |
|--------|-----|---------|
| OAuth Client | `gmail-oauth-token` | App identity for Gmail OAuth |
| User Token | `gmail-user-token` | User's access/refresh tokens |
| Anthropic Key | `anthropic-api-key-{env}` | Claude API access |
| DB Password | `db-password-{env}` | Auto-generated database password |

### Monitoring

| Component | Resource | Configuration |
|-----------|----------|---------------|
| Log Sink | `gmail-agent-archive-{env}` | Exports Cloud Run logs |
| Log Bucket | `{project}-logs-{env}` | 90-day retention |
| Alert Policy | `Gmail Agent High Error Rate` | Triggers on >10% 5xx errors for 5 min |

## Authentication Flows

| Flow | Method | Details |
|------|--------|---------|
| Scheduler → Cloud Run | OIDC Token | Service account identity verification |
| Cloud Tasks → Cloud Run | OIDC Token | Service agent impersonates runtime SA via `serviceAccountUser` role |
| Cloud Run → Cloud Tasks | IAM | `cloudtasks.enqueuer` role on runtime SA |
| Cloud Run → Gmail API | OAuth 2.0 | User tokens with `gmail.modify` scope |
| Cloud Run → Anthropic API | API Key | Bearer token authentication |
| Cloud Run → Secret Manager | IAM | `secretAccessor` role on runtime SA |
| Cloud Run → Cloud SQL | Private IP | Via VPC connector, password from Secret Manager |
| Admin → Bastion | IAP | Identity-Aware Proxy SSH tunneling |
| Bastion → Cloud SQL | Direct | PostgreSQL client over private network |

## Network Security

```
┌─────────────────────────────────────────────────────────────────┐
│                        PUBLIC INTERNET                          │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    ▲
        │ HTTPS              │ HTTPS              │ NAT (outbound only)
        ▼                    ▼                    │
┌───────────────┐    ┌───────────────┐    ┌──────┴──────┐
│ Cloud Run URL │    │   IAP Proxy   │    │  Cloud NAT  │
│  (Invoker)    │    │ 35.235.240.0  │    │  (Auto IP)  │
└───────┬───────┘    └───────┬───────┘    └──────▲──────┘
        │                    │                    │
        ▼                    ▼                    │
┌─────────────────────────────────────────────────┴───────────────┐
│                         VPC NETWORK                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   Cloud Run     │  │     Bastion     │  │   VPC Access    │  │
│  │   (Serverless)  │  │   (10.0.1.x)    │  │   Connector     │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │ :5432              │           │
│           └────────────────────┼────────────────────┘           │
│                                ▼                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Private Service Connect                      │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              Cloud SQL (Private IP)                 │  │  │
│  │  │              No public IP exposure                  │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Firewall Rules

| Rule | Source | Target | Ports | Purpose |
|------|--------|--------|-------|---------|
| `allow-iap-ssh-{env}` | 35.235.240.0/20 (IAP) | `iap-ssh` tagged instances | TCP 22 | SSH via IAP |
| `allow-bastion-sql-{env}` | `bastion` tagged instances | VPC | TCP 5432 | Database access |

## Processing Flows

### Hourly Processing (Cloud Scheduler)

```
1. Cloud Scheduler (hourly cron: 0 * * * *)
   │
   ▼ POST /process + OIDC token
2. Cloud Run Service
   │
   ├──► Secret Manager (get credentials)
   │    ├─ Gmail OAuth tokens
   │    ├─ Anthropic API key
   │    └─ Database password
   │
   ├──► Gmail API (via NAT)
   │    ├─ Fetch recent emails (100/batch)
   │    └─ Apply labels
   │
   ├──► Anthropic API (via NAT)
   │    └─ Claude classification/analysis
   │
   └──► Cloud SQL (via VPC Connector)
        ├─ Store processed emails
        ├─ Save checkpoints
        └─ Log actions
```

### Batch Processing (Cloud Tasks)

```
1. User calls POST /batch-process
   │
   ├──► Cloud SQL: Create batch_jobs record
   │    └─ Status: "running", chunks_total: N
   │
   └──► Cloud Tasks: Enqueue first chunk task
        └─ OIDC token for authentication

2. Cloud Tasks dispatches to /batch-worker
   │
   ▼ POST /batch-worker + OIDC token
3. Cloud Run processes chunk
   │
   ├──► Gmail API: Fetch emails for date range
   │    └─ 2-month chunks, 500 emails max
   │
   ├──► Anthropic API: Classify emails
   │    └─ Rate limit handling with retries
   │
   ├──► Cloud SQL: Update progress
   │    ├─ chunks_completed++
   │    ├─ emails_processed, emails_categorized
   │    └─ last_activity timestamp
   │
   └──► Cloud Tasks: Enqueue next chunk (if more remain)
        └─ Self-continuation pattern

4. Repeat until all chunks complete
   │
   └──► Cloud SQL: Status = "completed"
```

### Batch Processing State Machine

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │ POST /batch-process
                           ▼
                    ┌─────────────┐
               ┌───►│   running   │◄───┐
               │    └──────┬──────┘    │
               │           │           │
        Cloud Tasks    Process    Cloud Tasks
        retry on       chunk      enqueue next
        failure        success    chunk
               │           │           │
               │           ▼           │
               │    ┌─────────────┐    │
               └────┤ processing  ├────┘
                    │   chunk N   │
                    └──────┬──────┘
                           │ All chunks done
                           ▼
                    ┌─────────────┐
                    │  completed  │
                    └─────────────┘
```

## Resource Dependencies

```
google_compute_network.main
├── google_compute_subnetwork.cloudrun
├── google_compute_global_address.sql_private_ip
│   └── google_service_networking_connection.sql_private_vpc
│       └── google_sql_database_instance.main
│           ├── google_sql_database.main
│           └── google_sql_user.agent
├── google_vpc_access_connector.connector
│   └── google_cloud_run_v2_service.main
│       ├── google_cloud_scheduler_job.hourly_processor
│       └── google_cloud_tasks_queue.batch
│           ├── google_cloud_tasks_queue_iam_member.enqueuer
│           └── google_cloud_run_service_iam_member.cloudtasks_invoker
├── google_compute_router.router
│   └── google_compute_router_nat.nat
├── google_compute_instance.bastion
├── google_compute_firewall.iap_ssh
└── google_compute_firewall.bastion_to_sql
```
