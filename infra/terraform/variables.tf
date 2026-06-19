variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'."
  }
}

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.medium"
}

variable "db_password" {
  description = "Master password for RDS (injected from Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "backend_image" {
  description = "ECR image URI for backend container"
  type        = string
}

variable "frontend_image" {
  description = "ECR image URI for frontend container"
  type        = string
}

variable "domain_name" {
  description = "Public domain (e.g. finpilot.example.com)"
  type        = string
  default     = "finpilot.example.com"
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
  default     = ""
}
