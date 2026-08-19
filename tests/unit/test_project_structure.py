from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_required_project_files_exist() -> None:
    required_files = [
        "README.md",
        "pyproject.toml",
        ".gitignore",
        ".env.example",
        ".python-version",
    ]

    for relative_path in required_files:
        assert (ROOT / relative_path).exists(), f"Missing required project file: {relative_path}"


def test_required_project_directories_exist() -> None:
    required_directories = [
        "src/payments_intelligence",
        "pipelines/bronze",
        "pipelines/silver",
        "pipelines/gold",
        "tests/unit",
        "tests/integration",
        "bundle/resources",
        "infra/terraform/aws",
        "infra/terraform/azure",
        "docs/architecture",
        "docs/adr",
        "docs/demo",
        ".github/workflows",
    ]

    for relative_path in required_directories:
        assert (ROOT / relative_path).is_dir(), f"Missing required directory: {relative_path}"


def test_python_package_imports() -> None:
    import payments_intelligence

    assert payments_intelligence.PROJECT_NAME == "enterprise-payments-intelligence-platform"


def test_databricks_bundle_configuration_exists() -> None:
    assert (ROOT / "databricks.yml").exists()
    assert (ROOT / "bundle.targets.yml").exists()


def test_databricks_bundle_name() -> None:
    with (ROOT / "databricks.yml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert config["bundle"]["name"] == "enterprise-payments-intelligence-platform"


def test_bundle_uses_direct_deployment_engine() -> None:
    with (ROOT / "databricks.yml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert config["bundle"]["engine"] == "direct"


def test_dev_target_is_default() -> None:
    with (ROOT / "bundle.targets.yml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert config["targets"]["dev"]["default"] is True


def test_dev_target_uses_development_mode() -> None:
    with (ROOT / "bundle.targets.yml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert config["targets"]["dev"]["mode"] == "development"
