"""Application configuration loaded from the local environment file."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import URL


class Settings(BaseSettings):
    """Provide database settings for the local development environment."""

    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def get_postgres_url(self, host: str | None = None, port: int | None = None) -> URL:
        """Build the synchronous SQLAlchemy URL for PostgreSQL."""
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=host if host is not None else self.POSTGRES_HOST,
            port=port if port is not None else self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        )
