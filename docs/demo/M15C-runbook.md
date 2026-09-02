M15C separates CI from CD.

Pull requests authenticate through GitHub OIDC and can validate
and preview Databricks changes but cannot deploy.

After code is merged into main, a separate GitHub Actions workflow
authenticates using the same short-lived OIDC trust and dedicated
service principal.

The CI deployment uses an isolated payments_ci Unity Catalog and
deploys a controlled, low-cost resource slice. Global platform
foundation resources and expensive AI infrastructure are deliberately
excluded from automated CI deployment.

Production deployment is handled separately in M15E with production
mode, approval gates, and a full promotion model.