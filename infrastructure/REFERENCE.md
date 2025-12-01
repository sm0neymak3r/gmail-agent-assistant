# Gmail Agent Infrastructure Reference

A comprehensive dictionary of all Terraform configuration files, resources, and their components.

---

## Table of Contents

1. [versions.tf](#versionstf)
2. [variables.tf](#variablestf)
3. [network.tf](#networktf)
4. [database.tf](#databasetf)
5. [database_schema.tf](#database_schematf)
6. [secrets.tf](#secretstf)
7. [registry.tf](#registrytf)
8. [cloudrun.tf](#cloudruntf)
9. [scheduler.tf](#schedulertf)
10. [tasks.tf](#taskstf)
11. [monitoring.tf](#monitoringtf)
12. [bastion.tf](#bastiontf)
13. [outputs.tf](#outputstf)
14. [terraform.tfvars.example](#terraformtfvarsexample)

---

## versions.tf

Defines Terraform version constraints, required providers, backend configuration, and provider settings.

### Terraform Block

```hcl
terraform {
  required_version = ">= 1.0"
  ...
}
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `required_version` | `>= 1.0` | Minimum Terraform CLI version required to run this configuration |

### Required Providers

| Provider | Source | Version | Description |
|----------|--------|---------|-------------|
| `google` | `hashicorp/google` | `~> 5.0` | Primary GCP provider for most resources |
| `google-beta` | `hashicorp/google-beta` | `~> 5.0` | Beta GCP provider for preview features |
| `random` | `hashicorp/random` | `~> 3.0` | Generates random values (used for database password) |

### Backend Configuration

```hcl
backend "gcs" {
  bucket = "gmail-agent-terraform-state"
  prefix = "terraform/state"
}
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `bucket` | `gmail-agent-terraform-state` | GCS bucket storing Terraform state files |
| `prefix` | `terraform/state` | Path prefix within bucket for state files; workspace name appended automatically |

### Provider: google

| Attribute | Value | Description |
|-----------|-------|-------------|
| `project` | `var.project_id` | GCP project for resource creation |
| `region` | `var.region` | Default region for regional resources |

### Provider: google-beta

| Attribute | Value | Description |
|-----------|-------|-------------|
| `project` | `var.project_id` | GCP project for resource creation |
| `region` | `var.region` | Default region for regional resources |

---

## variables.tf

Defines input variables that parameterize the infrastructure configuration.

### Variable: project_id

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"gmail-agent-prod"` | GCP project ID |
| `description` | GCP project ID | Human-readable description |

**Usage:** Referenced throughout configuration as `var.project_id`

### Variable: region

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"us-central1"` | GCP region for resource deployment |
| `description` | GCP region | Human-readable description |

**Usage:** Determines geographic location of all regional resources

### Variable: environment

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"dev"` | Environment name |
| `description` | Environment name (dev/staging/prod) | Human-readable description |

**Usage:** Appended to resource names for environment separation (e.g., `gmail-agent-vpc-dev`)

### Variable: db_tier

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"db-f1-micro"` | Smallest shared-core instance |
| `description` | Cloud SQL instance tier | Human-readable description |

**Common Values:**
| Tier | vCPUs | Memory | Use Case |
|------|-------|--------|----------|
| `db-f1-micro` | Shared | 0.6 GB | Development |
| `db-g1-small` | Shared | 1.7 GB | Light staging |
| `db-n1-standard-1` | 1 | 3.75 GB | Production |
| `db-n1-standard-2` | 2 | 7.5 GB | High-load production |

### Variable: cloudrun_cpu

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"2"` | 2 vCPUs allocated |
| `description` | Cloud Run CPU allocation | Human-readable description |

**Valid Values:** `"1"`, `"2"`, `"4"`, `"8"` (string format required)

### Variable: cloudrun_memory

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"4Gi"` | 4 GiB memory |
| `description` | Cloud Run memory allocation | Human-readable description |

**Valid Values:** `"512Mi"`, `"1Gi"`, `"2Gi"`, `"4Gi"`, `"8Gi"`, `"16Gi"`, `"32Gi"`

### Variable: cloudrun_timeout

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `string` | Data type |
| `default` | `"3600"` | 1 hour (maximum allowed) |
| `description` | Cloud Run timeout in seconds | Human-readable description |

**Range:** 1-3600 seconds

### Variable: cloudrun_max_instances

| Attribute | Value | Description |
|-----------|-------|-------------|
| `type` | `number` | Data type |
| `default` | `5` | Maximum concurrent instances |
| `description` | Maximum Cloud Run instances | Human-readable description |

**Purpose:** Controls cost and prevents runaway scaling

---

## network.tf

Defines VPC networking infrastructure for secure private connectivity.

### Resource: google_compute_network.main

**Type:** VPC Network
**Name Pattern:** `gmail-agent-vpc-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-vpc-${var.environment}` | VPC network name |
| `auto_create_subnetworks` | `false` | Disables automatic subnet creation; we define custom subnets |
| `mtu` | `1460` | Maximum Transmission Unit; GCP default for VPCs |

**Purpose:** Primary network container for all private resources

### Resource: google_compute_subnetwork.cloudrun

**Type:** VPC Subnet
**Name Pattern:** `cloudrun-subnet-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `cloudrun-subnet-${var.environment}` | Subnet name |
| `ip_cidr_range` | `10.0.1.0/24` | IP range (254 usable addresses) |
| `region` | `var.region` | Regional placement |
| `network` | `google_compute_network.main.id` | Parent VPC reference |

**Purpose:** Dedicated subnet for Cloud Run VPC connector

### Resource: google_compute_global_address.sql_private_ip

**Type:** Global Internal Address Range
**Name Pattern:** `sql-private-ip-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `sql-private-ip-${var.environment}` | Address range name |
| `purpose` | `VPC_PEERING` | Reserved for VPC peering with Google services |
| `address_type` | `INTERNAL` | Private IP addresses only |
| `prefix_length` | `16` | /16 CIDR block (65,536 addresses) |
| `network` | `google_compute_network.main.id` | Associated VPC |

**Purpose:** Reserved IP range for Cloud SQL Private Service Connect

### Resource: google_service_networking_connection.sql_private_vpc

**Type:** Private Service Connection

| Attribute | Value | Description |
|-----------|-------|-------------|
| `network` | `google_compute_network.main.id` | VPC to peer |
| `service` | `servicenetworking.googleapis.com` | Google's service networking API |
| `reserved_peering_ranges` | `[google_compute_global_address.sql_private_ip.name]` | IP ranges for peering |

**Purpose:** Establishes VPC peering between your network and Google's service network, enabling private Cloud SQL access

### Resource: google_vpc_access_connector.connector

**Type:** Serverless VPC Access Connector
**Name Pattern:** `gmail-agent-connector-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-connector-${var.environment}` | Connector name |
| `region` | `var.region` | Must match Cloud Run region |
| `ip_cidr_range` | `10.8.0.0/28` | Connector's IP range (16 addresses) |
| `network` | `google_compute_network.main.id` | VPC to connect to |
| `min_instances` | `2` | Minimum connector instances |
| `max_instances` | `3` | Maximum connector instances |

**Purpose:** Enables Cloud Run to access resources in the VPC (like Cloud SQL)

**Instance Scaling:**
| Instances | Throughput |
|-----------|------------|
| 2 | ~200 Mbps |
| 3 | ~300 Mbps |
| 10 (max) | ~1 Gbps |

### Resource: google_compute_router.router

**Type:** Cloud Router
**Name Pattern:** `gmail-agent-router-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-router-${var.environment}` | Router name |
| `region` | `var.region` | Regional placement |
| `network` | `google_compute_network.main.id` | Associated VPC |

**Purpose:** Required for Cloud NAT; manages dynamic routing

### Resource: google_compute_router_nat.nat

**Type:** Cloud NAT Gateway
**Name Pattern:** `gmail-agent-nat-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-nat-${var.environment}` | NAT name |
| `router` | `google_compute_router.router.name` | Associated router |
| `region` | `var.region` | Regional placement |
| `nat_ip_allocate_option` | `AUTO_ONLY` | GCP auto-assigns external IPs |
| `source_subnetwork_ip_ranges_to_nat` | `ALL_SUBNETWORKS_ALL_IP_RANGES` | NAT all traffic from all subnets |

**Purpose:** Provides outbound internet access for VPC resources (needed for Gmail API, Anthropic API, etc.)

---

## database.tf

Defines Cloud SQL PostgreSQL database infrastructure.

### Resource: random_password.db_password

**Type:** Random Password Generator

| Attribute | Value | Description |
|-----------|-------|-------------|
| `length` | `32` | Password length in characters |
| `special` | `true` | Include special characters |

**Purpose:** Generates a secure random password for database user

### Resource: google_sql_database_instance.main

**Type:** Cloud SQL Instance
**Name Pattern:** `gmail-agent-db-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-db-${var.environment}` | Instance name |
| `database_version` | `POSTGRES_15` | PostgreSQL version 15 |
| `region` | `var.region` | Regional placement |
| `depends_on` | `[google_service_networking_connection.sql_private_vpc]` | Ensures VPC peering exists first |
| `deletion_protection` | `false` | Allows terraform destroy (set `true` in prod) |

#### Settings Block

| Attribute | Value | Description |
|-----------|-------|-------------|
| `tier` | `var.db_tier` | Machine type/size |
| `availability_type` | Conditional | `REGIONAL` for prod (HA), `ZONAL` otherwise |

#### IP Configuration

| Attribute | Value | Description |
|-----------|-------|-------------|
| `ipv4_enabled` | `false` | No public IP (security) |
| `private_network` | `google_compute_network.main.id` | VPC for private access |
| `enable_private_path_for_google_cloud_services` | `true` | Allows GCP services to connect privately |

#### Backup Configuration

| Attribute | Value | Description |
|-----------|-------|-------------|
| `enabled` | `true` | Automated backups on |
| `start_time` | `"03:00"` | Backup window start (UTC) |
| `location` | `var.region` | Backup storage region |
| `retained_backups` | `7` | Keep 7 backups |
| `retention_unit` | `COUNT` | Retention by count (not days) |

#### Insights Configuration

| Attribute | Value | Description |
|-----------|-------|-------------|
| `query_insights_enabled` | `true` | Enable Query Insights |
| `query_string_length` | `1024` | Max query length to capture |
| `record_application_tags` | `true` | Record app-level tags |
| `record_client_address` | `true` | Record client IPs |

### Resource: google_sql_database.main

**Type:** Database
**Name:** `email_agent`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `email_agent` | Database name |
| `instance` | `google_sql_database_instance.main.name` | Parent instance |

### Resource: google_sql_user.agent

**Type:** Database User
**Name:** `agent_user`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `agent_user` | Username |
| `instance` | `google_sql_database_instance.main.name` | Parent instance |
| `password` | `random_password.db_password.result` | Auto-generated password |

---

## database_schema.tf

Defines database schema initialization via local-exec provisioner.

### Resource: null_resource.db_schema

**Type:** Null Resource (for provisioning only)

| Attribute | Value | Description |
|-----------|-------|-------------|
| `depends_on` | `[google_sql_database.main, google_sql_user.agent]` | Ensures DB exists first |

#### Provisioner: local-exec

Executes a shell command to create `/tmp/schema.sql` containing the database schema.

### Database Tables Created

#### Table: emails

Primary table for storing processed emails.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `email_id` | `VARCHAR(255)` | PRIMARY KEY | Unique identifier |
| `message_id` | `VARCHAR(255)` | UNIQUE NOT NULL | Gmail message ID |
| `thread_id` | `VARCHAR(255)` | | Gmail thread ID |
| `from_email` | `VARCHAR(255)` | NOT NULL | Sender address |
| `to_emails` | `TEXT[]` | | Array of recipients |
| `subject` | `TEXT` | | Email subject |
| `date` | `TIMESTAMP` | NOT NULL | Email date |
| `body` | `TEXT` | | Email body content |
| `category` | `VARCHAR(255)` | | Classified category |
| `confidence` | `FLOAT` | | Classification confidence score |
| `importance_level` | `VARCHAR(20)` | | Priority level |
| `status` | `VARCHAR(50)` | DEFAULT 'unread' | Processing status |
| `processed_at` | `TIMESTAMP` | DEFAULT NOW() | When processed |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() | Record creation time |
| `updated_at` | `TIMESTAMP` | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_emails_date` on `date`
- `idx_emails_category` on `category`
- `idx_emails_from` on `from_email`
- `idx_emails_status` on `status`

#### Table: checkpoints

Stores LangGraph checkpoint state for recovery.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `checkpoint_id` | `SERIAL` | PRIMARY KEY | Auto-increment ID |
| `email_id` | `VARCHAR(255)` | REFERENCES emails | Associated email |
| `step` | `VARCHAR(100)` | NOT NULL | Processing step name |
| `state_json` | `JSONB` | NOT NULL | Serialized state |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() | Checkpoint time |

**Indexes:**
- `idx_checkpoints_email_id` on `email_id`
- `idx_checkpoints_created_at` on `created_at`

#### Table: feedback

Stores user feedback for model improvement.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `feedback_id` | `SERIAL` | PRIMARY KEY | Auto-increment ID |
| `email_id` | `VARCHAR(255)` | REFERENCES emails | Associated email |
| `user_action` | `VARCHAR(50)` | NOT NULL | Action taken (approve/reject/modify) |
| `proposed_category` | `VARCHAR(255)` | | Agent's proposed category |
| `final_category` | `VARCHAR(255)` | | User's chosen category |
| `timestamp` | `TIMESTAMP` | DEFAULT NOW() | Feedback time |

#### Table: importance_rules

Stores learned importance classification rules.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `rule_id` | `SERIAL` | PRIMARY KEY | Auto-increment ID |
| `rule_type` | `VARCHAR(50)` | NOT NULL | Rule type (sender/subject/keyword) |
| `pattern` | `TEXT` | NOT NULL | Matching pattern |
| `priority` | `VARCHAR(20)` | NOT NULL | Priority level |
| `confidence` | `FLOAT` | DEFAULT 0.8 | Rule confidence |
| `approved` | `BOOLEAN` | DEFAULT FALSE | User-approved flag |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() | Creation time |
| `updated_at` | `TIMESTAMP` | DEFAULT NOW() | Last update time |

#### Table: unsubscribe_queue

Manages pending unsubscribe actions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `queue_id` | `SERIAL` | PRIMARY KEY | Auto-increment ID |
| `email_id` | `VARCHAR(255)` | REFERENCES emails | Source email |
| `sender` | `VARCHAR(255)` | NOT NULL | Sender to unsubscribe from |
| `method` | `VARCHAR(50)` | NOT NULL | Unsubscribe method (link/email/manual) |
| `unsubscribe_link` | `TEXT` | | Unsubscribe URL if available |
| `status` | `VARCHAR(50)` | DEFAULT 'pending' | Queue status |
| `user_action` | `VARCHAR(50)` | | User decision |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() | Queue time |
| `executed_at` | `TIMESTAMP` | | Execution time |

#### Table: processing_log

Audit log for all agent actions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `log_id` | `SERIAL` | PRIMARY KEY | Auto-increment ID |
| `email_id` | `VARCHAR(255)` | | Associated email (nullable for system events) |
| `agent` | `VARCHAR(100)` | | Agent name |
| `action` | `VARCHAR(100)` | | Action performed |
| `status` | `VARCHAR(50)` | | Action status |
| `error` | `TEXT` | | Error message if failed |
| `latency_ms` | `INTEGER` | | Action duration in milliseconds |
| `timestamp` | `TIMESTAMP` | DEFAULT NOW() | Log time |

**Indexes:**
- `idx_processing_log_email_id` on `email_id`
- `idx_processing_log_timestamp` on `timestamp`

---

## secrets.tf

Defines Secret Manager resources and IAM bindings.

### Data Source: google_secret_manager_secret.gmail_oauth_client

**Type:** Existing Secret Reference

| Attribute | Value | Description |
|-----------|-------|-------------|
| `secret_id` | `gmail-oauth-token` | OAuth client credentials secret |

**Purpose:** References the OAuth client credentials (client_id, client_secret) for app identity

**JSON Structure:**
```json
{
  "installed": {
    "client_id": "...",
    "client_secret": "...",
    "project_id": "...",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost"]
  }
}
```

### Data Source: google_secret_manager_secret.gmail_user_token

**Type:** Existing Secret Reference

| Attribute | Value | Description |
|-----------|-------|-------------|
| `secret_id` | `gmail-user-token` | User OAuth tokens secret |

**Purpose:** References the user's access and refresh tokens for Gmail API access

**JSON Structure:**
```json
{
  "token": "ya29...",
  "refresh_token": "1//...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/gmail.modify"]
}
```

### Resource: google_secret_manager_secret.anthropic_api_key

**Type:** Secret Manager Secret
**Name Pattern:** `anthropic-api-key-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `secret_id` | `anthropic-api-key-${var.environment}` | Secret name |
| `replication.auto` | `{}` | Automatic replication across regions |

**Purpose:** Stores Anthropic API key for all Claude models (Haiku for fast/cheap tasks, Sonnet/Opus for complex tasks)

### Resource: google_secret_manager_secret.db_password

**Type:** Secret Manager Secret
**Name Pattern:** `db-password-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `secret_id` | `db-password-${var.environment}` | Secret name |
| `replication.auto` | `{}` | Automatic replication across regions |

**Purpose:** Stores auto-generated database password

### Resource: google_secret_manager_secret_version.db_password

**Type:** Secret Version

| Attribute | Value | Description |
|-----------|-------|-------------|
| `secret` | `google_secret_manager_secret.db_password.id` | Parent secret |
| `secret_data` | `random_password.db_password.result` | The password value |

**Purpose:** Creates initial version of database password secret

### IAM Bindings

All IAM bindings grant `roles/secretmanager.secretAccessor` to the runtime service account.

| Resource | Secret | Description |
|----------|--------|-------------|
| `google_secret_manager_secret_iam_member.oauth_client_access` | gmail-oauth-token | Access to OAuth client credentials |
| `google_secret_manager_secret_iam_member.user_token_access` | gmail-user-token | Access to user tokens |
| `google_secret_manager_secret_iam_member.anthropic_access` | anthropic-api-key-{env} | Access to Anthropic key |
| `google_secret_manager_secret_iam_member.db_password_access` | db-password-{env} | Access to DB password |

**Member Format:** `serviceAccount:email-agent-runtime@{project_id}.iam.gserviceaccount.com`

---

## registry.tf

Defines Artifact Registry for Docker image storage.

### Resource: google_artifact_registry_repository.main

**Type:** Artifact Registry Repository
**Name Pattern:** `gmail-agent-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `location` | `var.region` | Regional placement |
| `repository_id` | `gmail-agent-${var.environment}` | Repository name |
| `format` | `DOCKER` | Container image format |
| `description` | `Docker repository for Gmail Agent` | Human-readable description |

#### Cleanup Policy

| Attribute | Value | Description |
|-----------|-------|-------------|
| `id` | `keep-recent` | Policy identifier |
| `action` | `DELETE` | Action to take on matched images |
| `condition.tag_state` | `UNTAGGED` | Target untagged images |
| `condition.older_than` | `604800s` | Delete if older than 7 days |

**Purpose:** Automatically removes untagged images older than 7 days to save storage costs

### Resource: google_artifact_registry_repository_iam_member.runtime_pull

**Type:** IAM Binding

| Attribute | Value | Description |
|-----------|-------|-------------|
| `repository` | `google_artifact_registry_repository.main.name` | Target repository |
| `location` | `var.region` | Repository location |
| `role` | `roles/artifactregistry.reader` | Pull-only access |
| `member` | Service account | Runtime service account |

**Purpose:** Allows Cloud Run to pull images from the registry

---

## cloudrun.tf

Defines Cloud Run service for the Gmail Agent application.

### Resource: google_cloud_run_v2_service.main

**Type:** Cloud Run Service (v2 API)
**Name Pattern:** `gmail-agent-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-${var.environment}` | Service name |
| `location` | `var.region` | Regional deployment |

#### Template Block

| Attribute | Value | Description |
|-----------|-------|-------------|
| `service_account` | `email-agent-runtime@{project}.iam.gserviceaccount.com` | Runtime identity |
| `timeout` | `${var.cloudrun_timeout}s` | Request timeout |

#### VPC Access Block

| Attribute | Value | Description |
|-----------|-------|-------------|
| `connector` | `google_vpc_access_connector.connector.id` | VPC connector reference |
| `egress` | `PRIVATE_RANGES_ONLY` | Only route private IPs through VPC |

**Egress Options:**
| Value | Description |
|-------|-------------|
| `ALL_TRAFFIC` | All traffic through VPC (higher NAT costs) |
| `PRIVATE_RANGES_ONLY` | Only RFC 1918 ranges through VPC |

#### Container Block

| Attribute | Value | Description |
|-----------|-------|-------------|
| `image` | `gcr.io/cloudrun/hello` | Placeholder image (update after build) |

#### Resource Limits

| Attribute | Value | Description |
|-----------|-------|-------------|
| `cpu` | `var.cloudrun_cpu` | CPU allocation |
| `memory` | `var.cloudrun_memory` | Memory allocation |
| `cpu_idle` | `false` | CPU always allocated (not just during requests) |
| `startup_cpu_boost` | `true` | Extra CPU during cold start |

#### Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `PROJECT_ID` | Direct value | GCP project ID |
| `ENVIRONMENT` | Direct value | Environment name |
| `DATABASE_HOST` | Direct value | Cloud SQL private IP |
| `DATABASE_NAME` | Direct value | Database name |
| `DATABASE_USER` | Direct value | Database username |
| `DATABASE_PASSWORD` | Secret reference | Database password from Secret Manager |
| `GMAIL_OAUTH_CLIENT` | Secret reference | OAuth client credentials JSON from Secret Manager |
| `GMAIL_USER_TOKEN` | Secret reference | User access/refresh tokens JSON from Secret Manager |
| `ANTHROPIC_API_KEY` | Secret reference | Anthropic API key from Secret Manager (all Claude models) |

#### Scaling Block

| Attribute | Value | Description |
|-----------|-------|-------------|
| `min_instance_count` | `0` | Scale to zero when idle |
| `max_instance_count` | `var.cloudrun_max_instances` | Maximum concurrent instances |

#### Traffic Block

| Attribute | Value | Description |
|-----------|-------|-------------|
| `percent` | `100` | All traffic to latest revision |
| `type` | `TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST` | Always route to latest |

### Resource: google_cloud_run_service_iam_member.public_access

**Type:** IAM Binding

| Attribute | Value | Description |
|-----------|-------|-------------|
| `service` | `google_cloud_run_v2_service.main.name` | Target service |
| `location` | `var.region` | Service location |
| `role` | `roles/run.invoker` | Permission to invoke |
| `member` | `allUsers` | Public access |

**Security Note:** This allows unauthenticated access. For production, consider using IAM authentication or Cloud Endpoints.

---

## scheduler.tf

Defines Cloud Scheduler for periodic email processing.

### Resource: google_cloud_scheduler_job.hourly_processor

**Type:** Cloud Scheduler Job
**Name Pattern:** `gmail-agent-processor-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-processor-${var.environment}` | Job name |
| `description` | `Hourly email processing trigger` | Human-readable description |
| `schedule` | `0 * * * *` | Cron expression: every hour at minute 0 |
| `time_zone` | `America/New_York` | Timezone for schedule interpretation |
| `region` | `var.region` | Regional placement |

#### Cron Expression Reference

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6)
│ │ │ │ │
0 * * * *
```

**Common Schedules:**
| Expression | Description |
|------------|-------------|
| `0 * * * *` | Every hour |
| `*/15 * * * *` | Every 15 minutes |
| `0 9 * * 1-5` | 9 AM weekdays |
| `0 0 * * *` | Midnight daily |

#### Retry Configuration

| Attribute | Value | Description |
|-----------|-------|-------------|
| `retry_count` | `3` | Maximum retry attempts |
| `min_backoff_duration` | `30s` | Initial retry delay |
| `max_backoff_duration` | `600s` | Maximum retry delay (10 min) |

#### HTTP Target

| Attribute | Value | Description |
|-----------|-------|-------------|
| `uri` | `${cloud_run_url}/process` | Endpoint to call |
| `http_method` | `POST` | HTTP method |
| `headers` | `{"Content-Type": "application/json"}` | Request headers |
| `body` | Base64-encoded JSON | Request payload |

**Request Body (decoded):**
```json
{
  "trigger": "scheduled",
  "mode": "batch"
}
```

#### OIDC Token

| Attribute | Value | Description |
|-----------|-------|-------------|
| `service_account_email` | Runtime SA | Service account for authentication |

**Purpose:** Cloud Scheduler authenticates to Cloud Run using OIDC tokens signed by the specified service account

---

## tasks.tf

Defines Cloud Tasks for reliable batch processing of historical inbox emails.

### Resource: google_cloud_tasks_queue.batch

**Type:** Cloud Tasks Queue
**Name:** `gmail-agent-batch-v3`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-batch-v3` | Queue name (v3 after previous queues were corrupted) |
| `location` | `var.region` | Regional placement |

**Note:** Queue names have a 7-day tombstone period after deletion. If a queue becomes corrupted/stuck, create a new queue with incremented version (v3, v4, etc.).

#### Rate Limits

| Attribute | Value | Description |
|-----------|-------|-------------|
| `max_concurrent_dispatches` | `1` | Serial processing - one chunk at a time |
| `max_dispatches_per_second` | `1` | 1 dispatch per second for faster processing |

**Serial Processing Rationale:** Batch processing modifies shared state (job progress, email counts). Serial execution prevents race conditions and ensures predictable ordering.

#### Stackdriver Logging Configuration

| Attribute | Value | Description |
|-----------|-------|-------------|
| `sampling_ratio` | `1.0` | Log 100% of task operations |

**Purpose:** Full logging enables debugging of dispatch failures. Set to `0.0` (default) or lower in production if log volume is a concern.

**Log Query:**
```
resource.type="cloud_tasks_queue"
jsonPayload.@type="type.googleapis.com/google.cloud.tasks.logging.v1.TaskActivityLog"
```

#### Retry Configuration

| Attribute | Value | Description |
|-----------|-------|-------------|
| `max_attempts` | `4` | Original attempt + 3 retries |
| `min_backoff` | `10s` | Initial retry delay |
| `max_backoff` | `600s` | Maximum retry delay (10 minutes) |
| `max_doublings` | `4` | Exponential backoff doublings |

**Backoff Progression:** 10s → 20s → 40s → 80s → 160s → 320s → 600s (capped)

### Resource: google_cloud_tasks_queue_iam_member.enqueuer

**Type:** IAM Binding

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `google_cloud_tasks_queue.batch.id` | Target queue |
| `role` | `roles/cloudtasks.enqueuer` | Permission to add tasks to queue |
| `member` | Runtime service account | `email-agent-runtime@{project}.iam.gserviceaccount.com` |

**Purpose:** Allows Cloud Run to enqueue continuation tasks after processing each chunk

### Resource: google_cloud_run_service_iam_member.cloudtasks_invoker

**Type:** IAM Binding

| Attribute | Value | Description |
|-----------|-------|-------------|
| `service` | `google_cloud_run_v2_service.main.name` | Target Cloud Run service |
| `location` | `var.region` | Service location |
| `role` | `roles/run.invoker` | Permission to invoke the service |
| `member` | Runtime service account | `email-agent-runtime@{project}.iam.gserviceaccount.com` |

**Purpose:** Allows Cloud Tasks to invoke the `/batch-worker` endpoint

### Output: cloud_tasks_queue

| Attribute | Value | Description |
|-----------|-------|-------------|
| `value` | `google_cloud_tasks_queue.batch.id` | Full queue path |
| `description` | Full path to Cloud Tasks queue for batch processing | Human-readable description |

**Example:** `projects/gmail-agent-prod/locations/us-central1/queues/gmail-agent-batch-v3`

### Critical IAM Configuration (Manual)

Cloud Tasks auto-dispatch requires an IAM binding that is NOT managed by Terraform (requires project number):

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe gmail-agent-prod --format='value(projectNumber)')

# Grant serviceAccountUser to Cloud Tasks service agent
gcloud iam service-accounts add-iam-policy-binding \
  email-agent-runtime@gmail-agent-prod.iam.gserviceaccount.com \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

**Why serviceAccountUser?** Cloud Tasks needs `iam.serviceAccounts.actAs` permission to generate OIDC tokens for authenticated HTTP requests. This permission comes from `serviceAccountUser`, NOT `serviceAccountTokenCreator`.

| Role | Key Permission | Used by Cloud Tasks |
|------|----------------|---------------------|
| `roles/iam.serviceAccountUser` | `iam.serviceAccounts.actAs` | ✅ Required for OIDC auto-dispatch |
| `roles/iam.serviceAccountTokenCreator` | `iam.serviceAccounts.getOpenIdToken` | ❌ Not used by service agent |

### Task Structure (Application Code)

Tasks are created by the application with this structure:

```python
task = {
    "http_request": {
        "http_method": "POST",
        "url": "https://{cloud-run-url}/batch-worker",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"job_id": "...", "task_id": "..."}).encode("utf-8"),
        "oidc_token": {
            "service_account_email": "email-agent-runtime@{project}.iam.gserviceaccount.com",
            "audience": "https://{cloud-run-url}",
        },
    }
}
```

**OIDC Audience:** Must be the Cloud Run `.run.app` URL, not a custom domain. Custom domains are not supported for OIDC token validation.

### Batch Processing Flow

```
1. User calls POST /batch-process
   └─► Creates batch_jobs record in database
   └─► Enqueues first chunk task to Cloud Tasks

2. Cloud Tasks dispatches task to /batch-worker
   └─► Task includes job_id and task_id
   └─► OIDC token authenticates request

3. /batch-worker processes chunk
   └─► Fetches emails for date range
   └─► Classifies with Anthropic API
   └─► Updates job progress in database
   └─► Enqueues next chunk (if more remain)

4. Repeat until all chunks complete
   └─► Job status changes to "completed"
```

### Troubleshooting

| Symptom | Diagnostic | Solution |
|---------|------------|----------|
| Tasks stuck at 0 dispatch attempts | `gcloud tasks describe TASK_ID` shows `dispatchCount: 0` | Add `serviceAccountUser` IAM binding |
| Manual dispatch works, auto fails | `gcloud tasks run TASK_ID` succeeds | Missing `actAs` permission on service agent |
| Queue stuck/corrupted | Tasks never dispatch even with correct IAM | Create new queue (v4, v5, etc.) |
| OIDC audience mismatch | 401 errors in Cloud Run logs | Ensure audience is `.run.app` URL |

**Manual Dispatch for Testing:**
```bash
gcloud tasks run TASK_ID \
  --queue=gmail-agent-batch-v3 \
  --location=us-central1
```

Note: Manual dispatch uses your credentials, bypassing the service agent. Success with manual dispatch but failure with auto-dispatch indicates IAM misconfiguration.

---

## monitoring.tf

Defines logging, storage, and alerting infrastructure.

### Resource: google_storage_bucket.logs

**Type:** Cloud Storage Bucket
**Name Pattern:** `{project_id}-logs-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `${var.project_id}-logs-${var.environment}` | Globally unique bucket name |
| `location` | `var.region` | Regional storage |
| `force_destroy` | Conditional | `true` for non-prod (allows deletion with contents) |

#### Lifecycle Rule

| Attribute | Value | Description |
|-----------|-------|-------------|
| `action.type` | `Delete` | Delete old objects |
| `condition.age` | `90` | Objects older than 90 days |

**Purpose:** Automatically deletes logs older than 90 days to control costs

### Resource: google_logging_project_sink.archive

**Type:** Log Sink
**Name Pattern:** `gmail-agent-archive-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-archive-${var.environment}` | Sink name |
| `destination` | `storage.googleapis.com/${bucket}` | Target storage bucket |
| `filter` | See below | Log filter expression |
| `unique_writer_identity` | `true` | Creates dedicated service account |

**Filter Expression:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gmail-agent-{environment}"
```

**Purpose:** Exports all Cloud Run logs to Cloud Storage for long-term retention

### Resource: google_storage_bucket_iam_member.log_writer

**Type:** IAM Binding

| Attribute | Value | Description |
|-----------|-------|-------------|
| `bucket` | `google_storage_bucket.logs.name` | Target bucket |
| `role` | `roles/storage.objectCreator` | Write-only access |
| `member` | `google_logging_project_sink.archive.writer_identity` | Log sink's service account |

### Resource: google_monitoring_alert_policy.error_rate

**Type:** Monitoring Alert Policy
**Name Pattern:** `Gmail Agent High Error Rate - {environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `display_name` | `Gmail Agent High Error Rate - ${var.environment}` | Alert name |
| `combiner` | `OR` | Alert if ANY condition is true |

#### Condition: Error Rate

| Attribute | Value | Description |
|-----------|-------|-------------|
| `display_name` | `Error rate > 10%` | Condition name |
| `filter` | See below | Metric filter |
| `duration` | `300s` | Condition must persist for 5 minutes |
| `comparison` | `COMPARISON_GT` | Greater than threshold |
| `threshold_value` | `0.1` | 10% error rate |

**Metric Filter:**
```
resource.type="cloud_run_revision"
AND resource.labels.service_name="gmail-agent-{environment}"
AND metric.type="run.googleapis.com/request_count"
AND metric.labels.response_code_class="5xx"
```

#### Aggregation

| Attribute | Value | Description |
|-----------|-------|-------------|
| `alignment_period` | `60s` | 1-minute windows |
| `per_series_aligner` | `ALIGN_RATE` | Calculate rate of change |

#### Alert Strategy

| Attribute | Value | Description |
|-----------|-------|-------------|
| `auto_close` | `1800s` | Auto-close after 30 minutes of no alerts |

**notification_channels:** Empty array; add channel IDs for email/SMS/PagerDuty notifications

---

## bastion.tf

Defines a bastion host for secure database access via IAP (Identity-Aware Proxy).

### Resource: google_compute_instance.bastion

**Type:** Compute Engine Instance
**Name Pattern:** `gmail-agent-bastion-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `gmail-agent-bastion-${var.environment}` | Instance name |
| `machine_type` | `e2-micro` | Smallest instance type (cost-effective) |
| `zone` | `${var.region}-a` | Zone within region |

#### Boot Disk

| Attribute | Value | Description |
|-----------|-------|-------------|
| `image` | `debian-cloud/debian-12` | Debian 12 OS |
| `size` | `10` | 10 GB disk (minimum) |
| `auto_delete` | `true` | Delete disk when instance deleted |

#### Network Interface

| Attribute | Value | Description |
|-----------|-------|-------------|
| `network` | `google_compute_network.main.id` | VPC network |
| `subnetwork` | `google_compute_subnetwork.cloudrun.id` | Subnet |
| No external IP | - | Access via IAP only (secure) |

#### Startup Script

Automatically installs PostgreSQL client:
```bash
apt-get update
apt-get install -y postgresql-client
```

#### Scheduling

| Attribute | Value | Description |
|-----------|-------|-------------|
| `preemptible` | Conditional | `true` in non-prod (cheaper, may restart) |
| `automatic_restart` | Conditional | `true` in prod only |

#### Tags

- `bastion` - Identifies as bastion host
- `iap-ssh` - Allows IAP SSH firewall rule

**Purpose:** Provides secure SSH access to the VPC for database administration without exposing a public IP

### Resource: google_service_account.bastion

**Type:** Service Account
**Name Pattern:** `bastion-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `account_id` | `bastion-${var.environment}` | Service account ID |
| `display_name` | `Bastion Host Service Account - ${var.environment}` | Human-readable name |

**Purpose:** Dedicated identity for bastion with minimal permissions

### Resource: google_secret_manager_secret_iam_member.bastion_db_password

**Type:** IAM Binding

| Attribute | Value | Description |
|-----------|-------|-------------|
| `secret_id` | `google_secret_manager_secret.db_password.id` | DB password secret |
| `role` | `roles/secretmanager.secretAccessor` | Read access |
| `member` | Bastion service account | Grants access to bastion |

**Purpose:** Allows bastion to retrieve database password for connections

### Resource: google_compute_firewall.iap_ssh

**Type:** Firewall Rule
**Name Pattern:** `allow-iap-ssh-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `allow-iap-ssh-${var.environment}` | Rule name |
| `network` | `google_compute_network.main.id` | VPC network |
| `allow.protocol` | `tcp` | TCP protocol |
| `allow.ports` | `["22"]` | SSH port |
| `source_ranges` | `["35.235.240.0/20"]` | Google IAP IP range |
| `target_tags` | `["iap-ssh"]` | Apply to tagged instances |

**Purpose:** Allows SSH connections from Google's IAP service only (not public internet)

### Resource: google_compute_firewall.bastion_to_sql

**Type:** Firewall Rule
**Name Pattern:** `allow-bastion-sql-{environment}`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `allow-bastion-sql-${var.environment}` | Rule name |
| `network` | `google_compute_network.main.id` | VPC network |
| `allow.protocol` | `tcp` | TCP protocol |
| `allow.ports` | `["5432"]` | PostgreSQL port |
| `source_tags` | `["bastion"]` | From bastion only |

**Purpose:** Allows bastion to connect to Cloud SQL on PostgreSQL port

### Connecting via Bastion

```bash
# SSH to bastion via IAP (no public IP needed)
gcloud compute ssh gmail-agent-bastion-dev \
  --zone=us-central1-a \
  --tunnel-through-iap

# Once connected, get DB password and connect
DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password-dev")
PGPASSWORD=$DB_PASSWORD psql -h <DB_PRIVATE_IP> -U agent_user -d email_agent
```

---

## outputs.tf

Defines output values exposed after deployment.

### Output: cloud_run_url

| Attribute | Value | Description |
|-----------|-------|-------------|
| `description` | URL of the Cloud Run service | Human-readable description |
| `value` | `google_cloud_run_v2_service.main.uri` | The service URL |

**Example:** `https://gmail-agent-dev-abc123-uc.a.run.app`

### Output: database_private_ip

| Attribute | Value | Description |
|-----------|-------|-------------|
| `description` | Private IP address of the Cloud SQL instance | Human-readable description |
| `value` | `google_sql_database_instance.main.private_ip_address` | Internal IP |
| `sensitive` | `true` | Hidden from logs/console |

**Example:** `10.0.0.5`

### Output: artifact_registry_url

| Attribute | Value | Description |
|-----------|-------|-------------|
| `description` | URL of the Artifact Registry | Human-readable description |
| `value` | `{region}-docker.pkg.dev/{project}/{repo}` | Full registry path |

**Example:** `us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev`

**Usage:** `docker push {artifact_registry_url}/image:tag`

### Output: vpc_connector_name

| Attribute | Value | Description |
|-----------|-------|-------------|
| `description` | Name of the VPC connector | Human-readable description |
| `value` | `google_vpc_access_connector.connector.name` | Connector name |

**Example:** `gmail-agent-connector-dev`

### Output: scheduler_job_name

| Attribute | Value | Description |
|-----------|-------|-------------|
| `description` | Name of the Cloud Scheduler job | Human-readable description |
| `value` | `google_cloud_scheduler_job.hourly_processor.name` | Job name |

**Example:** `gmail-agent-processor-dev`

---

## terraform.tfvars.example

Example variable values file. Copy to `terraform.tfvars` and customize.

```hcl
project_id  = "gmail-agent-prod"    # Your GCP project ID
region      = "us-central1"          # Deployment region
environment = "dev"                  # Environment name

# Database
db_tier = "db-f1-micro"              # Instance size

# Cloud Run
cloudrun_cpu           = "2"         # vCPUs
cloudrun_memory        = "4Gi"       # Memory
cloudrun_timeout       = "3600"      # Timeout (seconds)
cloudrun_max_instances = 5           # Max scaling
```

### Recommended Values by Environment

| Variable | Dev | Staging | Prod |
|----------|-----|---------|------|
| `db_tier` | `db-f1-micro` | `db-g1-small` | `db-n1-standard-1` |
| `cloudrun_cpu` | `"1"` | `"2"` | `"2"` |
| `cloudrun_memory` | `"2Gi"` | `"4Gi"` | `"4Gi"` |
| `cloudrun_max_instances` | `3` | `5` | `10` |

---

## Resource Dependencies Graph

```
                    ┌─────────────────┐
                    │  google_compute │
                    │   _network.main │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ subnetwork    │  │ global_address  │  │ vpc_access      │
│ .cloudrun     │  │ .sql_private_ip │  │ _connector      │
└───────────────┘  └────────┬────────┘  └────────┬────────┘
                            │                    │
                            ▼                    │
                   ┌─────────────────┐           │
                   │ service_network │           │
                   │ ing_connection  │           │
                   └────────┬────────┘           │
                            │                    │
                            ▼                    │
                   ┌─────────────────┐           │
                   │ sql_database    │           │
                   │ _instance.main  │           │
                   └────────┬────────┘           │
                            │                    │
              ┌─────────────┼─────────────┐      │
              │             │             │      │
              ▼             ▼             ▼      │
       ┌──────────┐  ┌──────────┐  ┌──────────┐ │
       │ database │  │ sql_user │  │ secrets  │ │
       │ .main    │  │ .agent   │  │ (all)    │ │
       └──────────┘  └──────────┘  └────┬─────┘ │
                                        │       │
                                        ▼       ▼
                                   ┌─────────────────┐
                                   │ cloud_run_v2    │
                                   │ _service.main   │
                                   └────────┬────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │ cloud_scheduler │
                                   │ _job            │
                                   └─────────────────┘
```

---

## Quick Reference: Resource Naming

| Resource Type | Naming Pattern | Example |
|---------------|----------------|---------|
| VPC | `gmail-agent-vpc-{env}` | `gmail-agent-vpc-dev` |
| Subnet | `cloudrun-subnet-{env}` | `cloudrun-subnet-dev` |
| VPC Connector | `gmail-agent-connector-{env}` | `gmail-agent-connector-dev` |
| Cloud Router | `gmail-agent-router-{env}` | `gmail-agent-router-dev` |
| Cloud NAT | `gmail-agent-nat-{env}` | `gmail-agent-nat-dev` |
| Cloud SQL | `gmail-agent-db-{env}` | `gmail-agent-db-dev` |
| Secret (OAuth Client) | `gmail-oauth-token` | `gmail-oauth-token` |
| Secret (User Token) | `gmail-user-token` | `gmail-user-token` |
| Secret (Anthropic) | `anthropic-api-key-{env}` | `anthropic-api-key-dev` |
| Secret (DB) | `db-password-{env}` | `db-password-dev` |
| Artifact Registry | `gmail-agent-{env}` | `gmail-agent-dev` |
| Cloud Run | `gmail-agent-{env}` | `gmail-agent-dev` |
| Scheduler | `gmail-agent-processor-{env}` | `gmail-agent-processor-dev` |
| Cloud Tasks Queue | `gmail-agent-batch-v3` | `gmail-agent-batch-v3` |
| Log Sink | `gmail-agent-archive-{env}` | `gmail-agent-archive-dev` |
| Log Bucket | `{project}-logs-{env}` | `gmail-agent-prod-logs-dev` |
| Alert Policy | `Gmail Agent High Error Rate - {env}` | `Gmail Agent High Error Rate - dev` |

---

## Quick Reference: IAM Roles Used

| Role | Resource | Purpose |
|------|----------|---------|
| `roles/secretmanager.secretAccessor` | Secret Manager | Read secret values |
| `roles/artifactregistry.reader` | Artifact Registry | Pull Docker images |
| `roles/run.invoker` | Cloud Run | Invoke the service |
| `roles/storage.objectCreator` | Cloud Storage | Write log files |
| `roles/cloudtasks.enqueuer` | Cloud Tasks Queue | Add tasks to queue |
| `roles/iam.serviceAccountUser` | Service Account | Cloud Tasks OIDC token generation (manual) |

---

## Quick Reference: APIs Required

These APIs must be enabled in your GCP project:

| API | Service | Purpose |
|-----|---------|---------|
| `compute.googleapis.com` | Compute Engine | VPC, subnets, NAT |
| `sqladmin.googleapis.com` | Cloud SQL Admin | Database management |
| `servicenetworking.googleapis.com` | Service Networking | VPC peering |
| `vpcaccess.googleapis.com` | VPC Access | Serverless connector |
| `run.googleapis.com` | Cloud Run | Container service |
| `artifactregistry.googleapis.com` | Artifact Registry | Image storage |
| `secretmanager.googleapis.com` | Secret Manager | Secret storage |
| `cloudscheduler.googleapis.com` | Cloud Scheduler | Job scheduling |
| `cloudtasks.googleapis.com` | Cloud Tasks | Batch processing queue |
| `logging.googleapis.com` | Cloud Logging | Log management |
| `monitoring.googleapis.com` | Cloud Monitoring | Alerts and metrics |
