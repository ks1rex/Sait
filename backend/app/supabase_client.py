"""
Клиент Supabase с service-role ключом — используется backend'ом для
работы с БД и Storage в обход RLS (доступ к чужим записям всё равно
контролируется в коде эндпоинтов через project.user_id == current_user.id).
"""
from __future__ import annotations

import os

from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client
