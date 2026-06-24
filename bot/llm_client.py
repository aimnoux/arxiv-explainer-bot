import asyncio
import json
import re

import anthropic
import openai

from .config import PROVIDERS

MAX_RATE_LIMIT_WAIT = 60  # секунд — не ждём дольше этого

SYSTEM_PROMPT = """\
You are a scientific paper analyzer. Given a research paper, produce a structured analysis in {language}.
Return ONLY a JSON object with these exact keys:
{{
  "title": "название статьи",
  "tldr": "1-2 предложения: суть работы для неспециалиста",
  "problem": "какую проблему решает (2-3 предложения)",
  "method": "как решает, ключевые технические идеи (3-5 предложений)",
  "results": "главные результаты и цифры (2-4 предложения)",
  "limitations": "ограничения и слабые стороны (1-3 предложения)",
  "why_it_matters": "почему важно для области (1-2 предложения)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}
Do not add any text outside the JSON. Language: {language}.\
"""

USER_PROMPT = """\
Paper title: {title}
Authors: {authors}
Abstract: {abstract}

Full text (truncated):
{full_text}\
"""

REQUIRED_KEYS = {"title", "tldr", "problem", "method", "results", "limitations", "why_it_matters", "keywords"}


def _parse_retry_after(error_text: str) -> int | None:
    m = re.search(r"retry_after_seconds['\"]:\s*([\d.]+)", error_text) or \
        re.search(r"Retry-After['\"]:\s*['\"]?([\d.]+)", error_text) or \
        re.search(r"try again in ([\d.]+)s", error_text, re.IGNORECASE)
    if m:
        return max(1, int(float(m.group(1))) + 1)
    return None


def get_llm_client(config: dict):
    provider = config["llm_provider"]
    if provider == "anthropic":
        return AnthropicClient(config)
    return OpenAICompatibleClient(config)


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    # strip possible markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"В ответе LLM отсутствуют ключи: {missing}")
    return data


class OpenAICompatibleClient:
    def __init__(self, config: dict):
        provider_cfg = PROVIDERS[config["llm_provider"]]
        self.client = openai.AsyncOpenAI(
            api_key=config["llm_api_key"],
            base_url=provider_cfg["base_url"],
        )
        self.model = config["llm_model"]
        self.language = config.get("language", "ru")

    async def analyze(self, paper: dict) -> dict:
        system = SYSTEM_PROMPT.format(language=self.language)
        user = USER_PROMPT.format(
            title=paper["title"],
            authors=", ".join(paper["authors"]),
            abstract=paper["abstract"],
            full_text=paper["full_text"],
        )
        return await self._call(system, user)

    async def _call(self, system: str, user: str, retry: bool = True) -> dict:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
        except openai.RateLimitError as e:
            wait = _parse_retry_after(str(e))
            if wait and wait <= MAX_RATE_LIMIT_WAIT:
                await asyncio.sleep(wait)
                return await self._call(system, user, retry=retry)
            raise ValueError(
                f"Провайдер перегружен (rate limit). Попробуйте через ~{wait or 60} сек или смените модель (/status → wizard)."
            ) from e

        raw = resp.choices[0].message.content or ""
        try:
            return _parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            if retry:
                clarified_system = system + "\n\nIMPORTANT: Your previous response was not valid JSON. Return ONLY the JSON object, nothing else."
                return await self._call(clarified_system, user, retry=False)
            raise ValueError("LLM вернул некорректный JSON после повторного запроса.")


class AnthropicClient:
    def __init__(self, config: dict):
        self.client = anthropic.AsyncAnthropic(api_key=config["llm_api_key"])
        self.model = config["llm_model"]
        self.language = config.get("language", "ru")

    async def analyze(self, paper: dict) -> dict:
        system = SYSTEM_PROMPT.format(language=self.language)
        user = USER_PROMPT.format(
            title=paper["title"],
            authors=", ".join(paper["authors"]),
            abstract=paper["abstract"],
            full_text=paper["full_text"],
        )
        return await self._call(system, user)

    async def _call(self, system: str, user: str, retry: bool = True) -> dict:
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError as e:
            wait = _parse_retry_after(str(e))
            if wait and wait <= MAX_RATE_LIMIT_WAIT:
                await asyncio.sleep(wait)
                return await self._call(system, user, retry=retry)
            raise ValueError(
                f"Провайдер перегружен (rate limit). Попробуйте через ~{wait or 60} сек."
            ) from e

        raw = resp.content[0].text if resp.content else ""
        try:
            return _parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            if retry:
                clarified_system = system + "\n\nIMPORTANT: Your previous response was not valid JSON. Return ONLY the JSON object, nothing else."
                return await self._call(clarified_system, user, retry=False)
            raise ValueError("LLM вернул некорректный JSON после повторного запроса.")
