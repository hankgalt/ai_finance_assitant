locals {
  immutable_repository = "${split("/", var.repository)[0]}@${var.repository_owner_id}/${split("/", var.repository)[1]}@${var.repository_id}"
}

resource "google_service_account" "github" {
  project         = var.project_id
  account_id      = var.service_account_id
  display_name    = "Finance Assistant ${var.environment} GitHub identity"
  description     = "Keyless ${var.environment} identity restricted to the approved GitHub repository."
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = "AIFA ${var.environment} GitHub"
  description               = "GitHub Actions identity pool for Finance Assistant ${var.environment}."
  deletion_policy           = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = "AIFA ${var.environment} GitHub provider"
  deletion_policy                    = "ABANDON"

  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ref"                 = "assertion.ref"
  }

  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.repository_id}'",
    "assertion.repository_owner_id == '${var.repository_owner_id}'",
    "assertion.ref == '${var.ref}'",
    "assertion.sub == 'repo:${local.immutable_repository}:environment:${var.environment}'",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com/"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account_iam_member" "github_impersonation" {
  service_account_id = google_service_account.github.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.repository_id}"
}

resource "google_project_iam_member" "read_only_roles" {
  for_each = var.roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github.email}"
}
