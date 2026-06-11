# CLAUDE.md — Coursework GOST Calculator

## Что это за проект

Веб-сервис для студентов: пользователь загружает PDF с заданием
(курсовая/контрольная/расчётно-графическая работа, содержащая методику,
формулы и индивидуальные исходные данные по варианту). Сервис:

1. Извлекает текст из PDF.
2. Через DeepSeek API строит структурированную **спецификацию расчёта**
   (JSON: входные данные, таблицы для интерполяции, последовательность
   формул-шагов).
3. Показывает пользователю экран проверки/редактирования спецификации —
   ОБЯЗАТЕЛЬНЫЙ шаг, без него ошибки AI попадут в финальный документ.
4. Python-движок последовательно вычисляет шаги, подставляя числа.
5. Генерируется отчёт по ГОСТ: .docx (через python-docx) и .pdf
   (конвертация LibreOffice headless).
6. Файлы и история проектов хранятся в Supabase Storage/DB.

Вдохновлён предыдущим проектом `ks1rex/Test3` (МедТест) — та же связка
Supabase auth/DB/storage + коды доступа для платных функций, но здесь
дополнительно есть свой Python backend (FastAPI), т.к. нужен вызов LLM
с серверным ключом и выполнение Python-кода (расчёты, генерация docx).

## Стек

- **Frontend**: React + Vite + Tailwind, без сборщика-монолита — простой SPA.
- **Backend**: Python 3.11, FastAPI, Uvicorn.
- **AI**: DeepSeek API (`deepseek-v4-flash`, OpenAI-совместимый эндпоинт
  `https://api.deepseek.com/v1`). Слой абстракции в `app/ai_provider.py`,
  чтобы можно было переключиться на Claude/другую модель через `.env`
  (Anthropic-совместимый эндпоинт DeepSeek: `https://api.deepseek.com/anthropic`).
- **DB / Auth / Storage**: Supabase (тот же проект-стиль, что в МедТесте).
- **PDF → текст**: PyMuPDF (`fitz`).
- **Расчётный движок**: безопасный вычислитель выражений (`asteval`),
  без `eval()`. Поддержка табличной интерполяции через `interp(table_id, x)`.
- **Генерация документов**: `python-docx` для .docx, `soffice --headless
  --convert-to pdf` для .pdf.

## Структура репозитория

```
/backend
  /app
    main.py            — FastAPI приложение, роуты
    ai_provider.py      — обёртка над DeepSeek/Claude
    schemas.py           — Pydantic-модели (CalculationSpec и т.д.)
    pdf_extract.py        — извлечение текста/таблиц из PDF
    calc_engine.py         — движок последовательных вычислений
    docx_generator.py       — генерация отчёта по ГОСТ
    supabase_client.py       — клиент Supabase (service role)
  requirements.txt
/frontend                       — React + Vite SPA
/supabase
  /migrations                    — SQL миграции схемы БД
/docs
  calculation_spec_schema.json   — JSON Schema спецификации расчёта
  extraction_prompt.md            — системный промпт для DeepSeek
```

## Этапы разработки (roadmap)

1. [ ] Supabase: применить миграцию `0001_init.sql`, настроить auth,
       создать buckets `uploads` и `outputs`.
2. [ ] Backend: каркас FastAPI, `/health`, аутентификация по Supabase JWT.
3. [ ] `/upload` — приём PDF, извлечение текста (`pdf_extract.py`),
       сохранение в Storage, запись в `projects`.
4. [ ] `/extract` — вызов DeepSeek по промпту из `docs/extraction_prompt.md`,
       валидация JSON по схеме, сохранение в `calculation_specs`.
5. [ ] Frontend: экран загрузки + экран проверки/редактирования спецификации
       (таблица input_data, список шагов с формулами — всё редактируемое).
6. [ ] `/compute` — `calc_engine.py` считает шаги по спецификации.
7. [ ] `/generate` — `docx_generator.py` собирает отчёт, конвертация в PDF,
       выгрузка в bucket `outputs`.
8. [ ] Личный кабинет: история проектов, скачивание файлов, лимиты по
       количеству AI-запросов в месяц (таблица `ai_usage`).
9. [ ] Сквозной тест на примере курсовой "Расчёт очистных сооружений"
       (есть PDF-эталон) — сравнить результат с оригиналом.
10. [ ] Деплой: backend на Render/Fly.io (Docker с LibreOffice), frontend
        на Vercel/GitHub Pages, Supabase prod.

## Конвенции

- Тексты интерфейса — на русском, код/переменные/коммиты — на английском.
- Все формулы в спецификации — Python-выражения с именами переменных
  (`Q_сут`, `Q_ср_час` и т.п.; разрешена кириллица в идентификаторах,
  `asteval` это поддерживает).
- Никаких "магических чисел" в формулах — только ссылки на `input_data`
  или результаты предыдущих шагов.
- Каждый шаг расчёта — отдельный объект с `id`, `formula`, `description`,
  `unit`, `rounding`.
- Не вызывать DeepSeek повторно без необходимости — кэшировать спецификацию
  в `calculation_specs`, пересчёт (`/compute`) идёт без обращения к AI.
- Секреты (`DEEPSEEK_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) — только в
  `.env`, никогда не коммитить. См. `.env.example`.
