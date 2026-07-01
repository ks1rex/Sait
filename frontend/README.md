# GOST Calculator — Frontend

React + Vite + Tailwind SPA. Часть проекта [GOST Calculator](../README.md).

## Локальный запуск

```bash
npm install
cp .env.example .env.local
# Заполнить .env.local
npm run dev
```

Переменные окружения (`.env.local`):

| Переменная | Описание |
|-----------|----------|
| `VITE_API_BASE_URL` | URL backend API (локально: `http://localhost:8000`) |
| `VITE_SUPABASE_URL` | URL Supabase-проекта |
| `VITE_SUPABASE_ANON_KEY` | Публичный anon-ключ Supabase |

## Сборка

```bash
npm run build   # собирает в dist/
npm run preview # превью продакшен-сборки
```

## Деплой

GitHub Actions автоматически собирает и деплоит на GitHub Pages при пуше в `master`
(папка `frontend/`). Конфиг: [`../.github/workflows/deploy-frontend.yml`](../.github/workflows/deploy-frontend.yml).

## Страницы

| Маршрут | Страница | Описание |
|---------|----------|----------|
| `/` | `LoginPage` | Вход / регистрация |
| `/dashboard` | `DashboardPage` | История проектов |
| `/new` | `NewProjectPage` | Загрузка PDF / выбор режима |
| `/project/:id/review` | `ReviewPage` | Проверка и редактирование спецификации |
| `/project/:id/result` | `ResultPage` | Результат расчёта, скачивание |
| `/project/:id/chat` | `ChatPage` | AI-чат по документу |
| `/format-gost` | `FormatGostPage` | Форматирование текста по ГОСТ |
| `/admin` | `AdminPage` | Панель администратора |
