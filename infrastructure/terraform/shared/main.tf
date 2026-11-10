locals {
  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "sts.googleapis.com",
  ])

  state_buckets = {
    shared     = "${var.project_id}-aifa-tf-bootstrap"
    staging    = "${var.project_id}-aifa-tf-staging"
    production = "${var.project_id}-aifa-tf-production"
  }
}

module "project_services" {
  source = "../modules/project_services"

  project_id = var.project_id
  services   = local.required_services
}

resource "google_artifact_registry_repository" "containers" {
  project         = var.project_id
  location        = var.region
  repository_id   = "aifa-containers"
  description     = "Immutable Finance Assistant deployment images."
  format          = "DOCKER"
  deletion_policy = "ABANDON"

  docker_config {
    immutable_tags = true
  }

  labels = {
    application = "finance-assistant"
    capability  = "delivery"
    managed-by  = "terraform"
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [module.project_services]
}

module "staging_identity" {
  source = "../modules/delivery_identity"

  project_id          = var.project_id
  environment         = "staging"
  pool_id             = "aifa-stg-github"
  provider_id         = "github"
  service_account_id  = "aifa-staging-deploy"
  repository          = var.repository
  repository_id       = "1435001816"
  repository_owner_id = "2118128"
  ref                 = "refs/heads/main"
  roles = [
    "roles/viewer",
    "roles/serviceusage.serviceUsageConsumer",
  ]

  depends_on = [module.project_services]
}

module "production_identity" {
  source = "../modules/delivery_identity"

  project_id          = var.project_id
  environment         = "production"
  pool_id             = "aifa-prod-github"
  provider_id         = "github"
  service_account_id  = "aifa-production-deploy"
  repository          = var.repository
  repository_id       = "1435001816"
  repository_owner_id = "2118128"
  ref                 = "refs/heads/main"
  roles = [
    "roles/viewer",
    "roles/serviceusage.serviceUsageConsumer",
  ]

  depends_on = [module.project_services]
}

resource "google_storage_bucket_iam_member" "delivery_state" {
  for_each = {
    shared = {
      bucket = local.state_buckets.shared
      member = module.staging_identity.service_account_email
    }
    staging = {
      bucket = local.state_buckets.staging
      member = module.staging_identity.service_account_email
    }
    production = {
      bucket = local.state_buckets.production
      member = module.production_identity.service_account_email
    }
  }

  bucket = each.value.bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${each.value.member}"
}

resource "google_billing_budget" "private_demo" {
  billing_account = var.billing_account_id
  display_name    = "Finance Assistant private demo"

  budget_filter {
    projects = ["projects/${var.project_number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = "100"
    }
  }

  dynamic "threshold_rules" {
    for_each = toset([0.5, 0.8, 1.0])
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  depends_on = [module.project_services]
}
