"""Agent 注册表 - 5 个域 Agent + 1 个 Supervisor（共 6 个）

双模式构建：
  - LLM_PROVIDER=mock（默认）：使用 MockAgent，返回预设响应
  - LLM_PROVIDER=openai：使用 LLMAgent + ToolLoop，真实 LLM 驱动 + 工具调用

每个域 Agent 持有多个 Skill，由 Orchestrator 根据意图选择具体 Skill 执行。
"""
import logging
from typing import Optional

from ai.agents.base import MockAgent

logger = logging.getLogger(__name__)

# 决定使用哪种 Agent 实现
try:
    from config import settings
    _USE_LLM_AGENT = settings.LLM_PROVIDER == "openai"
except Exception:
    _USE_LLM_AGENT = False

if _USE_LLM_AGENT:
    try:
        from ai.agents.llm_agent import LLMAgent
    except Exception as e:
        logger.warning("LLMAgent 导入失败，回退到 MockAgent: %s", e)
        _USE_LLM_AGENT = False


# ──────────────────────────────────────────────
# Agent 定义数据（6 个域 Agent，每个持有多 Skill）
# ──────────────────────────────────────────────

_AGENT_DEFS = [
    # 全局监督者
    {
        "name": "Supervisor",
        "display_name": "监督者",
        "domain": "global",
        "description": "意图路由、跨域编排、降级兜底",
        "system_prompt": "你是平台监督者（Supervisor），负责理解用户意图、路由到合适的领域 Agent，并在无法识别意图时直接给出兜底回复。始终以中文回答。",
        "tools": [],
        "skills": [],
        "few_shot_examples": [],
        "domain_filter": ["User", "Tenant"],
    },

    # 销售执行域
    {
        "name": "SalesAgent",
        "display_name": "销售助手",
        "domain": "sales",
        "description": "拜访计划、覆盖分析、反馈抽取、积分、ROI、矩阵、KOL",
        "system_prompt": (
            "你是一位资深医药销售专家，擅长拜访计划生成、覆盖分析、反馈抽取、积分管理、"
            "ROI 分析、矩阵分析和 KOL 管理。根据用户具体需求选择合适的技能执行。"
            "请基于上下文给出可执行的建议。"
        ),
        "tools": [
            "list_visit_plans", "create_visit_plan", "create_visit_record",
            "list_visit_records", "get_coverage_matrix", "compute_coverage_gap",
            "list_doctors", "list_hospitals", "compute_roi", "compute_kpi",
            # N+5：visit-planner 工作流原语（7 个）
            "fetch_visit_config", "sync_visit_draft", "merge_visit_draft",
            "compute_visit_priority", "generate_visit_payload",
            "create_visit_plan_record", "validate_visit_gate",
            # v2.0：kol-analyzer 工作流原语（8 个）
            "fetch_kol_candidates", "sync_kol_dimensions", "aggregate_kol_data",
            "generate_kol_profile", "classify_kol_tier", "merge_kol_strategy",
            "create_kol_record", "validate_kol_gate",
        ],
        "skills": [
            "visit-planner", "coverage-analyzer", "feedback-extractor",
            "scoring-analyzer", "roi-analyzer", "matrix-builder", "kol-analyzer",
        ],
        "few_shot_examples": [],
        "domain_filter": [
            "VisitPlan", "VisitPlanItem", "VisitRecord", "VisitFeedback",
            "Hospital", "Doctor", "Product", "Zone",
            "CoverageAssignment", "CoverageMatrix",
        ],
    },

    # 智能培训域
    {
        "name": "TrainingAgent",
        "display_name": "培训助手",
        "domain": "training",
        "description": "课程推荐、考试组卷、直播管理、学习路径、场景演练",
        "system_prompt": (
            "你是一位医药培训顾问，擅长课程推荐、智能组卷、直播管理、学习路径优化和演练场景设计。"
            "根据用户的学习需求和进度，选择合适的技能执行。"
        ),
        "tools": [
            "list_courses", "enroll_course", "list_exams", "get_my_learning",
            # N+5：培训场景创建工作流原语（8 个）
            "fetch_scene_config", "sync_scene_draft", "merge_scene_draft",
            "finalize_scene_knowledge", "validate_scene_gate",
            "suggest_scene_knowledge", "generate_context_payload", "create_scene_record",
            # N+5：exam-generator 工作流原语（7 个）
            "fetch_exam_config", "sync_exam_draft", "merge_exam_draft",
            "generate_questions_batch", "validate_exam_paper",
            "create_exam_record", "validate_exam_gate",
            # v2.2 Phase 2：pharma-rep-onboarding 工作流原语（6 个，医药代表上岗备案）
            "fetch_onboarding_checklist", "sync_onboarding_draft",
            "sign_compliance_commitment", "submit_onboarding_registration",
            "create_onboarding_record", "validate_onboarding_gate",
        ],
        "skills": [
            "course-recommender", "exam-generator", "live-scheduler",
            "path-optimizer", "scenario-generator", "practice-coach",
            "pharma-rep-onboarding",
        ],
        "few_shot_examples": [],
        "domain_filter": [
            "Course", "CourseSection", "LearningPath", "LearningProgress",
            "Exam", "ExamAttempt", "TrainingScene", "TrainingDrill",
        ],
    },

    # 决策支持域
    {
        "name": "DecisionAgent",
        "display_name": "决策助手",
        "domain": "decision",
        "description": "KPI 监控、归因分析、What-if 模拟、预警管理",
        "system_prompt": (
            "你是一位决策分析专家，擅长 KPI 监控、多因素归因、What-if 模拟推演和预警管理。"
            "根据用户的决策需求，选择合适的技能执行，提供数据驱动的建议。"
        ),
        "tools": [
            "compute_kpi", "get_alerts", "simulate_scenario",
            # N+5：what-if-simulator 工作流原语（6 个）
            "fetch_kpi_baseline", "sync_simulation_params", "merge_scenario_metadata",
            "run_simulation_step", "compare_scenarios", "validate_whatif_gate",
            # v2.0：alert-manager 工作流原语（7 个）
            "fetch_alerts_batch", "sync_alert_filter", "merge_alert_metadata",
            "analyze_alert_root_cause", "generate_alert_suggestion",
            "create_alert_disposition_record", "validate_alert_gate",
        ],
        "skills": [
            "kpi-monitor", "attribution-analyzer",
            "what-if-simulator", "alert-manager",
        ],
        "few_shot_examples": [],
        "domain_filter": [
            "KPIDefinition", "KPIValue", "Alert",
            "AttributionResult", "SimulationScenario",
        ],
    },

    # 协同办公域
    {
        "name": "CollabAgent",
        "display_name": "协同助手",
        "domain": "collab",
        "description": "待办管理、审批建议、会议组织、报告生成",
        "system_prompt": (
            "你是一位协同办公专家，擅长待办管理、审批建议、会议组织和报告生成。"
            "根据用户的协作需求，选择合适的技能执行。"
        ),
        "tools": [
            "list_documents",
            # v2.0：meeting-organizer 工作流原语（7 个）
            "fetch_meeting_config", "sync_meeting_agenda", "merge_meeting_notice",
            "attach_meeting_materials", "create_meeting_record",
            "dispatch_meeting_notice", "validate_meeting_gate",
            # v2.0：report-builder 工作流原语（8 个）
            "fetch_report_config", "sync_report_scope", "merge_report_outline",
            "aggregate_report_data", "generate_report_content",
            "validate_report_quality", "create_report_record", "validate_report_gate",
            # v2.2 Phase 2：academic-activity-lifecycle 工作流原语（6 个，学术活动全生命周期）
            "fetch_activity_template", "sync_activity_draft",
            "submit_activity_checkin", "submit_activity_expense",
            "submit_activity_feedback", "validate_activity_gate",
        ],
        "skills": [
            "task-prioritizer", "approval-assistant",
            "meeting-organizer", "report-builder",
            "academic-activity-lifecycle",
        ],
        "few_shot_examples": [],
        "domain_filter": [
            "Task", "Approval", "Announcement", "Meeting",
            "WeeklyReport", "MonthlyReport", "Report",
        ],
    },

    # 知识库域
    {
        "name": "KnowledgeAgent",
        "display_name": "知识助手",
        "domain": "knowledge",
        "description": "RAG 问答、文档检索、外发链接",
        "system_prompt": (
            "你是一位知识管理专家，擅长 RAG 问答、文档检索和外发链接管理。"
            "根据用户的知识需求，选择合适的技能执行，提供准确的引用溯源。"
        ),
        "tools": [
            "search_knowledge", "list_documents",
        ],
        "skills": [
            "rag-qa", "content-outsender",
        ],
        "few_shot_examples": [],
        "domain_filter": [
            "KnowledgeSpace", "WikiPage", "Document", "Annotation",
            "KnowledgeDocument", "FaqItem", "OutsendLink",
        ],
    },
]


# ──────────────────────────────────────────────
# 构建 Agent Registry
# ──────────────────────────────────────────────

def _build_registry() -> dict:
    """构建 name -> Agent 的注册表

    根据 LLM_PROVIDER 配置决定使用 MockAgent 还是 LLMAgent：
      - mock：MockAgent（预设响应，开发/测试用）
      - openai：LLMAgent（真实 LLM + 工具循环）
    """
    registry = {}
    for defn in _AGENT_DEFS:
        if _USE_LLM_AGENT:
            agent = LLMAgent(defn=defn)
        else:
            agent = MockAgent(
                name=defn["name"],
                display_name=defn["display_name"],
                domain=defn["domain"],
                description=defn["description"],
                system_prompt=defn["system_prompt"],
                tools=defn.get("tools", []),
                skills=defn.get("skills", []),
                few_shot_examples=defn.get("few_shot_examples", []),
                domain_filter=defn.get("domain_filter", []),
            )
        registry[defn["name"]] = agent
    return registry


# 全局 Agent 注册表
AGENT_REGISTRY = _build_registry()


def list_agents(domain: Optional[str] = None) -> list[dict]:
    """列出所有 Agent 的元数据（不含 system_prompt）"""
    agents = list(AGENT_REGISTRY.values())
    if domain:
        agents = [a for a in agents if a.domain == domain]
    return [a.metadata() for a in agents]


def get_agent(name: str) -> Optional[object]:
    """按名称获取 Agent 实例（MockAgent 或 LLMAgent）"""
    return AGENT_REGISTRY.get(name)


def build_agent(defn: dict, llm_client=None, tool_loop=None):
    """工厂函数：根据当前模式构建 Agent

    Args:
        defn: Agent 定义字典
        llm_client: LLMClient 实例（仅 LLMAgent 使用）
        tool_loop: ToolLoop 实例（仅 LLMAgent 使用）

    Returns:
        MockAgent 或 LLMAgent 实例
    """
    if _USE_LLM_AGENT and llm_client is not None:
        return LLMAgent(defn=defn, llm_client=llm_client, tool_loop=tool_loop)
    return MockAgent(
        name=defn["name"],
        display_name=defn["display_name"],
        domain=defn["domain"],
        description=defn["description"],
        system_prompt=defn["system_prompt"],
        tools=defn.get("tools", []),
        skills=defn.get("skills", []),
        few_shot_examples=defn.get("few_shot_examples", []),
        domain_filter=defn.get("domain_filter", []),
    )


def get_agent_mode() -> str:
    """返回当前 Agent 模式（mock / llm）"""
    return "llm" if _USE_LLM_AGENT else "mock"
