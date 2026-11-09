"""Settings read from environment variables and the project's .env file."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Copernicus
    cds_url: str = "https://cds.climate.copernicus.eu/api"
    cds_key: SecretStr | None = None
    ads_url: str = "https://ads.atmosphere.copernicus.eu/api"
    ads_key: SecretStr | None = None

    # Postgres + PostGIS
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "locintel"
    postgres_user: str = "locintel"
    postgres_password: SecretStr = SecretStr("")

    # S3-compatible lake (RustFS locally)
    s3_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_buckets: str = "raw staged"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
            f"user={self.postgres_user} password={self.postgres_password.get_secret_value()}"
        )

    @property
    def bucket_names(self) -> list[str]:
        return self.s3_buckets.split()


@lru_cache
def get_settings() -> Settings:
    return Settings()
