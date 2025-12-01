# Cloud Scheduler for hourly email processing
resource "google_cloud_scheduler_job" "hourly_processor" {
  name        = "gmail-agent-processor-${var.environment}"
  description = "Hourly email processing trigger"
  schedule    = "0 * * * *"  # Every hour
  time_zone   = "America/New_York"
  region      = var.region

  retry_config {
    retry_count = 3
    min_backoff_duration = "30s"
    max_backoff_duration = "600s"
  }

  http_target {
    uri         = "${google_cloud_run_v2_service.main.uri}/process"
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      trigger = "scheduled"
      mode    = "batch"
    }))

    oidc_token {
      service_account_email = "email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
    }
  }
}
