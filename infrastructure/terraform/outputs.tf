output "cloudfront_domain" {
  description = "Public entry point for AEGIS MissionOS"
  value       = aws_cloudfront_distribution.web.domain_name
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "rds_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "web_bucket" {
  value = aws_s3_bucket.web.id
}

output "migrate_task_definition" {
  value = aws_ecs_task_definition.migrate.family
}

# --- CD wiring: set these as GitHub Actions repository variables ---
output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.api.name
}

output "private_subnet_ids" {
  value = join(",", aws_subnet.private[*].id)
}

output "api_security_group_id" {
  value = aws_security_group.api.id
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.web.id
}
