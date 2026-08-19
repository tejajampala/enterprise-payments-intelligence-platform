# ADR-0002: Serverless-First Development Environment

## Status

Accepted

---

## Context

The Enterprise Payments Intelligence Platform is designed as an enterprise Databricks
solution running primarily on AWS.

The target architecture will eventually include cloud infrastructure such as:

- Amazon S3
- IAM
- PostgreSQL / Amazon RDS
- Kafka / Amazon MSK
- networking
- Databricks integrations

Provisioning all infrastructure at the start of the project would introduce unnecessary
cost and operational complexity before the corresponding platform capabilities exist.

---

## Decision

Use a Databricks serverless development workspace during the early development milestones.

Introduce AWS infrastructure incrementally through Terraform when each corresponding
capability is implemented.

For example:

```text
S3 infrastructure
    ↓
introduced when file ingestion is implemented

PostgreSQL / RDS
    ↓
introduced when database ingestion is implemented

MSK / Kafka
    ↓
introduced when streaming ingestion is implemented
```

---

## Benefits

- lower development cost
- faster project setup
- reduced infrastructure administration
- easier experimentation
- fewer idle cloud resources
- infrastructure is introduced only when required

---

## Trade-offs

Some AWS-specific enterprise scenarios cannot be fully demonstrated during the earliest development milestones.

These scenarios will be implemented later through Terraform and integration testing.

---

## Consequences

The repository must maintain a clear separation between:

```text
Application Development
        │
        └── Databricks Declarative Automation Bundles

Cloud Infrastructure
        │
        └── Terraform
```

This ensures that moving from serverless development to more complete AWS integration does not require redesigning the application architecture.