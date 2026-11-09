import pytest

from locintel.config import Settings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in ("POSTGRES_HOST", "POSTGRES_PASSWORD", "S3_BUCKETS", "CDS_KEY"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_env_overrides_defaults(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("POSTGRES_HOST", "db.example")
    clean_env.setenv("POSTGRES_PASSWORD", "s3cret")
    s = Settings(_env_file=None)
    assert s.postgres_host == "db.example"
    assert "password=s3cret" in s.postgres_dsn


def test_secrets_hidden_in_repr(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("CDS_KEY", "abc-123")
    s = Settings(_env_file=None)
    assert "abc-123" not in repr(s)
    assert s.cds_key is not None and s.cds_key.get_secret_value() == "abc-123"


def test_bucket_names_split(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("S3_BUCKETS", "raw staged")
    assert Settings(_env_file=None).bucket_names == ["raw", "staged"]
