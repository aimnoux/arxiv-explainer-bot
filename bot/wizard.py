"""Interactive setup wizard — stdlib only."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# Inline copy so wizard has zero imports from the package itself
PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "free": True,
        "free_note": "15 req/min, 1M tokens/day",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "docs": "https://aistudio.google.com/apikey",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "free": True, "default": True},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "free": True},
            {"id": "gemini-1.5-pro",   "name": "Gemini 1.5 Pro",   "free": False},
        ],
    },
    "groq": {
        "name": "Groq",
        "free": True,
        "free_note": "14,400 req/day бесплатно",
        "base_url": "https://api.groq.com/openai/v1",
        "docs": "https://console.groq.com/keys",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B",        "free": True, "default": True},
            {"id": "llama-3.1-8b-instant",    "name": "Llama 3.1 8B Instant", "free": True},
            {"id": "mixtral-8x7b-32768",       "name": "Mixtral 8x7B",         "free": True},
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "free": True,
        "free_note": "есть бесплатные модели",
        "base_url": "https://openrouter.ai/api/v1",
        "docs": "https://openrouter.ai/keys",
        "models": [
            {"id": "google/gemini-2.0-flash-001:free",          "name": "Gemini 2.0 Flash (free)", "free": True, "default": True},
            {"id": "meta-llama/llama-3.3-70b-instruct:free",  "name": "Llama 3.3 70B (free)",   "free": True},
            {"id": "deepseek/deepseek-r1-0528:free",           "name": "DeepSeek R1 (free)",     "free": True},
            {"id": "anthropic/claude-3.5-haiku",               "name": "Claude 3.5 Haiku",       "free": False},
            {"id": "openai/gpt-4o-mini",                       "name": "GPT-4o Mini",            "free": False},
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "free": False,
        "free_note": None,
        "base_url": None,
        "docs": "https://console.anthropic.com/",
        "models": [
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5",  "free": False, "default": True},
            {"id": "claude-sonnet-4-6",          "name": "Claude Sonnet 4.6", "free": False},
        ],
    },
    "openai": {
        "name": "OpenAI",
        "free": False,
        "free_note": None,
        "base_url": "https://api.openai.com/v1",
        "docs": "https://platform.openai.com/api-keys",
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "free": False, "default": True},
            {"id": "gpt-4o",      "name": "GPT-4o",       "free": False},
        ],
    },
}


# ── helpers ──────────────────────────────────────────────────────────────────

def header(text: str) -> None:
    print(f"\n─── {text} ───")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if val:
            return val
        if default:
            return default
        print("  Значение обязательно.")


def choose(options: list[str], prompt: str = "Выберите") -> int:
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    while True:
        raw = input(f"{prompt} [1-{len(options)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  Введите число от 1 до {len(options)}.")


# ── token validators ──────────────────────────────────────────────────────────
# Return values: "ok" | "invalid" | "unreachable"

def check_telegram_token(token: str) -> str:
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            return "ok" if data.get("ok") else "invalid"
    except urllib.error.HTTPError as e:
        return "invalid" if e.code in (401, 403) else "unreachable"
    except Exception:
        return "unreachable"


def check_openai_compatible(base_url: str, api_key: str) -> str:
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return "ok" if r.status == 200 else "unreachable"
    except urllib.error.HTTPError as e:
        return "invalid" if e.code in (401, 403) else "unreachable"
    except Exception:
        return "unreachable"


def check_anthropic_key(api_key: str) -> str:
    url = "https://api.anthropic.com/v1/models"
    req = urllib.request.Request(
        url,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return "ok" if r.status == 200 else "unreachable"
    except urllib.error.HTTPError as e:
        return "invalid" if e.code in (401, 403) else "unreachable"
    except Exception:
        return "unreachable"


# ── wizard ────────────────────────────────────────────────────────────────────

def run_wizard() -> None:
    print("╔══════════════════════════════════════╗")
    print("║   ArXiv Explainer Bot — Настройка   ║")
    print("╚══════════════════════════════════════╝")

    existing_cfg = None
    if CONFIG_PATH.exists():
        print("\nКонфиг уже существует.")
        idx = choose(["Изменить существующий", "Создать заново"], "Выберите")
        if idx == 0:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                existing_cfg = json.load(f)

    cfg: dict = existing_cfg or {}

    # ── Step 1: Telegram token ────────────────────────────────────────────────
    header("Шаг 1: Telegram Bot Token")
    default_token = cfg.get("telegram_token", "")
    while True:
        token = ask("Введите токен бота (от @BotFather)", default_token)
        print("  Проверяю Telegram-токен...", end=" ", flush=True)
        status = check_telegram_token(token)
        if status == "ok":
            print("✓")
            cfg["telegram_token"] = token
            break
        elif status == "unreachable":
            print("⚠ не удалось проверить (нет подключения к Telegram). Токен сохранён.")
            cfg["telegram_token"] = token
            break
        else:
            print("✗ Токен недействителен. Попробуйте ещё раз.")

    # ── Step 2: Provider ──────────────────────────────────────────────────────
    header("Шаг 2: Провайдер LLM")
    provider_keys = list(PROVIDERS.keys())
    provider_labels = []
    for p in PROVIDERS.values():
        badge = f"✅ БЕСПЛАТНО ({p['free_note']})" if p["free"] and p["free_note"] else ("✅ есть бесплатные" if p["free"] else "💰 платно")
        provider_labels.append(f"{p['name']:<20} {badge}")

    current_provider = cfg.get("llm_provider", "")
    default_provider_idx = provider_keys.index(current_provider) if current_provider in provider_keys else 0
    idx = choose(provider_labels, f"Выберите провайдер (по умолчанию {default_provider_idx + 1})")
    provider_key = provider_keys[idx]
    provider_cfg = PROVIDERS[provider_key]
    cfg["llm_provider"] = provider_key

    # ── Step 3: Model ─────────────────────────────────────────────────────────
    header("Шаг 3: Модель")
    models = provider_cfg["models"]
    current_model = cfg.get("llm_model", "")
    model_labels = []
    default_model_idx = 0
    for i, m in enumerate(models):
        badge = "✅ БЕСПЛАТНО" if m["free"] else "💰 платно"
        rec = "  [рекомендуется]" if m.get("default") else ""
        model_labels.append(f"{m['name']:<35} {badge}{rec}")
        if m.get("default") or m["id"] == current_model:
            default_model_idx = i

    print(f"Доступные модели для {provider_cfg['name']}:")
    idx = choose(model_labels, f"Выберите модель (по умолчанию {default_model_idx + 1})")
    cfg["llm_model"] = models[idx]["id"]

    # ── Step 4: API key ───────────────────────────────────────────────────────
    header("Шаг 4: API-ключ")
    print(f"  Получить ключ: {provider_cfg['docs']}")
    default_key = cfg.get("llm_api_key", "")
    while True:
        api_key = ask("Введите API-ключ", default_key)
        print("  Проверяю LLM API-ключ...", end=" ", flush=True)
        if provider_key == "anthropic":
            status = check_anthropic_key(api_key)
        else:
            status = check_openai_compatible(provider_cfg["base_url"], api_key)
        if status == "ok":
            print("✓")
            cfg["llm_api_key"] = api_key
            break
        elif status == "unreachable":
            print("⚠ не удалось проверить (нет подключения к провайдеру). Ключ сохранён.")
            cfg["llm_api_key"] = api_key
            break
        else:
            print("✗ Ключ отклонён (401/403). Проверьте ключ и попробуйте ещё раз.")

    # ── Step 5: Language ──────────────────────────────────────────────────────
    header("Шаг 5: Язык ответов")
    lang_map = {"1": "ru", "2": "en"}
    current_lang = cfg.get("language", "ru")
    print(f"  [1] Русский{'  [по умолчанию]' if current_lang == 'ru' else ''}")
    print(f"  [2] English{'  [по умолчанию]' if current_lang == 'en' else ''}")
    raw = input("Выберите [1-2] (Enter — оставить текущий): ").strip()
    cfg["language"] = lang_map.get(raw, current_lang)

    # ── Pages limit ───────────────────────────────────────────────────────────
    cfg.setdefault("max_paper_pages", 20)

    # ── Save ──────────────────────────────────────────────────────────────────
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Конфиг сохранён в {CONFIG_PATH}")
    print("   Запуск бота: python3 -m bot.main")


if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\nОтменено.")
        sys.exit(0)
