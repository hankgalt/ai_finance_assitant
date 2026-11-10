variable "project_id" {
  description = "Google Cloud project that owns the private-demo infrastructure."
  type        = string
  default     = "comfforts-369117"
}

variable "region" {
  description = "Owner-approved primary Google Cloud region."
  type        = string
  default     = "us-west1"
}
