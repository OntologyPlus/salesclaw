"""AI Skill Registry - 22 个 Skill（Action 的业务封装）"""
from typing import Optional


# ──────────────────────────────────────────────
# Skill 定义
# ──────────────────────────────────────────────

SKILLS = [
    {
        "name": "ppt-generator",
        "display_name": "PPT 生成器",
        "description": "生成业务报告 PPT",
        "actions": ["generate_weekly_report", "create_export_job"],
    },
    {
        "name": "notification-dispatcher",
        "display_name": "通知分发器",
        "description": "多渠道通知分发",
        "actions": ["create_subscription", "dispatch_alert"],
    },
    {
        "name": "event-analytics",
        "display_name": "事件分析器",
        "description": "事件采集与分析",
        "actions": ["list_visit_records", "compute_kpi", "run_attribution"],
    },
    {
        "name": "rag-qa",
        "display_name": "RAG 问答",
        "description": "基于知识库的问答",
        "actions": ["search_knowledge", "search_documents", "read_wiki"],
    },
    {
        "name": "plan-recommender",
        "display_name": "计划推荐器",
        "description": "拜访计划推荐",
        "actions": ["list_visit_plans", "create_visit_plan", "get_coverage_matrix"],
    },
    {
        "name": "visit-recorder",
        "display_name": "拜访记录器",
        "description": "记录拜访并抽取反馈",
        "actions": ["create_visit_record", "extract_feedback", "save_visit_draft"],
    },
    {
        "name": "feedback-extractor",
        "display_name": "反馈抽取器",
        "description": "从拜访记录抽取反馈",
        "actions": ["list_visit_records", "extract_feedback", "list_visit_feedback"],
    },
    {
        "name": "coverage-analyzer",
        "display_name": "覆盖分析器",
        "description": "分析覆盖空白与潜力",
        "actions": ["get_coverage_matrix", "compute_coverage_gap", "list_coverage_assignments"],
    },
    {
        "name": "score-calculator",
        "display_name": "积分计算器",
        "description": "计算行为与指令积分",
        "actions": ["get_behavior_points", "get_instruction_points", "calculate_behavior_points", "calculate_instruction_points"],
    },
    {
        "name": "roi-reporter",
        "display_name": "ROI 报告器",
        "description": "ROI 计算与报告",
        "actions": ["list_visit_records", "get_kpi_value", "compute_kpi"],
    },
    {
        "name": "matrix-viewer",
        "display_name": "矩阵查看器",
        "description": "覆盖矩阵可视化",
        "actions": ["get_coverage_matrix", "compute_coverage_gap"],
    },
    {
        "name": "course-recommender",
        "display_name": "课程推荐器",
        "description": "推荐培训课程",
        "actions": ["list_courses", "get_course", "enroll_course"],
    },
    {
        "name": "exam-generator",
        "display_name": "考试生成器",
        "description": "智能组卷与阅卷",
        "actions": ["generate_exam", "grade_exam", "get_exam_score"],
    },
    {
        "name": "live-summarizer",
        "display_name": "直播总结器",
        "description": "总结直播要点",
        "actions": ["list_live_classes", "summarize_live_class"],
    },
    {
        "name": "path-optimizer",
        "display_name": "路径优化器",
        "description": "优化学习路径",
        "actions": ["list_learning_paths", "get_learning_progress", "optimize_learning_path"],
    },
    {
        "name": "scene-designer",
        "display_name": "场景设计器",
        "description": "设计演练场景",
        "actions": ["list_training_scenes", "generate_drill_scene", "run_drill", "grade_drill"],
    },
    {
        "name": "kpi-monitor",
        "display_name": "KPI 监控器",
        "description": "监控 KPI 与预警",
        "actions": ["get_kpi_value", "list_kpi_definitions", "list_alerts", "detect_anomaly"],
    },
    {
        "name": "attribution-analyzer",
        "display_name": "归因分析器",
        "description": "多因素归因分析",
        "actions": ["run_attribution", "list_attribution_results", "get_kpi_value"],
    },
    {
        "name": "simulation-runner",
        "display_name": "模拟运行器",
        "description": "What-if 模拟",
        "actions": ["run_simulation", "list_simulation_scenarios"],
    },
    {
        "name": "alert-dispatcher",
        "display_name": "预警分发器",
        "description": "预警检测与分发",
        "actions": ["detect_anomaly", "list_alerts", "dispatch_alert"],
    },
    {
        "name": "task-organizer",
        "display_name": "任务整理器",
        "description": "待办生成与分配",
        "actions": ["list_tasks", "create_todo", "assign_task", "complete_task"],
    },
    {
        "name": "knowledge-curator",
        "display_name": "知识策展器",
        "description": "知识库整理与批注",
        "actions": ["search_knowledge", "read_wiki", "add_annotation", "create_wiki_page"],
    },
]

# 构建 name -> skill 的映射
SKILL_MAP = {skill["name"]: skill for skill in SKILLS}


def list_skills() -> list[dict]:
    """列出所有 Skill"""
    return SKILLS


def get_skill(name: str) -> Optional[dict]:
    """按名称获取 Skill"""
    return SKILL_MAP.get(name)


__all__ = ["SKILLS", "SKILL_MAP", "list_skills", "get_skill"]
