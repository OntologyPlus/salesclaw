"""决策支持 API - 请求模型"""
from pydantic import BaseModel, Field


class SimulateRequest(BaseModel):
    visit_change: float = Field(0, ge=-0.5, le=1.0, description="拜访频次变化率")
    training_change: float = Field(0, ge=-0.5, le=1.0, description="培训投入变化率")


class CreateExecutionRequest(BaseModel):
    decision_type: str  # visit_plan/training/coverage
    title: str
    description: str = ""
    baseline: dict = Field(default_factory=dict)
    target: dict = Field(default_factory=dict)


class UpdateProgressRequest(BaseModel):
    actual_metrics: dict = Field(default_factory=dict)


class ConfirmDiagnosisRequest(BaseModel):
    """确认诊断建议，进入随访闭环"""
    rep_id: int
    domain: str  # 合规/学术/拜访/执行
    suggestion: dict = Field(
        ...,
        description="diagnosis_loop 输出的单条建议 {dimension, reason, recommended_courses[], baseline_metrics, target_metrics}",
    )


class CompleteLoopRequest(BaseModel):
    """完成随访执行→自动验证+判定闭环"""
    actual_metrics: dict = Field(default_factory=dict)
    force_closure_state: str | None = None  # closed|partial|unresolved


class AiDiagnoseRequest(BaseModel):
    """AI 诊断请求：结构化推理生成 Diagnosis 草稿实体"""
    domain: str = Field("coverage", description="业务域 coverage/visit/adoption/...")
    target_type: str | None = Field(None, description="hospital/department/doctor/product")
    target_id: int | None = Field(None, description="目标对象 ID")


class ConfirmDiagnosisByIdRequest(BaseModel):
    """人工确认某条诊断草稿（合规闸门）"""
    diagnosis_id: int


class AdvanceDiagnosisRequest(BaseModel):
    """推进诊断状态机 confirmed→executing→verified→closed"""
    diagnosis_id: int
    to_status: str  # executing|verified|closed


class ClearSignalRequest(BaseModel):
    """消除异常信号（需 API 触发，满足合规人工留痕）"""
    signal_id: int


class ParadigmListRequest(BaseModel):
    """查询范式库（本体 Paradigm 实体，新表）"""
    domain: str | None = None


class ParadigmDeriveRequest(BaseModel):
    """从已闭环执行沉淀通用解题范式"""
    execution_id: int
    domain: str = "general"
