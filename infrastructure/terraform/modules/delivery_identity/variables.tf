variable "project_id" {
  type = string
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production"
  }
}

variable "pool_id" {
  type = string
}

variable "provider_id" {
  type = string
}

variable "service_account_id" {
  type = string
}

variable "repository" {
  type = string
}

variable "repository_id" {
  type = string
}

variable "repository_owner_id" {
  type = string
}

variable "ref" {
  type = string
}

variable "roles" {
  type = set(string)
}
