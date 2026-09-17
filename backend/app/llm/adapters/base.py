from abc import ABC, abstractmethod
from dataclasses import dataclass


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
