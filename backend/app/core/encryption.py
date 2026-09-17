"""Application-level encryption for sensitive fields at rest (e.g. patient identifiers).

Uses Fernet symmetric encryption. The key is read from FIELD_ENCRYPTION_KEY in the
environment, never stored in source control. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from datetime import date
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import get_settings


@lru_cache
def get_fernet() -> Fernet:
    settings = get_settings()
    if not settings.field_encryption_key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. Generate one and set it in the environment "
            "before storing or reading encrypted fields."
        )
    return Fernet(settings.field_encryption_key.encode())


def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    try:
        return get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt field: invalid token or wrong key") from exc


class EncryptedString(TypeDecorator):
    """Stores a string column encrypted at rest, transparent to application code."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt_value(value)


class EncryptedDate(TypeDecorator):
    """Stores a date column encrypted at rest as ISO text, transparent to application code."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: date | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt_value(value.isoformat())

    def process_result_value(self, value: str | None, dialect) -> date | None:
        if value is None:
            return None
        return date.fromisoformat(decrypt_value(value))
