"""S3-compatible data lake (RustFS locally).

`uv run python -m locintel.load.lake init` creates the configured buckets (safe to re-run).
"""

import sys

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from locintel.config import Settings, get_settings


def s3_client(settings: Settings | None = None) -> BaseClient:
    s = settings or get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        region_name=s.s3_region,
        aws_access_key_id=s.s3_access_key.get_secret_value(),
        aws_secret_access_key=s.s3_secret_key.get_secret_value(),
        config=Config(
            s3={"addressing_style": "path"}, connect_timeout=5, retries={"max_attempts": 3}
        ),
    )


def ensure_buckets(client: BaseClient, names: list[str]) -> list[str]:
    """Create each bucket if missing. Returns the names that were created."""
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    created: list[str] = []
    for name in names:
        if name in existing:
            continue
        try:
            client.create_bucket(Bucket=name)
            created.append(name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in (
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            ):
                raise
    return created


def main(argv: list[str]) -> int:
    if argv != ["init"]:
        print("usage: python -m locintel.load.lake init")
        return 2
    settings = get_settings()
    try:
        created = ensure_buckets(s3_client(settings), settings.bucket_names)
    except Exception as exc:  # noqa: BLE001 - one-line error for a CLI
        print(f"FAIL {type(exc).__name__}: {exc}")
        return 1
    for name in settings.bucket_names:
        print(f"bucket {name}: {'created' if name in created else 'exists'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
