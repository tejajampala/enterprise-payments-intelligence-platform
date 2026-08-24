# -------------------------------------------------------------------
# Amazon MSK networking
# -------------------------------------------------------------------
#
# This VPC is intentionally dedicated to the streaming demonstration.
#
# The MSK cluster is created in Step 4B.3.
#
# Public subnets are required because the portfolio implementation
# will later enable public MSK broker connectivity using:
#
#   TLS + AWS IAM authentication on TCP 9198
#
# Public access is NOT enabled in this file.
# -------------------------------------------------------------------


data "aws_availability_zones" "available" {
  state = "available"
}


locals {
  msk_name_prefix = "epip-${var.environment}-msk"

  msk_availability_zones = slice(
    data.aws_availability_zones.available.names,
    0,
    2
  )
}


# -------------------------------------------------------------------
# Dedicated MSK VPC
# -------------------------------------------------------------------

resource "aws_vpc" "msk" {
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
# Internet gateway
# -------------------------------------------------------------------

resource "aws_internet_gateway" "msk" {
  vpc_id = aws_vpc.msk.id

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
# Two subnets are created across two Availability Zones.
#
# map_public_ip_on_launch is enabled because these subnets are
# intentionally public and will later support public MSK endpoints.
# -------------------------------------------------------------------

resource "aws_subnet" "msk_public" {
  count = 2

  vpc_id = aws_vpc.msk.id

  cidr_block = var.msk_public_subnet_cidrs[count.index]

  availability_zone = local.msk_availability_zones[count.index]

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
  vpc_id = aws_vpc.msk.id

  route {
    cidr_block = "0.0.0.0/0"

    gateway_id = aws_internet_gateway.msk.id
  }

  tags = merge(
    local.common_tags,
    {
      Name    = "${local.msk_name_prefix}-public-rt"
      Purpose = "Amazon MSK public subnet routing"
    }
  )
}


resource "aws_route_table_association" "msk_public" {
  count = 2

  subnet_id = aws_subnet.msk_public[count.index].id

  route_table_id = aws_route_table.msk_public.id
}


# -------------------------------------------------------------------
# MSK security group
# -------------------------------------------------------------------
#
# TCP 9198 is the public Amazon MSK port for SASL/IAM.
#
# Access is intentionally restricted to CIDRs supplied through:
#
#   var.msk_public_ingress_cidrs
#
# Initially this contains the developer workstation's public /32.
#
# Before Databricks consumes the stream, the current Databricks
# serverless outbound CIDRs will also be added.
# -------------------------------------------------------------------

resource "aws_security_group" "msk" {
  name_prefix = "${local.msk_name_prefix}-"

  description = (
    "Restricts access to the Enterprise Payments Amazon MSK cluster."
  )

  vpc_id = aws_vpc.msk.id

  ingress {
    description = "IAM-authenticated public Kafka clients"

    from_port = 9198
    to_port   = 9198
    protocol  = "tcp"

    cidr_blocks = var.msk_public_ingress_cidrs
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