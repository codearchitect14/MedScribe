"""Bootstrap the first admin user for an organization.

Registration is admin-invited only; there is no public self-signup endpoint.
This script creates the very first admin so they can then invite everyone
else through POST /users.

Usage:
    python -m scripts.create_admin --org "Acme Clinic" --email admin@acme.com --password "ChangeMe123!" --name "Admin User"
"""

import argparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, help="Organization name (created if it does not exist)")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.sync_database_url)

    with Session(engine) as session:
        org = session.execute(select(Organization).where(Organization.name == args.org)).scalar_one_or_none()
        if org is None:
            org = Organization(name=args.org)
            session.add(org)
            session.flush()

        existing = session.execute(select(User).where(User.email == args.email.lower())).scalar_one_or_none()
        if existing is not None:
            print(f"User {args.email} already exists.")
            return

        user = User(
            email=args.email.lower(),
            hashed_password=hash_password(args.password),
            full_name=args.name,
            role=UserRole.admin,
            organization_id=org.id,
            is_active=True,
        )
        session.add(user)
        session.commit()

    print(f"Created admin '{args.email}' in organization '{args.org}'.")


if __name__ == "__main__":
    main()
