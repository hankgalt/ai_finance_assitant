variable "project_id" {
  type    = string
  default = "comfforts-369117"
}

variable "project_number" {
  type    = string
  default = "730340912967"
}

variable "region" {
  type    = string
  default = "us-west1"
}

variable "iap_oauth_client_id" {
  type        = string
  description = "Non-secret custom External OAuth web client ID."

  validation {
    condition     = can(regex("^[0-9]+-[a-z0-9]+\\.apps\\.googleusercontent\\.com$", var.iap_oauth_client_id))
    error_message = "iap_oauth_client_id must be a Google OAuth web client ID."
  }
}

variable "iap_oauth_secret_version" {
  type        = string
  description = "Enabled numeric version of aifa-staging-iap-oauth-client-secret."

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.iap_oauth_secret_version))
    error_message = "iap_oauth_secret_version must be a positive numeric version, never latest."
  }
}
