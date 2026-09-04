                 Databricks Account
                        │
                 Account Groups
                        │
                        ▼
                   Unity Catalog
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
           RBAC                    ABAC
            │                       │
   Object permissions      Governed tags
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                    Column Masks         Row Filters
                          │                   │
                          └─────────┬─────────┘
                                    ▼
                           Governed Data
                         payments_dev/prod