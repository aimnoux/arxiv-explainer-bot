import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

PROVIDERS = {
    "gemini":     {"name": "Google Gemini", "free": True,  "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "docs": "https://aistudio.google.com/apikey"},
    "groq":       {"name": "Groq",          "free": True,  "base_url": "https://api.groq.com/openai/v1",                          "docs": "https://console.groq.com/keys"},
    "cerebras":   {"name": "Cerebras",      "free": True,  "base_url": "https://api.cerebras.ai/v1",                              "docs": "https://cloud.cerebras.ai/"},
    "sambanova":  {"name": "SambaNova",     "free": True,  "base_url": "https://api.sambanova.ai/v1",                             "docs": "https://cloud.sambanova.ai/"},
    "openrouter": {"name": "OpenRouter",    "free": True,  "base_url": "https://openrouter.ai/api/v1",                            "docs": "https://openrouter.ai/keys"},
    "anthropic":  {"name": "Anthropic",     "free": False, "base_url": None,                                                      "docs": "https://console.anthropic.com/"},
    "openai":     {"name": "OpenAI",        "free": False, "base_url": "https://api.openai.com/v1",                               "docs": "https://platform.openai.com/api-keys"},
    "deepseek":   {"name": "DeepSeek",      "free": False, "base_url": "https://api.deepseek.com",                                "docs": "https://platform.deepseek.com/api_keys"},
    "mistral":    {"name": "Mistral AI",    "free": False, "base_url": "https://api.mistral.ai/v1",                               "docs": "https://console.mistral.ai/"},
    "together":   {"name": "Together AI",   "free": False, "base_url": "https://api.together.xyz/v1",                             "docs": "https://api.together.ai/settings/api-keys"},
    "xai":        {"name": "xAI (Grok)",    "free": False, "base_url": "https://api.x.ai/v1",                                    "docs": "https://console.x.ai/"},
    "perplexity": {"name": "Perplexity",    "free": False, "base_url": "https://api.perplexity.ai",                               "docs": "https://www.perplexity.ai/settings/api"},
    "cohere":     {"name": "Cohere",        "free": False, "base_url": "https://api.cohere.ai/compatibility/v1",                  "docs": "https://dashboard.cohere.com/api-keys"},
    "nvidia":     {"name": "Nvidia NIM",    "free": False, "base_url": "https://integrate.api.nvidia.com/v1",                     "docs": "https://build.nvidia.com/"},
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
