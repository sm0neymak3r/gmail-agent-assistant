# Log sink for archival
resource "google_logging_project_sink" "archive" {
  name        = "gmail-agent-archive-${var.environment}"
  destination = "storage.googleapis.com/${google_storage_bucket.logs.name}"

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="gmail-agent-${var.environment}"
  EOT

  unique_writer_identity = true
}

# Storage bucket for logs
resource "google_storage_bucket" "logs" {
  name          = "${var.project_id}-logs-${var.environment}"
  location      = var.region
  force_destroy = var.environment != "prod"

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90
    }
  }
}

# Grant write access to log sink
resource "google_storage_bucket_iam_member" "log_writer" {
  bucket = google_storage_bucket.logs.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.archive.writer_identity
}

# Alert policy for high error rate
resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "Gmail Agent High Error Rate - ${var.environment}"
  combiner     = "OR"

  conditions {
    display_name = "Error rate > 10%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"gmail-agent-${var.environment}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.1

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []  # Add notification channels as needed

  alert_strategy {
    auto_close = "1800s"
  }
}
