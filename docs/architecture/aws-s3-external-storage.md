# AWS S3 External Storage

## Purpose

The Enterprise Payments Intelligence Platform uses Unity Catalog external locations
to govern access from Databricks to customer-owned AWS S3 storage.

AWS credentials are never embedded in application code, notebooks, SQL, or GitHub.

---

## Architecture

```text
AWS Account
|
+-- S3
|   |
|   +-- payments landing bucket
|       |
|       +-- payments/landing/
|
+-- IAM
    |
    +-- Unity Catalog IAM role
        |
        +-- least-privilege S3 access
        +-- Databricks cross-account trust
        +-- storage credential External ID
        +-- self-assume trust

                    |
                    v

Databricks Unity Catalog
|
+-- Storage Credential
|   |
|   +-- payments_s3_dev
|
+-- External Location
    |
    +-- payments_s3_landing_dev
        |
        v
    s3://<bucket>/payments/landing
```

---

## Security Model

The S3 bucket:

- blocks public access
- disables ACL ownership through BucketOwnerEnforced
- enables server-side encryption
- enables versioning
- prevents accidental Terraform deletion when data remains

The IAM role:

- is scoped to the payments landing prefix
- uses the Unity Catalog AWS trust principal
- requires the Databricks-generated External ID
- explicitly supports the required self-assume pattern

---

## Storage Credential Bootstrap

The AWS IAM role must exist before the Databricks storage credential can reference it.

The Databricks storage credential must then exist before its generated External ID is
available.

Therefore provisioning occurs in two controlled stages:

```text
Terraform
    |
    +-- IAM role with temporary External ID
          |
          v
Databricks Storage Credential
          |
          +-- generates real External ID
          |
          v
Terraform
    |
    +-- updates IAM trust policy
          |
          v
Credential Validation
```

The generated External ID is environment-specific and is not committed to Git.

---

## External Location

Unity Catalog does not expose the IAM role directly to data workloads.

Instead:

```text
IAM Role
    |
    v
Storage Credential
    |
    v
External Location
    |
    v
S3 landing prefix
```

Access can therefore be governed using Unity Catalog privileges rather than embedding
AWS credentials in application code.

---

## Milestone Boundary

Step 3B establishes connectivity only.

Historical payment files remain in the managed development volume until Step 3C.

Step 3C will:

1. copy deterministic payment files into S3
2. add a Unity Catalog external volume
3. switch batch ingestion to the external S3 source
4. perform source-to-target reconciliation