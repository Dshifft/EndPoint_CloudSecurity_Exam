"""SQLAlchemy database configuration."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import Settings


settings = Settings()
Engine = create_engine(settings.get_postgres_url().render_as_string(hide_password=False))
SessionLocal = sessionmaker(bind=Engine)
Base = declarative_base()


def get_db():
    """Provide a database session for one request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
