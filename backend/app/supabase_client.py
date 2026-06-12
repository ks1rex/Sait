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


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        # Bypass system SOCKS proxy (Windows registry) that breaks httpx
        http = httpx.Client(trust_env=False, http2=True)
        _client = create_client(url, key, options=ClientOptions(httpx_client=http))
    return _client


def get_supabase_as_user(jwt: str) -> Client:
    """
    Return a Supabase client whose PostgREST calls are authenticated with
    the given user JWT.  auth.uid() resolves correctly inside SECURITY DEFINER
    RPCs because PostgREST sets the JWT claims on the DB session.
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    http = httpx.Client(trust_env=False, http2=True)
    client = create_client(url, key, options=ClientOptions(httpx_client=http))
    # Override PostgREST Authorization header so auth.uid() works in RPCs
    client.postgrest.auth(jwt)
    return client
