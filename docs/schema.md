# Database schema (Supabase)

Migrations live in `supabase/migrations/0001`–`0011`. Read the actual migration
files for current column-level truth — this doc is a map of *what* each
migration adds, not a full DDL mirror, and RLS/columns can drift from memory.

## Migrations overview

| # | Purpose |
|---|---------|
| 0001 | init — base tables/project setup |
| 0002 | storage — `uploads` / `outputs` buckets |
| 0003 | `project_files` table |
| 0004 | `generation_modes` (adds `fixed_template` / `custom_template` modes used by `/format-gost`) |
| 0005 | `custom_template_task_path` |
| 0006 | tokens (billing balances) |
| 0007 | admin (admin tables/roles) |
| 0008 | RLS hardening |
| 0009 | billing atomicity (safe token consumption) |
| 0010 | `template_overrides` |
| 0011 | (see migration file for latest additions) |

## Key tables

- **`calculation_specs`** — stores the AI-extracted `CalculationSpec` JSON per
  project (validated against the Pydantic model in `backend/app/schemas.py`;
  JSON-shape reference: `docs/calculation_spec_schema.json`). Edited by the
  user via `GET/PUT /spec/{project_id}` before `/compute` runs.
- **`project_files`** — tracks uploaded/generated files per project.
- Token/billing tables (from migration 0006/0009) — balances consumed via the
  `consume_tokens` RPC (see `backend/app/billing.py`).
- Admin tables (migration 0007) — backs `backend/app/admin.py` routes.
- **`template_overrides`** (migration 0010) — per-user/project custom template
  overrides for `custom_template` generation mode.

## Storage buckets

- `uploads` — user-submitted PDFs (source of `/upload`).
- `outputs` — generated `.docx`/`.pdf` reports (source of `/generate`).

## RLS

Row-Level Security is enabled (hardened in migration 0008). Service-role
access (bypasses RLS) is used server-side via `backend/app/supabase_client.py`;
user-JWT Supabase clients are used for RLS-scoped operations (e.g. billing
RPCs in `backend/app/billing.py`).
