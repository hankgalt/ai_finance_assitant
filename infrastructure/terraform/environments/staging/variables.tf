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
