-- ============================================================================
-- EPIP M17B — OBSERVABILITY FOUNDATION
-- Create the governed monitoring schema.
--
-- The bundle resource in bundle/resources/monitoring_observability.yml is the
-- preferred deployment path. This SQL remains useful for direct validation or
-- controlled bootstrap in the development catalog.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS payments_dev.monitoring
COMMENT 'Governed EPIP platform observability, reliability, performance and cost monitoring.';


-- Validate the schema.
DESCRIBE SCHEMA EXTENDED payments_dev.monitoring;
