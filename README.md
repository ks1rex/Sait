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
# Создать frontend/.env.local:
# VITE_API_URL=http://localhost:8000

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
    calc_engine.py       — движок последовательных вычислений
    docx_generator.py    — генерация отчёта по ГОСТ
    supabase_client.py   — клиент Supabase (service role)
  requirements.txt
  Dockerfile
  .env.example
/frontend                — React + Vite + Tailwind SPA
  /src
    /pages               — LoginPage, DashboardPage, NewProjectPage, AdminPage...
    /contexts            — AuthContext, TokenContext
    /components          — Layout, Toast, RedeemModal...
  vercel.json
/supabase
  /migrations            — SQL миграции схемы БД
/.github/workflows
  deploy-frontend.yml    — GitHub Actions: build + deploy to gh-pages
render.yaml              — Render.com: Docker web service config
```
