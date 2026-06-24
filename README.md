# 📄 ArXiV Explainer Bot

> Телеграм-бот, который принимает ссылку на научную статью с arxiv.org и возвращает структурированный разбор — на русском или английском — через LLM-провайдер на ваш выбор. Разворачивается на Ubuntu VPS за один скрипт.

---

## Что умеет бот

- **Принимает любой формат ссылки** — `arxiv.org/abs/...`, `arxiv.org/pdf/...`, просто ID вроде `2406.12345`
- **Скачивает и читает PDF** прямо с сервера arxiv, без сохранения на диск
- **Анализирует статью** через один из 14 поддерживаемых LLM-провайдеров
- **Возвращает структурированный разбор** по семи разделам:
  - 💡 TL;DR — суть за 1–2 предложения
  - 🎯 Проблема — что решает работа
  - 🔬 Метод — ключевые технические идеи
  - 📊 Результаты — главные цифры и выводы
  - ⚠️ Ограничения — слабые стороны
  - 🌍 Почему это важно — значение для области
  - 🏷️ Ключевые слова
- **Управляется прямо из Telegram** — владелец меняет провайдера, модель, ключ и язык через inline-кнопки без выхода на сервер

---

## Поддерживаемые LLM-провайдеры

| Провайдер | Tier | Примечание |
|-----------|------|-----------|
| **Google Gemini** | ✅ бесплатно | 15 req/min, 1M tokens/day |
| **Groq** | ✅ бесплатно | 14 400 req/day |
| **Cerebras** | ✅ бесплатно | быстрый инференс |
| **SambaNova** | ✅ бесплатно | бесплатный tier |
| **OpenRouter** | ✅ есть бесплатные | 46+ бесплатных моделей |
| **Anthropic** | 💰 платно | Claude Haiku / Sonnet |
| **OpenAI** | 💰 платно | GPT-4o / o-series |
| **DeepSeek** | 💰 от $0.07/M | очень дёшево |
| **Mistral AI** | 💰 платно | open-weight модели |
| **Together AI** | 💰 платно | $1 при регистрации |
| **xAI (Grok)** | 💰 платно | — |
| **Perplexity** | 💰 платно | — |
| **Cohere** | 💰 платно | trial без карты |
| **Nvidia NIM** | 💰 платно | 1000 бесплатных запросов |

Список моделей загружается **динамически** из API провайдера при каждой настройке — всегда актуален.

Для бесплатного старта рекомендуется **Google Gemini** или **Groq**.  
**OpenRouter** даёт доступ к 46+ бесплатным моделям через один ключ.

---

## Быстрый старт на VPS (Ubuntu 22.04+)

```bash
git clone https://github.com/YOUR_USERNAME/arxiv-explainer-bot
cd arxiv-explainer-bot
chmod +x setup.sh
sudo ./setup.sh
```

Скрипт автоматически:
1. Установит системные зависимости (`python3`, `pip`, `git`)
2. Создаст виртуальное окружение `.venv`
3. Установит Python-пакеты из `requirements.txt`
4. Запустит интерактивный мастер настройки
5. Предложит зарегистрировать systemd-сервис для автозапуска
6. Установит команду `arxiv-bot` глобально и сразу откроет панель управления

---

## Панель управления (CLI)

После установки вся работа с ботом ведётся через одну команду:

```bash
arxiv-bot
```

Панель остаётся открытой, пока вы сами не выберете «Выход»:

```
╔══════════════════════════════════════╗
║     ArXiV Explainer Bot — CLI       ║
╚══════════════════════════════════════╝

  Статус бота: ● работает

  [1] Остановить бота
  [2] Настроить (wizard)
  [3] Показать логи
  [4] Проверить и установить обновления

  [0] Выход
```

После установки обновлений бот и сама панель перезапускаются автоматически.

---

## Admin-панель в Telegram

Владелец бота управляет всем прямо из чата — без выхода на сервер.

```
/admin
```

```
🛠 Панель администратора

Провайдер: Google Gemini
Модель: gemini-2.0-flash
Язык: Русский 🇷🇺

[⚙️ Провайдер / Модель]
[🔑 API-ключ]    [🌍 Язык]
[📊 Статус]      [📋 Логи]
[🔄 Проверить и установить обновления]
[♻️ Перезапуск]
```

**Возможности admin-панели:**
- Смена провайдера → список провайдеров → ввод ключа → живой список моделей → выбор
- Модели загружаются с пагинацией (46+ бесплатных на OpenRouter)
- На каждом шаге есть кнопки «Назад» и «Оставить текущий»
- API-ключ удаляется из чата сразу после ввода
- Обновления: `git pull` + `pip install` + автоперезапуск одной кнопкой
- После перезапуска бот отправляет сообщение `✅ Бот запущен и готов к работе`

**Права доступа:**
- Первый пользователь, отправивший `/start`, автоматически становится владельцем
- Обычные пользователи видят только возможность отправлять ссылки
- Для проверки своего Telegram ID: `/myid`

---

## Локальный запуск (macOS / Linux)

```bash
# Клонировать репозиторий
git clone https://github.com/YOUR_USERNAME/arxiv-explainer-bot
cd arxiv-explainer-bot

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Настроить бота
python3 -m bot.wizard

# Открыть панель управления
python3 -m bot.cli
```

---

## Настройка: мастер конфигурации

Мастер запускается автоматически при `setup.sh` или вручную:

```bash
python3 -m bot.wizard
```

Шаги мастера:

1. **Telegram Bot Token** — получить у [@BotFather](https://t.me/BotFather) командой `/newbot`
2. **Провайдер LLM** — выбрать из 14 провайдеров
3. **API-ключ** — мастер проверяет ключ; для OpenRouter показывает текущий баланс и расход
4. **Модель** — загружается живой список с разбивкой на ✅ бесплатные / 💰 платные, с пагинацией
5. **Язык ответов** — русский или английский
6. **Telegram ID** — для доступа к `/admin` (или пропустить — назначится автоматически при первом `/start`)

Конфиг сохраняется в `config.json` (в `.gitignore`).

### Где получить API-ключи

| Провайдер | Ссылка |
|-----------|--------|
| Google Gemini | https://aistudio.google.com/apikey |
| Groq | https://console.groq.com/keys |
| Cerebras | https://cloud.cerebras.ai/ |
| SambaNova | https://cloud.sambanova.ai/ |
| OpenRouter | https://openrouter.ai/keys |
| Anthropic | https://console.anthropic.com/ |
| OpenAI | https://platform.openai.com/api-keys |
| DeepSeek | https://platform.deepseek.com/api_keys |
| Mistral AI | https://console.mistral.ai/ |
| Together AI | https://api.together.ai/settings/api-keys |
| xAI (Grok) | https://console.x.ai/ |
| Perplexity | https://www.perplexity.ai/settings/api |
| Cohere | https://dashboard.cohere.com/api-keys |
| Nvidia NIM | https://build.nvidia.com/ |

---

## Использование бота

Просто отправьте боту ссылку на статью в любом формате:

```
https://arxiv.org/abs/2406.12345
https://arxiv.org/pdf/2406.12345
https://arxiv.org/pdf/2406.12345v2
2406.12345
```

### Команды

| Команда | Доступ | Описание |
|---------|--------|----------|
| `/start` | все | Приветствие и инструкция |
| `/help` | все | Справка |
| `/status` | все | Текущий провайдер и модель |
| `/myid` | все | Показать свой Telegram ID |
| `/admin` | владелец | Открыть панель управления |

---

## Управление сервисом (systemd)

```bash
# Статус
sudo systemctl status arxiv-bot

# Перезапуск
sudo systemctl restart arxiv-bot

# Остановка
sudo systemctl stop arxiv-bot

# Логи в реальном времени
sudo journalctl -u arxiv-bot -f

# Логи за последний час
sudo journalctl -u arxiv-bot --since "1 hour ago"
```

### Установить сервис вручную (если пропустили при setup.sh)

```bash
sudo sed \
  -e "s|REPLACE_USER|$USER|g" \
  -e "s|REPLACE_WORKDIR|$(pwd)|g" \
  arxiv_bot.service > /etc/systemd/system/arxiv-bot.service

sudo systemctl daemon-reload
sudo systemctl enable arxiv-bot
sudo systemctl start arxiv-bot
```

---

## Структура проекта

```
arxiv-explainer-bot/
├── bot/
│   ├── main.py            # точка входа, polling loop, startup notification
│   ├── handlers.py        # обработчики Telegram-сообщений
│   ├── admin.py           # Telegram admin-панель (inline-кнопки)
│   ├── arxiv_client.py    # скачивание PDF и метаданных
│   ├── llm_client.py      # клиенты LLM-провайдеров (OpenAI-compat + Anthropic)
│   ├── model_fetcher.py   # async загрузка моделей из API провайдеров
│   ├── formatter.py       # форматирование в Telegram MarkdownV2
│   ├── config.py          # 14 провайдеров, чтение/запись config.json
│   ├── wizard.py          # CLI-мастер настройки (stdlib only)
│   └── cli.py             # постоянная CLI-панель (команда arxiv-bot)
├── config.json            # ваш конфиг (создаётся wizard'ом, не в git)
├── config.example.json    # шаблон конфига
├── arxiv_bot.service      # шаблон systemd unit-файла
├── setup.sh               # скрипт установки
└── requirements.txt
```

---

## Устранение неполадок

**Бот не отвечает на ссылки**
Убедитесь, что сообщение содержит `arxiv.org/abs/`, `arxiv.org/pdf/` или голый ID вида `2406.12345`.

**`/admin` не работает**
Отправьте `/myid` и сравните с `admin_user_id` в `config.json`. Если не совпадает — перенастройте через `python3 -m bot.wizard` (шаг 6) или исправьте вручную:
```bash
# Быстро узнать сохранённый ID
grep admin_user_id /root/arxiv-explainer-bot/config.json
```

**`❌ Не удалось скачать статью`**
ArXiv иногда временно недоступен. Подождите минуту. Проверьте интернет: `curl -I https://arxiv.org`.

**`❌ LLM вернул некорректный ответ`**
Смените модель через `/admin` → `⚙️ Провайдер / Модель`. Некоторые лёгкие модели плохо следуют инструкции возвращать JSON.

**Провайдер возвращает 429 (rate limit)**
Бот автоматически повторяет запрос если `retry_after ≤ 60 сек`. Если ждать дольше — попробуйте другую модель или провайдера.

**Сервис не запускается**
```bash
sudo journalctl -u arxiv-bot -n 50
```
Чаще всего причина — неверный токен или API-ключ. Перенастройте: `arxiv-bot` → `[2] Настроить`.

**Как убедиться, что сервис перезапускается после ребута**
```bash
sudo systemctl is-enabled arxiv-bot   # должно вернуть "enabled"
```

---

## Требования

- Python 3.11+
- Ubuntu 22.04+ (для VPS-деплоя) или любой современный Linux / macOS (для локального запуска)
- Telegram Bot Token — бесплатно от [@BotFather](https://t.me/BotFather)
- API-ключ одного из поддерживаемых провайдеров (Gemini, Groq, Cerebras, SambaNova — бесплатно)
