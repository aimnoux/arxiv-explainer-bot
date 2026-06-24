"""Interactive setup wizard — stdlib only."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "free": True,
        "free_note": "15 req/min, 1M tokens/day",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "docs": "https://aistudio.google.com/apikey",
        "fallback_models": [
            {"id": "gemini-2.0-flash",     "name": "Gemini 2.0 Flash",     "free": True,  "default": True},
            {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite","free": True},
            {"id": "gemini-1.5-flash",      "name": "Gemini 1.5 Flash",     "free": True},
            {"id": "gemini-1.5-pro",        "name": "Gemini 1.5 Pro",       "free": False},
        ],
    },
    "groq": {
        "name": "Groq",
        "free": True,
        "free_note": "14,400 req/day бесплатно",
        "base_url": "https://api.groq.com/openai/v1",
        "docs": "https://console.groq.com/keys",
        "fallback_models": [
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
        "fallback_models": [
            {"id": "google/gemini-2.0-flash-001:free",         "name": "Gemini 2.0 Flash (free)", "free": True, "default": True},
            {"id": "meta-llama/llama-3.3-70b-instruct:free",   "name": "Llama 3.3 70B (free)",   "free": True},
            {"id": "deepseek/deepseek-r1-0528:free",            "name": "DeepSeek R1 (free)",     "free": True},
            {"id": "anthropic/claude-3.5-haiku",                "name": "Claude 3.5 Haiku",       "free": False},
            {"id": "openai/gpt-4o-mini",                        "name": "GPT-4o Mini",            "free": False},
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "free": False,
        "free_note": None,
        "base_url": None,
        "docs": "https://console.anthropic.com/",
        "fallback_models": [
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
        "fallback_models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "free": False, "default": True},
            {"id": "gpt-4o",      "name": "GPT-4o",       "free": False},
            {"id": "o4-mini",     "name": "O4 Mini",      "free": False},
        ],
    },
}

# Models to exclude from dynamic lists (audio, embedding, image, moderation)
_EXCLUDE_PATTERNS = (
    "whisper", "tts", "dall-e", "embedding", "text-embedding",
    "moderation", "babbage", "davinci", "ada", "curie", "instruct",
)
_GROQ_CHAT_PREFIXES = ("llama", "mixtral", "gemma", "qwen", "deepseek", "mistral", "compound")


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


def choose(options: list[str], prompt: str = "Выберите", page_size: int = 15) -> int:
    page = 0
    total = len(options)
    while True:
        start = page * page_size
        end = min(start + page_size, total)
        for i in range(start, end):
            print(f"  [{i + 1:>3}] {options[i]}")
        nav = []
        if end < total:
            nav.append(f"[n] ещё ({end}/{total})")
        if page > 0:
            nav.append("[p] назад")
        if nav:
            print(f"        {' · '.join(nav)}")
        raw = input(f"  {prompt} [1-{total}]: ").strip().lower()
        if raw == "n" and end < total:
            page += 1
        elif raw == "p" and page > 0:
            page -= 1
        elif raw.isdigit() and 1 <= int(raw) <= total:
            return int(raw) - 1
        else:
            print(f"  Введите число от 1 до {total}.")


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


def check_api_key(provider_key: str, provider_cfg: dict, api_key: str) -> str:
    try:
        if provider_key == "anthropic":
            url = "https://api.anthropic.com/v1/models"
            req = urllib.request.Request(
                url, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            )
        else:
            url = provider_cfg["base_url"].rstrip("/") + "/models"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return "ok" if r.status == 200 else "unreachable"
    except urllib.error.HTTPError as e:
        return "invalid" if e.code in (401, 403) else "unreachable"
    except Exception:
        return "unreachable"


# ── dynamic model fetching ────────────────────────────────────────────────────

def _http_get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _fetch_openrouter(api_key: str) -> list[dict]:
    data = _http_get_json(
        "https://openrouter.ai/api/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    free, paid = [], []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        is_free = str(pricing.get("prompt", "1")) == "0" and str(pricing.get("completion", "1")) == "0"
        entry = {"id": m["id"], "name": m.get("name", m["id"]), "free": is_free}
        (free if is_free else paid).append(entry)

    free.sort(key=lambda m: m["name"].lower())
    paid.sort(key=lambda m: m["name"].lower())
    return free + paid[:15]  # all free + top-15 paid


def _fetch_openai_compat(base_url: str, api_key: str, provider_key: str) -> list[dict]:
    data = _http_get_json(
        base_url.rstrip("/") + "/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    result = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        mid_lower = mid.lower()

        if any(p in mid_lower for p in _EXCLUDE_PATTERNS):
            continue

        if provider_key == "gemini":
            if not mid.startswith("gemini-"):
                continue
            free = "flash" in mid_lower
        elif provider_key == "groq":
            if not any(mid_lower.startswith(p) for p in _GROQ_CHAT_PREFIXES):
                continue
            free = True
        elif provider_key == "openai":
            if not any(mid.startswith(p) for p in ("gpt-4", "gpt-3.5", "o1", "o3", "o4")):
                continue
            free = False
        else:
            free = False

        result.append({"id": mid, "name": mid, "free": free})

    result.sort(key=lambda m: m["id"])
    return result


def _fetch_anthropic(api_key: str) -> list[dict]:
    data = _http_get_json(
        "https://api.anthropic.com/v1/models",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    return [
        {"id": m["id"], "name": m.get("display_name", m["id"]), "free": False}
        for m in data.get("data", [])
    ]


def fetch_models(provider_key: str, provider_cfg: dict, api_key: str) -> tuple[list[dict], bool]:
    """Returns (models, is_dynamic). Falls back to hardcoded on error."""
    try:
        if provider_key == "anthropic":
            models = _fetch_anthropic(api_key)
        elif provider_key == "openrouter":
            models = _fetch_openrouter(api_key)
        else:
            models = _fetch_openai_compat(provider_cfg["base_url"], api_key, provider_key)
        if models:
            return models, True
    except Exception:
        pass
    return provider_cfg["fallback_models"], False


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
            print("⚠ не удалось проверить (нет подключения). Токен сохранён.")
            cfg["telegram_token"] = token
            break
        else:
            print("✗ Токен недействителен. Попробуйте ещё раз.")

    # ── Step 2: Provider ──────────────────────────────────────────────────────
    header("Шаг 2: Провайдер LLM")
    provider_keys = list(PROVIDERS.keys())
    provider_labels = []
    for p in PROVIDERS.values():
        if p["free"] and p["free_note"]:
            badge = f"✅ БЕСПЛАТНО ({p['free_note']})"
        elif p["free"]:
            badge = "✅ есть бесплатные"
        else:
            badge = "💰 платно"
        provider_labels.append(f"{p['name']:<20} {badge}")

    current_provider = cfg.get("llm_provider", "")
    default_idx = provider_keys.index(current_provider) if current_provider in provider_keys else 0
    idx = choose(provider_labels, f"Выберите провайдер (по умолчанию {default_idx + 1})")
    provider_key = provider_keys[idx]
    provider_cfg = PROVIDERS[provider_key]
    cfg["llm_provider"] = provider_key

    # ── Step 3: API key (before models — needed to fetch them) ───────────────
    header("Шаг 3: API-ключ")
    print(f"  Получить ключ: {provider_cfg['docs']}")
    default_key = cfg.get("llm_api_key", "")
    while True:
        api_key = ask("Введите API-ключ", default_key)
        print("  Проверяю API-ключ...", end=" ", flush=True)
        status = check_api_key(provider_key, provider_cfg, api_key)
        if status == "ok":
            print("✓")
            cfg["llm_api_key"] = api_key
            break
        elif status == "unreachable":
            print("⚠ не удалось проверить (нет подключения). Ключ сохранён.")
            cfg["llm_api_key"] = api_key
            break
        else:
            print("✗ Ключ отклонён (401/403). Проверьте ключ и попробуйте ещё раз.")

    # ── Step 4: Model (fetched dynamically) ──────────────────────────────────
    header("Шаг 4: Модель")
    print(f"  Загружаю актуальный список моделей {provider_cfg['name']}...", end=" ", flush=True)
    models, is_dynamic = fetch_models(provider_key, provider_cfg, cfg["llm_api_key"])
    if is_dynamic:
        print(f"✓ ({len(models)} моделей)")
    else:
        print("⚠ не удалось загрузить, используется встроенный список")

    current_model = cfg.get("llm_model", "")
    model_labels = []
    default_model_idx = 0
    for i, m in enumerate(models):
        badge = "✅" if m["free"] else "💰"
        label = f"{badge} {m['name']}"
        model_labels.append(label)
        if m["id"] == current_model or (i == 0 and not current_model):
            default_model_idx = i

    print(f"\n  Найдено моделей: {len(models)}"
          f"{' (бесплатных: ' + str(sum(1 for m in models if m['free'])) + ')' if is_dynamic else ''}")
    idx = choose(model_labels, f"Выберите модель (по умолчанию {default_model_idx + 1})")
    cfg["llm_model"] = models[idx]["id"]

    # ── Step 5: Language ──────────────────────────────────────────────────────
    header("Шаг 5: Язык ответов")
    lang_map = {"1": "ru", "2": "en"}
    current_lang = cfg.get("language", "ru")
    print(f"  [1] Русский{'  [по умолчанию]' if current_lang == 'ru' else ''}")
    print(f"  [2] English{'  [по умолчанию]' if current_lang == 'en' else ''}")
    raw = input("  Выберите [1-2] (Enter — оставить текущий): ").strip()
    cfg["language"] = lang_map.get(raw, current_lang)

    cfg.setdefault("max_paper_pages", 20)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Конфиг сохранён в {CONFIG_PATH}")
    print(f"   Провайдер: {provider_cfg['name']} / {cfg['llm_model']}")
    print("   Запуск бота: python3 -m bot.main")


if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\nОтменено.")
        sys.exit(0)
