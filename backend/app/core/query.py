from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.schemas.pagination import PageParams


async def paginate(session: AsyncSession, stmt: Select, params: PageParams) -> tuple[list, int]:
    """Runs `stmt` with an offset/limit applied, plus a separate COUNT query
    for the total. `stmt` should already have its WHERE/ORDER BY applied."""
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    paged_stmt = stmt.offset(params.offset).limit(params.page_size)
    items = list((await session.execute(paged_stmt)).scalars().all())
    return items, total
