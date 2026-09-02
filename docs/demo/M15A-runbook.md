# Milestone 15A Runbook — PR Quality Gates and Databricks OIDC CI

## 1. Create the M15 branch

```powershell
git checkout main
git pull origin main
git checkout -b feature/m15-enterprise-cicd
```

## 2. Add the M15A files

Add or replace:

```text
.github/workflows/ci.yml
.github/workflows/databricks-ci.yml
bundle.targets.yml
tests/unit/test_enterprise_cicd_contracts.py
docs/architecture/enterprise-cicd.md
docs/demo/M15A-runbook.md
```

## 3. Validate locally

```powershell
uv sync
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv build
```

Terraform:

```powershell
cd infra/terraform/aws

terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate

cd ../../..
```

Bundle:

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle validate -t ci -p PAYMENTS_DEV
databricks bundle plan -t ci -p PAYMENTS_DEV
```

The local `ci` commands use your interactive `PAYMENTS_DEV` profile only for
development verification. GitHub Actions will use OIDC instead.

## 4. Create a Databricks CI/CD service principal

Create a dedicated Databricks service principal for GitHub Actions.

Suggested display name:

```text
epip-github-actions-ci
```

Do not configure the workflow to authenticate as your personal user.

The service principal requires only the workspace permissions needed for bundle
validation/planning initially. Expand privileges only when M15C begins actual
deployment.

Record:

```text
service principal application/client ID
service principal numeric Databricks ID
Databricks account ID
```

Do not commit any of these as credentials. The client/application ID is an
identifier, not a secret.

## 5. Create GitHub Environment

Repository:

```text
tejajampala/enterprise-payments-intelligence-platform
```

Create a GitHub Environment named:

```text
ci
```

Add environment variables:

```text
DATABRICKS_HOST
DATABRICKS_CLIENT_ID
```

Values:

```text
DATABRICKS_HOST
= your Databricks workspace URL

DATABRICKS_CLIENT_ID
= the CI/CD service principal application/client ID
```

No Databricks token is stored in GitHub.

## 6. Configure Databricks federation policy

Create a service-principal federation policy for GitHub Actions.

Issuer:

```text
https://token.actions.githubusercontent.com
```

Recommended audience:

```text
your Databricks account ID
```

Subject:

```text
repo:tejajampala/enterprise-payments-intelligence-platform:environment:ci
```

Conceptual policy:

```json
{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": [
      "<DATABRICKS_ACCOUNT_ID>"
    ],
    "subject": "repo:tejajampala/enterprise-payments-intelligence-platform:environment:ci"
  }
}
```

The exact account-level command requires account-admin authentication and the
service principal's numeric Databricks ID.

## 7. Verify GitHub OIDC workflow

Push the branch:

```powershell
git add .
git commit -m "feat(cicd): add enterprise pull request quality gates"
git push -u origin feature/m15-enterprise-cicd
```

Create a PR.

Expected GitHub checks:

```text
Python Quality Gates
Terraform Quality Gates
Databricks Bundle Validation
```

## 8. Interpret failures

### Python Quality Gates

Fix the underlying:

- unit test;
- lint;
- formatting;
- typing;
- packaging

failure.

Do not bypass the check.

### Terraform Quality Gates

For formatting:

```powershell
terraform fmt -recursive infra/terraform/aws
```

For validation errors, correct the Terraform source.

The CI workflow never runs `apply`.

### Databricks authentication

If:

```text
databricks current-user me
```

fails, check:

- `id-token: write`;
- GitHub Environment name is exactly `ci`;
- `DATABRICKS_HOST`;
- `DATABRICKS_CLIENT_ID`;
- service-principal federation policy issuer/audience/subject;
- workspace assignment and permissions for the service principal.

Do not fall back to a personal PAT simply to make the workflow green.

### Bundle validation

Run locally:

```powershell
databricks bundle validate -t ci -p PAYMENTS_DEV
```

and fix the bundle error.

### Bundle plan

A pull request plan may show proposed changes. It must not actually deploy them.

## 9. Definition of done

M15A is complete when:

- Python quality gates pass;
- Terraform quality gates pass;
- GitHub Actions authenticates through OIDC;
- no Databricks PAT/client secret exists in the workflow;
- `bundle validate -t ci` passes;
- `bundle plan -t ci` passes;
- PR CI does not deploy resources;
- all workflow-contract tests pass.

## Next

M15B/M15C will introduce controlled Databricks deployment after merge, then add
ML and M13 agent-regression promotion gates.
