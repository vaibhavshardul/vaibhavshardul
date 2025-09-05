locals {
  region = var.aws_lambda.region != "" ? var.aws_lambda.region : data.aws_region.current.region
  account_id = data.aws_caller_identity.current.account_id
}

resource "aws_lambda_layer_version" "main" {
  s3_bucket = var.aws_lambda.s3_existing_package.bucket
  s3_key    = var.aws_lambda.s3_existing_package.layer_key

  layer_name = "${var.aws_lambda.function_name}-layer"
  description = "${var.aws_lambda.function_name} layer for dev environment"

  compatible_runtimes      = [var.aws_lambda.runtime]
  compatible_architectures = ["x86_64"]
}

module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "8.0.1"

  attach_network_policy  = var.aws_lambda.attach_network_policy
  create_package         = var.aws_lambda.create_package
  create_role            = var.aws_lambda.create_role
  description            = var.aws_lambda.description
  function_name          = var.aws_lambda.function_name
  handler                = var.aws_lambda.handler
  runtime                = var.aws_lambda.runtime
  memory_size            = var.aws_lambda.memory_size
  timeout                = var.aws_lambda.timeout
  layers                 = try(
    concat(
      [aws_lambda_layer_version.main.arn], 
      ["arn:aws:lambda:${local.region}:${var.aws_lambda.pandas_account_id}:layer:${var.aws_lambda.layer_pandas_name}"],
      [for layer in split(",", var.aws_lambda.layers) : "arn:aws:lambda:${local.region}:${local.account_id}:layer:${layer}"]),
    []
  )
  lambda_role            = "arn:aws:iam::${local.account_id}:role/${var.aws_lambda.role_name}"
  vpc_security_group_ids = try(split(",", var.aws_lambda.vpc_security_group_ids), [])
  vpc_subnet_ids         = try(split(",", var.aws_lambda.vpc_subnet_ids), [])
  environment_variables  = var.aws_lambda.environment_variables

  region              = var.aws_lambda.region
  s3_existing_package = var.aws_lambda.s3_existing_package
  tags                = var.aws_lambda.tags

  event_source_mapping = [
    {
      event_source_arn = "arn:aws:sqs:${local.region}:${local.account_id}:${var.aws_lambda.sqs_queue_name}"
      enabled          = try(var.aws_lambda.sqs_enabled, false)
      batch_size       = var.aws_lambda.sqs_batch_size
    }
  ]
}
