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

variable "frontend_image" {
  type        = string
  description = "Immutable Finance Assistant frontend image reference."

  validation {
    condition     = strcontains(var.frontend_image, "@sha256:")
    error_message = "frontend_image must be pinned by sha256 digest."
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

variable "runtime_service_account_email" {
  type = string
}

variable "frontend_service_account_email" {
  type = string
}

variable "qdrant_url" {
  type = string

  validation {
    condition     = startswith(var.qdrant_url, "https://")
    error_message = "qdrant_url must use HTTPS."
  }
}

variable "qdrant_secret_id" {
  type = string
}

variable "qdrant_secret_version" {
  type        = string
  description = "Enabled numeric Secret Manager version containing the Qdrant runtime API key."

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.qdrant_secret_version))
    error_message = "qdrant_secret_version must be a positive numeric version, never latest."
  }
}

variable "iap_audience" {
  type        = string
  description = "Expected signed IAP audience. The pre-edge value must be an explicitly fail-closed sentinel."

  validation {
    condition     = can(regex("^/projects/[0-9]+/global/backendServices/[0-9]+$", var.iap_audience))
    error_message = "iap_audience must identify one numeric global backend service."
  }
}

variable "iap_owner_email" {
  type = string
}
