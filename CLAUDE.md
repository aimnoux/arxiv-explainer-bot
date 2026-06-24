# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Telegram-бот, который принимает ссылку на статью с arxiv.org и возвращает структурированный разбор через выбранный LLM-провайдер. Разворачивается на Ubuntu VPS за один скрипт. Управляется как через CLI-панель на сервере, так и через Telegram admin-панель.

**Стек:** Python 3.11+, `python-telegram-bot` v21 (async), `openai` SDK, `anthropic` SDK, `PyMuPDF`, `httpx`, `feedparser`

## Команды

```bash
# Деплой на VPS (venv, зависимости, wizard, systemd, CLI-команда)
sudo ./setup.sh

# CLI-панель управления (после деплоя)
arxiv-bot

# Локальный запуск
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m bot.wizard   # настройка (6 шагов)
python3 -m bot.main     # запуск бота
python3 -m bot.cli      # CLI-панель
```

## Архитектура

```
bot/
├── main.py            # polling loop, post_init startup notification
├── handlers.py        # Telegram-хендлеры; роутит текст через admin.handle_text первым
├── admin.py           # Telegram admin-панель (inline-кнопки, /admin команда)
├── arxiv_client.py    # скачивание PDF + парсинг метаданных
├── llm_client.py      # OpenAICompatibleClient + AnthropicClient
├── model_fetcher.py   # async httpx загрузка моделей из API провайдеров
├── formatter.py       # escape_md(), шаблон MarkdownV2, split_message()
├── config.py          # PROVIDERS (14 шт.), load_config(), save_config()
├── wizard.py          # CLI-мастер настройки (только stdlib, без внешних зависимостей)
└── cli.py             # постоянная CLI-панель (команда arxiv-bot)
```

`config.json` содержит: `telegram_token`, `llm_provider`, `llm_model`, `llm_api_key`, `max_paper_pages`, `language`, `admin_user_id`. Файл в `.gitignore`; шаблон — `config.example.json`.

## Провайдеры

14 провайдеров в `PROVIDERS` в `bot/config.py`. Каждый имеет поля `name`, `free`, `base_url`, `docs`.

**Два типа клиентов** в `llm_client.py`:
- `OpenAICompatibleClient` — все провайдеры кроме Anthropic (openai SDK + кастомный `base_url`)
- `AnthropicClient` — только Anthropic (anthropic SDK напрямую, `base_url=None`)

**Динамическая загрузка моделей:** `bot/model_fetcher.py` (async, httpx) используется admin-панелью. `bot/wizard.py` имеет собственную копию на stdlib (urllib) — это намеренно, wizard должен работать без pip-зависимостей.

**Фильтрация моделей** по провайдеру: исключаются embed/whisper/tts/dall-e/rerank. Gemini → только `gemini-*`, OpenAI → только gpt-4/gpt-3.5/o-series, Groq → только chat-модели.

**`_FULLY_FREE`** = `{"groq", "cerebras", "sambanova"}` — все модели этих провайдеров бесплатны. OpenRouter определяет бесплатность по `pricing.prompt == "0"`.

## Admin-панель (Telegram)

`bot/admin.py` — inline-keyboard панель только для владельца (`admin_user_id` в config.json).

**Доступ:** `is_admin(update)` проверяет `update.effective_user.id == load_config().get("admin_user_id")`. Bootstrap: первый `/start` автоматически становится владельцем если `admin_user_id` не задан.

**Callback data:** все кнопки используют префикс `adm:`. Критично: Telegram лимитирует `callback_data` до **64 байт**. Кнопки выбора модели используют `adm:mi:{index}` (индекс в flat-списке), а НЕ `adm:model:{id}` — длинные OpenRouter ID превышают лимит.

**Кэш моделей:** `_models_cache: dict[int, list[dict]]` — модульный dict в `admin.py`. Хранит загруженные модели по user_id. Это важно: `context.user_data` может сброситься между кликами пагинации, кэш — нет.

**Состояние многошагового flow** хранится в `context.user_data`:
- `awaiting`: `"key"` | `"key_only"` — ожидание текстового ввода API-ключа
- `temp_provider`: выбранный провайдер (ещё не сохранён)
- `temp_key`: введённый ключ (ещё не сохранён)
- `models`: загруженный список моделей (дублирует кэш)

**`handle_text`** в `admin.py` вызывается из `handlers.py` первым для всех текстовых сообщений — перехватывает ввод API-ключа, удаляет сообщение с ключом из чата.

**Startup notification:** `post_init` в `main.py` отправляет `✅ Бот запущен и готов к работе.` владельцу при каждом старте.

## CLI-панель (`cli.py`)

Постоянное меню, не закрывается само. Команда `arxiv-bot` устанавливается в `/usr/local/bin/` через `setup.sh`.

**Управление ботом:** если есть `/etc/systemd/system/arxiv-bot.service` — использует `systemctl`, иначе — PID-файл `.bot.pid`.

**Обновления:** `[4] Проверить и установить обновления` — один шаг: `git fetch`, сравнивает хэши, при наличии обновлений делает `git pull` + `pip install` + перезапускает сервис бота + перезапускает CLI через `os.execv`.

## Wizard (`wizard.py`)

**Только stdlib** (urllib, json, pathlib) — намеренно, чтобы работал до `pip install`.

**Порядок шагов:** Telegram token → провайдер → **API-ключ** → модели (загружаются с ключом) → язык → admin Telegram ID.

**Ключ перед моделями** — это намеренно: нужен для запроса `/models` у провайдера.

**OpenRouter баланс:** после валидации ключа вызывает `GET /api/v1/key` и показывает `usage`, `usage_daily`, `usage_monthly`, `limit`, `limit_remaining`. Поле `rate_limit` в ответе — deprecated, всегда возвращает `-1`, игнорируется.

**Валидация ключа** возвращает `"ok"` | `"invalid"` | `"unreachable"`. При `"unreachable"` сохраняет ключ с предупреждением (не блокирует).

## Ключевые технические детали

**MarkdownV2:** все спецсимволы `. ! ( ) [ ] { } # + - = | > ~ _ *` экранируются через `escape_md()` в `formatter.py`. Admin-панель использует HTML parse_mode (проще, не требует экранирования).

**PDF-парсинг:** `fitz.open(stream=bytes, filetype="pdf")` — не сохранять на диск.

**LLM-промпт:** требует ответа строго в JSON с ключами `title`, `tldr`, `problem`, `method`, `results`, `limitations`, `why_it_matters`, `keywords`. При невалидном JSON — один retry. При 429 rate limit — авторетрай если `retry_after ≤ 60 сек`.

**Длина сообщений:** Telegram ограничивает 4096 символов, `split_message()` разбивает по границе абзаца.

**Порядок хендлеров в `main.py`:** важен. `MessageHandler` для текста вызывает `admin.handle_text` первым (перехват ввода ключа), затем обрабатывает arxiv-ссылки.
