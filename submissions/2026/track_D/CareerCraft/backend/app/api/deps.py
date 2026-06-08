"""Shared FastAPI dependencies.

Identity resolution is centralized here so the rest of the application can
depend on a stable seam while authentication evolves. The active strategy is
selected via ``settings.auth_mode`` and built once at import time so invalid
configurations fail fast at startup rather than during request handling.

Error responses use a structured ``detail`` payload:
``{"code": "<machine_code>", "message": "<human readable>"}``. Clients should
branch on ``code``; ``message`` is for diagnostics only.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

PLAYER_ID_HEADER = "X-Player-Id"
AUTHORIZATION_HEADER = "Authorization"

# Stable machine-readable error codes returned in HTTPException.detail.code.
ERR_MISSING_PLAYER_ID = "identity.missing_player_id"
ERR_INVALID_PLAYER_ID = "identity.invalid_player_id"
ERR_MISSING_BEARER = "identity.missing_bearer"
ERR_JWT_NOT_IMPLEMENTED = "identity.jwt_not_implemented"


class IdentityResolver(Protocol):
  """Pluggable strategy used to resolve the current player identity."""

  def resolve(self, request: Request) -> "IdentityContext":
    """Resolve and validate identity context from incoming request."""


@dataclass(frozen=True)
class IdentityContext:
  """Canonical identity object used by API layer.

  TODO(auth-upgrade): Extend with account_id/session_id/scopes once JWT-based
  account auth is introduced. Keep this as the single context type passed from
  dependency layer to route layer.
  """

  principal_id: str
  auth_type: str


def _identity_error(code: str, message: str) -> HTTPException:
  return HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail={"code": code, "message": message},
  )


def _normalize_uuid4(value: str) -> str | None:
  try:
    parsed = uuid.UUID(value)
  except (ValueError, AttributeError, TypeError):
    return None
  if parsed.version != 4:
    return None
  return str(parsed)  # canonical lowercase form with dashes


class AnonymousHeaderResolver:
  """Resolve anonymous player id from ``X-Player-Id`` request header."""

  def resolve(self, request: Request) -> IdentityContext:
    candidate = request.headers.get(PLAYER_ID_HEADER, "")
    if not candidate:
      raise _identity_error(
          ERR_MISSING_PLAYER_ID,
          f"Missing {PLAYER_ID_HEADER} header",
      )
    normalized = _normalize_uuid4(candidate)
    if not normalized:
      raise _identity_error(
          ERR_INVALID_PLAYER_ID,
          f"Invalid {PLAYER_ID_HEADER} header (expected UUID v4)",
      )
    return IdentityContext(principal_id=normalized, auth_type="anonymous")


class JWTResolver:
  """Resolve account identity from ``Authorization: Bearer <token>`` header.

  JWT signature/claims validation is intentionally not implemented yet. To
  avoid the foot-gun of running with auth "enabled" but never validated, the
  resolver builder fails fast when ``auth_mode == "jwt"``; this class only
  ships the shape so future implementations can drop in without touching
  callers.
  """

  def resolve(self, request: Request) -> IdentityContext:
    auth_header = request.headers.get(AUTHORIZATION_HEADER, "")
    if not auth_header.startswith("Bearer ") or not auth_header[len("Bearer "):].strip():
      raise _identity_error(
          ERR_MISSING_BEARER,
          "Missing or invalid Authorization header",
      )
    raise _identity_error(
        ERR_JWT_NOT_IMPLEMENTED,
        "JWT validation is not implemented in this build",
    )


class HybridResolver:
  """Try account bearer auth first, then fall back to anonymous header auth.

  Compatibility-first: when an ``Authorization`` header is present we attempt
  bearer auth; any 401 from that path silently degrades to the anonymous
  header path so legacy clients keep working during the migration window.
  """

  def __init__(
      self,
      jwt_resolver: IdentityResolver | None = None,
      anonymous_resolver: IdentityResolver | None = None,
  ) -> None:
    self._jwt_resolver = jwt_resolver or JWTResolver()
    self._anonymous_resolver = anonymous_resolver or AnonymousHeaderResolver()

  def resolve(self, request: Request) -> IdentityContext:
    if request.headers.get(AUTHORIZATION_HEADER, ""):
      try:
        return self._jwt_resolver.resolve(request)
      except HTTPException:
        # TODO(auth-upgrade): once real JWT validation lands, restrict this
        # to status_code == 401 AND detail.code in {ERR_MISSING_BEARER,
        # ERR_JWT_NOT_IMPLEMENTED}. Non-401 errors (KMS down, signature
        # service unavailable) must propagate so outages are not masked as
        # silent anonymous downgrades.
        pass
    return self._anonymous_resolver.resolve(request)


def build_identity_resolver(mode: str | None = None) -> IdentityResolver:
  """Build the configured identity resolver, failing fast on misconfiguration."""
  selected_mode = (mode or settings.auth_mode or "anonymous").lower()
  if selected_mode == "anonymous":
    return AnonymousHeaderResolver()
  if selected_mode == "hybrid":
    return HybridResolver()
  if selected_mode == "jwt":
    raise RuntimeError(
        "auth_mode='jwt' selected but JWT validation is not implemented; "
        "set AUTH_MODE=hybrid or anonymous until JWTResolver is completed."
    )
  raise RuntimeError(f"Unsupported auth_mode: {selected_mode}")


identity_resolver: IdentityResolver = build_identity_resolver()
logger.info(
    "identity_resolver_initialized auth_mode=%s resolver=%s",
    settings.auth_mode,
    type(identity_resolver).__name__,
)


def get_current_identity(request: Request) -> IdentityContext:
  """Resolve active identity context from request, logging the outcome."""
  try:
    identity = identity_resolver.resolve(request)
  except HTTPException as exc:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "identity.unknown"}
    logger.info(
        "identity_resolution_failed auth_mode=%s code=%s",
        settings.auth_mode,
        detail.get("code"),
    )
    raise
  logger.debug(
      "identity_resolution_ok auth_mode=%s auth_type=%s",
      settings.auth_mode,
      identity.auth_type,
  )
  return identity


def get_current_user_id(request: Request) -> str:
  """Resolve active player id from request.

  Compatibility wrapper for existing routes/services that still consume a
  string user id. New code should prefer ``get_current_identity``.
  """
  return get_current_identity(request).principal_id
