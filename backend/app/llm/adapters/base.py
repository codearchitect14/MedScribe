from abc import ABC, abstractmethod
from dataclasses import dataclass

ERROR_SNIPPET_MAX_CHARS = 200


def truncate_for_error(text: str, max_chars: int = ERROR_SNIPPET_MAX_CHARS) -> str:
    """Bounds how much of a provider's raw response body ends up embedded in
    an exception message (and, from there, in server-side logs - see
    docs/data-flow-review.md). A short snippet is still useful for
    debugging a malformed/erroring provider response; the full body is not
    needed, and in the worst case a provider could echo request content
    (including transcript-derived text) back in an error body.
    """
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... (truncated, {len(text)} chars total)"


@dataclass
class ProviderResponse:
    content: str
    tokens_input: int
    tokens_output: int
    model: str


class ProviderAdapter(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ProviderResponse:
        """Runs one completion call. Raises app.llm.exceptions.ProviderError
        (or RateLimitExceededError) on failure. Never raises for a
        successful-but-malformed JSON body; that is validated by the caller.
        """
        raise NotImplementedError
