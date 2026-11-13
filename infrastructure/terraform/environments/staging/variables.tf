variable "project_id" {
  type    = string
  default = "comfforts-369117"
}

variable "region" {
  type    = string
  default = "us-west1"
}

variable "database_tier" {
  type        = string
  default     = "db-g1-small"
  description = "Cloud SQL tier; the down wizard temporarily preserves the observed live tier while removing deletion guards."

  validation {
    condition     = contains(["db-f1-micro", "db-g1-small"], var.database_tier)
    error_message = "database_tier must be db-f1-micro or db-g1-small for the private-demo lifecycle."
  }
}

variable "backend_image" {
  type        = string
  description = "Qualified backend image pinned by immutable digest."

  validation {
    condition = (
      startswith(
        var.backend_image,
        "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"
      ) && strcontains(var.backend_image, "@sha256:")
    )
    error_message = "backend_image must use the approved us-west1 Artifact Registry and be pinned by sha256 digest."
  }
}

variable "live_provider_secrets_enabled" {
  type        = bool
  default     = false
  description = "Create owner-only live-provider secret metadata and runtime access grants."
}
