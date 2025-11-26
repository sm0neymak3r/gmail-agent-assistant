# Placeholder Cloud Run service
resource "google_cloud_run_v2_service" "main" {
  name     = "gmail-agent-${var.environment}"
  location = var.region

  template {
    service_account = "email-agent-runtime@${var.project_id}.iam.gserviceaccount.com"
    timeout         = "${var.cloudrun_timeout}s"

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      # Initially use a simple hello-world image
      image = "gcr.io/cloudrun/hello"

      resources {
        limits = {
          cpu    = var.cloudrun_cpu
          memory = var.cloudrun_memory
        }
        cpu_idle = false
        startup_cpu_boost = true
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "DATABASE_HOST"
        value = google_sql_database_instance.main.private_ip_address
      }

      env {
        name  = "DATABASE_NAME"
        value = google_sql_database.main.name
      }

      env {
        name  = "DATABASE_USER"
        value = google_sql_user.agent.name
      }

      env {
        name = "DATABASE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }

      # Gmail OAuth client credentials (app identity)
      env {
        name = "GMAIL_OAUTH_CLIENT"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.gmail_oauth_client.secret_id
            version = "latest"
          }
        }
      }

      # Gmail user token (access/refresh tokens)
      env {
        name = "GMAIL_USER_TOKEN"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.gmail_user_token.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = var.cloudrun_max_instances
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Allow unauthenticated access for health checks
resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_v2_service.main.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
