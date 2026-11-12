output "global_ip_address" {
  value = module.private_edge.global_ip_address
}

output "backend_iap_audience" {
  value = module.private_edge.backend_iap_audience
}

output "backend_service_ids" {
  value = module.private_edge.backend_service_ids
}

output "backend_service_names" {
  value = module.private_edge.backend_service_names
}

output "certificate_name" {
  value = module.private_edge.certificate_name
}

output "url_map_name" {
  value = module.private_edge.url_map_name
}
