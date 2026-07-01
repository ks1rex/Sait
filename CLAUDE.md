# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это за проект

Веб-сервис для студентов: пользователь загружает PDF с заданием (курсовая/
контрольная/расчётно-графическая работа). Сервис извлекает текст, через
DeepSeek API строит структурированную спецификацию расчёта (JSON), даёт
пользователю проверить/отредактировать её, затем Python-движок вычисляет
шаги и генерирует отчёт по ГОСТ (.docx / .pdf).

**Продакшен:** Frontend — https://ks1rex.github.io/Sait/, Backend —
https://sait-p07q.onrender.com

Detailed docs: DB schema → @docs/schema.md, API routes → @docs/api.md.

---

## Backend (`backend/`) — Python 3.11, FastAPI

This is the service that owns the data (Supabase), the AI extraction, and
report generation. See @docs/api.md for the full route list and @docs/schema.md
for tables/migrations.

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env    # заполнить DEEPSEEK_API_KEY, SUPABASE_*
uvicorn app.main:app --reload     # http://localhost:8000, Swagger на /docs
python smoke_test.py              # 17 сквозных проверок (health, auth, compute...)
python acceptance_test.py
python verify_spec.py
python test_generate.py
```
Docker: `docker build -t gost-calc-backend . && docker run -p 8000:8000 --env-file .env gost-calc-backend`

### Ключевые модули (`backend/app/`)
- `main.py` — все роуты FastAPI, единый файл (кроме admin)
- `schemas.py` — Pydantic-модели, `CalculationSpec` (см. `docs/calculation_spec_schema.json`)
- `pdf_extract.py` — PyMuPDF (`fitz`)
- `calc_engine.py` — sandboxed `asteval.Interpreter`, формулы шагов ссылаются друг на друга по `step.id`; табличная интерполяция — `interp('table_id', x)`
- `docx_generator.py` / `docx_md_converter.py` / `gost_styles.py` — генерация .docx по ГОСТ; Jinja2-шаблоны (intro/conclusion) рендерятся через `SandboxedEnvironment` (untrusted, правятся пользователем)
- `ai_provider.py` — абстракция DeepSeek/OpenAI-совместимых эндпоинтов, `.env`: `AI_PROVIDER=deepseek|openai`; не вызывать LLM без нужды — спецификация кэшируется
- `auth.py` / `billing.py` — Supabase JWT, RPC `consume_tokens`
- `supabase_client.py` — клиент с service role key (обходит RLS)

---

## Frontend (`frontend/`) — React + Vite + Tailwind, standalone product

**Важно:** это отдельный, самостоятельный продукт со своей сборкой/деплоем —
НЕ портал "ebu.gubkin", просто клиент к этому же backend-у из этого репозитория.
Не смешивать его конвенции/структуру с backend-секцией выше.

```bash
cd frontend
npm install
npm run dev        # Vite dev server
npm run build       # tsc -b && vite build
npm run lint        # eslint
```
`frontend/.env.local`: `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.

Структура (`frontend/src/`): SPA без роутера-монолита — `pages/` (LoginPage,
DashboardPage, NewProjectPage, ReviewPage, ResultPage, ChatPage,
FormatGostPage, AdminPage), `contexts/` (AuthContext, TokenContext),
`lib/api.ts` — обёртка над backend API, `lib/supabase.ts` — клиент Supabase
(anon key).

---

## Деплой

Push в `master` триггерит: frontend → GitHub Pages
(`.github/workflows/deploy-frontend.yml`, только при изменениях в
`frontend/`), backend → Render.com Docker (`render.yaml`, только при
изменениях в `backend/`).

## Конвенции

- Тексты интерфейса — на русском, код/переменные/коммиты — на английском.
- Формулы в спецификации — Python-выражения, поддерживают кириллицу в именах
  переменных (`Q_сут` и т.п.) через asteval.
- Никаких "магических чисел" в формулах — только ссылки на `input_data` или
  результаты предыдущих шагов.
- Каждый шаг расчёта — объект с `id`, `formula`, `description`, `unit`, `rounding`.
- Секреты (`DEEPSEEK_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`)
  — только в `.env`, не коммитить.
