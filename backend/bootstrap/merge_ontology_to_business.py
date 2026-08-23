"""一次性数据迁移：psp_ontology.db → psp.db —— 第 14 批双库合一收尾。

策略：SQLAlchemy 反射两库同名表，逐表读源 src → 写 dst。先在 dst 用源 DDL
反推建表+索引，再 INSERT OR IGNORE 用 SQLite raw API（防 SQLite concurrent
lock，并把每张表放独立事务）。

阶段 A：反推 DDL 在 psp.db 内 CREATE TABLE IF NOT EXISTS
阶段 B：逐表（独立事务）INSERT OR IGNORE
阶段 C：校验 dst 行数 ≥ src
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
SRC_DB = DATA_DIR / "psp_ontology.db"
DST_DB = DATA_DIR / "psp.db"
BACKUP_SRC = DATA_DIR / "psp_ontology.db.pre14b.backup"
BACKUP_DST = DATA_DIR / "psp.db.pre14b.backup"

TABLES: tuple[str, ...] = (
    "action_definitions",
    "action_executions",
    "ai_conversation_logs",
    "link_definitions",
    "object_definitions",
    "object_permission_definitions",
    "ontology_ai_access",
    "ontology_change_log",
    "role_definitions",
    "role_permission_definitions",
)


def _safe_count(conn, t: str) -> int:
    try:
        return conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    except sqlite3.OperationalError:
        return -1


def phase_a_create_tables() -> None:
    """从源库提取每张表的 CREATE 语句，重放到 dst。"""
    src = sqlite3.connect(str(SRC_DB))
    dst = sqlite3.connect(str(DST_DB))
    try:
        dst_existing = set(
            t[0] for t in dst.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall())
        for t in TABLES:
            if t in dst_existing:
                logger.info("  %s 已存在", t)
                continue
            ddl_rows = src.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE tbl_name = ? AND sql IS NOT NULL "
                "ORDER BY type DESC, name", (t,)).fetchall()
            for (sql,) in ddl_rows:
                p = sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
                p = p.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS", 1)
                p = p.replace("CREATE UNIQUE INDEX",
                              "CREATE UNIQUE INDEX IF NOT EXISTS", 1)
                try:
                    dst.execute(p)
                except Exception as e:
                    logger.warning("    DDL 失败 %s / %s", str(e)[:80], p[:60])
            dst.commit()
            logger.info("  %s DDL 块数=%d", t, len(ddl_rows))
    finally:
        src.close()
        dst.close()


def phase_b_copy_data() -> dict[str, dict]:
    """逐表以独立事务拷数据（避免 ATTACH 长事务的锁争用）。"""
    # 备份
    for s, d in [(SRC_DB, BACKUP_SRC), (DST_DB, BACKUP_DST)]:
        if not d.exists():
            shutil.copy2(s, d)
            logger.info("  backup %s -> %s", s.name, d.name)

    src = sqlite3.connect(str(SRC_DB))
    try:
        summary: dict[str, dict] = {}
        for t in TABLES:
            rows = list(src.execute(f"SELECT * FROM {t}").fetchall())
            if not rows:
                summary[t] = {"src": 0, "dst_before": -1, "dst_after": -1,
                                "inserted": 0}
                continue
            col_info = src.execute(f"PRAGMA table_info({t})").fetchall()
            cols = [d[1] for d in col_info]  # name 是第 2 列
            dst = sqlite3.connect(str(DST_DB), timeout=20.0)
            try:
                dst_before = _safe_count(dst, t)
                placeholders = ",".join("?" for _ in cols)
                col_list = ",".join(cols)
                dst.executemany(
                    f"INSERT OR IGNORE INTO {t} ({col_list}) VALUES ({placeholders})",
                    rows)
                dst.commit()
                dst_after = _safe_count(dst, t)
                actual = dst_after - dst_before if dst_before >= 0 else len(rows)
                logger.info(
                    "  %-32s src=%4d dst_before=%4d dst_after=%4d actual=%4d",
                    t, len(rows), max(dst_before, 0), dst_after, actual,
                )
                summary[t] = {"src": len(rows), "dst_before": dst_before,
                                "dst_after": dst_after, "inserted": actual}
            finally:
                dst.close()
        return summary
    finally:
        src.close()


def phase_c_verify(summary: dict[str, dict]) -> bool:
    ok = True
    dst = sqlite3.connect(str(DST_DB))
    try:
        for t in TABLES:
            if t not in summary:
                continue
            src_n = summary[t]["src"]
            if src_n == 0:
                # src 没数据，跳过该表的对账
                continue
            dst_n = summary[t]["dst_after"]
            if dst_n < src_n:
                logger.error("[FAIL] %s src=%d > dst=%d", t, src_n, dst_n)
                ok = False
    finally:
        dst.close()
    if ok:
        logger.info("[phase C] OK：全部 src>0 的表 dst 行数 ≥ src")
    return ok


def phase_b_probe_summary() -> dict[str, dict]:
    """幂等检测：直读 dst 当前行数 + src 行数（不下事务）。"""
    src = sqlite3.connect(str(SRC_DB))
    dst = sqlite3.connect(str(DST_DB))
    summary: dict[str, dict] = {}
    try:
        for t in TABLES:
            try:
                src_n = src.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                src_n = 0
            dst_n = _safe_count(dst, t)
            summary[t] = {"src": src_n, "dst_before": dst_n, "dst_after": dst_n,
                          "inserted": 0}
    finally:
        src.close(); dst.close()
    return summary


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)-7s [%(name)s] %(message)s")
    if not SRC_DB.exists():
        logger.info("[skip] %s 不存在，跳过迁移", SRC_DB)
        return 0
    # 第 15 批：幂等 marker 已存在则跳过阶段 B 但仍校验
    done_marker = DATA_DIR / ".merge_ontology_to_business.done"
    if done_marker.exists():
        logger.info("[skip] 已标记完成 %s，跳过 phase A/B（仅 phase C 校验）",
                    done_marker.name)
        # 仍跑一次校验
        summary_eval = phase_b_probe_summary()
        ok = phase_c_verify(summary_eval)
        return 0 if ok else 2
    try:
        phase_a_create_tables()
        summary = phase_b_copy_data()
        if not phase_c_verify(summary):
            return 2
    except Exception as e:
        logger.exception("[abort] 迁移失败: %s", e)
        return 3
    print("\n=== 迁移摘要 ===")
    print(f"{'table':40s} {'src':>6s} {'dst_before':>11s} {'inserted':>9s}")
    for t, v in summary.items():
        b = max(v["dst_before"], 0)
        print(f"{t:40s} {v['src']:>6d} {b:>11d} {v['inserted']:>9d}")
    print("\n[OK] 数据迁移完成。后续手工步骤：")
    print("  1) 启动 app 确认 /health 与 /health/neo4j 正常")
    print("  2) 删 alembic/versions/ontology/ 整个目录")
    print("  3) 删 alembic.ini 的 [ontology] section")
    print("  4) mv data/psp_ontology.db data/psp_ontology.db.archived")
    # 第 15 批：标记归档，便于重复执行时自跳过
    done_marker = DATA_DIR / ".merge_ontology_to_business.done"
    done_marker.write_text(
        f"merged on {Path(__file__).stat().st_mtime:.0f}\n"
        f"summary: {summary}\n",
        encoding="utf-8")
    print(f"  5) 标记完成: {done_marker.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
