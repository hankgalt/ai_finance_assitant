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

output "migration_service_account" {
  value = google_service_account.workload["migration"].email
}

output "retention_service_account" {
  value = google_service_account.workload["retention"].email
}

output "regional_secret_names" {
  value = { for key, secret in google_secret_manager_regional_secret.staging : key => secret.id }
}
