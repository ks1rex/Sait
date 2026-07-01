# Backend API (FastAPI, `backend/app/main.py`)

All routes live in `main.py` (~2100 lines, single file, not split into
routers except admin). Swagger/OpenAPI is available at `/docs` when running
locally (`uvicorn app.main:app --reload`).

## Core project flow

1. **`POST /upload`** — accepts PDF, stores it in the `uploads` bucket,
   `pdf_extract.py` (PyMuPDF/`fitz`) extracts text.
2. **`POST /extract`** — sends extracted text to DeepSeek using
   `backend/prompts/extraction_system_prompt.txt`; response is validated
   against `CalculationSpec` (`schemas.py`) and saved to `calculation_specs`.
3. **`GET /spec/{project_id}`** / **`PUT /spec/{project_id}`** — user
   reviews/edits the generated spec (frontend: `ReviewPage`).
4. **`POST /compute`** — `calc_engine.py` evaluates each step's formula via a
   sandboxed `asteval.Interpreter` (no AI call; spec is cached, not re-sent).
5. **`POST /generate`** — `docx_generator.py` builds the `.docx` per ГОСТ,
   LibreOffice headless converts to `.pdf`, result uploaded to `outputs`
   bucket.

## Alternate mode — no AI extraction

- **`POST /format-gost`** — takes ready-made text/document and formats it to
  ГОСТ directly, in `fixed_template` or `custom_template` mode (see
  `generation_modes`, migration 0004, and routing logic in `main.py`).
- **`POST /chat/{project_id}`** — chat endpoint for iteratively editing
  `custom_template` documents.

## Billing / access

- **`POST /redeem-code`** — redeems an access/top-up code.
- Paid operations deduct tokens via the `consume_tokens` RPC
  (`backend/app/billing.py`), costs from `TOKEN_COSTS`:
  - `format_gost` = 1
  - `fixed_template` = 2
  - `universal` = 3
  - `custom_template.minimal_edit` = 5
  - `custom_template.chat` = 1 per message
- `InsufficientTokensError` is handled by a global exception handler in
  `main.py`.

## Admin

- **`/admin/*`** — implemented in `backend/app/admin.py` +
  `backend/app/admin_templates.py` (the only routes split out of `main.py`).

## Auth

Supabase JWT is verified in `backend/app/auth.py` via `SUPABASE_JWT_SECRET`
(passed on every authenticated request).
