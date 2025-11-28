from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.sql import Select

from ..extensions import db


@dataclass(slots=True)
class Page:
    items: list
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        if self.per_page == 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page


def paginate_select(
    query: Select,
    *,
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100,
) -> Page:
    """Execute a Select with pagination support."""
    safe_page = max(page, 1)
    safe_per_page = min(max(per_page, 1), max_per_page)

    total_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.session.execute(total_query).scalar_one()

    stmt = query.limit(safe_per_page).offset((safe_page - 1) * safe_per_page)
    result = db.session.execute(stmt)
    items = list(result.scalars())

    return Page(items=items, total=total, page=safe_page, per_page=safe_per_page)

