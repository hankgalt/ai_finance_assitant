output "global_ip_address" {
  value = google_compute_global_address.application.address
}

output "backend_iap_audience" {
  value = "/projects/${var.project_number}/global/backendServices/${google_compute_backend_service.application["backend"].generated_id}"
}

output "backend_service_ids" {
  value = {
    for name, service in google_compute_backend_service.application : name => service.generated_id
  }
}

output "backend_service_names" {
  value = {
    for name, service in google_compute_backend_service.application : name => service.name
  }
}

output "certificate_name" {
  value = google_compute_managed_ssl_certificate.application.name
}

output "url_map_name" {
  value = google_compute_url_map.https.name
}
