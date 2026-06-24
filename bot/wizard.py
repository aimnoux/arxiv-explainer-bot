"""Interactive setup wizard — stdlib only."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# ── Provider registry ─────────────────────────────────────────────────────────
# base_url=None means Anthropic SDK (handled separately in llm_client.py)

PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "free": True,
        "free_note": "15 req/min, 1M tokens/day",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "docs": "https://aistudio.google.com/apikey",
    },
    "groq": {
        "name": "Groq",
        "free": True,
        "free_note": "14,400 req/day",
        "base_url": "https://api.groq.com/openai/v1",
        "docs": "https://console.groq.com/keys",
    },
    "cerebras": {
        "name": "Cerebras",
        "free": True,
        "free_note": "бесплатно",
        "base_url": "https://api.cerebras.ai/v1",
        "docs": "https://cloud.cerebras.ai/",
    },
    "sambanova": {
        "name": "SambaNova",
        "free": True,
        "free_note": "бесплатный tier",
        "base_url": "https://api.sambanova.ai/v1",
        "docs": "https://cloud.sambanova.ai/",
    },
    "openrouter": {
        "name": "OpenRouter",
        "free": True,
        "free_note": "есть бесплатные модели",
        "base_url": "https://openrouter.ai/api/v1",
        "docs": "https://openrouter.ai/keys",
    },
    "anthropic": {
        "name": "Anthropic",
        "free": False,
        "free_note": None,
        "base_url": None,
        "docs": "https://console.anthropic.com/",
    },
    "openai": {
        "name": "OpenAI",
        "free": False,
        "free_note": None,
        "base_url": "https://api.openai.com/v1",
        "docs": "https://platform.openai.com/api-keys",
    },
    "deepseek": {
        "name": "DeepSeek",
        "free": False,
        "free_note": "от $0.07/M tokens",
        "base_url": "https://api.deepseek.com",
        "docs": "https://platform.deepseek.com/api_keys",
    },
    "mistral": {
        "name": "Mistral AI",
        "free": False,
        "free_note": None,
        "base_url": "https://api.mistral.ai/v1",
        "docs": "https://console.mistral.ai/",
    },
    "together": {
        "name": "Together AI",
        "free": False,
        "free_note": "$1 кредит при регистрации",
        "base_url": "https://api.together.xyz/v1",
        "docs": "https://api.together.ai/settings/api-keys",
    },
    "xai": {
        "name": "xAI (Grok)",
        "free": False,
        "free_note": None,
        "base_url": "https://api.x.ai/v1",
        "docs": "https://console.x.ai/",
    },
    "perplexity": {
        "name": "Perplexity",
        "free": False,
        "free_note": None,
        "base_url": "https://api.perplexity.ai",
        "docs": "https://www.perplexity.ai/settings/api",
    },
    "cohere": {
        "name": "Cohere",
        "free": False,
        "free_note": "trial ключ без карты",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "docs": "https://dashboard.cohere.com/api-keys",
    },
    "nvidia": {
        "name": "Nvidia NIM",
        "free": False,
        "free_note": "1000 бесплатных запросов",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "docs": "https://build.nvidia.com/",
    },
}

# ── Per-provider model filters ────────────────────────────────────────────────

_EXCLUDE_ALWAYS = ("embed", "whisper", "tts", "dall-e", "rerank", "moderation", "guard")

_PROVIDER_KEEP = {
    "gemini":     lambda mid: mid.startswith("gemini-"),
    "groq":       lambda mid: True,
    "cerebras":   lambda mid: True,
    "sambanova":  lambda mid: True,
    "openai":     lambda mid: any(mid.startswith(p) for p in ("gpt-4", "gpt-3.5", "o1", "o3", "o4")),
    "deepseek":   lambda mid: True,
    "mistral":    lambda mid: True,
    "together":   lambda mid: True,
    "xai":        lambda mid: True,
    "perplexity": lambda mid: True,
    "cohere":     lambda mid: True,
    "nvidia":     lambda mid: True,
    "openrouter": lambda mid: True,
    "anthropic":  lambda mid: True,
}

# Providers where every returned model is on the free tier
_FULLY_FREE = {"groq", "cerebras", "sambanova"}


def _is_free(provider_key: str, model_id: str, openrouter_pricing: dict | None = None) -> bool:
    if provider_key in _FULLY_FREE:
        return True
    if provider_key == "gemini":
        return "flash" in model_id.lower()
    if provider_key == "openrouter" and openrouter_pricing:
        return str(openrouter_pricing.get("prompt", "1")) == "0"
    return False


def _keep_model(provider_key: str, model_id: str) -> bool:
    mid_lower = model_id.lower()
    if any(p in mid_lower for p in _EXCLUDE_ALWAYS):
        return False
    return _PROVIDER_KEEP.get(provider_key, lambda _: True)(model_id)


# ── Dynamic model fetching ────────────────────────────────────────────────────

def _http_get(url: str, headers: dict, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _fetch_openrouter(api_key: str) -> list[dict]:
    data = _http_get(
        "https://openrouter.ai/api/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    result = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if not _keep_model("openrouter", mid):
            continue
        pricing = m.get("pricing", {})
        result.append({
            "id": mid,
            "name": m.get("name", mid),
            "free": _is_free("openrouter", mid, pricing),
        })
    result.sort(key=lambda m: (not m["free"], m["name"].lower()))
    return result


def _fetch_anthropic(api_key: str) -> list[dict]:
    data = _http_get(
        "https://api.anthropic.com/v1/models",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    return [
        {"id": m["id"], "name": m.get("display_name", m["id"]), "free": False}
        for m in data.get("data", [])
        if _keep_model("anthropic", m.get("id", ""))
    ]


def _fetch_together(api_key: str) -> list[dict]:
    data = _http_get(
        "https://api.together.xyz/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    result = []
    for m in data:
        mid = m.get("id", "")
        # Together returns objects with a "type" field
        if m.get("type") not in ("chat", "language", None):
            continue
        if not _keep_model("together", mid):
            continue
        result.append({"id": mid, "name": m.get("display_name", mid), "free": False})
    result.sort(key=lambda m: m["name"].lower())
    return result


def _fetch_openai_compat(provider_key: str, base_url: str, api_key: str) -> list[dict]:
    data = _http_get(
        base_url.rstrip("/") + "/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    result = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if not _keep_model(provider_key, mid):
            continue
        result.append({
            "id": mid,
            "name": m.get("name", mid),
            "free": _is_free(provider_key, mid),
        })
    result.sort(key=lambda m: (not m["free"], m["id"]))
    return result


def fetch_models(provider_key: str, provider_cfg: dict, api_key: str) -> list[dict]:
    """Fetch models from provider. Raises on failure — caller must handle."""
    if provider_key == "anthropic":
        return _fetch_anthropic(api_key)
    if provider_key == "openrouter":
        return _fetch_openrouter(api_key)
    if provider_key == "together":
        return _fetch_together(api_key)
    return _fetch_openai_compat(provider_key, provider_cfg["base_url"], api_key)


# ── UI helpers ────────────────────────────────────────────────────────────────

def header(text: str) -> None:
    print(f"\n─── {text} ───")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if val:
            return val
        if default:
            return default
        print("  Значение обязательно.")


def choose(options: list[str], prompt: str = "Выберите", page_size: int = 15) -> int:
    """Simple numbered list with optional pagination."""
    total = len(options)
    page = 0
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


def choose_models(models: list[dict], current_id: str = "", page_size: int = 15) -> dict:
    """Display models in FREE / PAID sections with pagination. Returns selected model."""
    free = [m for m in models if m["free"]]
    paid = [m for m in models if not m["free"]]
    flat = free + paid  # numbered 0..N-1; free section first

    free_range = range(0, len(free))
    paid_range = range(len(free), len(flat))
    default_idx = next((i for i, m in enumerate(flat) if m["id"] == current_id), 0)
    total = len(flat)
    page = 0

    while True:
        page_start = page * page_size
        page_end = min(page_start + page_size, total)
        page_indices = range(page_start, page_end)

        # Free section header (only if any free items are visible on this page)
        if free and any(i in free_range for i in page_indices):
            print(f"\n  ── ✅ Бесплатные ({len(free)}) {'─' * 30}")
        for i in page_indices:
            if i not in free_range:
                break
            marker = "→" if i == default_idx else " "
            print(f"  {marker}[{i + 1:>3}] {flat[i]['name']}")

        # Paid section header (only if any paid items are visible on this page)
        if paid and any(i in paid_range for i in page_indices):
            print(f"\n  ── 💰 Платные ({len(paid)}) {'─' * 32}")
        for i in page_indices:
            if i not in paid_range:
                continue
            marker = "→" if i == default_idx else " "
            print(f"  {marker}[{i + 1:>3}] {flat[i]['name']}")

        print()
        nav = []
        if page_end < total:
            nav.append(f"[n] ещё ({page_end}/{total})")
        if page > 0:
            nav.append("[p] назад")
        if nav:
            print(f"        {' · '.join(nav)}")

        raw = input(f"  Выберите [1-{total}] (Enter = {default_idx + 1}): ").strip().lower()

        if raw == "":
            return flat[default_idx]
        if raw == "n" and page_end < total:
            page += 1
        elif raw == "p" and page > 0:
            page -= 1
        elif raw.isdigit() and 1 <= int(raw) <= total:
            return flat[int(raw) - 1]
        else:
            print(f"  Введите число от 1 до {total}.")


# ── API key validation ────────────────────────────────────────────────────────

def check_telegram_token(token: str) -> str:
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=10
        ) as r:
            return "ok" if json.loads(r.read()).get("ok") else "invalid"
    except urllib.error.HTTPError as e:
        return "invalid" if e.code in (401, 403) else "unreachable"
    except Exception:
        return "unreachable"


def check_api_key(provider_key: str, provider_cfg: dict, api_key: str) -> str:
    try:
        if provider_key == "anthropic":
            url = "https://api.anthropic.com/v1/models"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        elif provider_key == "together":
            url = "https://api.together.xyz/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            url = provider_cfg["base_url"].rstrip("/") + "/models"
            headers = {"Authorization": f"Bearer {api_key}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return "ok" if r.status == 200 else "unreachable"
    except urllib.error.HTTPError as e:
        return "invalid" if e.code in (401, 403) else "unreachable"
    except Exception:
        return "unreachable"


# ── Wizard ────────────────────────────────────────────────────────────────────

def run_wizard() -> None:
    print("╔══════════════════════════════════════╗")
    print("║   ArXiv Explainer Bot — Настройка   ║")
    print("╚══════════════════════════════════════╝")

    cfg: dict = {}
    if CONFIG_PATH.exists():
        print("\nКонфиг уже существует.")
        if choose(["Изменить существующий", "Создать заново"], "Выберите") == 0:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)

    # ── Step 1: Telegram token ────────────────────────────────────────────────
    header("Шаг 1: Telegram Bot Token")
    default_token = cfg.get("telegram_token", "")
    while True:
        token = ask("Токен бота (от @BotFather)", default_token)
        print("  Проверяю...", end=" ", flush=True)
        status = check_telegram_token(token)
        if status == "ok":
            print("✓")
            cfg["telegram_token"] = token
            break
        elif status == "unreachable":
            print("⚠ нет подключения к Telegram. Сохраняю как есть.")
            cfg["telegram_token"] = token
            break
        else:
            print("✗ Токен недействителен.")

    # ── Step 2: Provider ──────────────────────────────────────────────────────
    header("Шаг 2: Провайдер LLM")
    provider_keys = list(PROVIDERS.keys())
    provider_labels = []
    for p in PROVIDERS.values():
        if p["free"] and p["free_note"]:
            badge = f"✅ {p['free_note']}"
        elif p["free"]:
            badge = "✅ бесплатно"
        elif p["free_note"]:
            badge = f"💰 {p['free_note']}"
        else:
            badge = "💰 платно"
        provider_labels.append(f"{p['name']:<18} {badge}")

    current_provider = cfg.get("llm_provider", "")
    default_p = provider_keys.index(current_provider) if current_provider in provider_keys else 0
    idx = choose(provider_labels, f"Провайдер (по умолчанию {default_p + 1})")
    provider_key = provider_keys[idx]
    provider_cfg = PROVIDERS[provider_key]
    cfg["llm_provider"] = provider_key

    # ── Step 3: API key ───────────────────────────────────────────────────────
    header("Шаг 3: API-ключ")
    print(f"  Получить ключ: {provider_cfg['docs']}")
    default_key = cfg.get("llm_api_key", "")
    while True:
        api_key = ask("API-ключ", default_key)
        print("  Проверяю ключ...", end=" ", flush=True)
        status = check_api_key(provider_key, provider_cfg, api_key)
        if status == "ok":
            print("✓")
            cfg["llm_api_key"] = api_key
            break
        elif status == "unreachable":
            print("⚠ нет подключения к провайдеру. Сохраняю как есть.")
            cfg["llm_api_key"] = api_key
            break
        else:
            print("✗ Ключ отклонён (401/403). Проверьте и попробуйте ещё раз.")

    # ── Step 4: Model (fetched live) ─────────────────────────────────────────
    header("Шаг 4: Модель")
    models: list[dict] = []
    while not models:
        print(f"  Загружаю модели {provider_cfg['name']}...", end=" ", flush=True)
        try:
            models = fetch_models(provider_key, provider_cfg, cfg["llm_api_key"])
            free_n = sum(1 for m in models if m["free"])
            paid_n = len(models) - free_n
            print(f"✓  {len(models)} моделей (✅ {free_n} бесплатных, 💰 {paid_n} платных)")
        except urllib.error.HTTPError as e:
            print(f"✗ HTTP {e.code}")
            if e.code in (401, 403):
                print("  Ключ был принят на проверке, но /models вернул ошибку авторизации.")
            raw = input("  Повторить попытку? [y/N]: ").strip().lower()
            if raw != "y":
                print("  Выход из wizard.")
                sys.exit(1)
        except Exception as e:
            print(f"✗ {e}")
            raw = input("  Повторить попытку? [y/N]: ").strip().lower()
            if raw != "y":
                print("  Выход из wizard.")
                sys.exit(1)

    selected = choose_models(models, current_id=cfg.get("llm_model", ""))
    cfg["llm_model"] = selected["id"]
    print(f"  Выбрано: {selected['name']} ({selected['id']})")

    # ── Step 5: Language ──────────────────────────────────────────────────────
    header("Шаг 5: Язык ответов")
    current_lang = cfg.get("language", "ru")
    print(f"  [1] Русский{'  ← текущий' if current_lang == 'ru' else ''}")
    print(f"  [2] English{'  ← текущий' if current_lang == 'en' else ''}")
    raw = input("  Выберите [1/2] (Enter — оставить): ").strip()
    cfg["language"] = {"1": "ru", "2": "en"}.get(raw, current_lang)

    cfg.setdefault("max_paper_pages", 20)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Конфиг сохранён.")
    print(f"   {provider_cfg['name']} / {cfg['llm_model']}")
    print("   Запуск: python3 -m bot.main")


if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\nОтменено.")
        sys.exit(0)
