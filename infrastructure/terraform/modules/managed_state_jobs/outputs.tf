output "job_names" {
  value = { for operation, job in google_cloud_run_v2_job.operator : operation => job.name }
}
