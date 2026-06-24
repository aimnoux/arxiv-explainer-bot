import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "free": True,
        "free_note": "15 req/min, 1M tokens/day",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "docs": "https://aistudio.google.com/apikey",
        "models": [
            {"id": "gemini-2.0-flash",  "name": "Gemini 2.0 Flash",  "free": True},
            {"id": "gemini-1.5-flash",  "name": "Gemini 1.5 Flash",  "free": True},
            {"id": "gemini-1.5-pro",    "name": "Gemini 1.5 Pro",    "free": False},
        ],
    },
    "groq": {
        "name": "Groq",
        "free": True,
        "free_note": "14,400 req/day бесплатно",
        "base_url": "https://api.groq.com/openai/v1",
        "docs": "https://console.groq.com/keys",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B",        "free": True},
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
            {"id": "google/gemini-2.0-flash-001:free",          "name": "Gemini 2.0 Flash (free)", "free": True},
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
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5",  "free": False},
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
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "free": False},
            {"id": "gpt-4o",      "name": "GPT-4o",       "free": False},
        ],
    },
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Конфиг не найден: {CONFIG_PATH}\n"
            "Запустите: python3 -m bot.wizard"
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
