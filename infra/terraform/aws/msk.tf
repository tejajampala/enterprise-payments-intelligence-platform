# -------------------------------------------------------------------
# Amazon MSK Provisioned cluster
# -------------------------------------------------------------------
#
# Milestone 4B streaming infrastructure.
#
# Initial deployment:
#
#   Public access = DISABLED
#   Authentication = AWS IAM
#   Client traffic = TLS
#   Broker-to-broker encryption = enabled
#
# Public broker connectivity is enabled only after the cluster
# reaches ACTIVE state.
# -------------------------------------------------------------------


locals {
  msk_cluster_name = "epip-${var.environment}-payments-streaming"
}


resource "aws_msk_cluster" "payments_streaming" {
  cluster_name = local.msk_cluster_name

  kafka_version = var.msk_kafka_version

  # Two brokers across the two Availability Zones created in 4B.2.
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
      aws_security_group.msk.id,
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
    # AWS does not permit public connectivity during initial cluster
    # creation.
    #
    # Step 4B.4 changes enable_msk_public_access to true after this
    # cluster becomes ACTIVE.
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
  # Only AWS IAM authenticated Kafka clients are allowed.
  #
  # No anonymous/unauthenticated Kafka access.
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
  #
  # client_broker = TLS
  #     Kafka clients must use encrypted connections.
  #
  # in_cluster = true
  #     Broker-to-broker traffic is also encrypted.
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


  tags = merge(
    local.common_tags,
    {
      Name    = local.msk_cluster_name
      Purpose = "Real-time payment event streaming"
    }
  )
}