# Milestone 15 — Enterprise CI/CD Architecture

## Purpose

Milestone 15 turns EPIP from a locally validated portfolio repository into a
controlled delivery system for data engineering, ML, GenAI, agent evaluation,
analytics, and infrastructure assets.

M15 builds on the existing GitHub Actions foundation rather than replacing it.

## Delivery architecture

```text
Developer Branch
      │
      ▼
Pull Request
      │
      ├─────────────────────────────────────┐
      │                                     │
      ▼                                     ▼
Python / Repo Quality                 Databricks Validation
      │                                     │
      ├─ pytest                              ├─ GitHub OIDC
      ├─ Ruff                               ├─ Service Principal
      ├─ formatting                         ├─ bundle validate
      ├─ mypy                               └─ bundle plan
      ├─ package build
      └─ Terraform validate
      │                                     │
      └──────────────────┬──────────────────┘
                         │
                         ▼
                    PR Can Merge
                         │
                         ▼
                       main
                         │
                         ▼
                  Controlled Deploy
                         │
                ┌────────┴─────────┐
                ▼                  ▼
          Pre-production       Production
          deployment           promotion
                │                  │
                ▼                  ▼
         Smoke / ML / AI     Approval + gates
             gates
```

## Identity model

CI/CD must not use a developer's Databricks PAT.

The target architecture is:

```text
GitHub Actions
      │
      │ OIDC token
      ▼
Databricks Workload Identity Federation
      │
      ▼
CI/CD Service Principal
      │
      ▼
Databricks Workspace
```

GitHub supplies a short-lived OIDC token. Databricks exchanges it for a
Databricks OAuth token associated with the CI/CD service principal.

This removes long-lived Databricks secrets from GitHub.

## M15A — Pull-request quality gates

M15A implements:

### Credential-free quality workflow

```text
.github/workflows/ci.yml
```

The workflow checks:

- locked dependency synchronization;
- pytest;
- Ruff linting;
- Ruff formatting;
- mypy;
- Python package build;
- Terraform formatting;
- Terraform initialization without a backend;
- Terraform validation.

It deliberately does not run:

```text
terraform apply
terraform destroy
```

during pull-request CI.

### Databricks-aware workflow

```text
.github/workflows/databricks-ci.yml
```

The workflow:

1. requests a GitHub OIDC token;
2. authenticates to Databricks as a service principal;
3. validates the `ci` bundle target;
4. previews the deployment with `bundle plan`.

It deliberately does not deploy on pull requests.

## CI bundle target

The `ci` target uses development mode.

Development mode is intentionally safe for ephemeral/pre-production validation:

- schedules and triggers remain paused;
- pipelines remain in development mode;
- resources are clearly CI-prefixed;
- job concurrency is bounded.

The CI deployment root is resolved from the authenticated service principal's
Databricks identity:

```text
/Workspace/Users/${workspace.current_user.userName}/.bundle/...
```

This keeps CI state separate from the developer's personal `dev` deployment.

## Promotion strategy

Later M15 steps will add:

```text
M15B  CI service-principal / GitHub OIDC setup
M15C  controlled deployment after merge
M15D  ML + fraud-agent promotion gates
M15E  production-style environment approval and release flow
```

## Promotion gates

The intended release chain is:

```text
Code Quality
    +
Terraform Validation
    +
Bundle Validation
    +
Data / Pipeline Smoke Tests
    +
ML Validation
    +
M13 Agent Regression Gate
    +
Dashboard Validation
    ↓
Promotion
```

A failed safety, scope, ML, or data-quality gate must block promotion rather than
being converted into a warning.

## Security principles

- no user PAT in GitHub;
- no Databricks OAuth client secret when OIDC is available;
- least-privilege CI/CD service principal;
- GitHub Environment-scoped federation policy;
- pull requests validate and plan, but do not deploy;
- production promotion is separated from ordinary PR CI;
- Terraform plans are separated from infrastructure apply;
- deployments are traceable to Git commits and workflow runs.
