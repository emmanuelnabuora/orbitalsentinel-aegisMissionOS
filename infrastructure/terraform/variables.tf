variable "region" {
  description = "AWS region. DoD/federal workloads: use AWS GovCloud regions."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "project" {
  type    = string
  default = "aegis"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "api_image" {
  description = "ECR image URI for the API (e.g. <acct>.dkr.ecr.<region>.amazonaws.com/aegis-api:sha)"
  type        = string
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 50
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "acm_certificate_arn" {
  description = "ACM cert for the ALB HTTPS listener. Empty = HTTP-only listener (dev/bootstrap only; never production)."
  type        = string
  default     = ""
}

variable "github_repository" {
  description = "GitHub org/repo allowed to deploy via OIDC (e.g. orbitalsentinel/aegis-missionos)"
  type        = string
  default     = "orbitalsentinel/aegis-missionos"
}

variable "single_nat_gateway" {
  description = "true = one shared NAT (cheaper, dev). false = one NAT per AZ (no cross-AZ egress dependency; production default)."
  type        = bool
  default     = false
}

variable "waf_rate_limit_5min" {
  description = "Requests per 5 minutes per IP before WAF throttles (coarse outer layer)."
  type        = number
  default     = 2000
}

variable "waf_login_rate_limit_5min" {
  description = "Login-path requests per 5 minutes per IP at the edge. The app enforces a much tighter Redis budget behind this."
  type        = number
  default     = 100
}
