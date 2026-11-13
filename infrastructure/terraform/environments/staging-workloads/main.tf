locals {
  environment = "staging"
  service_accounts = {
    runtime  = "aifa-stg-runtime@${var.project_id}.iam.gserviceaccount.com"
    frontend = "aifa-stg-frontend@${var.project_id}.iam.gserviceaccount.com"
  }
}

module "application_workloads" {
  source = "../../modules/application_workloads"

  project_id                     = var.project_id
  region                         = var.region
  environment                    = local.environment
  backend_image                  = var.backend_image
  frontend_image                 = var.frontend_image
  cloud_sql_proxy_image          = "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/cloud-sql-proxy@sha256:7d156a5c466e31596afd6c8ed134f19c207a297418392fdad2686524ca4e7a3c"
  network_id                     = "projects/${var.project_id}/global/networks/aifa-staging"
  subnetwork_id                  = "projects/${var.project_id}/regions/${var.region}/subnetworks/aifa-staging-${var.region}"
  instance_connection_name       = "${var.project_id}:${var.region}:aifa-staging-postgres"
  database_name                  = "aifa"
  runtime_service_account_email  = local.service_accounts.runtime
  frontend_service_account_email = local.service_accounts.frontend
  qdrant_url                     = "https://57c4d676-360a-4f1a-aad3-92d775292673.us-central1-0.gcp.cloud.qdrant.io"
  qdrant_secret_id               = "aifa-staging-qdrant-runtime-api-key"
  qdrant_secret_version          = var.qdrant_secret_version
  provider_mode                  = var.provider_mode
  openai_secret_id               = "aifa-staging-openai-api-key"
  openai_secret_version          = var.openai_secret_version
  massive_secret_id              = "aifa-staging-massive-api-key"
  massive_secret_version         = var.massive_secret_version
  tavily_secret_id               = "aifa-staging-tavily-api-key"
  tavily_secret_version          = var.tavily_secret_version
  iap_audience                   = var.iap_audience
  iap_owner_email                = "vtalwar.w@comfforts.com"
}
