from typing import Any

from locintel.load.lake import ensure_buckets


class FakeS3:
    def __init__(self, existing: list[str]) -> None:
        self.buckets = list(existing)

    def list_buckets(self) -> dict[str, Any]:
        return {"Buckets": [{"Name": b} for b in self.buckets]}

    def create_bucket(self, Bucket: str) -> None:  # noqa: N803 - boto3 argument name
        self.buckets.append(Bucket)


def test_creates_only_missing_buckets() -> None:
    s3 = FakeS3(existing=["raw"])
    assert ensure_buckets(s3, ["raw", "staged"]) == ["staged"]  # type: ignore[arg-type]
    assert sorted(s3.buckets) == ["raw", "staged"]


def test_rerun_is_noop() -> None:
    s3 = FakeS3(existing=["raw", "staged"])
    assert ensure_buckets(s3, ["raw", "staged"]) == []  # type: ignore[arg-type]
