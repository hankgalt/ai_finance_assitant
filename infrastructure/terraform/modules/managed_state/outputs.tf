output "network_id" {
  value = google_compute_network.private.id
}

output "subnetwork_id" {
  value = google_compute_subnetwork.private.id
}

output "instance_name" {
  value = google_sql_database_instance.postgres.name
}

output "instance_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "private_ip_address" {
  value = google_sql_database_instance.postgres.private_ip_address
}

output "database_name" {
  value = google_sql_database.application.name
}
