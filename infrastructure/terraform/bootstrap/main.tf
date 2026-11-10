locals {
  state_buckets = {
    bootstrap  = "${var.project_id}-aifa-tf-bootstrap"
    staging    = "${var.project_id}-aifa-tf-staging"
    production = "${var.project_id}-aifa-tf-production"
  }
}

resource "google_storage_bucket" "terraform_state" {
  for_each = local.state_buckets

  name                        = each.value
  project                     = var.project_id
  location                    = upper(var.region)
  storage_class               = "STANDARD"
  force_destroy               = false
  deletion_policy             = "ABANDON"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  labels = {
    application = "finance-assistant"
    capability  = "terraform-state"
    environment = each.key
    managed-by  = "terraform"
  }

  lifecycle {
    prevent_destroy = true
  }
}
