# Bastion host for secure database access
# Uses IAP (Identity-Aware Proxy) for SSH - no public IP needed on bastion

# Small Compute Engine instance in the VPC
resource "google_compute_instance" "bastion" {
  name         = "gmail-agent-bastion-${var.environment}"
  machine_type = "e2-micro"  # Smallest/cheapest instance
  zone         = "${var.region}-a"

  # Auto-delete when instance is deleted
  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10  # GB - minimum needed
    }
    auto_delete = true
  }

  network_interface {
    network    = google_compute_network.main.id
    subnetwork = google_compute_subnetwork.cloudrun.id
    # No external IP - access via IAP only
  }

  # Install PostgreSQL client on startup
  metadata_startup_script = <<-EOF
    #!/bin/bash
    apt-get update
    apt-get install -y postgresql-client
  EOF

  # Allow the instance to be stopped to save costs
  scheduling {
    preemptible       = var.environment != "prod"  # Use preemptible in non-prod to save costs
    automatic_restart = var.environment == "prod"
  }

  # Service account with minimal permissions
  service_account {
    email  = google_service_account.bastion.email
    scopes = ["cloud-platform"]
  }

  tags = ["bastion", "iap-ssh"]

  labels = {
    environment = var.environment
    purpose     = "database-access"
  }
}

# Dedicated service account for bastion
resource "google_service_account" "bastion" {
  account_id   = "bastion-${var.environment}"
  display_name = "Bastion Host Service Account - ${var.environment}"
}

# Grant bastion SA access to read secrets (for DB password)
resource "google_secret_manager_secret_iam_member" "bastion_db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.bastion.email}"
}

# Firewall rule to allow IAP SSH access to bastion
resource "google_compute_firewall" "iap_ssh" {
  name    = "allow-iap-ssh-${var.environment}"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP's IP range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["iap-ssh"]
}

# Firewall rule to allow bastion to connect to Cloud SQL
resource "google_compute_firewall" "bastion_to_sql" {
  name    = "allow-bastion-sql-${var.environment}"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_tags = ["bastion"]
  # Cloud SQL is on the peered network, this allows egress
}
