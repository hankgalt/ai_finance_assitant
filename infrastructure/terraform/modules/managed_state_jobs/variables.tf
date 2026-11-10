variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "backend_image" {
  type        = string
  description = "Immutable Finance Assistant backend image reference."

  validation {
    condition     = strcontains(var.backend_image, "@sha256:")
    error_message = "backend_image must be pinned by sha256 digest."
  }
}

variable "cloud_sql_proxy_image" {
  type        = string
  description = "Immutable Cloud SQL Auth Proxy image reference."

  validation {
    condition     = strcontains(var.cloud_sql_proxy_image, "@sha256:")
    error_message = "cloud_sql_proxy_image must be pinned by sha256 digest."
  }
}

variable "network_id" {
  type = string
}

variable "subnetwork_id" {
  type = string
}

variable "instance_connection_name" {
  type = string
}

variable "database_name" {
  type = string
}

variable "service_account_emails" {
  type = object({
    runtime   = string
    migration = string
    retention = string
  })
}
