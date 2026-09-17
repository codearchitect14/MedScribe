from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ContactInquiry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A public marketing-site contact form submission (plan.md Phase 8).
    No organization_id: submitted by a prospect who is not yet a user.
    """

    __tablename__ = "contact_inquiries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
