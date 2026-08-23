"""RBAC 权限矩阵 + OBAC Object 级声明 + ABAC 列级脱敏"""

from typing import Any, Optional

# ──────────────────────────────────────────────
# RBAC：12 个角色及其权限
# ──────────────────────────────────────────────

ROLE_PERMISSIONS = {
    # 平台/租户管理
    "admin": ["*"],
    "platform_admin": [
        "platform.read", "platform.write", "tenant.read", "tenant.write",
        "user.read", "user.write", "role.read", "role.write",
        "audit.read", "ai_assistant.use",
        "compliance.read", "compliance.write",
    ],
    "auditor": [
        "audit.read", "visit_plan.read", "visit_record.read", "kpi.read",
        "report.read", "approval.read", "ai_assistant.use",
        "compliance.read",
    ],

    # 销售线
    "sales_rep": [
        "visit_plan.read", "visit_plan.write",
        "visit_record.read", "visit_record.write",
        "hospital.read", "doctor.read", "product.read", "zone.read",
        "coverage.read", "point.read",
        "course.read", "course.write", "exam.read", "exam.write",
        "path.read", "path.write", "live.read", "live.write",
        "scene.read", "scene.run", "certificate.read",
        "knowledge.read", "knowledge.write",
        "task.read", "task.write", "report.read", "report.write",
        "subscription.read", "subscription.write", "export.read", "export.write",
        "compliance.read",
        "ai_assistant.use",
    ],
    "regional_manager": [
        "visit_plan.read", "visit_plan.write", "visit_plan.approve",
        "visit_record.read", "visit_record.write",
        "hospital.read", "doctor.read", "product.read", "zone.read",
        "coverage.read", "coverage.write", "point.read", "point.compute",
        "report.read", "report.write", "report.generate", "report.submit",
        "approval.read", "approval.approve",
        "task.read", "task.write", "task.assign",
        "kpi.read", "alert.read",
        "knowledge.read", "knowledge.write",
        "compliance.read",
        "ai_assistant.use",
    ],
    "sales_director": [
        "visit_plan.read", "visit_plan.write", "visit_plan.approve",
        "visit_record.read", "visit_record.write",
        "hospital.read", "hospital.write", "doctor.read", "doctor.write",
        "product.read", "product.write", "zone.read", "zone.write",
        "coverage.read", "coverage.write", "point.read", "point.compute",
        "report.read", "report.write", "report.generate",
        "approval.read", "approval.approve", "approval.write",
        "task.read", "task.write", "task.assign",
        "kpi.read", "kpi.write", "kpi.compute", "alert.read", "alert.dispatch",
        "simulation.read", "simulation.run",
        "knowledge.read", "knowledge.write",
        "ai_assistant.use",
    ],

    # 培训线
    "training_manager": [
        "course.read", "course.write", "course.publish",
        "question.read", "question.write",
        "exam.read", "exam.write", "exam.generate", "exam.grade",
        "path.read", "path.write", "path.optimize",
        "live.read", "live.write", "live.summarize",
        "scene.read", "scene.generate", "scene.run", "scene.grade",
        "certificate.read", "certificate.issue",
        "score.adjust", "score.bulk",
        "report.read", "approval.read",
        "compliance.read",
        "ai_assistant.use",
    ],
    "trainer": [
        "course.read", "course.write",
        "question.read", "question.write",
        "exam.read", "exam.generate", "exam.grade",
        "path.read", "path.write",
        "live.read", "live.write", "live.summarize",
        "scene.read", "scene.generate", "scene.run", "scene.grade",
        "certificate.read",
        "compliance.read",
        "ai_assistant.use",
    ],

    # 市场/医学/客户/会议线
    "marketing_manager": [
        "knowledge.read", "knowledge.write", "knowledge.delete",
        "report.read", "report.write",
        "kol.read",
        "meeting.read", "meeting.write",
        "hospital.read", "doctor.read", "product.read",
        "compliance.read", "compliance.write",
        "ai_assistant.use",
    ],
    "medical_manager": [
        "knowledge.read", "knowledge.write", "knowledge.delete",
        "report.read",
        "kol.read",
        "meeting.read", "meeting.write",
        "hospital.read", "doctor.read", "product.read",
        "compliance.read", "compliance.write",
        "ai_assistant.use",
    ],
    "kol_coordinator": [
        "kol.read", "kol.write",
        "doctor.read", "doctor.write", "hospital.read",
        "meeting.read", "meeting.write",
        "knowledge.read",
        "compliance.read",
        "task.read", "task.write",
        "ai_assistant.use",
    ],
    "im_coordinator": [
        "meeting.read", "meeting.write",
        "knowledge.read", "knowledge.write",
        "compliance.read", "compliance.write",
        "task.read", "task.write",
        "subscription.read", "subscription.write",
        "ai_assistant.use",
    ],
}

# 12 个角色的展示信息
ROLE_DEFINITIONS = [
    {"code": "admin", "display_name": "超级管理员", "description": "拥有全部权限"},
    {"code": "platform_admin", "display_name": "平台管理员", "description": "管理租户与平台配置"},
    {"code": "auditor", "display_name": "审计员", "description": "只读审计权限"},
    {"code": "sales_rep", "display_name": "医药代表", "description": "一线销售人员"},
    {"code": "regional_manager", "display_name": "区域经理", "description": "管理区域销售团队"},
    {"code": "sales_director", "display_name": "销售总监", "description": "管理销售全局"},
    {"code": "training_manager", "display_name": "培训经理", "description": "管理培训体系"},
    {"code": "trainer", "display_name": "培训师", "description": "执行培训课程"},
    {"code": "marketing_manager", "display_name": "市场经理", "description": "管理市场与知识"},
    {"code": "medical_manager", "display_name": "医学经理", "description": "管理医学知识"},
    {"code": "kol_coordinator", "display_name": "KOL 协调员", "description": "管理 KOL 客户"},
    {"code": "im_coordinator", "display_name": "IM 协调员", "description": "管理会议与即时通讯"},
]


# ──────────────────────────────────────────────
# OBAC：Object 级权限声明
# ──────────────────────────────────────────────

OBJECT_PERMISSIONS = {
    "VisitPlan": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "approve": ["regional_manager", "sales_director", "admin"],
        "delete": ["sales_director", "admin"],
    },
    "VisitPlanItem": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["sales_rep", "regional_manager", "admin"],
        "delete": ["sales_director", "admin"],
    },
    "VisitRecord": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "delete": ["sales_director", "admin"],
    },
    "VisitFeedback": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["sales_rep", "regional_manager", "admin"],
        "delete": ["sales_director", "admin"],
    },
    "Hospital": {
        "read": ["sales_rep", "regional_manager", "sales_director", "marketing_manager", "medical_manager", "kol_coordinator", "admin", "auditor"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "Doctor": {
        "read": ["sales_rep", "regional_manager", "sales_director", "marketing_manager", "medical_manager", "kol_coordinator", "admin", "auditor"],
        "write": ["sales_director", "kol_coordinator", "admin"],
        "delete": ["admin"],
    },
    "Product": {
        "read": ["sales_rep", "regional_manager", "sales_director", "marketing_manager", "medical_manager", "admin"],
        "write": ["sales_director", "marketing_manager", "admin"],
        "delete": ["admin"],
    },
    "Zone": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "CoverageAssignment": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["sales_director", "admin"],
    },
    "CoverageMatrix": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "BehaviorPoint": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "InstructionPoint": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "WeeklyReport": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "MonthlyReport": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "CollectionProject": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "CollectionPeriod": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "SchemaTemplate": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "Course": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "CourseSection": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "Question": {
        "read": ["training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "QuestionBank": {
        "read": ["training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "Exam": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "ExamAttempt": {
        "read": ["sales_rep", "training_manager", "trainer", "admin", "auditor"],
        "write": ["training_manager", "admin"],
        "delete": ["admin"],
    },
    "LiveClass": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "LearningPath": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "LearningProgress": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["sales_rep", "training_manager", "admin"],
        "delete": ["admin"],
    },
    "TrainingScene": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["training_manager", "admin"],
    },
    "TrainingDrill": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "trainer", "admin"],
        "delete": ["admin"],
    },
    "Certificate": {
        "read": ["sales_rep", "training_manager", "trainer", "admin"],
        "write": ["training_manager", "admin"],
        "delete": ["admin"],
    },
    "KPIDefinition": {
        "read": ["sales_director", "regional_manager", "admin", "auditor"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "KPIValue": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "AttributionResult": {
        "read": ["sales_director", "admin", "auditor"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "SimulationScenario": {
        "read": ["sales_director", "admin"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "Alert": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_director", "admin"],
        "delete": ["admin"],
    },
    "Task": {
        "read": ["sales_rep", "regional_manager", "sales_director", "training_manager", "kol_coordinator", "im_coordinator", "admin"],
        "write": ["sales_rep", "regional_manager", "sales_director", "training_manager", "kol_coordinator", "im_coordinator", "admin"],
        "delete": ["admin"],
    },
    "Report": {
        "read": ["sales_rep", "regional_manager", "sales_director", "marketing_manager", "admin", "auditor"],
        "write": ["sales_rep", "regional_manager", "sales_director", "marketing_manager", "admin"],
        "delete": ["admin"],
    },
    "Approval": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin", "auditor"],
        "write": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "Subscription": {
        "read": ["sales_rep", "im_coordinator", "admin"],
        "write": ["sales_rep", "im_coordinator", "admin"],
        "delete": ["admin"],
    },
    "ExportJob": {
        "read": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "write": ["sales_rep", "regional_manager", "sales_director", "admin"],
        "delete": ["admin"],
    },
    "KnowledgeSpace": {
        "read": ["sales_rep", "marketing_manager", "medical_manager", "kol_coordinator", "im_coordinator", "admin"],
        "write": ["marketing_manager", "medical_manager", "im_coordinator", "admin"],
        "delete": ["marketing_manager", "medical_manager", "admin"],
    },
    "WikiPage": {
        "read": ["sales_rep", "marketing_manager", "medical_manager", "kol_coordinator", "im_coordinator", "admin"],
        "write": ["sales_rep", "marketing_manager", "medical_manager", "im_coordinator", "admin"],
        "delete": ["marketing_manager", "medical_manager", "admin"],
    },
    "Document": {
        "read": ["sales_rep", "marketing_manager", "medical_manager", "kol_coordinator", "im_coordinator", "admin"],
        "write": ["marketing_manager", "medical_manager", "im_coordinator", "admin"],
        "delete": ["marketing_manager", "medical_manager", "admin"],
    },
    "OutsendLink": {
        "read": ["marketing_manager", "medical_manager", "admin"],
        "write": ["marketing_manager", "medical_manager", "admin"],
        "delete": ["marketing_manager", "medical_manager", "admin"],
    },
    "Annotation": {
        "read": ["sales_rep", "marketing_manager", "medical_manager", "kol_coordinator", "im_coordinator", "admin"],
        "write": ["sales_rep", "marketing_manager", "medical_manager", "im_coordinator", "admin"],
        "delete": ["admin"],
    },
    "User": {
        "read": ["admin", "platform_admin", "auditor"],
        "write": ["admin", "platform_admin"],
        "delete": ["admin"],
    },
    "Role": {
        "read": ["admin", "platform_admin"],
        "write": ["admin", "platform_admin"],
        "delete": ["admin"],
    },
    "Tenant": {
        "read": ["admin", "platform_admin", "auditor"],
        "write": ["admin", "platform_admin"],
        "delete": ["admin"],
    },
    "AuditLog": {
        "read": ["admin", "platform_admin", "auditor"],
        "write": [],
        "delete": ["admin"],
    },
}


# ──────────────────────────────────────────────
# 权限判定入口
#
# 权威源已迁至 psp_ontology.db（见 ontology/permission_registry.py），
# 上面的 ROLE_PERMISSIONS / OBJECT_PERMISSIONS / ROLE_DEFINITIONS 常量
# 降级为「seed 声明 + DB 不可用时的兜底默认」。
#
# 下列函数签名与历史版本完全一致，新增可选 tenant_id 支持租户级覆盖。
# ──────────────────────────────────────────────

def get_role_permissions(role: str, tenant_id: Optional[str] = None) -> list[str]:
    """获取角色的权限列表"""
    from ontology.permission_registry import registry
    return registry.get_role_permissions(role, tenant_id)


def has_permission(role: str, permission: str,
                   tenant_id: Optional[str] = None) -> bool:
    """检查角色是否拥有指定权限（支持通配符 *）"""
    from ontology.permission_registry import registry
    return registry.has_permission(role, permission, tenant_id)


def can_access_object(role: str, object_name: str, access: str = "read",
                      tenant_id: Optional[str] = None) -> bool:
    """检查角色是否能访问指定 Object（OBAC）"""
    from ontology.permission_registry import registry
    return registry.can_access_object(role, object_name, access, tenant_id)


# ──────────────────────────────────────────────
# ABAC：列级权限脱敏（方案第八章 Column-Level Security）
# 复用现有 RBAC 角色判定（has_permission），对核心高敏字段做列级脱敏
# ──────────────────────────────────────────────

# 默认核心字段脱敏规则（方案第八章）
#   hide  : 完全隐藏（替换为 None / 掩码占位）
#   range : 数值区间化（高 / 中 / 低）
#   mask  : 评分脱敏（替换为 ***）
DEFAULT_FIELD_RULES = {
    "income": "hide",          # 代表看他人收入完全隐藏
    "salary": "hide",          # 收入相关别名
    "gross_margin": "range",   # 跨区毛利率区间化
    "kpi_score": "mask",       # 个人 KPI 评分脱敏
    "kpi": "mask",             # KPI 别名
}


def band_gross_margin(value) -> Optional[str]:
    """将毛利率数值区间化为 高/中/低（区间边界可配）"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v >= 0.6:
        return "高"
    if v >= 0.3:
        return "中"
    return "低"


def desensitize_value(field: str, value, rule: str, *, is_self: bool,
                      same_zone: bool, role: str) -> Any:
    """对单个字段按规则脱敏，返回脱敏后值或原值。

    规则：
    - hide : 仅当「非本人 且 角色为一线代表」时隐藏（经理/总监可见）
    - range: 仅当「跨区」时区间化（同区保持原值）
    - mask : 仅当「非本人 且 角色为一线代表」时掩码
    """
    # 经理及以上 / 本人 / 同区 一般无需脱敏（hide/range/mask 的条件不满足）
    if rule == "hide":
        if (not is_self) and role == "sales_rep":
            return None  # 完全隐藏
        return value
    if rule == "range":
        if not same_zone:
            return band_gross_margin(value)  # 跨区区间化
        return value
    if rule == "mask":
        if (not is_self) and role == "sales_rep":
            return "***"  # KPI 评分脱敏
        return value
    return value


def desensitize_row(role: str, viewer_id: int, owner_id: int, row: dict,
                    *, owner_zone: Optional[str] = None,
                    viewer_zone: Optional[str] = None,
                    field_rules: Optional[dict] = None) -> dict:
    """对一行数据做列级脱敏（ABAC 维度），返回脱敏后副本（不修改入参）。

    Args:
        role      : 查看者角色（复用 RBAC 判定，一线代表 sales_rep 受限最严）
        viewer_id : 查看者用户 ID
        owner_id  : 数据归属用户 ID
        row       : 原始行 dict
        owner_zone: 数据归属区域（用于跨区判定）
        viewer_zone: 查看者区域
        field_rules: 字段→规则映射（默认 DEFAULT_FIELD_RULES）
    """
    rules = field_rules or DEFAULT_FIELD_RULES
    is_self = viewer_id == owner_id
    same_zone = (owner_zone is not None and viewer_zone is not None
                 and owner_zone == viewer_zone)
    out = dict(row)
    for field, rule in rules.items():
        if field in out:
            out[field] = desensitize_value(
                field, out[field], rule,
                is_self=is_self, same_zone=same_zone, role=role,
            )
    return out


def desensitize_records(role: str, viewer_id: int, records: list[dict],
                       *, owner_id_key: str = "user_id",
                       owner_zone_key: Optional[str] = None,
                       viewer_zone: Optional[str] = None,
                       field_rules: Optional[dict] = None) -> list[dict]:
    """批量列级脱敏（ABAC）：desensitize_row 的列表包装，供 service 列表查询统一接入。

    设计意图（蓝图片段 1.3 权限引擎统一入口）：任何返回用户行数据的 service
    列表接口，只需在返回前调用本函数即可获得与单条脱敏一致的列级安全，
    避免每个 service 各自实现脱敏逻辑造成规则漂移。
    """
    if not records:
        return records
    out = []
    for rec in records:
        owner_id = rec.get(owner_id_key)
        owner_zone = rec.get(owner_zone_key) if owner_zone_key else None
        out.append(desensitize_row(
            role, viewer_id, owner_id, rec,
            owner_zone=owner_zone, viewer_zone=viewer_zone,
            field_rules=field_rules,
        ))
    return out


def check_object_permission_coverage(object_names: list[str]) -> dict:
    """校验「本体实体」与「OBAC 权限矩阵」的覆盖一致性（单一本体源延伸，蓝图片段 1.3）。

    返回未在 OBJECT_PERMISSIONS 中声明 OBAC 规则的本体实体集合，供运维/启动期告警，
    避免本体新增实体后权限矩阵遗漏（双写漂移）。本函数只读、不修改任何状态。

    Args:
        object_names: 本体 OBJECTS 的 name 列表（来自 ontology.OBJECTS）
    Returns:
        {"missing_in_obac": [...], "covered": int, "total": int}
    """
    missing = [n for n in object_names if n not in OBJECT_PERMISSIONS]
    return {
        "missing_in_obac": missing,
        "covered": len(object_names) - len(missing),
        "total": len(object_names),
    }

