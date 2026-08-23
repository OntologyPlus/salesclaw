"""培训效果因果归因 — 滞后窗口调度器（B 路径）

设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §9

无依赖外部 scheduler。设计要点：
- 进程内 daemon 线程：main.py 启动时 start_lag_scheduler()；
- tick() 是纯函数：扫 DecisionExecution 中 status=planned 且 created_at+30d<=now 的训练执行，
  抓 actual 快照并 update_progress；扫 status=executing 且 created_at+180d<=now 的，调 complete_execution；
- 完全可注入时钟（clock callable），测试可冻时；
- 重启恢复：依赖 DB 中 DecisionExecution 自身状态，无需独立调度表。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import settings
from database import DecisionExecution
from services.effect_tracking_service import effect_tracking_service
from services.training_effect_snapshot import snapshot_metrics, snapshot_to_dict

logger = logging.getLogger(__name__)


# 时钟可注入
def _default_clock() -> datetime:
    return datetime.utcnow()


class LagScheduler:
    """滞后窗口回填调度器（轻量，无外部依赖）"""

    # 30d → 进入 executing 并落 actual；180d → 完成
    _WINDOW_FIRST_DAYS = 30
    _WINDOW_TERMINAL_DAYS = 180

    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Optional[Callable[[], datetime]] = None,
        interval_seconds: float = 3600.0,
    ):
        self._factory = session_factory
        self._clock = clock or _default_clock
        self._interval = interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ────────────────────── 生命周期 ──────────────────────

    def start(self) -> None:
        """启动后台 daemon 线程（幂等）"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="training-lag-scheduler", daemon=True,
        )
        self._thread.start()
        logger.info("lag_scheduler started (interval=%.1fs)", self._interval)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("lag_scheduler stopped")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                logger.exception("lag_scheduler tick failed: %s", exc)
            self._stop.wait(self._interval)

    # ────────────────────── 纯函数（测试可调用） ──────────────────────

    def tick(self) -> dict:
        """单次扫描并执行一次回填。

        Returns:
            {first_window_processed: int, terminal_processed: int, error: int}
        """
        stats = {"first_window_processed": 0, "terminal_processed": 0, "error": 0}
        now = self._clock()
        try:
            db = self._factory()
        except Exception as exc:
            logger.warning("lag_scheduler: open session failed: %s", exc)
            stats["error"] += 1
            return stats

        try:
            # 1. first-window: planned → executing 并落 30d actual
            stats["first_window_processed"] = self._process_first_window(db, now)
            # 2. terminal: executing → completed（180d）
            stats["terminal_processed"] = self._process_terminal_window(db, now)
        except Exception as exc:
            logger.exception("lag_scheduler tick error: %s", exc)
            stats["error"] += 1
        finally:
            try:
                db.close()
            except Exception:
                pass
        return stats

    # ────────────────────── 内部 ──────────────────────

    def _process_first_window(self, db: Session, now: datetime) -> int:
        """处理 30d 窗口：status=planned + 30d 到期 → update_progress"""
        threshold = now - timedelta(days=self._WINDOW_FIRST_DAYS)
        rows = (
            db.query(DecisionExecution)
            .filter(
                DecisionExecution.is_deleted == 0,
                DecisionExecution.decision_type == "training",
                DecisionExecution.status == "planned",
                DecisionExecution.created_at <= threshold,
            )
            .all()
        )
        processed = 0
        for row in rows:
            try:
                snap = snapshot_metrics(db, row.user_id, kind="actual", window_days=30)
                effect_tracking_service.update_progress(
                    execution_id=row.id,
                    tenant_id=row.tenant_id,
                    db=db,
                    actual_metrics=snapshot_to_dict(snap.metrics),
                )
                processed += 1
            except Exception as exc:
                logger.warning("first_window process failed exec=%s: %s", row.id, exc)
                try:
                    db.rollback()
                except Exception:
                    pass
        return processed

    def _process_terminal_window(self, db: Session, now: datetime) -> int:
        """处理 180d 窗口：status=executing + 180d 到期 → complete_execution"""
        threshold = now - timedelta(days=self._WINDOW_TERMINAL_DAYS)
        rows = (
            db.query(DecisionExecution)
            .filter(
                DecisionExecution.is_deleted == 0,
                DecisionExecution.decision_type == "training",
                DecisionExecution.status == "executing",
                DecisionExecution.created_at <= threshold,
            )
            .all()
        )
        processed = 0
        for row in rows:
            try:
                effect_tracking_service.complete_execution(
                    execution_id=row.id,
                    tenant_id=row.tenant_id,
                    db=db,
                    actual_metrics=None,  # 已有 actual 合并
                )
                processed += 1
            except Exception as exc:
                logger.warning("terminal_window process failed exec=%s: %s", row.id, exc)
                try:
                    db.rollback()
                except Exception:
                    pass
        return processed


# ──────────────────────────────────────────────
# 全局单例（在 main.py / bootstrap 启动）
# ──────────────────────────────────────────────

_lag_scheduler: Optional[LagScheduler] = None


def get_lag_scheduler() -> Optional[LagScheduler]:
    return _lag_scheduler


def start_lag_scheduler(session_factory: Callable[[], Session]) -> LagScheduler:
    """启动滞后调度器（懒初始化单例）。可重复调用，幂等。"""
    global _lag_scheduler
    if _lag_scheduler is None:
        _lag_scheduler = LagScheduler(session_factory=session_factory)
    _lag_scheduler.start()
    return _lag_scheduler


def stop_lag_scheduler() -> None:
    global _lag_scheduler
    if _lag_scheduler is not None:
        _lag_scheduler.stop()


__all__ = [
    "LagScheduler",
    "get_lag_scheduler",
    "start_lag_scheduler",
    "stop_lag_scheduler",
]
