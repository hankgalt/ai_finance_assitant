locals {
  service_accounts = {
    runtime   = "aifa-stg-runtime"
    migration = "aifa-stg-migration"
    retention = "aifa-stg-retention"
  }

  secret_ids = toset([
    "postgres-runtime-dsn",
    "postgres-migration-dsn",
    "postgres-retention-dsn",
    "qdrant-runtime-api-key",
  ])

  identity_roles = {
    runtime_cloudsql_client = {
      identity = "runtime"
      role     = "roles/cloudsql.client"
    }
    runtime_cloudsql_instance_user = {
      identity = "runtime"
      role     = "roles/cloudsql.instanceUser"
    }
    migration_cloudsql_client = {
      identity = "migration"
      role     = "roles/cloudsql.client"
    }
    migration_cloudsql_instance_user = {
      identity = "migration"
      role     = "roles/cloudsql.instanceUser"
    }
    retention_cloudsql_client = {
      identity = "retention"
      role     = "roles/cloudsql.client"
    }
    retention_cloudsql_instance_user = {
      identity = "retention"
      role     = "roles/cloudsql.instanceUser"
    }
  }

  secret_access = {
    runtime_postgres = {
      secret   = "postgres-runtime-dsn"
      identity = "runtime"
    }
    runtime_qdrant = {
      secret   = "qdrant-runtime-api-key"
      identity = "runtime"
    }
    migration_postgres = {
      secret   = "postgres-migration-dsn"
      identity = "migration"
    }
    retention_postgres = {
      secret   = "postgres-retention-dsn"
      identity = "retention"
    }
  }
}

resource "google_service_account" "workload" {
  for_each = local.service_accounts

  project         = var.project_id
  account_id      = each.value
  display_name    = "Finance Assistant staging ${each.key}"
  description     = "Least-privilege staging identity for ${each.key} operations."
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "workload_roles" {
  for_each = local.identity_roles

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.workload[each.value.identity].email}"
}

module "managed_state" {
  source = "../../modules/managed_state"

  project_id                      = var.project_id
  region                          = var.region
  environment                     = "staging"
  network_cidr                    = "10.30.0.0/24"
  private_service_prefix_length   = 16
  tier                            = "db-f1-micro"
  disk_size_gib                   = 10
  disk_autoresize_limit_gib       = 20
  retained_backups                = 7
  transaction_log_retention_days  = 3
  deletion_protection             = true
  retain_backups_on_delete        = true
  runtime_service_account_email   = google_service_account.workload["runtime"].email
  migration_service_account_email = google_service_account.workload["migration"].email
  retention_service_account_email = google_service_account.workload["retention"].email
}

resource "google_secret_manager_regional_secret" "staging" {
  for_each = local.secret_ids

  project             = var.project_id
  location            = "us-west1"
  secret_id           = "aifa-staging-${each.value}"
  deletion_protection = true
  deletion_policy     = "ABANDON"

  labels = {
    application = "finance-assistant"
    environment = "staging"
    managed-by  = "terraform"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_regional_secret_iam_member" "access" {
  for_each = local.secret_access

  project   = var.project_id
  location  = "us-west1"
  secret_id = google_secret_manager_regional_secret.staging[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload[each.value.identity].email}"
}
