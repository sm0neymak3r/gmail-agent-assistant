output "cloud_run_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.main.uri
}

output "database_private_ip" {
  description = "Private IP address of the Cloud SQL instance"
  value       = google_sql_database_instance.main.private_ip_address
  sensitive   = true
}

output "artifact_registry_url" {
  description = "URL of the Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}

output "vpc_connector_name" {
  description = "Name of the VPC connector"
  value       = google_vpc_access_connector.connector.name
}

output "scheduler_job_name" {
  description = "Name of the Cloud Scheduler job"
  value       = google_cloud_scheduler_job.hourly_processor.name
}

output "bastion_name" {
  description = "Name of the bastion host instance"
  value       = google_compute_instance.bastion.name
}

output "bastion_zone" {
  description = "Zone of the bastion host instance"
  value       = google_compute_instance.bastion.zone
}
