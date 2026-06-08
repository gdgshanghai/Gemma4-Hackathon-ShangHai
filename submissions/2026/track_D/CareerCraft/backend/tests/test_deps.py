"""Unit tests for API dependency identity resolution."""

import unittest

from fastapi import HTTPException
from starlette.requests import Request

from app.api.deps import (
  AnonymousHeaderResolver,
  ERR_INVALID_PLAYER_ID,
  ERR_JWT_NOT_IMPLEMENTED,
  ERR_MISSING_PLAYER_ID,
  HybridResolver,
  IdentityContext,
  JWTResolver,
  build_identity_resolver,
  get_current_identity,
  get_current_user_id,
)

TEST_PLAYER_ID = "00000000-0000-4000-8000-000000000001"


def _request_with_headers(headers: dict[str, str]) -> Request:
  scope = {
      "type": "http",
      "headers": [
          (key.lower().encode("latin-1"), value.encode("latin-1"))
          for key, value in headers.items()
      ],
  }
  return Request(scope)


class TestUserIdDependency(unittest.TestCase):
  def test_valid_uuid4_header_returns_user_id(self):
    request = _request_with_headers({"X-Player-Id": TEST_PLAYER_ID})
    user_id = get_current_user_id(request)
    self.assertEqual(user_id, TEST_PLAYER_ID)

  def test_valid_uuid4_header_returns_identity_context(self):
    request = _request_with_headers({"X-Player-Id": TEST_PLAYER_ID})
    identity = get_current_identity(request)
    self.assertEqual(identity.principal_id, TEST_PLAYER_ID)
    self.assertEqual(identity.auth_type, "anonymous")

  def test_missing_header_raises_401_with_missing_code(self):
    request = _request_with_headers({})
    with self.assertRaises(HTTPException) as ctx:
      get_current_user_id(request)
    self.assertEqual(ctx.exception.status_code, 401)
    self.assertEqual(ctx.exception.detail["code"], ERR_MISSING_PLAYER_ID)

  def test_invalid_header_raises_401_with_invalid_code(self):
    request = _request_with_headers({"X-Player-Id": "not-a-uuid"})
    with self.assertRaises(HTTPException) as ctx:
      get_current_user_id(request)
    self.assertEqual(ctx.exception.status_code, 401)
    self.assertEqual(ctx.exception.detail["code"], ERR_INVALID_PLAYER_ID)

  def test_uppercase_uuid_header_is_normalized(self):
    request = _request_with_headers(
        {"X-Player-Id": TEST_PLAYER_ID.upper()}
    )
    user_id = get_current_user_id(request)
    self.assertEqual(user_id, TEST_PLAYER_ID)


class TestResolverSelection(unittest.TestCase):
  def test_build_anonymous_mode(self):
    resolver = build_identity_resolver("anonymous")
    self.assertIsInstance(resolver, AnonymousHeaderResolver)

  def test_build_hybrid_mode(self):
    resolver = build_identity_resolver("hybrid")
    self.assertIsInstance(resolver, HybridResolver)

  def test_build_jwt_mode_fails_fast(self):
    # JWT validation is not implemented yet; selecting jwt mode must error
    # at build time to prevent running with "auth enabled but not validated".
    with self.assertRaises(RuntimeError):
      build_identity_resolver("jwt")

  def test_build_invalid_mode_raises(self):
    with self.assertRaises(RuntimeError):
      build_identity_resolver("nope")


class TestHybridResolverBehavior(unittest.TestCase):
  def test_no_authorization_falls_back_to_anonymous(self):
    resolver = HybridResolver()
    request = _request_with_headers({"X-Player-Id": TEST_PLAYER_ID})
    identity = resolver.resolve(request)
    self.assertEqual(identity.auth_type, "anonymous")
    self.assertEqual(identity.principal_id, TEST_PLAYER_ID)

  def test_jwt_path_falls_back_when_token_unverifiable(self):
    # Real JWTResolver currently always rejects; hybrid must still serve
    # legacy anonymous clients carrying both headers.
    resolver = HybridResolver()
    request = _request_with_headers({
        "Authorization": "Bearer some-token",
        "X-Player-Id": TEST_PLAYER_ID,
    })
    identity = resolver.resolve(request)
    self.assertEqual(identity.auth_type, "anonymous")
    self.assertEqual(identity.principal_id, TEST_PLAYER_ID)

  def test_jwt_success_path_is_honored(self):
    class _StubJwt:
      def resolve(self, request):
        return IdentityContext(principal_id="acct-1", auth_type="account")

    resolver = HybridResolver(jwt_resolver=_StubJwt())
    request = _request_with_headers({"Authorization": "Bearer t"})
    identity = resolver.resolve(request)
    self.assertEqual(identity.auth_type, "account")
    self.assertEqual(identity.principal_id, "acct-1")

  def test_no_credentials_at_all_returns_missing_player_id(self):
    resolver = HybridResolver()
    request = _request_with_headers({})
    with self.assertRaises(HTTPException) as ctx:
      resolver.resolve(request)
    self.assertEqual(ctx.exception.status_code, 401)
    self.assertEqual(ctx.exception.detail["code"], ERR_MISSING_PLAYER_ID)


class TestJWTResolverShape(unittest.TestCase):
  def test_missing_bearer_returns_missing_bearer_code(self):
    resolver = JWTResolver()
    request = _request_with_headers({})
    with self.assertRaises(HTTPException) as ctx:
      resolver.resolve(request)
    self.assertEqual(ctx.exception.detail["code"], "identity.missing_bearer")

  def test_present_bearer_returns_not_implemented_code(self):
    resolver = JWTResolver()
    request = _request_with_headers({"Authorization": "Bearer token"})
    with self.assertRaises(HTTPException) as ctx:
      resolver.resolve(request)
    self.assertEqual(ctx.exception.detail["code"], ERR_JWT_NOT_IMPLEMENTED)


if __name__ == "__main__":
  unittest.main()

