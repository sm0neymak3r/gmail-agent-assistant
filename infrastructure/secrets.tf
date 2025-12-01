# Import existing OAuth client credentials secret
data "google_secret_manager_secret" "gmail_oauth_client" {
  secret_id = "gmail-oauth-token"
}

# Import existing Gmail user token secret
data "google_secret_manager_secret" "gmail_user_token" {
  secret_id = "gmail-user-token"
}

# Create secret for Anthropic API key (used for all Claude models: Haiku, Sonnet, Opus)
resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "anthropic-api-key-${var.environment}"

  replication {
    auto {}
  }
}

# Store database password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password-${var.environment}"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Grant access to runtime service account
resource "google_secret_manager_secret_iam_member" "oauth_client_access" {
  secret_id = data.google_secret_manager_secret.gmail_oauth_client.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "user_token_access" {
  secret_id = data.google_secret_manager_secret.gmail_user_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "anthropic_access" {
  secret_id = google_secret_manager_secret.anthropic_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "db_password_access" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
}
