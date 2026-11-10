output "enabled_services" {
  value = sort([for service in google_project_service.required : service.service])
}
