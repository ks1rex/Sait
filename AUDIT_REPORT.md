# Аудит проекта — отчёт

Дата: 2026-06-12. Полный аудит backend (FastAPI), frontend (React/Vite),
Supabase-схемы, конфигурации и безопасности.

Severity: **critical** — эксплуатируемая уязвимость / потеря денег или данных;
**high** — серьёзный баг или дыра, проявляется в реальных сценариях;
**medium** — баг/риск в краевых случаях; **low** — качество кода, гигиена.

---

## Категория 1. Безопасность — секреты и конфигурация

| # | Severity | Файл | Проблема | Что сделано |
|---|----------|------|----------|-------------|
| 1.1 | medium | `backend/app/main.py:47` | CORS по умолчанию `*` при `allow_credentials=True` — невалидная по спецификации комбинация; в проде при незаданной переменной открывались все origin'ы. | Дефолт заменён на `http://localhost:5173,http://localhost:3000`; origin'ы триммируются; при явном `*` пишется warning в лог и credentials отключаются. |
| 1.2 | high | `backend/Dockerfile`, `backend/app/ai_provider.py` | Системный промпт извлечения лежал в `docs/` (вне Docker-контекста `./backend`) — в продакшен-образ не попадал, и AI работал на слабом fallback-промпте из 3 строк. Качество извлечения спецификации в проде деградировало молча. | Промпт перемещён в `backend/prompts/extraction_system_prompt.txt`, добавлен `COPY prompts/` в Dockerfile; загрузчик проверяет оба пути (новый и легаси `docs/`). |
| 1.3 | low | `.gitignore` | Не игнорировались: `*.log` (uvicorn-логи в рабочей копии), `test_output/`, `backend/acceptance_out/`, `supabase/.temp/`, `frontend/supabase/`. Сгенерированные артефакты `test_output/*.docx/pdf` были закоммичены. | Добавлены правила в `.gitignore`; `test_output/*` удалён из индекса (`git rm --cached`). |
| 1.4 | ok | git history | Проверено `git log -p` по `.env`-файлам и поиском `sk-` по всей истории — секреты в историю не попадали. `.env` обоих приложений не отслеживаются. | Без изменений. |
| 1.5 | ok | исходники | Все секреты читаются из `os.environ` / `import.meta.env`; хардкода ключей нет. Захардкоженный Supabase URL в CI-workflow — публичное значение, не секрет. | Без изменений. |

Проверка: рестарт uvicorn, smoke-тест `backend/smoke_test.py` (создан в рамках
аудита, 17 проверок: /health, /me c auth и без, /templates, /redeem-code,
/upload (валидный/битый PDF/битый режим), /spec свой-чужой, /compute без spec,
/format-gost, /admin/* для админа и не-админа) — все OK. Vite dev-сервер
поднимается, отдаёт 200.

---

## Категория 2. Безопасность — Auth и RLS

| # | Severity | Файл | Проблема | Что сделано |
|---|----------|------|----------|-------------|
| 2.1 | critical | `supabase/migrations/0001_init.sql:128` (политика profiles) | RLS-политика `profiles: update own` фиксировала `has_access`/`unlimited_access`/`is_admin`, но **не** `token_balance`. Любой авторизованный пользователь мог прямым PATCH'ем через публичный anon-key выставить себе любой баланс токенов — полный обход биллинга. | Миграция `0009_rls_hardening.sql`: в `WITH CHECK` добавлено `token_balance = (old)`. Проверено атакой anon-key PATCH → теперь **HTTP 403** (было бы 200). |
| 2.2 | high | `supabase/migrations/0001_init.sql:140` (политика access_codes) | Политика `access_codes: select any unused` (`used_by IS NULL`) позволяла любому пользователю прочитать **все** неиспользованные коды (текст + номинал в токенах) прямым SELECT через anon-key и активировать их бесплатно. `redeem_code()` — SECURITY DEFINER и в этой политике не нуждается. | Миграция `0009`: политика заменена на `used_by = auth.uid()` (видишь только свои активированные). Проверено: SELECT неиспользованных → пустой список. |
| 2.3 | medium | `backend/app/auth.py:44` | `_decode_jwt` брал `alg` из заголовка токена и передавал в `jwt.decode` против JWKS-ключей без allowlist — потенциальная algorithm-confusion атака (подмена alg). | Добавлен allowlist: для JWKS-ветки разрешены только `ES256`/`RS256` (асимметричные); прочее → JWTError. HS256 верифицируется отдельной веткой по shared-secret. |
| 2.4 | low | `backend/app/admin.py:20`, `main.py:/me` | `.single()` бросает исключение при отсутствии строки профиля → необработанный 500 вместо 403/404. | Обёрнуто в try/except: нет профиля → не-админ (403) для admin-зависимости, 404 для `/me`. |
| 2.5 | ok | storage policies, backend ownership | Storage-политики `uploads`/`outputs` ограничивают доступ по `{user_id}/...` префиксу (`foldername[1] = auth.uid()`). Все backend-эндпоинты грузят проект через `_require_project(project_id, user_id)` с `.eq("user_id", ...)` — чужой `project_id` даёт 404. `require_admin` сверяет `is_admin` через service-role. DEV_MODE отсутствует. | Без изменений. |

Проверка: миграция применена (`supabase db push`), две RLS-атаки через anon-key
дают 403 / пустой результат, smoke-тест — все 17 проверок OK.

---

## Категория 3. Безопасность — обработка пользовательского контента

| # | Severity | Файл | Проблема | Что сделано |
|---|----------|------|----------|-------------|
| 3.1 | high | `backend/app/main.py:/format-gost` | Эндпоинт читал загруженный файл `await file.read()` **без лимита размера** (в отличие от `/upload`, где есть `_read_limited` 20 МБ) — DoS-вектор: можно прислать гигабайтный файл и исчерпать память. | Заменено на `_read_limited(file, "Документ")` (413 при превышении 20 МБ). |
| 3.2 | medium | `backend/app/main.py:/format-gost` | Токен списывался **до** чтения и валидации файла — за битый/оверсайз/не-docx файл пользователь терял токен. | Списание перенесено после успешного парсинга `Document(...)`; невалидный вход больше не тарифицируется. |
| 3.3 | medium | `backend/prompts/extraction_system_prompt.txt` | Текст из загруженного PDF шёл в промпт как данные в размеченных блоках, но модель не была явно проинструктирована игнорировать «команды» внутри текста задания — риск prompt injection (выдача системного промпта, отказ от JSON-формата). | В начало системного промпта добавлен блок «БЕЗОПАСНОСТЬ»: текст между маркерами — данные, не инструкции; любые указания внутри игнорировать; всегда отвечать валидным JSON. |
| 3.4 | ok | `backend/app/calc_engine.py` (asteval 1.0.9) | Проверено probing'ом: `__import__`, `open`, `exec`, `eval`, `getattr`, dunder-traversal (`__class__.__mro__.__subclasses__`) — все блокируются (NameError/AttributeError/RuntimeError). Ресурсные атаки (`9**9**9`, `'a'*10**12`, `[0]*10**12`) тоже пресекаются (RuntimeError/MemoryError). Дефолтный `Interpreter()` безопасен; `interp` — единственная добавленная функция. | Без изменений. |
| 3.5 | ok | `backend/app/main.py` (storage paths, soffice) | Path traversal невозможен: storage-пути строятся из `uuid` + фиксированного `file_type`, имя файла пользователя в путь не попадает (только в `original_name` как метаданные). LibreOffice вызывается списком аргументов без `shell=True`, во временной директории с `TemporaryDirectory()`. Magic-bytes валидация PDF выполняется через `fitz.open` (реальный парсинг), docx — через `Document()`. | Без изменений. |

Примечание: промпты `extract_variant_inputs` / `minimal_edit_rewrite` / chat также
принимают пользовательский контент; основной (полное извлечение спецификации)
усилен. Усиление остальных — низкий приоритет, в «Требует решения вручную» не выношу.

Проверка: рестарт uvicorn, smoke-тест (включая /format-gost валидный и
не-docx) — все OK.
