"""分页工具"""
import math
from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_order: str = "desc"

    def offset(self) -> int:
        return (max(self.page, 1) - 1) * self.effective_page_size()

    def effective_page_size(self) -> int:
        return min(max(self.page_size, 1), 100)


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def paginate(items: list, total: int, params: PageParams) -> dict:
    """构建分页响应"""
    page_size = params.effective_page_size()
    return {
        "items": items,
        "total": total,
        "page": max(params.page, 1),
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }
