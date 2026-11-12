output "application_service_names" {
  value = module.application_workloads.service_names
}

output "application_service_uris" {
  value = module.application_workloads.service_uris
}

output "configured_iap_audience" {
  value = var.iap_audience
}
