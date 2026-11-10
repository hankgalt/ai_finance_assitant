resource "google_compute_network" "private" {
  project                 = var.project_id
  name                    = "aifa-${var.environment}"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "private" {
  project                  = var.project_id
  name                     = "aifa-${var.environment}-${var.region}"
  region                   = var.region
  network                  = google_compute_network.private.id
  ip_cidr_range            = var.network_cidr
  private_ip_google_access = true
}

resource "google_compute_global_address" "private_services" {
  project       = var.project_id
  name          = "aifa-${var.environment}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_prefix_length
  network       = google_compute_network.private.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.private.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

resource "google_sql_database_instance" "postgres" {
  project             = var.project_id
  name                = "aifa-${var.environment}-postgres"
  region              = var.region
  database_version    = "POSTGRES_17"
  deletion_protection = var.deletion_protection

  settings {
    tier                        = var.tier
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = var.disk_size_gib
    disk_autoresize             = true
    disk_autoresize_limit       = var.disk_autoresize_limit_gib
    deletion_protection_enabled = var.deletion_protection
    retain_backups_on_delete    = var.retain_backups_on_delete

    backup_configuration {
      enabled                        = true
      start_time                     = "10:00"
      location                       = var.region
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = var.transaction_log_retention_days

      backup_retention_settings {
        retained_backups = var.retained_backups
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.private.id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "ENCRYPTED_ONLY"
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    final_backup_config {
      enabled        = true
      retention_days = 7
    }

    user_labels = {
      application = "finance-assistant"
      environment = var.environment
      managed-by  = "terraform"
    }
  }

  depends_on = [google_service_networking_connection.private_services]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_database" "application" {
  project         = var.project_id
  name            = "aifa"
  instance        = google_sql_database_instance.postgres.name
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_user" "runtime" {
  project         = var.project_id
  name            = trimsuffix(var.runtime_service_account_email, ".gserviceaccount.com")
  instance        = google_sql_database_instance.postgres.name
  type            = "CLOUD_IAM_SERVICE_ACCOUNT"
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_user" "migration" {
  project         = var.project_id
  name            = trimsuffix(var.migration_service_account_email, ".gserviceaccount.com")
  instance        = google_sql_database_instance.postgres.name
  type            = "CLOUD_IAM_SERVICE_ACCOUNT"
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_user" "retention" {
  project         = var.project_id
  name            = trimsuffix(var.retention_service_account_email, ".gserviceaccount.com")
  instance        = google_sql_database_instance.postgres.name
  type            = "CLOUD_IAM_SERVICE_ACCOUNT"
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}
