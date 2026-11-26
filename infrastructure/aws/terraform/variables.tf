variable "aws_region" {
  type    = string
  default = "ap-south-2"
}
variable "project" {
  type    = string
  default = "my-ai-assistant"
}
variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}
variable "db_name" {
  type    = string
  default = "assistant"
}
variable "db_username" {
  type    = string
  default = "assistant_admin"
}
variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS. Leave empty to omit the listener until configured."
  default     = ""
}
