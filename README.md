# GOST Calculator

Веб-сервис для автоматического оформления студенческих расчётных работ по ГОСТ.

Студент загружает PDF с заданием — сервис извлекает текст, строит структурированную
спецификацию расчёта через DeepSeek API, выполняет вычисления и генерирует готовый
`.docx` / `.pdf` отчёт.

**Продакшен:**
- Frontend: https://ks1rex.github.io/Sait/
- Backend API: https://sait-p07q.onrender.com

## Стек

| Слой | Технологии |
|------|------------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI | DeepSeek API (`deepseek-v4-flash`, OpenAI-совместимый эндпоинт) |
| DB / Auth / Storage | Supabase |
| PDF → текст | PyMuPDF |
| Расчёты | asteval (безопасный вычислитель Python-выражений) |
| Генерация документов | python-docx + LibreOffice headless (docx → pdf) |
| Frontend | React + Vite + Tailwind |

## Деплой

| Сервис | Платформа | Триггер |
|--------|-----------|---------|
| Frontend | GitHub Pages | пуш в `master` (папка `frontend/`) |
| Backend | Render.com (Docker) | пуш в `master` (папка `backend/`) |

## Локальный запуск

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Заполнить .env: DEEPSEEK_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET

uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

### Backend через Docker

```bash
cd backend
docker build -t gost-calc-backend .
docker run -p 8000:8000 --env-file .env gost-calc-backend
```

### Frontend

```bash
cd frontend
npm install
# Создать frontend/.env.local на основе frontend/.env.example:
# VITE_API_BASE_URL=http://localhost:8000
# VITE_SUPABASE_URL=https://<project-ref>.supabase.co
# VITE_SUPABASE_ANON_KEY=<anon-key>

npm run dev
```

## Структура проекта

```
/backend
  /app
    main.py              — FastAPI приложение, роуты
    ai_provider.py       — обёртка над DeepSeek/OpenAI
    auth.py              — JWT-верификация, Supabase auth
    admin.py             — роуты /admin/*
    billing.py           — токены, списание, коды доступа
    schemas.py           — Pydantic-модели (CalculationSpec и др.)
    pdf_extract.py       — извлечение текста из PDF
    calc_engine.py       — движок последовательных вычислений (multi-pass)
    docx_generator.py    — генерация отчёта по ГОСТ (python-docx)
    docx_md_converter.py — конвертация Markdown → docx-параграфы
    gost_styles.py       — стили ГОСТ для python-docx
    supabase_client.py   — клиент Supabase (service role)
  /prompts
    extraction_system_prompt.txt — системный промпт для DeepSeek
  requirements.txt
  Dockerfile
  smoke_test.py          — 17 автоматических проверок (health, auth, compute...)
  .env.example
/frontend                — React + Vite + Tailwind SPA
  /src
    /pages               — LoginPage, DashboardPage, NewProjectPage,
                           ReviewPage, ResultPage, ChatPage,
                           FormatGostPage, AdminPage
    /contexts            — AuthContext, TokenContext
    /components          — Layout, Toast, RedeemModal,
                           InsufficientTokensModal, FileDropZone,
                           StatusBadge, ProtectedRoute
  vercel.json            — SPA rewrite-правила (на случай деплоя на Vercel)
  .env.example
/supabase
  /migrations            — SQL-миграции схемы БД (0001–0010)
/.github/workflows
  deploy-frontend.yml    — GitHub Actions: build + deploy to gh-pages
render.yaml              — Render.com: Docker web service config
```
