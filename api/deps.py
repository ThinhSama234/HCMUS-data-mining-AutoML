"""Shared API dependencies: pagination + the Page envelope (FR-006)."""
from dataclasses import dataclass

from fastapi import Query

MAX_LIMIT = 200


@dataclass
class Pagination:
    limit: int
    offset: int


def pagination(limit: int = Query(50, ge=1), offset: int = Query(0, ge=0)) -> Pagination:
    """Query params `limit` (default 50, clamped to 200) + `offset`."""
    return Pagination(limit=min(limit, MAX_LIMIT), offset=offset)


def page(items, total, pg: Pagination) -> dict:
    return {"items": items, "total": total, "limit": pg.limit, "offset": pg.offset}
