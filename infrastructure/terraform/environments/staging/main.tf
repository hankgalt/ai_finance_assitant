locals {
  service_accounts = {
    frontend  = "aifa-stg-frontend"
    runtime   = "aifa-stg-runtime"
    migration = "aifa-stg-migration"
    retention = "aifa-stg-retention"
  }

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
  live_provider_secrets = {
    openai  = "aifa-staging-openai-api-key"
    massive = "aifa-staging-massive-api-key"
    tavily  = "aifa-staging-tavily-api-key"
  }
}

resource "google_service_account" "workload" {
  for_each = local.service_accounts

  project         = var.project_id
  account_id      = each.value
  display_name    = "Finance Assistant staging ${each.key}"
  description     = "Least-privilege staging identity for ${each.key} operations."
  deletion_policy = "DELETE"
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
  tier                            = var.database_tier
  disk_size_gib                   = 10
  disk_autoresize_limit_gib       = 20
  deletion_protection             = false
  retain_backups_on_delete        = false
  runtime_service_account_email   = google_service_account.workload["runtime"].email
  migration_service_account_email = google_service_account.workload["migration"].email
  retention_service_account_email = google_service_account.workload["retention"].email
}

module "managed_state_jobs" {
  source = "../../modules/managed_state_jobs"

  project_id               = var.project_id
  region                   = var.region
  environment              = "staging"
  backend_image            = var.backend_image
  cloud_sql_proxy_image    = "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/cloud-sql-proxy@sha256:7d156a5c466e31596afd6c8ed134f19c207a297418392fdad2686524ca4e7a3c"
  network_id               = module.managed_state.network_id
  subnetwork_id            = module.managed_state.subnetwork_id
  instance_connection_name = module.managed_state.instance_connection_name
  database_name            = module.managed_state.database_name
  service_account_emails = {
    runtime   = google_service_account.workload["runtime"].email
    migration = google_service_account.workload["migration"].email
    retention = google_service_account.workload["retention"].email
  }
}

resource "google_secret_manager_secret" "qdrant_runtime" {
  project             = var.project_id
  secret_id           = "aifa-staging-qdrant-runtime-api-key"
  deletion_protection = false

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    application = "finance-assistant"
    capability  = "application-workload"
    environment = "staging"
    managed-by  = "terraform"
  }
}

resource "google_secret_manager_secret" "qdrant_release" {
  project             = var.project_id
  secret_id           = "aifa-staging-qdrant-release-api-key"
  deletion_protection = false

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    application = "finance-assistant"
    capability  = "knowledge-release"
    environment = "staging"
    managed-by  = "terraform"
  }
}

resource "google_secret_manager_secret_iam_member" "runtime_qdrant" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.qdrant_runtime.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload["runtime"].email}"
}

resource "google_secret_manager_secret" "live_provider" {
  for_each = var.live_provider_secrets_enabled ? local.live_provider_secrets : {}

  project             = var.project_id
  secret_id           = each.value
  deletion_protection = false

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    application = "finance-assistant"
    capability  = "live-provider"
    environment = "staging"
    managed-by  = "terraform"
  }
}

resource "google_secret_manager_secret_iam_member" "runtime_live_provider" {
  for_each = google_secret_manager_secret.live_provider

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload["runtime"].email}"
}
