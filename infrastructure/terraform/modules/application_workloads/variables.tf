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

variable "provider_mode" {
  type        = string
  default     = "credential_free"
  description = "Credential-free or owner-only approved live provider bundle."

  validation {
    condition     = contains(["credential_free", "live"], var.provider_mode)
    error_message = "provider_mode must be credential_free or live."
  }
}

variable "openai_secret_id" {
  type        = string
  default     = ""
  description = "Secret Manager ID for the OpenAI API key when live mode is selected."

  validation {
    condition     = var.provider_mode == "credential_free" || length(trimspace(var.openai_secret_id)) > 0
    error_message = "openai_secret_id is required in live mode."
  }
}

variable "openai_secret_version" {
  type        = string
  default     = "0"
  description = "Enabled numeric Secret Manager version for the OpenAI API key."

  validation {
    condition = var.provider_mode == "credential_free" || can(regex(
      "^[1-9][0-9]*$",
      var.openai_secret_version,
    ))
    error_message = "openai_secret_version must be positive and numeric in live mode."
  }
}

variable "massive_secret_id" {
  type        = string
  default     = ""
  description = "Secret Manager ID for the Massive API key when live mode is selected."

  validation {
    condition     = var.provider_mode == "credential_free" || length(trimspace(var.massive_secret_id)) > 0
    error_message = "massive_secret_id is required in live mode."
  }
}

variable "massive_secret_version" {
  type        = string
  default     = "0"
  description = "Enabled numeric Secret Manager version for the Massive API key."

  validation {
    condition = var.provider_mode == "credential_free" || can(regex(
      "^[1-9][0-9]*$",
      var.massive_secret_version,
    ))
    error_message = "massive_secret_version must be positive and numeric in live mode."
  }
}

variable "tavily_secret_id" {
  type        = string
  default     = ""
  description = "Secret Manager ID for the Tavily API key when live mode is selected."

  validation {
    condition     = var.provider_mode == "credential_free" || length(trimspace(var.tavily_secret_id)) > 0
    error_message = "tavily_secret_id is required in live mode."
  }
}

variable "tavily_secret_version" {
  type        = string
  default     = "0"
  description = "Enabled numeric Secret Manager version for the Tavily API key."

  validation {
    condition = var.provider_mode == "credential_free" || can(regex(
      "^[1-9][0-9]*$",
      var.tavily_secret_version,
    ))
    error_message = "tavily_secret_version must be positive and numeric in live mode."
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
