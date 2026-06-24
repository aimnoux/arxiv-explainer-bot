# 📄 ArXiv Explainer Bot

> Телеграм-бот, который принимает ссылку на научную статью с arxiv.org и возвращает её структурированный разбор — на русском или английском — через LLM-провайдер на ваш выбор.

---

## Что умеет бот

- **Принимает любой формат ссылки** — `arxiv.org/abs/...`, `arxiv.org/pdf/...`, просто ID вроде `2406.12345`
- **Скачивает и читает PDF** прямо с сервера arxiv, без сохранения на диск
- **Анализирует статью** через один из пяти поддерживаемых LLM-провайдеров
- **Возвращает структурированный разбор** по семи разделам:
  - 💡 TL;DR — суть за 1–2 предложения
  - 🎯 Проблема — что решает работа
  - 🔬 Метод — ключевые технические идеи
  - 📊 Результаты — главные цифры и выводы
  - ⚠️ Ограничения — слабые стороны
  - 🌍 Почему это важно — значение для области
  - 🏷️ Ключевые слова

---

## Поддерживаемые LLM-провайдеры

| Провайдер | Бесплатный tier | Рекомендуемая модель |
|-----------|----------------|----------------------|
| **Google Gemini** | ✅ 15 req/min, 1M tokens/day | Gemini 2.0 Flash |
| **Groq** | ✅ 14 400 req/day | Llama 3.3 70B |
| **OpenRouter** | ✅ есть бесплатные модели | Gemini 2.0 Flash (free) |
| **Anthropic** | 💰 платно | Claude Haiku 4.5 |
| **OpenAI** | 💰 платно | GPT-4o Mini |

Для бесплатного старта рекомендуется **Google Gemini** — щедрый лимит, высокое качество, поддержка длинных документов.

---

## Быстрый старт на VPS (Ubuntu 22.04+)

```bash
git clone https://github.com/YOUR_USERNAME/arxiv-explainer-bot
cd arxiv-explainer-bot
chmod +x setup.sh
sudo ./setup.sh
```

Скрипт автоматически:
1. Установит системные зависимости (`python3.11`, `pip`, `git`)
2. Создаст виртуальное окружение `.venv`
3. Установит Python-пакеты из `requirements.txt`
4. Запустит интерактивный мастер настройки
5. Предложит зарегистрировать systemd-сервис для автозапуска

---

## Локальный запуск (macOS / Linux)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/YOUR_USERNAME/arxiv-explainer-bot
cd arxiv-explainer-bot

# 2. Создать виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить бота
python3 -m bot.wizard

# 5. Запустить
python3 -m bot.main
```

---

## Настройка: мастер конфигурации

Мастер запускается автоматически при `setup.sh` или вручную:

```bash
python3 -m bot.wizard
```

Мастер проведёт вас через пять шагов:

1. **Telegram Bot Token** — получить у [@BotFather](https://t.me/BotFather) командой `/newbot`
2. **Провайдер LLM** — выбрать из списка
3. **Модель** — выбрать из доступных для провайдера
4. **API-ключ** — мастер проверит корректность ключа перед сохранением
5. **Язык ответов** — русский или английский

Конфиг сохраняется в `config.json` (в `.gitignore`, ключи не попадут в репозиторий).

### Где получить API-ключи

| Провайдер | Ссылка |
|-----------|--------|
| Google Gemini | https://aistudio.google.com/apikey |
| Groq | https://console.groq.com/keys |
| OpenRouter | https://openrouter.ai/keys |
| Anthropic | https://console.anthropic.com/ |
| OpenAI | https://platform.openai.com/api-keys |

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

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция |
| `/help` | Справка |
| `/status` | Текущий провайдер и модель |

---

## Управление сервисом (systemd)

Если при установке вы выбрали автозапуск через systemd:

```bash
# Статус
sudo systemctl status arxiv-bot

# Перезапуск (например, после смены конфига)
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

## Смена провайдера или модели

```bash
# Остановить сервис (если запущен)
sudo systemctl stop arxiv-bot

# Перенастроить
python3 -m bot.wizard

# Запустить снова
sudo systemctl start arxiv-bot
```

---

## Структура проекта

```
arxiv-explainer-bot/
├── bot/
│   ├── main.py          # точка входа, polling loop
│   ├── handlers.py      # обработчики Telegram-сообщений
│   ├── arxiv_client.py  # скачивание PDF и метаданных
│   ├── llm_client.py    # клиенты LLM-провайдеров
│   ├── formatter.py     # форматирование в Telegram MarkdownV2
│   ├── config.py        # провайдеры, чтение/запись config.json
│   └── wizard.py        # интерактивный мастер настройки
├── config.json          # ваш конфиг (создаётся wizard'ом, не в git)
├── config.example.json  # шаблон конфига
├── arxiv_bot.service    # шаблон systemd unit-файла
├── setup.sh             # скрипт установки
└── requirements.txt
```

---

## Устранение неполадок

**Бот не отвечает на ссылки**
Убедитесь, что сообщение содержит `arxiv.org/abs/`, `arxiv.org/pdf/` или голый ID вида `2406.12345`. Обычные текстовые сообщения бот игнорирует.

**Ошибка `Конфиг не найден`**
Запустите `python3 -m bot.wizard` — конфиг `config.json` ещё не создан.

**`❌ Не удалось скачать статью`**
Arxiv иногда временно недоступен. Подождите минуту и попробуйте снова. Также проверьте, что VPS имеет выход в интернет: `curl -I https://arxiv.org`.

**`❌ LLM вернул некорректный ответ`**
Попробуйте другую модель через `python3 -m bot.wizard`. Некоторые лёгкие модели плохо следуют инструкции возвращать только JSON.

**Сервис не запускается**
```bash
sudo journalctl -u arxiv-bot -n 50
```
Чаще всего причина — неверный токен или API-ключ. Перенастройте через `python3 -m bot.wizard`.

**Как убедиться, что сервис перезапускается после ребута**
```bash
sudo systemctl is-enabled arxiv-bot   # должно вернуть "enabled"
```

---

## Требования

- Python 3.11+
- Ubuntu 22.04+ (для VPS-деплоя) или любой современный Linux / macOS (для локального запуска)
- Telegram Bot Token (бесплатно, от [@BotFather](https://t.me/BotFather))
- API-ключ одного из поддерживаемых LLM-провайдеров (Gemini и Groq — бесплатно)
