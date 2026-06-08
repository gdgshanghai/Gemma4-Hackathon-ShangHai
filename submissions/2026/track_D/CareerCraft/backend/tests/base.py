"""Base test setup for database unit tests using standard library unittest."""

import asyncio
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import base

TEST_PLAYER_ID = "00000000-0000-4000-8000-000000000001"


class BaseDbTestCase(unittest.TestCase):
  """Base test case for clean, in-memory SQLite database setup."""

  def setUp(self):
    super().setUp()
    # Initialize in-memory clean database schema
    self.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    base.metadata.create_all(bind=self.engine)
    self.session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=self.engine
    )
    self.db_session = self.session_local()

  def tearDown(self):
    self.db_session.close()
    super().tearDown()

  def run_async(self, coro):
    """Helper method to run async coroutines synchronously in tests."""
    return asyncio.run(coro)
