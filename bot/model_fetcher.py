"""Async model fetching for all providers (used by admin panel)."""
import httpx

_EXCLUDE = ("embed", "whisper", "tts", "dall-e", "rerank", "moderation", "guard")
_GROQ_PREFIXES = ("llama", "mixtral", "gemma", "qwen", "deepseek", "mistral", "compound")
_OPENAI_PREFIXES = ("gpt-4", "gpt-3.5", "o1", "o3", "o4")
_ALL_FREE = {"groq", "cerebras", "sambanova"}


def _keep(provider_key: str, model_id: str) -> bool:
    mid = model_id.lower()
    if any(p in mid for p in _EXCLUDE):
        return False
    if provider_key == "gemini":
        return model_id.startswith("gemini-")
    if provider_key == "groq":
        return any(mid.startswith(p) for p in _GROQ_PREFIXES)
    if provider_key == "openai":
        return any(model_id.startswith(p) for p in _OPENAI_PREFIXES)
    return True


def _is_free(provider_key: str, model_id: str, pricing: dict | None = None) -> bool:
    if provider_key in _ALL_FREE:
        return True
    if provider_key == "gemini":
        return "flash" in model_id.lower()
    if provider_key == "openrouter" and pricing:
        return str(pricing.get("prompt", "1")) == "0"
    return False


async def fetch_models(provider_key: str, base_url: str | None, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        if provider_key == "anthropic":
            return await _anthropic(client, api_key)
        if provider_key == "openrouter":
            return await _openrouter(client, api_key)
        if provider_key == "together":
            return await _together(client, api_key)
        return await _openai_compat(client, provider_key, base_url, api_key)


async def _openrouter(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    r = await client.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    r.raise_for_status()
    free, paid = [], []
    for m in r.json().get("data", []):
        mid = m.get("id", "")
        pricing = m.get("pricing", {})
        entry = {"id": mid, "name": m.get("name", mid), "free": _is_free("openrouter", mid, pricing)}
        (free if entry["free"] else paid).append(entry)
    free.sort(key=lambda m: m["name"].lower())
    paid.sort(key=lambda m: m["name"].lower())
    return free + paid[:20]


async def _anthropic(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    r = await client.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    r.raise_for_status()
    return [
        {"id": m["id"], "name": m.get("display_name", m["id"]), "free": False}
        for m in r.json().get("data", [])
        if _keep("anthropic", m.get("id", ""))
    ]


async def _together(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    r = await client.get(
        "https://api.together.xyz/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    r.raise_for_status()
    result = []
    for m in r.json():
        mid = m.get("id", "")
        if m.get("type") not in ("chat", "language", None):
            continue
        if not _keep("together", mid):
            continue
        result.append({"id": mid, "name": m.get("display_name", mid), "free": False})
    result.sort(key=lambda m: m["name"].lower())
    return result


async def _openai_compat(
    client: httpx.AsyncClient, provider_key: str, base_url: str, api_key: str
) -> list[dict]:
    r = await client.get(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    r.raise_for_status()
    result = []
    for m in r.json().get("data", []):
        mid = m.get("id", "")
        if not _keep(provider_key, mid):
            continue
        result.append({
            "id": mid,
            "name": m.get("name", mid),
            "free": _is_free(provider_key, mid),
        })
    result.sort(key=lambda m: (not m["free"], m["id"]))
    return result
