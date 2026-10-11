"""Phase B Eval Harness — 加载 goldens，跑 Orchestrator.chat，做 schema 校验。

用法（conda env salesclaw）:
  cd backend && python -m eval.runner
  python -m eval.runner --case visit_intent
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("eval.runner")

GOLDENS_DIR = Path(__file__).resolve().parent / "goldens"


def _load_goldens(case_filter: Optional[str] = None) -> list[dict]:
    cases = []
    for path in sorted(GOLDENS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if case_filter and data.get("id") != case_filter and path.stem != case_filter:
            continue
        cases.append(data)
    return cases


async def _run_one(golden: dict, db, user) -> dict:
    from ai.orchestrator import Orchestrator
    from eval.schema_checks import score_trajectory

    orch = Orchestrator()
    inp = golden.get("input") or {}
    result = await orch.chat(
        message=inp.get("message", ""),
        user=user,
        session_id=f"eval-{golden.get('id')}",
        db=db,
        intent=inp.get("intent_override"),
        tenant_id=getattr(user, "tenant_id", "demo"),
    )
    return score_trajectory(result, golden)


def run_eval_suite(case_filter: Optional[str] = None) -> dict[str, Any]:
    """同步入口：返回 {passed, failed, results}。"""
    os.environ.setdefault("JWT_SECRET", os.environ.get("JWT_SECRET") or "eval-secret")

    from database import BusinessSessionLocal, User

    cases = _load_goldens(case_filter)
    if not cases:
        return {"passed": 0, "failed": 0, "results": [], "error": "no_cases"}

    db = BusinessSessionLocal()
    try:
        user = db.query(User).filter(User.is_deleted == 0).first()
        if user is None:
            # 最小 stub，避免无种子数据时完全无法跑
            class _Stub:
                id = 1
                tenant_id = "demo"
                username = "eval"
            user = _Stub()

        results = []
        for g in cases:
            try:
                score = asyncio.run(_run_one(g, db, user))
            except Exception as e:
                logger.exception("case %s failed", g.get("id"))
                score = {
                    "passed": False,
                    "errors": [f"exception:{e}"],
                    "case_id": g.get("id"),
                }
            results.append(score)

        passed = sum(1 for r in results if r.get("passed"))
        failed = len(results) - passed
        return {"passed": passed, "failed": failed, "results": results, "total": len(results)}
    finally:
        db.close()


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="SalesClaw Agent Eval Harness")
    parser.add_argument("--case", default=None, help="只跑指定 case id / 文件名")
    args = parser.parse_args(argv)
    summary = run_eval_suite(args.case)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("failed", 1) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
