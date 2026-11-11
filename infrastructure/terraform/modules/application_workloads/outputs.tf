output "service_names" {
  value = {
    backend  = google_cloud_run_v2_service.backend.name
    frontend = google_cloud_run_v2_service.frontend.name
  }
}

output "service_uris" {
  description = "Expected to remain null/empty while default Cloud Run URIs are disabled."
  value = {
    backend  = google_cloud_run_v2_service.backend.uri
    frontend = google_cloud_run_v2_service.frontend.uri
  }
}
