# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Telegram-бот, который принимает ссылку на статью с arxiv.org и возвращает структурированный разбор через выбранный LLM-провайдер. Разворачивается на Ubuntu VPS за один скрипт (`setup.sh`).

**Стек:** Python 3.11+, `python-telegram-bot` v21 (async), `openai` SDK, `anthropic` SDK, `PyMuPDF`, `httpx`, `feedparser`

## Команды

```bash
# Установка зависимостей
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Настройка конфига (интерактивный wizard)
python3 -m bot.wizard

# Запуск бота
python3 -m bot.main

# Деплой на VPS (всё включено)
sudo ./setup.sh
```

## Архитектура

```
bot/
├── main.py          # точка входа, asyncio polling loop
├── handlers.py      # Telegram-хендлеры (команды и ссылки)
├── arxiv_client.py  # скачивание PDF + парсинг метаданных
├── llm_client.py    # абстракция над LLM-провайдерами
├── formatter.py     # форматирование в Telegram MarkdownV2
├── config.py        # чтение/запись config.json + константа PROVIDERS
└── wizard.py        # CLI-мастер настройки (только stdlib)
```

`config.json` создаётся wizard'ом и содержит `telegram_token`, `llm_provider`, `llm_model`, `llm_api_key`, `max_paper_pages`, `language`. Файл в `.gitignore`; шаблон — `config.example.json`.

## Ключевые технические детали

**Async везде:** `python-telegram-bot` v21 использует `asyncio` — весь бот async/await.

**LLM-провайдеры:** Два типа клиентов в `llm_client.py`:
- `OpenAICompatibleClient` — для Gemini, Groq, OpenRouter, OpenAI (openai SDK + кастомный `base_url`)
- `AnthropicClient` — только для Anthropic (anthropic SDK напрямую)

Список провайдеров и моделей хранится в `bot/config.py` как константа `PROVIDERS`.

**PDF-парсинг:** `fitz.open(stream=bytes, filetype="pdf")` — не сохранять на диск. Берём первые `max_paper_pages` страниц.

**Метаданные arxiv:** HTTP-запрос к `http://export.arxiv.org/api/query?id_list={arxiv_id}`, парсинг XML через `feedparser`.

**MarkdownV2:** Все спецсимволы `. ! ( ) [ ] { } # + - = | > ~ _ *` экранируются через `escape_md()` в `formatter.py`. Реализовывать первым делом — ломает всё остальное если неправильно.

**Длина сообщений:** Telegram ограничивает 4096 символов. Длинные ответы разбивать по границе блока (после закрывающего абзаца).

**LLM-промпт:** Системный промпт требует ответа строго в JSON с ключами `title`, `tldr`, `problem`, `method`, `results`, `limitations`, `why_it_matters`, `keywords`. При невалидном JSON — один retry с уточнённым промптом.

## Порядок реализации

1. `config.py` — PROVIDERS, чтение/запись JSON
2. `arxiv_client.py` — парсинг URL (`r'(\d{4}\.\d{4,5})(v\d+)?'`), PDF, метаданные
3. `llm_client.py` — клиенты, системный промпт
4. `formatter.py` — `escape_md()`, шаблон сообщения
5. `handlers.py` — `/start`, `/help`, `/status`, обработчик arxiv-ссылок
6. `main.py` — polling loop
7. `wizard.py` — CLI без сторонних библиотек, проверка токенов
8. `setup.sh` — apt, venv, wizard, systemd
