locals {
  runtime_database_username = trimsuffix(var.runtime_service_account_email, ".gserviceaccount.com")
  runtime_database_uri_user = replace(
    local.runtime_database_username,
    "@",
    "%40",
  )
  backend_environment = {
    AIFA_MODE                            = "production"
    AIFA_HOST                            = "0.0.0.0"
    AIFA_PORT                            = "8080"
    AIFA_BASE_PATH                       = "/finance_assistant"
    AIFA_IDENTITY_MODE                   = "iap"
    AIFA_IAP_AUDIENCE                    = var.iap_audience
    AIFA_IAP_OWNER_EMAIL                 = var.iap_owner_email
    AIFA_IAP_VIEWER_EMAILS               = "[]"
    AIFA_CORS_ORIGINS                    = jsonencode(["https://apps.comfforts.com"])
    AIFA_QDRANT_URL                      = var.qdrant_url
    AIFA_PROVIDER_MODE                   = "credential_free"
    AIFA_MODEL_MODE                      = "credential_free"
    AIFA_STORAGE_BACKEND                 = "postgres"
    AIFA_POSTGRES_DSN                    = "postgresql://${local.runtime_database_uri_user}@127.0.0.1:5432/${var.database_name}?sslmode=disable"
    AIFA_POSTGRES_POOL_MIN_SIZE          = "1"
    AIFA_POSTGRES_POOL_MAX_SIZE          = "2"
    AIFA_STORAGE_MIGRATION_MODE          = "verify_only"
    AIFA_RETENTION_EXECUTION_MODE        = "scheduled"
    AIFA_STORAGE_EXPECTED_SCHEMA_VERSION = "4"
    AIFA_RESPONSE_CACHE_ADAPTER          = "disabled"
    AIFA_WORKFLOW_ID                     = "finance-assistant"
    AIFA_OTEL_SERVICE_NAME               = "finance-assistant-backend-${var.environment}"
    AIFA_OTEL_EXPORT_ENABLED             = "false"
    AIFA_LANGSMITH_TRACING_ENABLED       = "false"
    AIFA_LANGSMITH_PROJECT               = "finance-assistant-${var.environment}"
  }
}

resource "google_cloud_run_v2_service" "backend" {
  project              = var.project_id
  location             = var.region
  name                 = "aifa-${var.environment}-backend"
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  default_uri_disabled = true
  launch_stage         = "BETA"
  deletion_protection  = false

  labels = {
    application = "finance-assistant"
    capability  = "application-workload"
    environment = var.environment
    managed-by  = "terraform"
    tier        = "backend"
  }

  template {
    service_account                  = var.runtime_service_account_email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "300s"
    max_instance_request_concurrency = 4

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      name       = "backend"
      image      = var.backend_image
      depends_on = ["cloud-sql-proxy"]

      ports {
        name           = "http1"
        container_port = 8080
      }

      dynamic "env" {
        for_each = local.backend_environment
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name = "AIFA_QDRANT_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.qdrant_secret_id
            version = var.qdrant_secret_version
          }
        }
      }

      startup_probe {
        initial_delay_seconds = 2
        timeout_seconds       = 2
        period_seconds        = 5
        failure_threshold     = 24

        http_get {
          path = "/api/health/live"
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 10
        timeout_seconds       = 2
        period_seconds        = 10
        failure_threshold     = 3

        http_get {
          path = "/api/health/live"
          port = 8080
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
    }

    containers {
      name  = "cloud-sql-proxy"
      image = var.cloud_sql_proxy_image
      args = [
        "--structured-logs",
        "--private-ip",
        "--auto-iam-authn",
        "--address=0.0.0.0",
        "--port=5432",
        var.instance_connection_name,
      ]

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 1
        period_seconds        = 2
        failure_threshold     = 15

        tcp_socket {
          port = 5432
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"

      network_interfaces {
        network    = var.network_id
        subnetwork = var.subnetwork_id
      }
    }
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  project              = var.project_id
  location             = var.region
  name                 = "aifa-${var.environment}-frontend"
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  default_uri_disabled = true
  launch_stage         = "BETA"
  deletion_protection  = false

  labels = {
    application = "finance-assistant"
    capability  = "application-workload"
    environment = var.environment
    managed-by  = "terraform"
    tier        = "frontend"
  }

  template {
    service_account                  = var.frontend_service_account_email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "60s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      name  = "frontend"
      image = var.frontend_image

      ports {
        name           = "http1"
        container_port = 8080
      }

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 2
        period_seconds        = 5
        failure_threshold     = 12

        http_get {
          path = "/finance_assistant/healthz"
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 2
        period_seconds        = 10
        failure_threshold     = 3

        http_get {
          path = "/finance_assistant/healthz"
          port = 8080
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
    }
  }
}
