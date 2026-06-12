"""Admin-only router. All endpoints require is_admin=True in profiles."""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import get_current_user
from .supabase_client import get_supabase

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Admin dependency ──────────────────────────────────────────────────────────

async def _require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    db = get_supabase()
    result = (
        db.table("profiles")
        .select("is_admin")
        .eq("id", user["user_id"])
        .single()
        .execute()
    )
    if not result.data or not result.data.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Требуются права администратора"},
        )
    return user


AdminUser = Annotated[dict, Depends(_require_admin)]


# ── Request models ────────────────────────────────────────────────────────────

class AdjustTokensRequest(BaseModel):
    amount: int
    reason: str


class SetFlagRequest(BaseModel):
    flag: str
    value: bool


class GenerateCodesRequest(BaseModel):
    count: int = Field(ge=1, le=100)
    tokens: int = Field(ge=1)
    prefix: str = "CODE"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _list_auth_users(db) -> list:
    """Fetch all users from Supabase Auth admin API."""
    try:
        result = db.auth.admin.list_users()
        if hasattr(result, "users"):
            return result.users or []
        if isinstance(result, list):
            return result
        return []
    except Exception:
        return []


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(admin: AdminUser):
    """All users: auth email merged with profiles (balance, flags)."""
    db = get_supabase()

    raw_users = _list_auth_users(db)
    user_map: dict[str, str] = {
        str(u.id): (getattr(u, "email", "") or "")
        for u in raw_users
    }

    profiles = (
        db.table("profiles")
        .select("id, token_balance, unlimited_access, is_admin, created_at")
        .execute()
    )

    return [
        {
            "id": p["id"],
            "email": user_map.get(p["id"], ""),
            "token_balance": p["token_balance"],
            "unlimited_access": p["unlimited_access"],
            "is_admin": p["is_admin"],
            "created_at": p.get("created_at", ""),
        }
        for p in profiles.data
    ]


@router.post("/users/{user_id}/adjust-tokens")
async def adjust_tokens(user_id: str, body: AdjustTokensRequest, admin: AdminUser):
    """Add or subtract tokens (amount may be negative). Balance is clamped to 0."""
    db = get_supabase()

    profile = (
        db.table("profiles")
        .select("token_balance")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not profile.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": "Пользователь не найден"})

    current: int = profile.data["token_balance"]
    new_balance = max(0, current + body.amount)
    actual_change = new_balance - current

    db.table("profiles").update({"token_balance": new_balance}).eq("id", user_id).execute()

    if actual_change != 0:
        db.table("token_transactions").insert({
            "user_id": user_id,
            "amount": actual_change,
            "reason": f"admin: {body.reason}",
        }).execute()

    return {"new_balance": new_balance, "actual_change": actual_change}


@router.post("/users/{user_id}/set-flag")
async def set_flag(user_id: str, body: SetFlagRequest, admin: AdminUser):
    """Toggle unlimited_access or is_admin. Cannot remove own is_admin."""
    if body.flag not in ("unlimited_access", "is_admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": "Недопустимый флаг"})

    if body.flag == "is_admin" and not body.value and user_id == admin["user_id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": "Нельзя снять права администратора с себя"})

    db = get_supabase()
    db.table("profiles").update({body.flag: body.value}).eq("id", user_id).execute()
    return {"ok": True}


@router.post("/codes/generate")
async def generate_codes(body: GenerateCodesRequest, admin: AdminUser):
    """Generate N codes with given token value and optional prefix."""
    chars = string.ascii_uppercase + string.digits
    codes = [
        f"{body.prefix}-{''.join(random.choices(chars, k=8))}"
        for _ in range(body.count)
    ]

    db = get_supabase()
    db.table("access_codes").insert(
        [{"code": c, "tokens": body.tokens} for c in codes]
    ).execute()

    return {"codes": codes}


@router.get("/codes")
async def list_codes(
    admin: AdminUser,
    used: Optional[bool] = Query(default=None),
):
    """List all access codes. Filter: used=true (used only) / used=false (free only)."""
    db = get_supabase()

    query = db.table("access_codes").select("*").order("created_at", desc=True)
    if used is True:
        query = query.not_.is_("used_by", "null")
    elif used is False:
        query = query.is_("used_by", "null")

    result = query.execute()

    # Build email map for used codes only
    used_uids = list({row["used_by"] for row in result.data if row.get("used_by")})
    email_map: dict[str, str] = {}
    if used_uids:
        for u in _list_auth_users(db):
            uid = str(u.id)
            if uid in used_uids:
                email_map[uid] = getattr(u, "email", "") or ""

    return [
        {
            "id": row["id"],
            "code": row["code"],
            "tokens": row["tokens"],
            "used_by": row.get("used_by"),
            "used_by_email": email_map.get(row.get("used_by") or "", ""),
            "used_at": row.get("used_at"),
            "created_at": row.get("created_at"),
        }
        for row in result.data
    ]


@router.get("/stats")
async def get_stats(admin: AdminUser):
    """Aggregated platform statistics."""
    db = get_supabase()

    total_users = len(_list_auth_users(db))

    profiles = db.table("profiles").select("token_balance").execute()
    total_balance = sum(p["token_balance"] for p in profiles.data)

    neg_trans = db.table("token_transactions").select("amount").lt("amount", 0).execute()
    total_spent = sum(-t["amount"] for t in neg_trans.data)

    projects = db.table("projects").select("status, generation_mode").execute()
    by_status: dict[str, int] = {}
    by_mode: dict[str, int] = {}
    for p in projects.data:
        s = p.get("status") or "unknown"
        m = p.get("generation_mode") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1
        by_mode[m] = by_mode.get(m, 0) + 1

    ai_all = db.table("ai_usage").select("input_tokens, output_tokens").execute()
    ai_in_all = sum(r.get("input_tokens") or 0 for r in ai_all.data)
    ai_out_all = sum(r.get("output_tokens") or 0 for r in ai_all.data)

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    ai_7d = (
        db.table("ai_usage")
        .select("input_tokens, output_tokens")
        .gte("created_at", week_ago)
        .execute()
    )
    ai_in_7d = sum(r.get("input_tokens") or 0 for r in ai_7d.data)
    ai_out_7d = sum(r.get("output_tokens") or 0 for r in ai_7d.data)

    return {
        "total_users": total_users,
        "total_token_balance": total_balance,
        "total_tokens_spent": total_spent,
        "projects_by_status": by_status,
        "projects_by_mode": by_mode,
        "ai_usage_all": {"input_tokens": ai_in_all, "output_tokens": ai_out_all},
        "ai_usage_7d": {"input_tokens": ai_in_7d, "output_tokens": ai_out_7d},
    }
