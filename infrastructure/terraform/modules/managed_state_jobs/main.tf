locals {
  jobs = {
    migration = {
      name     = "migrate"
      identity = "migration"
      command = [
        "python",
        "-m",
        "ai_finance_assistant.persistence.cli",
        "migrate",
      ]
    }
    qualification = {
      name     = "qualify"
      identity = "runtime"
      command = [
        "python",
        "-m",
        "ai_finance_assistant.persistence.qualification",
        "prepare",
        "--qualification-id",
        "staging-cloud-sql-v1",
      ]
    }
    retention = {
      name     = "retention"
      identity = "retention"
      command = [
        "python",
        "-m",
        "ai_finance_assistant.persistence.cli",
        "retention",
      ]
    }
  }

  database_usernames = {
    for identity, email in var.service_account_emails :
    identity => trimsuffix(email, ".gserviceaccount.com")
  }

  database_usernames_uri_encoded = {
    for identity, username in local.database_usernames :
    identity => replace(username, "@", "%40")
  }
}

resource "google_cloud_run_v2_job" "operator" {
  for_each = local.jobs

  project             = var.project_id
  location            = var.region
  name                = "aifa-${var.environment}-${each.value.name}"
  deletion_protection = false

  labels = {
    application = "finance-assistant"
    capability  = "managed-state"
    environment = var.environment
    managed-by  = "terraform"
    operation   = each.key
  }

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account       = var.service_account_emails[each.value.identity]
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      max_retries           = 0
      timeout               = "900s"

      containers {
        name       = "operator"
        image      = var.backend_image
        command    = [each.value.command[0]]
        args       = slice(each.value.command, 1, length(each.value.command))
        depends_on = ["cloud-sql-proxy"]

        env {
          name  = "AIFA_STORAGE_BACKEND"
          value = "postgres"
        }

        env {
          name = "AIFA_POSTGRES_DSN"
          value = join("", [
            "postgresql://",
            local.database_usernames_uri_encoded[each.value.identity],
            "@127.0.0.1:5432/",
            var.database_name,
            "?sslmode=disable",
          ])
        }

        env {
          name  = "AIFA_WORKFLOW_ID"
          value = "finance-assistant"
        }

        env {
          name  = "AIFA_STORAGE_EXPECTED_SCHEMA_VERSION"
          value = "4"
        }

        env {
          name  = "AIFA_POSTGRES_RUNTIME_ROLE"
          value = local.database_usernames.runtime
        }

        env {
          name  = "AIFA_POSTGRES_RETENTION_ROLE"
          value = local.database_usernames.retention
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
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

}
