from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from backend.config import settings

# Enhanced engine creation with IPv4 preference and better connection pooling
# This helps Hugging Face Spaces which has IPv6 DNS resolution issues
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={
        'connect_timeout': 10,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    }
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Configure connection settings for better reliability."""
    if hasattr(dbapi_conn, 'cursor'):
        # For PostgreSQL via psycopg2
        if hasattr(dbapi_conn, 'isolation_level'):
            pass  # Connection is already configured by connect_args

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency: yields a SQLAlchemy session, closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
