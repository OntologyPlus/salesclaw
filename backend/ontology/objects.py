"""Object 注册表 - 30+ 业务实体定义（按域分组）"""
from typing import Optional


# ──────────────────────────────────────────────
# Object 定义
# ──────────────────────────────────────────────

OBJECTS = [
    # ── 销售执行域 ──
    {
        "name": "Zone",
        "display_name": "销售区划",
        "domain": "sales",
        "description": "销售区域的层级划分",
        "fields": ["id", "tenant_id", "name", "code", "parent_id", "level", "created_at"],
        "actions": ["list_zones", "create_zone", "update_zone"],
    },
    {
        "name": "Hospital",
        "display_name": "医院",
        "domain": "sales",
        "description": "客户医院主数据",
        "fields": ["id", "tenant_id", "name", "code", "level", "province", "city", "district", "address", "created_at"],
        "actions": ["list_hospitals", "get_hospital", "create_hospital", "update_hospital", "batch_import_hospitals"],
    },
    {
        "name": "Doctor",
        "display_name": "医生",
        "domain": "sales",
        "description": "客户医生主数据",
        "fields": ["id", "tenant_id", "name", "hospital_id", "department", "title", "phone", "specialty", "created_at"],
        "actions": ["list_doctors", "get_doctor", "create_doctor", "update_doctor", "batch_import_doctors", "merge_doctors"],
    },
    {
        "name": "Product",
        "display_name": "产品",
        "domain": "sales",
        "description": "药品主数据",
        "fields": ["id", "tenant_id", "name", "code", "category", "specifications", "manufacturer", "created_at"],
        "actions": ["list_products", "get_product", "create_product", "update_product"],
    },
    {
        "name": "CoverageAssignment",
        "display_name": "覆盖分管",
        "domain": "sales",
        "description": "代表对医院/医生的覆盖分配",
        "fields": ["id", "tenant_id", "user_id", "zone_id", "hospital_id", "doctor_id", "created_at"],
        "actions": ["list_coverage_assignments", "create_coverage_assignment", "compute_coverage_gap"],
    },
    {
        "name": "VisitPlan",
        "display_name": "拜访计划",
        "domain": "sales",
        "description": "代表的拜访计划",
        "fields": ["id", "tenant_id", "user_id", "period", "target", "status", "remark", "created_at"],
        "actions": ["list_visit_plans", "create_visit_plan", "submit_visit_plan", "approve_visit_plan", "reject_visit_plan"],
    },
    {
        "name": "VisitPlanItem",
        "display_name": "拜访计划明细",
        "domain": "sales",
        "description": "拜访计划下的具体明细项",
        "fields": ["id", "tenant_id", "plan_id", "hospital_id", "doctor_id", "product_id", "scheduled_at", "created_at"],
        "actions": ["list_visit_plan_items", "create_visit_plan_item"],
    },
    {
        "name": "VisitRecord",
        "display_name": "拜访记录",
        "domain": "sales",
        "description": "实际拜访的执行记录",
        "fields": ["id", "tenant_id", "plan_id", "user_id", "hospital_id", "doctor_id", "product_id", "visited_at", "duration", "status", "created_at"],
        "actions": ["list_visit_records", "create_visit_record", "save_visit_draft", "delete_visit_record"],
    },
    {
        "name": "VisitFeedback",
        "display_name": "拜访反馈",
        "domain": "sales",
        "description": "拜访后客户反馈信息",
        "fields": ["id", "tenant_id", "record_id", "content", "sentiment", "tags", "created_at"],
        "actions": ["list_visit_feedback", "extract_feedback"],
    },
    {
        "name": "BehaviorPoint",
        "display_name": "行为积分",
        "domain": "sales",
        "description": "代表的行为积分记录",
        "fields": ["id", "tenant_id", "user_id", "period", "dimension", "score", "created_at"],
        "actions": ["get_behavior_points", "calculate_behavior_points"],
    },
    {
        "name": "InstructionPoint",
        "display_name": "指令积分",
        "domain": "sales",
        "description": "代表的指令积分记录",
        "fields": ["id", "tenant_id", "user_id", "instruction_id", "score", "created_at"],
        "actions": ["get_instruction_points", "calculate_instruction_points"],
    },
    {
        "name": "CollectionProject",
        "display_name": "采集项目",
        "domain": "sales",
        "description": "数据采集项目",
        "fields": ["id", "tenant_id", "name", "period", "schema_id", "status", "created_at"],
        "actions": ["list_collection_projects", "create_collection_project"],
    },
    {
        "name": "CollectionPeriod",
        "display_name": "采集周期",
        "domain": "sales",
        "description": "采集项目的时间周期",
        "fields": ["id", "tenant_id", "project_id", "start_at", "end_at", "status", "created_at"],
        "actions": ["list_collection_periods", "create_collection_period"],
    },
    {
        "name": "SchemaTemplate",
        "display_name": "采集模板",
        "domain": "sales",
        "description": "数据采集的表单模板",
        "fields": ["id", "tenant_id", "name", "fields", "validation", "created_at"],
        "actions": ["list_schema_templates", "create_schema_template"],
    },
    {
        "name": "CoverageMatrix",
        "display_name": "覆盖矩阵",
        "domain": "sales",
        "description": "代表-医院-产品的覆盖关系矩阵",
        "fields": ["id", "tenant_id", "user_id", "hospital_id", "product_id", "covered", "created_at"],
        "actions": ["get_coverage_matrix", "compute_coverage_gap"],
    },
    {
        "name": "WeeklyReport",
        "display_name": "周报",
        "domain": "sales",
        "description": "代表每周的工作汇报",
        "fields": ["id", "tenant_id", "user_id", "period", "content", "summary", "created_at"],
        "actions": ["generate_weekly_report", "list_weekly_reports"],
    },
    {
        "name": "MonthlyReport",
        "display_name": "月报",
        "domain": "sales",
        "description": "代表每月的工作汇报",
        "fields": ["id", "tenant_id", "user_id", "period", "content", "summary", "created_at"],
        "actions": ["generate_monthly_report", "list_monthly_reports"],
    },

    # ── 智能培训域 ──
    {
        "name": "Course",
        "display_name": "课程",
        "domain": "training",
        "description": "培训课程主数据",
        "fields": ["id", "tenant_id", "name", "type", "duration", "difficulty", "status", "created_at"],
        "actions": ["list_courses", "get_course", "create_course", "publish_course"],
    },
    {
        "name": "CourseSection",
        "display_name": "课程章节",
        "domain": "training",
        "description": "课程的章节明细",
        "fields": ["id", "tenant_id", "course_id", "title", "content", "duration", "sort_order", "created_at"],
        "actions": ["list_course_sections", "complete_lesson"],
    },
    {
        "name": "Question",
        "display_name": "题目",
        "domain": "training",
        "description": "考试题目",
        "fields": ["id", "tenant_id", "bank_id", "type", "content", "answer", "score", "created_at"],
        "actions": ["list_questions", "create_question"],
    },
    {
        "name": "QuestionBank",
        "display_name": "题库",
        "domain": "training",
        "description": "题目集合",
        "fields": ["id", "tenant_id", "name", "category", "count", "created_at"],
        "actions": ["list_question_banks", "create_question_bank"],
    },
    {
        "name": "Exam",
        "display_name": "考试",
        "domain": "training",
        "description": "考试活动",
        "fields": ["id", "tenant_id", "name", "duration", "total_score", "pass_score", "status", "created_at"],
        "actions": ["list_exams", "generate_exam", "grade_exam"],
    },
    {
        "name": "ExamAttempt",
        "display_name": "考试记录",
        "domain": "training",
        "description": "用户参加考试的记录",
        "fields": ["id", "tenant_id", "user_id", "exam_id", "score", "passed", "started_at", "submitted_at", "created_at"],
        "actions": ["get_exam_score", "list_exam_attempts", "adjust_score"],
    },
    {
        "name": "LiveClass",
        "display_name": "直播课",
        "domain": "training",
        "description": "直播培训课程",
        "fields": ["id", "tenant_id", "title", "host_id", "start_at", "end_at", "status", "created_at"],
        "actions": ["list_live_classes", "join_live_class", "summarize_live_class"],
    },
    {
        "name": "LearningPath",
        "display_name": "学习路径",
        "domain": "training",
        "description": "用户的学习路径规划",
        "fields": ["id", "tenant_id", "name", "stages", "target", "created_at"],
        "actions": ["list_learning_paths", "create_learning_path", "optimize_learning_path"],
    },
    {
        "name": "LearningProgress",
        "display_name": "学习进度",
        "domain": "training",
        "description": "用户在路径上的学习进度",
        "fields": ["id", "tenant_id", "user_id", "path_id", "percent", "last_section_id", "created_at"],
        "actions": ["get_learning_progress", "update_learning_progress"],
    },
    {
        "name": "TrainingScene",
        "display_name": "演练场景",
        "domain": "training",
        "description": "AI 演练场景",
        "fields": ["id", "tenant_id", "name", "role", "difficulty", "script", "created_at"],
        "actions": ["list_training_scenes", "generate_drill_scene"],
    },
    {
        "name": "TrainingDrill",
        "display_name": "演练记录",
        "domain": "training",
        "description": "用户的演练执行记录",
        "fields": ["id", "tenant_id", "user_id", "scene_id", "score", "feedback", "created_at"],
        "actions": ["list_training_drills", "run_drill", "grade_drill"],
    },
    {
        "name": "Certificate",
        "display_name": "证书",
        "domain": "training",
        "description": "用户获得的证书",
        "fields": ["id", "tenant_id", "user_id", "course_id", "type", "issued_at", "created_at"],
        "actions": ["list_certificates", "issue_certificate"],
    },

    # ── 决策支持域 ──
    {
        "name": "KPIDefinition",
        "display_name": "KPI 定义",
        "domain": "decision",
        "description": "KPI 指标定义",
        "fields": ["id", "tenant_id", "name", "formula", "threshold", "frequency", "created_at"],
        "actions": ["list_kpi_definitions", "create_kpi_definition", "update_kpi_threshold"],
    },
    {
        "name": "KPIValue",
        "display_name": "KPI 数值",
        "domain": "decision",
        "description": "KPI 的实际数值",
        "fields": ["id", "tenant_id", "kpi_id", "period", "value", "target", "created_at"],
        "actions": ["get_kpi_value", "compute_kpi", "list_kpi_values"],
    },
    {
        "name": "AttributionResult",
        "display_name": "归因结果",
        "domain": "decision",
        "description": "多因素归因分析结果",
        "fields": ["id", "tenant_id", "kpi_id", "period", "factors", "weights", "created_at"],
        "actions": ["run_attribution", "list_attribution_results"],
    },
    {
        "name": "SimulationScenario",
        "display_name": "模拟场景",
        "domain": "decision",
        "description": "What-if 模拟场景",
        "fields": ["id", "tenant_id", "name", "params", "results", "status", "created_at"],
        "actions": ["run_simulation", "list_simulation_scenarios"],
    },
    {
        "name": "Alert",
        "display_name": "预警",
        "domain": "decision",
        "description": "异常预警",
        "fields": ["id", "tenant_id", "kpi_id", "severity", "status", "message", "created_at"],
        "actions": ["list_alerts", "detect_anomaly", "dispatch_alert"],
    },
    {
        "name": "Diagnosis",
        "display_name": "诊断",
        "domain": "decision",
        "description": "AI 对代表/医院/科室在某业务域上的诊断结论（一等语义实体），由结构化推理生成并进入状态机",
        "fields": ["id", "tenant_id", "rep_id", "domain", "target_type", "target_id",
                   "summary", "level", "confidence", "status", "evidence",
                   "reasoning_trace", "provenance", "trace_id", "created_at", "confirmed_at"],
        "actions": ["diagnose", "list_diagnoses", "confirm_diagnosis", "rerun_diagnosis"],
    },
    {
        "name": "Signal",
        "display_name": "信号",
        "domain": "decision",
        "description": "诊断中识别出的可观测异常信号（如覆盖缺口、拜访衰减、处方停滞），带严重度与消除条件",
        "fields": ["id", "tenant_id", "diagnosis_id", "name", "category", "severity",
                   "description", "clear_condition", "cleared", "observed_at", "cleared_at"],
        "actions": ["extract_signal", "list_signals", "clear_signal"],
    },
    {
        "name": "Paradigm",
        "display_name": "范式",
        "domain": "decision",
        "description": "从已闭环的有效执行中沉淀的通用解题范式（问题类型→有效办法），可跨代表复用",
        "fields": ["id", "tenant_id", "domain", "problem_type", "title",
                   "effective_method", "evidence_execution_ids", "usage_count",
                   "effectiveness_score", "created_at", "updated_at"],
        "actions": ["derive_paradigm", "list_paradigms", "apply_paradigm"],
    },

    # ── 协同办公域 ──
    {
        "name": "Task",
        "display_name": "待办",
        "domain": "collab",
        "description": "用户的待办任务",
        "fields": ["id", "tenant_id", "title", "owner_id", "source", "due_at", "status", "priority", "created_at"],
        "actions": ["list_tasks", "create_todo", "assign_task", "complete_task"],
    },
    {
        "name": "Report",
        "display_name": "汇报",
        "domain": "collab",
        "description": "用户提交的汇报",
        "fields": ["id", "tenant_id", "author_id", "period", "type", "content", "created_at"],
        "actions": ["list_reports", "create_report", "submit_report"],
    },
    {
        "name": "Approval",
        "display_name": "审批",
        "domain": "collab",
        "description": "审批流程实例",
        "fields": ["id", "tenant_id", "type", "applicant_id", "target_id", "status", "comment", "created_at"],
        "actions": ["list_approvals", "create_approval", "approve_request", "reject_request"],
    },
    {
        "name": "Subscription",
        "display_name": "订阅",
        "domain": "collab",
        "description": "消息订阅配置",
        "fields": ["id", "tenant_id", "user_id", "target_id", "channel", "config", "created_at"],
        "actions": ["list_subscriptions", "create_subscription"],
    },
    {
        "name": "ExportJob",
        "display_name": "导出任务",
        "domain": "collab",
        "description": "数据导出任务",
        "fields": ["id", "tenant_id", "user_id", "type", "params", "status", "file_url", "created_at"],
        "actions": ["list_export_jobs", "create_export_job"],
    },

    # ── 知识库域 ──
    {
        "name": "KnowledgeSpace",
        "display_name": "知识空间",
        "domain": "knowledge",
        "description": "知识的分类空间",
        "fields": ["id", "tenant_id", "name", "type", "owner_id", "settings", "created_at"],
        "actions": ["list_knowledge_spaces", "create_knowledge_space"],
    },
    {
        "name": "WikiPage",
        "display_name": "Wiki 页面",
        "domain": "knowledge",
        "description": "Wiki 文档页面",
        "fields": ["id", "tenant_id", "space_id", "title", "content", "version", "created_at"],
        "actions": ["read_wiki", "search_wiki", "create_wiki_page", "update_wiki_page"],
    },
    {
        "name": "Document",
        "display_name": "文档",
        "domain": "knowledge",
        "description": "知识库文档",
        "fields": ["id", "tenant_id", "space_id", "title", "format", "file_url", "size", "created_at"],
        "actions": ["search_documents", "upload_document", "delete_document"],
    },
    {
        "name": "OutsendLink",
        "display_name": "外发链接",
        "domain": "knowledge",
        "description": "外发的临时访问链接",
        "fields": ["id", "tenant_id", "doc_id", "expires_at", "password", "max_views", "views", "created_at"],
        "actions": ["create_outsend_link", "revoke_outsend_link"],
    },
    {
        "name": "Annotation",
        "display_name": "批注",
        "domain": "knowledge",
        "description": "文档批注",
        "fields": ["id", "tenant_id", "target_id", "target_type", "content", "author_id", "created_at"],
        "actions": ["list_annotations", "add_annotation", "delete_annotation"],
    },

    # ── 通用域 ──
    {
        "name": "User",
        "display_name": "用户",
        "domain": "common",
        "description": "系统用户",
        "fields": ["id", "tenant_id", "username", "email", "display_name", "role_id", "zone_id", "is_active", "last_login_at", "created_at"],
        "actions": ["list_users", "get_user", "create_user", "update_user", "delete_user"],
    },
    {
        "name": "Role",
        "display_name": "角色",
        "domain": "common",
        "description": "用户角色",
        "fields": ["id", "tenant_id", "name", "code", "permissions", "created_at"],
        "actions": ["list_roles", "create_role", "update_role"],
    },
    {
        "name": "Tenant",
        "display_name": "租户",
        "domain": "common",
        "description": "多租户隔离主体",
        "fields": ["id", "code", "name", "settings", "is_active", "created_at"],
        "actions": ["list_tenants", "get_tenant"],
    },
    {
        "name": "AuditLog",
        "display_name": "审计日志",
        "domain": "common",
        "description": "操作审计记录",
        "fields": ["id", "tenant_id", "actor_id", "action", "target", "target_id", "detail", "ts", "created_at"],
        "actions": ["list_audit_logs", "search_audit_logs"],
    },
]

# 构建 name -> object 的映射（seed 快照，仅供初始化/降级使用）
SEED_OBJECT_MAP = {obj["name"]: obj for obj in OBJECTS}


def __getattr__(name: str):
    """模块级懒转发：OBJECT_MAP 指向 registry 实时缓存代理。

    用 PEP 562 而非顶层 import，避免 objects.py <-> registry.py 循环导入
    （registry._seed_data() 需要反向 import 本模块的 OBJECTS）。
    """
    if name == "OBJECT_MAP":
        from ontology.registry import OBJECT_MAP as _m
        return _m
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def list_objects(domain: Optional[str] = None, tenant_id: Optional[str] = None) -> list[dict]:
    """列出所有 Object，可按域过滤（读运行时权威源）"""
    from ontology.registry import registry
    return registry.list_objects(domain, tenant_id)


def get_object(name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """按名称获取 Object（读运行时权威源）"""
    from ontology.registry import registry
    return registry.get_object(name, tenant_id)
