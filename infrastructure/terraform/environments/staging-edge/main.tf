locals {
  environment           = "staging"
  oauth_secret_id       = "aifa-staging-iap-oauth-client-secret"
  backend_service_name  = "aifa-staging-backend"
  frontend_service_name = "aifa-staging-frontend"
}

# The payload is available only while Terraform evaluates write-only provider
# arguments. It is omitted from the saved plan and remote state.
ephemeral "google_secret_manager_secret_version" "iap_oauth" {
  project = var.project_id
  secret  = local.oauth_secret_id
  version = var.iap_oauth_secret_version
}

module "private_edge" {
  source = "../../modules/private_edge"

  providers = {
    google      = google
    google-beta = google-beta
  }

  project_id                      = var.project_id
  project_number                  = var.project_number
  region                          = var.region
  environment                     = local.environment
  domain                          = "apps.comfforts.com"
  base_path                       = "/finance_assistant"
  backend_service_name            = local.backend_service_name
  frontend_service_name           = local.frontend_service_name
  iap_members                     = ["user:vtalwar.w@comfforts.com"]
  iap_oauth_client_id             = var.iap_oauth_client_id
  iap_oauth_client_secret         = ephemeral.google_secret_manager_secret_version.iap_oauth.secret_data
  iap_oauth_configuration_version = tonumber(var.iap_oauth_secret_version)
}
