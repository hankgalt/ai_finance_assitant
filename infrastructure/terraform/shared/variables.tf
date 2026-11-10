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

variable "billing_account_id" {
  description = "Bare billing account ID supplied at plan/apply time; it is not a credential."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "billing_account_id must be a bare XXXXXX-XXXXXX-XXXXXX billing account ID."
  }
}

variable "repository" {
  type    = string
  default = "hankgalt/ai_finance_assitant"
}

variable "repository_id" {
  type    = string
  default = "1435001816"
}

variable "repository_owner_id" {
  type    = string
  default = "2118128"
}

variable "ref" {
  type    = string
  default = "refs/heads/main"
}
