"""End-to-end contract tests for the identity dependency.

These tests exercise the real FastAPI app via ``TestClient`` to lock down the
public auth contract documented in ``docs/specification/03-interface-spec.md``:

* protected endpoints must return ``401`` with a structured
  ``{"detail": {"code": ..., "message": ...}}`` body when the player identity
  is missing or malformed;
* protected endpoints must accept a canonical ``X-Player-Id`` UUID v4 header
  and return their normal ``2xx`` response under the default ``hybrid`` mode;
* the ``code`` values are stable strings consumed by the frontend / clients
  and must not be changed without updating the spec and ADR.
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import (
    ERR_INVALID_PLAYER_ID,
    ERR_MISSING_PLAYER_ID,
)
from app.db.session import base, get_db
from app.main import app

TEST_PLAYER_ID = "00000000-0000-4000-8000-000000000001"


def _make_in_memory_session_factory():
  # StaticPool keeps a single shared connection so every request in the test
  # observes the same in-memory SQLite database (otherwise each connection
  # gets its own empty schema and queries hit "no such table: users").
  engine = create_engine(
      "sqlite:///:memory:",
      connect_args={"check_same_thread": False},
      poolclass=StaticPool,
  )
  base.metadata.create_all(bind=engine)
  return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TestIdentityContract(unittest.TestCase):
  """Lock down the public 401 / 200 contract for authenticated endpoints."""

  PROTECTED_GET_ENDPOINTS = [
      "/api/v1/user/sync",
  ]
  PROTECTED_POST_ENDPOINTS = [
      ("/api/v1/missions/generate", {"role_id": "mentor_ling", "difficulty": "easy"}),
      ("/api/v1/user/career", {"career_id": "career_data_analyst"}),
  ]

  def setUp(self):
    super().setUp()
    session_factory = _make_in_memory_session_factory()

    def _override_get_db():
      db = session_factory()
      try:
        yield db
      finally:
        db.close()

    app.dependency_overrides[get_db] = _override_get_db
    self.client = TestClient(app)

  def tearDown(self):
    app.dependency_overrides.clear()
    super().tearDown()

  # --- missing identity -------------------------------------------------- #

  def test_missing_player_id_header_returns_structured_401(self):
    for path in self.PROTECTED_GET_ENDPOINTS:
      with self.subTest(path=path, method="GET"):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 401)
        body = res.json()
        self.assertIsInstance(body.get("detail"), dict)
        self.assertEqual(body["detail"]["code"], ERR_MISSING_PLAYER_ID)

    for path, payload in self.PROTECTED_POST_ENDPOINTS:
      with self.subTest(path=path, method="POST"):
        res = self.client.post(path, json=payload)
        self.assertEqual(res.status_code, 401)
        body = res.json()
        self.assertEqual(body["detail"]["code"], ERR_MISSING_PLAYER_ID)

  # --- invalid identity -------------------------------------------------- #

  def test_invalid_player_id_header_returns_invalid_code(self):
    headers = {"X-Player-Id": "not-a-uuid"}
    res = self.client.get("/api/v1/user/sync", headers=headers)
    self.assertEqual(res.status_code, 401)
    self.assertEqual(res.json()["detail"]["code"], ERR_INVALID_PLAYER_ID)

  # --- happy path -------------------------------------------------------- #

  def test_valid_player_id_header_passes_auth(self):
    headers = {"X-Player-Id": TEST_PLAYER_ID}
    # user/sync auto-initialises the player and returns the aggregate state.
    res = self.client.get("/api/v1/user/sync", headers=headers)
    self.assertEqual(res.status_code, 200, msg=res.text)
    body = res.json()
    self.assertIn("user", body)
    self.assertEqual(body["user"]["id"], TEST_PLAYER_ID)

  def test_uppercase_player_id_is_normalized_to_lowercase(self):
    headers = {"X-Player-Id": TEST_PLAYER_ID.upper()}
    res = self.client.get("/api/v1/user/sync", headers=headers)
    self.assertEqual(res.status_code, 200, msg=res.text)
    self.assertEqual(res.json()["user"]["id"], TEST_PLAYER_ID)


if __name__ == "__main__":
  unittest.main()
