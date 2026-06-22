"""
Клиент Supabase с service-role ключом — используется backend'ом для
работы с БД и Storage в обход RLS (доступ к чужим записям всё равно
контролируется в коде эндпоинтов через project.user_id == current_user.id).
"""
from __future__ import annotations

import os

import httpx
from supabase import create_client, Client, ClientOptions

_client: Client | None = None
_http: httpx.Client | None = None


def _shared_http() -> httpx.Client:
    """One reusable HTTP transport for all Supabase clients.

    httpx.Client is safe to reuse concurrently and only carries the transport
    (connection pool) — per-user auth lives on the PostgREST headers, not here.
    Sharing it avoids leaking a socket pool on every get_supabase_as_user call.
    """
    global _http
    if _http is None:
        # Bypass system SOCKS proxy (Windows registry) that breaks httpx
        _http = httpx.Client(trust_env=False, http2=True)
    return _http


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key, options=ClientOptions(httpx_client=_shared_http()))
    return _client


def get_supabase_as_user(jwt: str) -> Client:
    """
    Return a Supabase client whose PostgREST calls are authenticated with
    the given user JWT.  auth.uid() resolves correctly inside SECURITY DEFINER
    RPCs because PostgREST sets the JWT claims on the DB session.

    A fresh client is intentional (per-user JWT isolation — a shared client
    with .postgrest.auth() would leak one user's token to another), but it
    reuses the shared HTTP transport so no connection pool is leaked.
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key, options=ClientOptions(httpx_client=_shared_http()))
    # Override PostgREST Authorization header so auth.uid() works in RPCs
    client.postgrest.auth(jwt)
    return client
