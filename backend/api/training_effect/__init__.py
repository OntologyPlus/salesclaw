"""培训效果因果归因 API（B 路径）

设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §10

路由前缀：/v1/training/effect
"""
from .routes import router

__all__ = ["router"]
