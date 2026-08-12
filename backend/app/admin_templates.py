"""Admin endpoints for editing fixed_template specs (DB override > disk file)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .admin import AdminUser
from .calc_engine import CalcError, run_calculation
from .schemas import CalculationSpec
from .supabase_client import get_supabase

router = APIRouter(prefix="/admin/templates", tags=["admin"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_MANIFEST_PATH = _TEMPLATES_DIR / "manifest.json"


class TemplateUpdateRequest(BaseModel):
    spec: dict[str, Any]
    display_name: str


def _manifest() -> list[dict]:
    if not _MANIFEST_PATH.exists():
        return []
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _manifest_entry(template_id: str) -> dict:
    entry = next((item for item in _manifest() if item.get("id") == template_id), None)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                             detail={"error": f"Шаблон '{template_id}' не найден в manifest.json"})
    return entry


def _get_override(template_id: str) -> dict | None:
    db = get_supabase()
    result = (
        db.table("gost_template_overrides")
        .select("spec, display_name, updated_at")
        .eq("template_id", template_id)
        .execute()
    )
    return result.data[0] if result.data else None


@router.get("")
async def list_templates(admin: AdminUser):
    overrides = {
        row["template_id"]: row
        for row in get_supabase().table("gost_template_overrides").select("template_id").execute().data
    }
    return [
        {
            "id": item["id"],
            "title": item.get("title", ""),
            "has_override": item["id"] in overrides,
            "source": "override" if item["id"] in overrides else "file",
        }
        for item in _manifest()
    ]


@router.get("/{template_id}")
async def get_template(template_id: str, admin: AdminUser):
    entry = _manifest_entry(template_id)
    override = _get_override(template_id)
    if override:
        return {"spec": override["spec"], "source": "override"}

    spec_path = _TEMPLATES_DIR / "specs" / entry.get("spec_file", "")
    if not spec_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                             detail={"error": f"Файл спецификации для '{template_id}' не найден"})
    return {"spec": json.loads(spec_path.read_text(encoding="utf-8")), "source": "file"}


@router.put("/{template_id}")
async def update_template(template_id: str, body: TemplateUpdateRequest, admin: AdminUser):
    _manifest_entry(template_id)  # 404 if unknown template

    # A bad formula saved here doesn't fail here — it fails at /compute, for
    # every user of the template, with no hint of where it came from. Dry-run
    # the engine on the incoming spec (input_data carries default values, so it
    # computes end-to-end) and refuse to store one that can't be calculated.
    try:
        run_calculation(CalculationSpec.model_validate(body.spec))
    except CalcError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                             detail={"error": str(exc), "step_id": exc.step_id})
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                             detail={"error": f"Спецификация не проходит проверку расчётом: {exc}"})

    db = get_supabase()
    db.table("gost_template_overrides").upsert({
        "template_id": template_id,
        "display_name": body.display_name,
        "spec": body.spec,
        "updated_by": admin["user_id"],
    }, on_conflict="template_id").execute()
    return {"spec": body.spec, "source": "override"}


@router.delete("/{template_id}/override")
async def delete_override(template_id: str, admin: AdminUser):
    _manifest_entry(template_id)
    get_supabase().table("gost_template_overrides").delete().eq("template_id", template_id).execute()
    return {"ok": True}
