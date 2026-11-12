variable "project_id" {
  type    = string
  default = "comfforts-369117"
}

variable "region" {
  type    = string
  default = "us-west1"
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

variable "frontend_image" {
  type        = string
  description = "Qualified frontend image pinned by immutable digest."

  validation {
    condition = (
      startswith(
        var.frontend_image,
        "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"
      ) && strcontains(var.frontend_image, "@sha256:")
    )
    error_message = "frontend_image must use the approved us-west1 Artifact Registry and be pinned by sha256 digest."
  }
}

variable "qdrant_secret_version" {
  type        = string
  description = "Enabled numeric version of aifa-staging-qdrant-runtime-api-key."

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.qdrant_secret_version))
    error_message = "qdrant_secret_version must be a positive numeric version, never latest."
  }
}

variable "iap_audience" {
  type        = string
  description = "Exact IAP backend-service JWT audience; backendServices/0 is the pre-edge fail-closed sentinel."
  default     = "/projects/730340912967/global/backendServices/0"

  validation {
    condition = can(regex(
      "^/projects/730340912967/global/backendServices/[0-9]+$",
      var.iap_audience,
    ))
    error_message = "iap_audience must be the exact Finance Assistant global backend-service audience."
  }
}
