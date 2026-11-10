output "provider_name" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "service_account_email" {
  value = google_service_account.github.email
}

output "pool_name" {
  value = google_iam_workload_identity_pool.github.name
}
