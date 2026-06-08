"""Database session managers and connection setup."""

import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Determine which database engine to use dynamically (SQLite/PostgreSQL)
db_url = settings.database_url or settings.sqlite_url

if db_url.startswith("sqlite"):
  engine = create_engine(
      db_url,
      connect_args={"check_same_thread": False},
  )
else:
  # For PostgreSQL and other databases, standard engine parameters apply
  engine = create_engine(
      db_url,
  )

session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
base = declarative_base()


# ChromaDB local client initialization.
chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)


def get_db():
  """Generator to yield a new database session per request.

  Yields:
    An active SQLAlchemy session object.
  """
  db = session_local()
  try:
    yield db
  finally:
    db.close()
