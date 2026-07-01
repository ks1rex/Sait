"""JWT authentication — shared dependency used by main and admin routers."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt

_bearer = HTTPBearer()

# JWKS cache — populated on first ES256 verification attempt
_jwks_cache: list[dict] | None = None


def _get_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache is None:
        import httpx as _httpx
        url = os.environ["SUPABASE_URL"]
        with _httpx.Client(trust_env=False) as _c:
            r = _c.get(f"{url}/auth/v1/.well-known/jwks.json", timeout=10)
        r.raise_for_status()
        _jwks_cache = r.json().get("keys", [])
    return _jwks_cache


def _decode_jwt(token: str) -> dict:
    """Verify JWT supporting both HS256 (legacy) and ES256 (new Supabase key API)."""
    secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if secret:
        try:
            return jose_jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        except JWTError:
            pass

    try:
        header = jose_jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError(f"Malformed JWT header: {exc}") from exc

    kid = header.get("kid")
    alg = header.get("alg", "ES256")
    # JWKS keys are asymmetric public keys — never verify a symmetric alg
    # against them (algorithm-confusion attack).
    if alg not in ("ES256", "RS256"):
        raise JWTError(f"Unsupported JWT algorithm: {alg}")
    keys = _get_jwks()
    matching = [k for k in keys if k.get("kid") == kid] if kid else keys

    last_exc: Exception = JWTError("No matching JWKS key found")
    for jwk in matching:
        try:
            return jose_jwt.decode(token, jwk, algorithms=[alg], audience="authenticated")
        except JWTError as exc:
            last_exc = exc
    raise last_exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    try:
        payload = _decode_jwt(credentials.credentials)
        return {
            "user_id": payload["sub"],
            "email": payload.get("email", ""),
            "jwt": credentials.credentials,
        }
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": f"Недействительный токен: {exc}"},
        )


CurrentUser = Annotated[dict, Depends(get_current_user)]
