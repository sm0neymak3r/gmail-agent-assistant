# Cloud Tasks for reliable batch processing
# Replaces unreliable self-continuation HTTP calls with guaranteed delivery
#
# NOTE: Cloud Tasks API must be enabled manually via gcloud:
#   gcloud services enable cloudtasks.googleapis.com --project=gmail-agent-prod

# Batch processing queue
# NOTE: Queue was recreated as gmail-agent-batch-v4 after v3 queue became stuck
# The previous queue names have a 7-day tombstone period
resource "google_cloud_tasks_queue" "batch" {
  name     = "gmail-agent-batch-v4"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 1    # Serial processing - one chunk at a time
    max_dispatches_per_second = 1    # 1 per second for faster processing
  }

  stackdriver_logging_config {
    sampling_ratio = 1.0  # Log all task operations for debugging
  }

  retry_config {
    max_attempts       = 4      # Original + 3 retries
    min_backoff        = "10s"
    max_backoff        = "600s" # 10 minutes max
    max_doublings      = 4
  }
}

# IAM for Cloud Run service account to enqueue tasks
resource "google_cloud_tasks_queue_iam_member" "enqueuer" {
  name   = google_cloud_tasks_queue.batch.id
  role   = "roles/cloudtasks.enqueuer"
  member = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}

# IAM for Cloud Tasks to invoke Cloud Run
resource "google_cloud_run_service_iam_member" "cloudtasks_invoker" {
  service  = google_cloud_run_v2_service.main.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}

# Output the queue path for use in application config
output "cloud_tasks_queue" {
  value       = google_cloud_tasks_queue.batch.id
  description = "Full path to Cloud Tasks queue for batch processing"
}
