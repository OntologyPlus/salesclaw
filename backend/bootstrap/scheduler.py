"""调度器启动 - 集中管理各域后台定时任务

原先散落在 main.py 的 startup() 里逐个 import + 启动，
现统一在此登记，便于查看「系统里到底跑了哪些定时任务」。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _iter_schedulers():
    """(名称, 启动函数) 列表。延迟 import，避免启动期循环依赖。"""
    from services.insight_scheduler import start_insight_scheduler
    from services.notification_scheduler import start_notification_scheduler
    from services.suggestion_evaluation_scheduler import (
        start_suggestion_evaluation_scheduler,
    )

    return (
        ("AI 洞察预生成（启动后 60s 首跑，之后每 24h）", start_insight_scheduler),
        ("通知催促", start_notification_scheduler),
        ("建议行动延迟评估（每 30min 扫描到期项）", start_suggestion_evaluation_scheduler),
    )


def start_all_schedulers() -> dict:
    """启动全部调度器。单个失败不阻断其余，也不阻断应用启动。"""
    results: dict[str, str] = {}
    for name, starter in _iter_schedulers():
        try:
            starter()
            results[name] = "started"
            logger.info("[bootstrap] 调度器已启动：%s", name)
        except Exception as e:
            results[name] = f"failed: {e}"
            logger.warning("[bootstrap] 调度器启动失败 %s: %s", name, e)
    return results
