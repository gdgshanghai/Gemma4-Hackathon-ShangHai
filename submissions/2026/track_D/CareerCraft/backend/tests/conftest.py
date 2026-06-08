"""Pytest configuration and shared database fixtures."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import base


@pytest.fixture(name="db_session")
def fixture_db_session():
  """Creates a clean, isolated in-memory SQLite database session for each test run."""
  # Use an in-memory SQLite database to avoid modifying any physical database files during tests
  engine = create_engine(
      "sqlite:///:memory:",
      connect_args={"check_same_thread": False},
  )
  base.metadata.create_all(bind=engine)
  testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
  
  db = testing_session_local()
  try:
    yield db
  finally:
    db.close()
