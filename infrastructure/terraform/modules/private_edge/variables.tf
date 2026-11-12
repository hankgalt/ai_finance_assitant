variable "project_id" {
  type = string
}

variable "project_number" {
  type = string

  validation {
    condition     = can(regex("^[0-9]+$", var.project_number))
    error_message = "project_number must contain only decimal digits."
  }
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "domain" {
  type = string

  validation {
    condition     = can(regex("^[a-z0-9.-]+$", var.domain)) && !startswith(var.domain, ".")
    error_message = "domain must be a lowercase DNS name."
  }
}

variable "base_path" {
  type = string

  validation {
    condition     = startswith(var.base_path, "/") && !endswith(var.base_path, "/")
    error_message = "base_path must start with one slash and must not end with a slash."
  }
}

variable "backend_service_name" {
  type = string
}

variable "frontend_service_name" {
  type = string
}

variable "iap_members" {
  type = set(string)

  validation {
    condition = (
      length(var.iap_members) > 0 &&
      alltrue([for member in var.iap_members : startswith(member, "user:")])
    )
    error_message = "iap_members must contain at least one explicit user principal and no broad audience."
  }
}

variable "iap_oauth_client_id" {
  type        = string
  description = "Non-secret Google OAuth web client ID used by both IAP backend services."

  validation {
    condition     = can(regex("^[0-9]+-[a-z0-9]+\\.apps\\.googleusercontent\\.com$", var.iap_oauth_client_id))
    error_message = "iap_oauth_client_id must be a Google OAuth web client ID."
  }
}

variable "iap_oauth_client_secret" {
  type        = string
  sensitive   = true
  ephemeral   = true
  description = "Ephemeral OAuth client secret passed only to write-only provider fields."
}

variable "iap_oauth_configuration_version" {
  type        = number
  description = "Monotonic numeric Secret Manager version used to trigger write-only IAP updates."

  validation {
    condition     = var.iap_oauth_configuration_version >= 1
    error_message = "iap_oauth_configuration_version must be positive."
  }
}
