output "artifact_registry_repository" {
  value = google_artifact_registry_repository.containers.name
}

output "staging_workload_identity_provider" {
  value = module.staging_identity.provider_name
}

output "staging_deploy_service_account" {
  value = module.staging_identity.service_account_email
}

output "production_workload_identity_provider" {
  value = module.production_identity.provider_name
}

output "production_deploy_service_account" {
  value = module.production_identity.service_account_email
}
