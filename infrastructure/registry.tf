resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "gmail-agent-${var.environment}"
  format        = "DOCKER"
  description   = "Docker repository for Gmail Agent"

  cleanup_policies {
    id     = "keep-recent"
    action = "DELETE"
    condition {
      tag_state    = "UNTAGGED"
      older_than   = "604800s" # 7 days
    }
  }
}

# Grant pull access to runtime service account
resource "google_artifact_registry_repository_iam_member" "runtime_pull" {
  repository = google_artifact_registry_repository.main.name
  location   = var.region
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}
