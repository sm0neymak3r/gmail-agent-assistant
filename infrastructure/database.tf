# Random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Cloud SQL PostgreSQL instance
resource "google_sql_database_instance" "main" {
  name             = "gmail-agent-db-${var.environment}"
  database_version = "POSTGRES_15"
  region           = var.region

  depends_on = [google_service_networking_connection.sql_private_vpc]

  settings {
    tier              = var.db_tier
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled    = true
      start_time = "03:00"
      location   = var.region

      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length    = 1024
      record_application_tags = true
      record_client_address  = true
    }
  }

  deletion_protection = false  # Set to true in production
}

# Database
resource "google_sql_database" "main" {
  name     = "email_agent"
  instance = google_sql_database_instance.main.name
}

# Database user
resource "google_sql_user" "agent" {
  name     = "agent_user"
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}
