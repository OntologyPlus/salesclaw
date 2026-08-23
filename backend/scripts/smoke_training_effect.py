"""培训效果因果归因 (B 路径) — smoke 自检脚本

运行方式：
    cd backend && python scripts/smoke_training_effect.py

不依赖 Neo4j、LLM、生产 DB schema；纯模块加载 + 函数实例化级别自检。
如需端到端验证，请使用 FastAPI TestClient 跑通业务 API（运行入口）。
"""
from __future__ import annotations

import importlib
import os
import sys
import traceback

# 兜底环境变量（不参与生产运行；仅供 smoke 自检使用）。
os.environ.setdefault("JWT_SECRET", "smoke_test_only_secret")
os.environ.setdefault("NEO4J_URI", "bolt://127.0.0.1:17687")  # smoke 不连 Neo4j
os.environ.setdefault("APP_ENV", "test")

# 将 backend 根目录加入 sys.path，使脚本可直接 python 启动
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


# (导入此 module 的对象 attr_path 是否包含 module_name 前缀, 短名)
CHECKS = [
    ("settings.TRAINING_LAG_WINDOWS", "config"),
    ("TRAINING_EFFECT_METRICS", "core.constants"),
    ("event_bus", "ai.event_bus"),
    ("register_subscribers", "ai.event_subscribers"),
    ("snapshot_metrics", "services.training_effect_snapshot"),
    ("LagScheduler", "services.lag_scheduler"),
    ("handle_training_completed", "services.training_effect_service"),
    ("router", "api.training_effect.routes"),
    ("api_router", "api"),
]


def main() -> int:
    failures: list[tuple[str, str]] = []
    print("=" * 70)
    print("Training Effect (B 路径) smoke check")
    print("=" * 70)
    for attr_name, module_name in CHECKS:
        try:
            mod = importlib.import_module(module_name)
            obj = mod
            for piece in attr_name.split("."):
                obj = getattr(obj, piece)
            print(f"  [OK]   {module_name}.{attr_name}")
        except Exception as exc:
            tb = traceback.format_exc().splitlines()[-3:]
            failures.append((f"{module_name}.{attr_name}", "\n".join(tb)))
            print(f"  [FAIL] {module_name}.{attr_name}: {exc}")

    print("-" * 70)
    if failures:
        print(f"FAILED checks: {len(failures)}")
        for label, tb in failures:
            print(f"\n--- {label} ---\n{tb}\n")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
