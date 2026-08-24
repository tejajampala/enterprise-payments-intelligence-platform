"""Amazon MSK IAM authentication helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def build_msk_iam_kafka_config(
    aws_region: str,
) -> dict[str, object]:
    """Build confluent-kafka configuration for Amazon MSK IAM auth."""

    region = aws_region.strip()

    if not region:
        raise ValueError("aws_region must not be empty")

    # MSKAuthTokenProvider is a submodule inside the AWS signer
    # package, rather than an attribute automatically loaded on the
    # top-level package.
    token_provider: Any = import_module("aws_msk_iam_sasl_signer.MSKAuthTokenProvider")

    def oauth_cb(
        _: str,
    ) -> tuple[str, float]:
        token, expiry_ms = token_provider.generate_auth_token(region)

        # AWS returns expiry in milliseconds since epoch.
        # confluent-kafka requires seconds since epoch.
        return (
            str(token),
            float(expiry_ms) / 1000.0,
        )

    return {
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "OAUTHBEARER",
        "oauth_cb": oauth_cb,
    }
