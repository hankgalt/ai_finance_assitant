output "state_buckets" {
  description = "Environment-separated, versioned Terraform state buckets."
  value       = { for key, bucket in google_storage_bucket.terraform_state : key => bucket.name }
}
