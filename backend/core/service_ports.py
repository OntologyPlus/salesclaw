"""服务接口协议层 — 跨域通信的抽象端口

高内聚低耦合原则：跨域调用通过 Protocol 接口，禁止直接 import 跨域 service。
使用 Python Protocol（鸭子类型），运行时无强制，但提供了清晰的接口契约。
"""
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ProfileServicePort(Protocol):
    """画像服务端口 — 其他域读写画像的统一接口"""

    def update_ability_score(self, db, user_id: int, dimension: str,
                            delta: float, source: str, source_id: int = None,
                            evidence: dict = None) -> dict: ...

    def get_ability_summary(self, db, user_id: int) -> dict: ...

    def get_weakest_dimensions(self, db, user_id: int, n: int = 2) -> list: ...

    def detect_weakness(self, db, user_id: int, threshold: float = 70.0) -> list: ...

    def apply_decay(self, db, tenant_id: str, days: int = 30) -> int: ...


@runtime_checkable
class CollectionServicePort(Protocol):
    """采集服务端口"""

    def apply_ability_impact(self, db, item_id: int) -> dict: ...

    def validate_item_values(self, db, item_id: int) -> list: ...

    def compute_derived_fields(self, db, item_id: int) -> dict: ...


@runtime_checkable
class TrainingServicePort(Protocol):
    """培训服务端口"""

    def recommend_scenarios(self, db, user_id: int, context: dict = None) -> list: ...

    def apply_session_to_ability(self, db, session_id: int) -> dict: ...


@runtime_checkable
class DecisionServicePort(Protocol):
    """决策服务端口

    参考1（决策支持体系）思路的吸收落点：
    - reason / confidence 提供"可解释 + 置信"能力（对应参考1 推理引擎/置信融合）
    - evaluate_diagnosis 提供统一 4 色灯诊断（对应参考2 诊断体系映射）
    """

    def attribute_change(self, db, metric: str, scope: dict, period: dict) -> list: ...

    def simulate(self, db, scenario: dict) -> dict: ...

    def derive_recommendations(self, db, insight_id: int) -> list: ...

    def accept_recommendation(self, db, rec_id: int, user_id: int) -> dict: ...

    def evaluate_diagnosis(self, db, tenant_id: str) -> dict:
        """统一诊断：将合规告警与决策预警归并为 4 色灯（GREEN/YELLOW/RED/BLACK）"""
        ...

    def reason(self, db, target_type: str, target_id: int,
               explanation_type: str = "causal") -> dict:
        """可解释推理：基于 InsightChain 因果链输出指定维度的解释"""
        ...

    def confidence(self, db, chain_id: int) -> float:
        """置信度查询：返回因果链推理的置信分数"""
        ...


@runtime_checkable
class NotificationServicePort(Protocol):
    """通知服务端口"""

    def send_recommendation(self, db, recommendation: dict) -> dict: ...


@runtime_checkable
class SalesServicePort(Protocol):
    """销售服务端口"""

    def smart_suggest_plan(self, db, user_id: int, period: str) -> list: ...

    def skill_fit(self, db, user_id: int, doctor_id: int) -> dict: ...


@runtime_checkable
class DataLineageServicePort(Protocol):
    """数据流追踪服务端口"""

    def record_lineage(self, db, source: dict, target: dict,
                       transformation: str, user_id: int = None,
                       tenant_id: str = None) -> int: ...

    def trace_upstream(self, db, target_type: str, target_id: int) -> list: ...

    def trace_downstream(self, db, source_type: str, source_id: int) -> list: ...
