variable "project" {
  type        = string
  description = "Name of the project"
}

variable "env" {
  type        = string
  description = "Env type: dev, prod, uat, etc."
}

variable "aws_lambda" {
  type = any
  description = "AWS Lambda function configuration"
}