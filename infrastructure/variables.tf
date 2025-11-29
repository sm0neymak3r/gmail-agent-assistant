variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "gmail-agent-prod"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "cloudrun_cpu" {
  description = "Cloud Run CPU allocation"
  type        = string
  default     = "2"
}

variable "cloudrun_memory" {
  description = "Cloud Run memory allocation"
  type        = string
  default     = "4Gi"
}

variable "cloudrun_timeout" {
  description = "Cloud Run timeout in seconds"
  type        = string
  default     = "3600"
}

variable "cloudrun_max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 5
}

variable "cloudrun_image" {
  description = "Cloud Run container image"
  type        = string
  default     = "us-central1-docker.pkg.dev/gmail-agent-prod/gmail-agent-dev/agent:v12"
}
