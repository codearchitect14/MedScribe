import httpx

from app.core.config import get_settings
from app.llm.adapters.base import ProviderAdapter, ProviderResponse, truncate_for_error
from app.llm.exceptions import ProviderError, RateLimitExceededError


class GroqAdapter(ProviderAdapter):
    """Groq's chat completions endpoint, OpenAI-compatible."""

    name = "groq"

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ProviderResponse:
        settings = get_settings()
        if not settings.groq_api_key:
            raise ProviderError("GROQ_API_KEY is not configured")

        payload = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.groq_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Groq request failed: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitExceededError("Groq rate limit exceeded")
        if response.status_code >= 400:
            raise ProviderError(f"Groq returned {response.status_code}: {truncate_for_error(response.text)}")

        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"Unexpected Groq response shape: {truncate_for_error(str(body))}") from exc

        return ProviderResponse(
            content=content,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            model=settings.groq_model,
        )
