output "cloud_sql_instance" {
  value = module.managed_state.instance_name
}

output "cloud_sql_connection_name" {
  value = module.managed_state.instance_connection_name
}

output "cloud_sql_private_ip" {
  value = module.managed_state.private_ip_address
}

output "runtime_service_account" {
  value = google_service_account.workload["runtime"].email
}

output "frontend_service_account" {
  value = google_service_account.workload["frontend"].email
}

output "migration_service_account" {
  value = google_service_account.workload["migration"].email
}

output "retention_service_account" {
  value = google_service_account.workload["retention"].email
}

output "qdrant_runtime_secret_id" {
  value = google_secret_manager_secret.qdrant_runtime.secret_id
}

output "qdrant_release_secret_id" {
  value = google_secret_manager_secret.qdrant_release.secret_id
}

output "live_provider_secret_ids" {
  value = {
    for provider, secret in google_secret_manager_secret.live_provider : provider => secret.secret_id
  }
}

output "managed_state_job_names" {
  value = module.managed_state_jobs.job_names
}
