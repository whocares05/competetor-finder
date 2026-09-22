"""LLM Provider Adapters: Groq (Ultra-Fast Free Tier) and Anthropic Claude

Implements BaseLLMProvider with strict structured JSON schema outputs and error handling.
"""
import json
import time
from typing import Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.config.settings import settings
from app.providers.base import (
    BaseLLMProvider,
    ProviderError,
    RateLimitError,
)

T = TypeVar("T", bound=BaseModel)


class GroqLLMAdapter(BaseLLMProvider):
    """Adapter for Groq's high-speed, free Llama-3 API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.default_model = settings.GROQ_DEFAULT_MODEL or "llama-3.3-70b-versatile"
        self.escalation_model = settings.GROQ_ESCALATION_MODEL or "llama-3.3-70b-versatile"
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, float, int]:
        """Call Groq API with JSON mode and validate against Pydantic schema."""
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is not configured", provider="groq")

        target_model = model or self.default_model
        schema_json = json.dumps(schema.model_json_schema(), indent=2)

        sys_msg = (
            (system_prompt or "You are an expert market intelligence and competitor analysis AI.")
            + "\nCRITICAL INSTRUCTION: You must respond ONLY with a single valid JSON object strictly matching this JSON schema:\n"
            + schema_json
            + "\nDo not include markdown codeblocks (```json), explanations, or preamble. Return raw JSON only."
        )

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        start_time = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=headers)
            except httpx.TimeoutException:
                raise ProviderError("Groq API request timed out", provider="groq")
            except Exception as e:
                raise ProviderError(f"Network error calling Groq: {str(e)}", provider="groq")

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 429:
            raise RateLimitError("Groq rate limit exceeded", provider="groq", status_code=429)

        if not response.is_success:
            raise ProviderError(
                f"Groq API returned error {response.status_code}: {response.text}",
                provider="groq",
                status_code=response.status_code,
            )

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        try:
            # Clean possible markdown wrapping if any
            clean_content = content.strip()
            if clean_content.startswith("```"):
                clean_content = clean_content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed_dict = json.loads(clean_content)
            parsed_obj = schema.model_validate(parsed_dict)
            return parsed_obj, 0.0, latency_ms
        except Exception as e:
            raise ProviderError(
                f"Failed to parse Groq response into schema {schema.__name__}: {str(e)}. Content: {content[:300]}",
                provider="groq",
            )


class AnthropicLLMAdapter(BaseLLMProvider):
    """Adapter for Anthropic Claude API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.default_model = settings.ANTHROPIC_DEFAULT_MODEL or "claude-3-5-haiku-latest"
        self.escalation_model = settings.ANTHROPIC_ESCALATION_MODEL or "claude-3-7-sonnet-latest"
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, float, int]:
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured", provider="anthropic")

        target_model = model or self.default_model
        schema_json = json.dumps(schema.model_json_schema(), indent=2)

        sys_msg = (
            (system_prompt or "You are an expert market intelligence AI.")
            + "\nRespond ONLY with valid JSON conforming to this schema:\n"
            + schema_json
        )

        start_time = time.time()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": target_model,
            "max_tokens": 4096,
            "system": sys_msg,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)

        latency_ms = int((time.time() - start_time) * 1000)

        if not response.is_success:
            raise ProviderError(f"Anthropic error: {response.text}", provider="anthropic")

        data = response.json()
        content = data["content"][0]["text"].strip()
        parsed_dict = json.loads(content)
        return schema.model_validate(parsed_dict), 0.005, latency_ms


def create_llm_adapter() -> BaseLLMProvider:
    """Factory creating active LLM adapter according to LLM_PROVIDER setting."""
    provider = (settings.LLM_PROVIDER or "groq").lower()
    if provider == "groq" or (settings.GROQ_API_KEY and not settings.ANTHROPIC_API_KEY):
        return GroqLLMAdapter()
    return AnthropicLLMAdapter()
