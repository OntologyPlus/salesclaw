"""Link 注册表 - 实体间关系定义"""
from typing import Optional


# ──────────────────────────────────────────────
# Link 定义
# ──────────────────────────────────────────────

LINKS = [
    # ── 销售执行域 ──
    {
        "name": "visit_plan_hospital",
        "display_name": "拜访计划-医院",
        "source_object": "VisitPlan",
        "target_object": "Hospital",
        "cardinality": "N:N",
        "description": "拜访计划涉及的医院",
    },
    {
        "name": "visit_plan_doctor",
        "display_name": "拜访计划-医生",
        "source_object": "VisitPlan",
        "target_object": "Doctor",
        "cardinality": "N:N",
        "description": "拜访计划涉及的医生",
    },
    {
        "name": "visit_record_visit_plan",
        "display_name": "拜访记录-计划",
        "source_object": "VisitRecord",
        "target_object": "VisitPlan",
        "cardinality": "N:1",
        "description": "拜访记录关联的计划",
    },
    {
        "name": "visit_feedback_visit_record",
        "display_name": "拜访反馈-记录",
        "source_object": "VisitFeedback",
        "target_object": "VisitRecord",
        "cardinality": "N:1",
        "description": "反馈所属的拜访记录",
    },
    {
        "name": "user_zone",
        "display_name": "用户-区域",
        "source_object": "User",
        "target_object": "Zone",
        "cardinality": "N:1",
        "description": "用户负责的区域",
    },
    {
        "name": "coverage_assignment_doctor",
        "display_name": "覆盖分管-医生",
        "source_object": "CoverageAssignment",
        "target_object": "Doctor",
        "cardinality": "N:N",
        "description": "代表分管的医生",
    },
    {
        "name": "coverage_assignment_hospital",
        "display_name": "覆盖分管-医院",
        "source_object": "CoverageAssignment",
        "target_object": "Hospital",
        "cardinality": "N:N",
        "description": "代表分管的医院",
    },
    {
        "name": "doctor_hospital",
        "display_name": "医生-医院",
        "source_object": "Doctor",
        "target_object": "Hospital",
        "cardinality": "N:1",
        "description": "医生就职于医院",
    },
    {
        "name": "visit_plan_user",
        "display_name": "拜访计划-代表",
        "source_object": "VisitPlan",
        "target_object": "User",
        "cardinality": "N:1",
        "description": "计划所属的代表",
    },
    {
        "name": "visit_record_product",
        "display_name": "拜访记录-产品",
        "source_object": "VisitRecord",
        "target_object": "Product",
        "cardinality": "N:N",
        "description": "拜访涉及的产品",
    },

    # ── 智能培训域 ──
    {
        "name": "exam_question",
        "display_name": "考试-题目",
        "source_object": "Exam",
        "target_object": "Question",
        "cardinality": "N:N",
        "description": "考试包含的题目",
    },
    {
        "name": "course_learning_path",
        "display_name": "课程-学习路径",
        "source_object": "LearningPath",
        "target_object": "Course",
        "cardinality": "N:N",
        "description": "学习路径包含的课程",
    },
    {
        "name": "learning_progress_learning_path",
        "display_name": "学习进度-路径",
        "source_object": "LearningProgress",
        "target_object": "LearningPath",
        "cardinality": "N:1",
        "description": "进度所属的学习路径",
    },
    {
        "name": "training_drill_training_scene",
        "display_name": "演练记录-场景",
        "source_object": "TrainingDrill",
        "target_object": "TrainingScene",
        "cardinality": "N:1",
        "description": "演练关联的场景",
    },
    {
        "name": "certificate_course",
        "display_name": "证书-课程",
        "source_object": "Certificate",
        "target_object": "Course",
        "cardinality": "N:1",
        "description": "证书对应的课程",
    },
    {
        "name": "course_exam",
        "display_name": "课程-考试",
        "source_object": "Course",
        "target_object": "Exam",
        "cardinality": "1:1",
        "description": "课程的结业考试",
    },

    # ── 决策支持域 ──
    {
        "name": "kpi_value_kpi_definition",
        "display_name": "KPI 数值-定义",
        "source_object": "KPIValue",
        "target_object": "KPIDefinition",
        "cardinality": "N:1",
        "description": "KPI 数值对应的定义",
    },
    {
        "name": "attribution_result_kpi_value",
        "display_name": "归因结果-KPI",
        "source_object": "AttributionResult",
        "target_object": "KPIValue",
        "cardinality": "N:1",
        "description": "归因结果对应的 KPI 数值",
    },
    {
        "name": "alert_kpi_definition",
        "display_name": "预警-KPI",
        "source_object": "Alert",
        "target_object": "KPIDefinition",
        "cardinality": "N:1",
        "description": "预警触发的 KPI",
    },
    {
        "name": "diagnosis_rep",
        "display_name": "诊断-代表",
        "source_object": "Diagnosis",
        "target_object": "User",
        "cardinality": "N:1",
        "description": "诊断所针对的医药代表",
    },
    {
        "name": "diagnosis_signal",
        "display_name": "诊断-信号",
        "source_object": "Diagnosis",
        "target_object": "Signal",
        "cardinality": "1:N",
        "description": "一个诊断识别出多个异常信号",
    },
    {
        "name": "signal_paradigm",
        "display_name": "信号-范式",
        "source_object": "Signal",
        "target_object": "Paradigm",
        "cardinality": "N:N",
        "description": "信号对应的一类问题可由若干通用范式解题",
    },
    {
        "name": "execution_diagnosis",
        "display_name": "执行-诊断",
        "source_object": "DecisionExecution",
        "target_object": "Diagnosis",
        "cardinality": "N:1",
        "description": "针对某诊断建议的执行动作",
    },
    {
        "name": "paradigm_execution",
        "display_name": "范式-执行",
        "source_object": "Paradigm",
        "target_object": "DecisionExecution",
        "cardinality": "N:N",
        "description": "范式可被复用为后续执行的参考方法",
    },

    # ── 协同办公域 ──
    {
        "name": "task_visit_plan",
        "display_name": "待办-拜访计划",
        "source_object": "Task",
        "target_object": "VisitPlan",
        "cardinality": "N:1",
        "description": "待办关联的拜访计划",
    },
    {
        "name": "approval_visit_plan",
        "display_name": "审批-拜访计划",
        "source_object": "Approval",
        "target_object": "VisitPlan",
        "cardinality": "N:1",
        "description": "审批关联的拜访计划",
    },

    # ── 知识库域 ──
    {
        "name": "wiki_page_knowledge_space",
        "display_name": "Wiki-知识空间",
        "source_object": "WikiPage",
        "target_object": "KnowledgeSpace",
        "cardinality": "N:1",
        "description": "Wiki 页面所属的知识空间",
    },
    {
        "name": "document_knowledge_space",
        "display_name": "文档-知识空间",
        "source_object": "Document",
        "target_object": "KnowledgeSpace",
        "cardinality": "N:1",
        "description": "文档所属的知识空间",
    },
    {
        "name": "annotation_document",
        "display_name": "批注-文档",
        "source_object": "Annotation",
        "target_object": "Document",
        "cardinality": "N:1",
        "description": "批注所属的文档",
    },
    {
        "name": "outsend_link_document",
        "display_name": "外发链接-文档",
        "source_object": "OutsendLink",
        "target_object": "Document",
        "cardinality": "N:1",
        "description": "外发链接对应的文档",
    },
]

# 构建 name -> link 的映射（seed 快照，仅供初始化/降级使用）
SEED_LINK_MAP = {link["name"]: link for link in LINKS}


def __getattr__(name: str):
    """模块级懒转发：LINK_MAP 指向 registry 实时缓存代理（避免循环导入）"""
    if name == "LINK_MAP":
        from ontology.registry import LINK_MAP as _m
        return _m
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def list_links(tenant_id: Optional[str] = None) -> list[dict]:
    """列出所有 Link（读运行时权威源）"""
    from ontology.registry import registry
    return registry.list_links(tenant_id)


def get_link(name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """按名称获取 Link（读运行时权威源）"""
    from ontology.registry import registry
    return registry.get_link(name, tenant_id)
