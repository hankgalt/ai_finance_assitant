variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "network_cidr" {
  type = string
}

variable "private_service_prefix_length" {
  type    = number
  default = 16
}

variable "tier" {
  type = string
}

variable "disk_size_gib" {
  type = number
}

variable "disk_autoresize_limit_gib" {
  type = number
}

variable "retained_backups" {
  type = number
}

variable "transaction_log_retention_days" {
  type = number
}

variable "deletion_protection" {
  type = bool
}

variable "retain_backups_on_delete" {
  type = bool
}

variable "runtime_service_account_email" {
  type = string
}

variable "migration_service_account_email" {
  type = string
}

variable "retention_service_account_email" {
  type = string
}
