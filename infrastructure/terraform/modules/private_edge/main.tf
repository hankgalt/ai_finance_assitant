locals {
  prefix                     = "aifa-${var.environment}"
  iap_service_agent          = "serviceAccount:service-${var.project_number}@gcp-sa-iap.iam.gserviceaccount.com"
  backend_api_exact_path     = "${var.base_path}/api"
  backend_api_prefix_path    = "${var.base_path}/api/*"
  frontend_application_paths = [var.base_path, "${var.base_path}/*"]
}

# Materialize the Google-managed IAP service identity before granting it the
# only Cloud Run invocation path. The resource is a no-op on destroy.
resource "google_project_service_identity" "iap" {
  provider = google-beta

  project = var.project_id
  service = "iap.googleapis.com"
}

resource "google_compute_region_network_endpoint_group" "serverless" {
  for_each = {
    backend  = var.backend_service_name
    frontend = var.frontend_service_name
  }

  project               = var.project_id
  region                = var.region
  name                  = "${local.prefix}-${each.key}-neg"
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = each.value
  }
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  for_each = {
    backend  = var.backend_service_name
    frontend = var.frontend_service_name
  }

  project  = var.project_id
  location = var.region
  name     = each.value
  role     = "roles/run.invoker"
  member   = local.iap_service_agent

  depends_on = [google_project_service_identity.iap]
}

resource "google_compute_backend_service" "application" {
  for_each = {
    backend = {
      neg_id      = google_compute_region_network_endpoint_group.serverless["backend"].id
      timeout_sec = 300
    }
    frontend = {
      neg_id      = google_compute_region_network_endpoint_group.serverless["frontend"].id
      timeout_sec = 60
    }
  }

  project               = var.project_id
  name                  = "${local.prefix}-${each.key}-edge"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = each.value.timeout_sec
  enable_cdn            = false

  backend {
    group = each.value.neg_id
  }

  # Write-only fields keep the custom External OAuth credential out of plans
  # and state. The numeric version deliberately triggers reviewed rotation.
  iap {
    enabled                         = true
    oauth2_client_id_wo             = var.iap_oauth_client_id
    oauth2_client_id_wo_version     = var.iap_oauth_configuration_version
    oauth2_client_secret_wo         = var.iap_oauth_client_secret
    oauth2_client_secret_wo_version = var.iap_oauth_configuration_version
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }

  depends_on = [google_cloud_run_v2_service_iam_member.iap_invoker]
}

resource "google_iap_web_backend_service_iam_member" "application_access" {
  for_each = {
    for pair in setproduct(keys(google_compute_backend_service.application), var.iap_members) :
    "${pair[0]}:${pair[1]}" => {
      backend = pair[0]
      member  = pair[1]
    }
  }

  project             = var.project_id
  web_backend_service = google_compute_backend_service.application[each.value.backend].name
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value.member
}

resource "google_compute_global_address" "application" {
  project      = var.project_id
  name         = "${local.prefix}-edge-ip"
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
}

resource "google_compute_managed_ssl_certificate" "application" {
  project = var.project_id
  name    = "${local.prefix}-edge-certificate"

  managed {
    domains = [var.domain]
  }
}

# The frontend is the fail-closed default. It is itself IAP protected, and its
# Nginx policy returns 404 outside /finance_assistant instead of proxying API.
resource "google_compute_url_map" "https" {
  project         = var.project_id
  name            = "${local.prefix}-https"
  default_service = google_compute_backend_service.application["frontend"].id

  host_rule {
    hosts        = [var.domain]
    path_matcher = "finance-assistant"
  }

  path_matcher {
    name            = "finance-assistant"
    default_service = google_compute_backend_service.application["frontend"].id

    # The public base path is a browser contract. FastAPI intentionally keeps
    # its origin routes at /api so probes and local proxying use one origin
    # contract; the edge removes only /finance_assistant from API requests.
    path_rule {
      paths   = [local.backend_api_exact_path]
      service = google_compute_backend_service.application["backend"].id

      route_action {
        url_rewrite {
          path_prefix_rewrite = "/api"
        }
      }
    }

    path_rule {
      paths   = [local.backend_api_prefix_path]
      service = google_compute_backend_service.application["backend"].id

      route_action {
        url_rewrite {
          path_prefix_rewrite = "/api/"
        }
      }
    }

    path_rule {
      paths   = local.frontend_application_paths
      service = google_compute_backend_service.application["frontend"].id
    }
  }
}

resource "google_compute_target_https_proxy" "application" {
  project          = var.project_id
  name             = "${local.prefix}-https"
  url_map          = google_compute_url_map.https.id
  ssl_certificates = [google_compute_managed_ssl_certificate.application.id]
}

resource "google_compute_global_forwarding_rule" "https" {
  project               = var.project_id
  name                  = "${local.prefix}-https"
  target                = google_compute_target_https_proxy.application.id
  ip_address            = google_compute_global_address.application.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  network_tier          = "PREMIUM"
}

resource "google_compute_url_map" "http_redirect" {
  project = var.project_id
  name    = "${local.prefix}-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "PERMANENT_REDIRECT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  project = var.project_id
  name    = "${local.prefix}-http-redirect"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http" {
  project               = var.project_id
  name                  = "${local.prefix}-http"
  target                = google_compute_target_http_proxy.redirect.id
  ip_address            = google_compute_global_address.application.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  network_tier          = "PREMIUM"
}
