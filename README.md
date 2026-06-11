# Coursework GOST Calculator

Веб-сервис для автоматического оформления студенческих расчётных работ по ГОСТ.

Студент загружает PDF с заданием — сервис извлекает текст, строит структурированную
спецификацию расчёта через DeepSeek API, выполняет вычисления и генерирует готовый
`.docx` / `.pdf` отчёт.

Подробная документация по архитектуре и roadmap: [CLAUDE.md](CLAUDE.md)

## Стек

| Слой | Технологии |
|------|------------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI | DeepSeek API (`deepseek-v4-flash`, OpenAI-совместимый эндпоинт) |
| DB / Auth / Storage | Supabase |
| PDF → текст | PyMuPDF |
| Расчёты | asteval (безопасный вычислитель Python-выражений) |
| Генерация документов | python-docx + LibreOffice headless (docx → pdf) |
| Frontend | React + Vite + Tailwind (в разработке) |

## Как запустить backend локально

### 1. Установить зависимости

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:
- `DEEPSEEK_API_KEY` — ключ DeepSeek API
- `SUPABASE_URL` — URL вашего проекта Supabase
- `SUPABASE_SERVICE_ROLE_KEY` — service role key из настроек Supabase
- `SUPABASE_JWT_SECRET` — JWT secret из настроек Supabase

### 3. Запустить сервер

```bash
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs  
ReDoc: http://localhost:8000/redoc

### Запуск через Docker

```bash
cd backend
docker build -t gost-calc-backend .
docker run -p 8000:8000 --env-file .env gost-calc-backend
```

## Структура проекта

```
/backend
  /app
    main.py            — FastAPI приложение, роуты
    ai_provider.py     — обёртка над DeepSeek/OpenAI
    schemas.py         — Pydantic-модели (CalculationSpec и др.)
    pdf_extract.py     — извлечение текста из PDF
    calc_engine.py     — движок последовательных вычислений
    docx_generator.py  — генерация отчёта по ГОСТ
    supabase_client.py — клиент Supabase (service role)
  requirements.txt
  Dockerfile
  .env.example
/frontend              — React + Vite SPA (в разработке)
/supabase
  /migrations          — SQL миграции схемы БД
/docs
  calculation_spec_schema.json  — JSON Schema спецификации расчёта
  extraction_prompt.md          — промпт для DeepSeek
```
