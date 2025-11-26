# VPC for Cloud SQL Private Service Connect
resource "google_compute_network" "main" {
  name                    = "gmail-agent-vpc-${var.environment}"
  auto_create_subnetworks = false
  mtu                     = 1460
}

# Subnet for Cloud Run
resource "google_compute_subnetwork" "cloudrun" {
  name          = "cloudrun-subnet-${var.environment}"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.main.id
}

# Private Service Connection for Cloud SQL
resource "google_compute_global_address" "sql_private_ip" {
  name          = "sql-private-ip-${var.environment}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "sql_private_vpc" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql_private_ip.name]
}

# Serverless VPC Connector for Cloud Run
resource "google_vpc_access_connector" "connector" {
  name          = "gmail-agent-connector-${var.environment}"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.main.id
  min_instances = 2
  max_instances = 3
}

# Cloud Router for NAT (needed for external API calls)
resource "google_compute_router" "router" {
  name    = "gmail-agent-router-${var.environment}"
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "gmail-agent-nat-${var.environment}"
  router                            = google_compute_router.router.name
  region                            = var.region
  nat_ip_allocate_option            = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
