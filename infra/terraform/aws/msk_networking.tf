# -------------------------------------------------------------------
# Optional Amazon MSK networking
# -------------------------------------------------------------------
#
# This network exists only when:
#
#   var.enable_msk = true
#
# It is intentionally dedicated to the streaming demonstration.
#
# When enable_msk = false:
#
#   VPC                = absent
#   Internet Gateway   = absent
#   Public subnets     = absent
#   Route table        = absent
#   Security group     = absent
#
# This allows the portfolio environment to retain the persistent
# S3/Unity Catalog infrastructure without paying for unused streaming
# infrastructure.
# -------------------------------------------------------------------


# Availability Zones are required only when MSK is enabled.
data "aws_availability_zones" "available" {
  count = var.enable_msk ? 1 : 0

  state = "available"
}


locals {
  msk_name_prefix = "epip-${var.environment}-msk"
}


# -------------------------------------------------------------------
# Dedicated MSK VPC
# -------------------------------------------------------------------

resource "aws_vpc" "msk" {
  count = var.enable_msk ? 1 : 0

  cidr_block = var.msk_vpc_cidr

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(
    local.common_tags,
    {
      Name    = "${local.msk_name_prefix}-vpc"
      Purpose = "Amazon MSK streaming network"
    }
  )
}


# -------------------------------------------------------------------
# Internet Gateway
# -------------------------------------------------------------------

resource "aws_internet_gateway" "msk" {
  count = var.enable_msk ? 1 : 0

  vpc_id = aws_vpc.msk[0].id

  tags = merge(
    local.common_tags,
    {
      Name    = "${local.msk_name_prefix}-igw"
      Purpose = "Amazon MSK public connectivity"
    }
  )
}


# -------------------------------------------------------------------
# Public MSK subnets
# -------------------------------------------------------------------
#
# Two subnets are provisioned across two Availability Zones.
#
# They are created only when enable_msk = true.
# -------------------------------------------------------------------

resource "aws_subnet" "msk_public" {
  count = var.enable_msk ? 2 : 0

  vpc_id = aws_vpc.msk[0].id

  cidr_block = var.msk_public_subnet_cidrs[count.index]

  availability_zone = (
    data.aws_availability_zones.available[0].names[count.index]
  )

  map_public_ip_on_launch = true

  tags = merge(
    local.common_tags,
    {
      Name = (
        "${local.msk_name_prefix}-public-${count.index + 1}"
      )

      Purpose = "Amazon MSK public broker subnet"
    }
  )
}


# -------------------------------------------------------------------
# Public route table
# -------------------------------------------------------------------

resource "aws_route_table" "msk_public" {
  count = var.enable_msk ? 1 : 0

  vpc_id = aws_vpc.msk[0].id

  route {
    cidr_block = "0.0.0.0/0"

    gateway_id = aws_internet_gateway.msk[0].id
  }

  tags = merge(
    local.common_tags,
    {
      Name    = "${local.msk_name_prefix}-public-rt"
      Purpose = "Amazon MSK public subnet routing"
    }
  )
}


# -------------------------------------------------------------------
# Route table associations
# -------------------------------------------------------------------

resource "aws_route_table_association" "msk_public" {
  count = var.enable_msk ? 2 : 0

  subnet_id = aws_subnet.msk_public[count.index].id

  route_table_id = aws_route_table.msk_public[0].id
}


# -------------------------------------------------------------------
# MSK security group
# -------------------------------------------------------------------
#
# TCP 9198 is used by the public Amazon MSK SASL/IAM endpoint.
#
# No ingress rule is created when:
#
#   msk_public_ingress_cidrs = []
#
# This is intentional and provides a secure default.
# -------------------------------------------------------------------

resource "aws_security_group" "msk" {
  count = var.enable_msk ? 1 : 0

  name_prefix = "${local.msk_name_prefix}-"

  description = (
    "Restricts access to the Enterprise Payments Amazon MSK cluster."
  )

  vpc_id = aws_vpc.msk[0].id

  dynamic "ingress" {
    for_each = (
      length(var.msk_public_ingress_cidrs) > 0
      ? [1]
      : []
    )

    content {
      description = "IAM-authenticated public Kafka clients"

      from_port = 9198
      to_port   = 9198
      protocol  = "tcp"

      cidr_blocks = var.msk_public_ingress_cidrs
    }
  }

  egress {
    description = "Allow broker outbound traffic"

    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  tags = merge(
    local.common_tags,
    {
      Name    = "${local.msk_name_prefix}-sg"
      Purpose = "Amazon MSK broker access control"
    }
  )
}