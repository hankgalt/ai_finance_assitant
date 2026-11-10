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
    condition     = strcontains(var.backend_image, "@sha256:")
    error_message = "backend_image must be pinned by sha256 digest."
  }
}
