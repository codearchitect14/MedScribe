import httpx

from app.core.config import get_settings
from app.llm.adapters.base import ProviderAdapter, ProviderResponse
from app.llm.exceptions import ProviderError, RateLimitExceededError


class GeminiAdapter(ProviderAdapter):
    """Google Gemini's generateContent endpoint."""

    name = "gemini"

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ProviderResponse:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ProviderError("GEMINI_API_KEY is not configured")

        generation_config: dict = {"maxOutputTokens": max_tokens, "temperature": 0.2}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }

        url = f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
                response = await client.post(
                    url,
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitExceededError("Gemini rate limit exceeded")
        if response.status_code >= 400:
            raise ProviderError(f"Gemini returned {response.status_code}: {response.text}")

        body = response.json()
        try:
            candidate = body["candidates"][0]
            content = "".join(part["text"] for part in candidate["content"]["parts"])
            usage = body.get("usageMetadata", {})
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"Unexpected Gemini response shape: {body}") from exc

        return ProviderResponse(
            content=content,
            tokens_input=usage.get("promptTokenCount", 0),
            tokens_output=usage.get("candidatesTokenCount", 0),
            model=settings.gemini_model,
        )
