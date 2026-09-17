class ProviderError(Exception):
    """Base error for a single provider call failing (network, 5xx, malformed response)."""


class RateLimitExceededError(ProviderError):
    """The provider itself returned a 429 / rate limit response."""


class ResponseValidationError(Exception):
    """The provider returned content that could not be parsed into the expected schema."""


class AllProvidersExhaustedError(Exception):
    """Every configured provider failed or had no remaining quota for this call."""
