"""
Token billing: costs, consumption, and error types.
"""
from __future__ import annotations

import re

TOKEN_COSTS: dict[str, int] = {
    "format_gost":                   1,
    "custom_template.format_only":   1,
    "fixed_template":                2,
    "universal":                     3,
    "custom_template.minimal_edit":  5,
    "custom_template.chat":          1,   # per message
}


def get_token_cost(generation_mode: str, sub_mode: str | None = None) -> int:
    key = f"{generation_mode}.{sub_mode}" if sub_mode else generation_mode
    return TOKEN_COSTS.get(key, TOKEN_COSTS.get(generation_mode, 1))


class InsufficientTokensError(Exception):
    def __init__(self, required: int, balance: int) -> None:
        self.required = required
        self.balance = balance
        super().__init__(f"insufficient_tokens: need {required}, have {balance}")


_NEED_HAVE_RE = re.compile(r"need=(\d+)\s+have=(\d+)")


def consume_tokens(
    user_client,
    amount: int,
    reason: str,
    project_id: str | None = None,
) -> None:
    """
    Call RPC consume_tokens via a user-JWT Supabase client.
    Raises InsufficientTokensError on 'insufficient_tokens' PostgreSQL exception.
    Raises any other exception as-is.
    """
    try:
        user_client.rpc(
            "consume_tokens",
            {
                "p_amount": amount,
                "p_reason": reason,
                "p_project_id": project_id,
            },
        ).execute()
    except Exception as exc:
        msg = str(exc)
        if "insufficient_tokens" in msg:
            m = _NEED_HAVE_RE.search(msg)
            required = int(m.group(1)) if m else amount
            balance = int(m.group(2)) if m else 0
            raise InsufficientTokensError(required=required, balance=balance) from exc
        raise
