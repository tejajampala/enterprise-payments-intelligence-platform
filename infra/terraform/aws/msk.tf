# -------------------------------------------------------------------
# Optional Amazon MSK Provisioned cluster
# -------------------------------------------------------------------
#
# Milestone 4 streaming infrastructure.
#
# The cluster is intentionally optional for development and portfolio
# cost control.
#
# enable_msk = false
#   -> no cluster
#
# enable_msk = true
#   -> provision the cluster
#
# Initial creation should use:
#
#   enable_msk               = true
#   enable_msk_public_access = false
#
# After the cluster reaches ACTIVE state, public connectivity can be
# enabled in a subsequent Terraform apply.
# -------------------------------------------------------------------


locals {
  msk_cluster_name = "epip-${var.environment}-payments-streaming"
}


resource "aws_msk_cluster" "payments_streaming" {
  count = var.enable_msk ? 1 : 0

  cluster_name = local.msk_cluster_name

  kafka_version = var.msk_kafka_version

  # Two brokers across two Availability Zones.
  number_of_broker_nodes = 2


  # -----------------------------------------------------------------
  # Broker infrastructure
  # -----------------------------------------------------------------

  broker_node_group_info {
    instance_type = var.msk_broker_instance_type

    client_subnets = [
      aws_subnet.msk_public[0].id,
      aws_subnet.msk_public[1].id,
    ]

    security_groups = [
      aws_security_group.msk[0].id,
    ]


    # Small EBS volumes are sufficient for the synthetic portfolio
    # streaming workload.
    storage_info {
      ebs_storage_info {
        volume_size = var.msk_broker_volume_size_gib
      }
    }


    # ---------------------------------------------------------------
    # Broker network connectivity
    # ---------------------------------------------------------------
    #
    # AWS MSK public connectivity is intentionally disabled during
    # initial cluster creation.
    #
    # After the cluster reaches ACTIVE state:
    #
    #   enable_msk_public_access = true
    #
    # can be applied separately.
    # ---------------------------------------------------------------

    connectivity_info {
      public_access {
        type = (
          var.enable_msk_public_access
          ? "SERVICE_PROVIDED_EIPS"
          : "DISABLED"
        )
      }
    }
  }


  # -----------------------------------------------------------------
  # Client authentication
  # -----------------------------------------------------------------
  #
  # Only AWS IAM-authenticated Kafka clients are allowed.
  # -----------------------------------------------------------------

  client_authentication {
    sasl {
      iam = true
    }

    unauthenticated = false
  }


  # -----------------------------------------------------------------
  # Encryption
  # -----------------------------------------------------------------

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }


  # -----------------------------------------------------------------
  # Monitoring
  # -----------------------------------------------------------------

  enhanced_monitoring = "DEFAULT"


  # Ensure subnet routing is established before cluster provisioning.
  depends_on = [
    aws_route_table_association.msk_public,
  ]


  tags = merge(
    local.common_tags,
    {
      Name    = local.msk_cluster_name
      Purpose = "Real-time payment event streaming"
    }
  )
}