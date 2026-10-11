"""数据库层 - 3 个 SQLite 引擎 + 模型定义 + 迁移系统"""
from datetime import datetime, timedelta, date
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text, DateTime, Boolean, Date,
    ForeignKey, Index, JSON, inspect, text
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from config import settings
from core.security import hash_password

# ──────────────────────────────────────────────
# Base 类
# ──────────────────────────────────────────────

class BusinessBase(DeclarativeBase):
    """业务数据库（psp.db）的 Base"""
    pass


class OntologyBase(DeclarativeBase):
    """本体数据库（psp_ontology.db）的 Base"""
    pass


# ──────────────────────────────────────────────
# 混入：基础字段
# ──────────────────────────────────────────────

class BaseFields:
    """所有业务表必带的公共字段"""
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    is_deleted = Column(Integer, default=0, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)


# ──────────────────────────────────────────────
# 通用 / 多租户表（psp.db）
# ──────────────────────────────────────────────

class Tenant(BusinessBase):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    settings = Column(JSON, default=dict)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(BusinessBase, BaseFields):
    __tablename__ = "users"
    username = Column(String(64), nullable=False)
    email = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(64), nullable=True)
    role_id = Column(Integer, nullable=True)
    zone_id = Column(Integer, nullable=True)
    is_active = Column(Integer, default=1)
    last_login_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("uniq_users_tenant_username", "tenant_id", "username", unique=True),
    )


class Role(BusinessBase, BaseFields):
    __tablename__ = "roles"
    name = Column(String(64), nullable=False)
    code = Column(String(64), nullable=False)
    permissions = Column(JSON, default=list)
    # N+3 Step5：数据范围权限 — all/products:[ids]/activities:[ids]
    data_scope = Column(JSON, default=lambda: {"type": "all"})


class Permission(BusinessBase, BaseFields):
    __tablename__ = "permissions"
    code = Column(String(128), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    resource = Column(String(64), nullable=True)
    action = Column(String(32), nullable=True)


class UserRole(BusinessBase, BaseFields):
    __tablename__ = "user_roles"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)


class AuditLog(BusinessBase, BaseFields):
    __tablename__ = "audit_logs"
    actor_id = Column(Integer, nullable=True)
    action = Column(String(64), nullable=False)
    target = Column(String(64), nullable=True)
    target_id = Column(Integer, nullable=True)
    detail = Column(JSON, default=dict)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 合规证据链字段（v2.1 合规适配，对应《医药代表管理办法》第 26 条全过程留痕）
    prev_hash = Column(String(64), nullable=True)  # 上一条 AuditLog 的 hash，构造链式结构
    record_hash = Column(String(64), nullable=True, index=True)  # 本条记录的 SHA-256
    actor_role = Column(String(32), nullable=True)  # 操作者角色（如 pharma_rep / sales_manager / compliance_officer）
    is_compliance_critical = Column(Integer, default=0, index=True)  # 是否合规关键操作（备案/承诺书/学术活动/违规处置）


class SessionRecord(BusinessBase, BaseFields):
    __tablename__ = "sessions"
    user_id = Column(Integer, nullable=False)
    refresh_token = Column(String(512), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)


class NotificationSubscription(BusinessBase, BaseFields):
    __tablename__ = "notification_subscriptions"
    user_id = Column(Integer, nullable=False)
    channel = Column(String(32), nullable=False)
    target = Column(String(64), nullable=True)
    config = Column(JSON, default=dict)


# ──────────────────────────────────────────────
# 主数据表（psp.db）
# ──────────────────────────────────────────────

class Hospital(BusinessBase, BaseFields):
    __tablename__ = "hospitals"
    name = Column(String(128), nullable=False)
    code = Column(String(64), nullable=True)
    level = Column(String(32), nullable=True)
    province = Column(String(32), nullable=True)
    city = Column(String(32), nullable=True)
    district = Column(String(32), nullable=True)
    address = Column(String(256), nullable=True)


class Doctor(BusinessBase, BaseFields):
    __tablename__ = "doctors"
    name = Column(String(64), nullable=False)
    hospital_id = Column(Integer, nullable=True)
    department = Column(String(64), nullable=True)
    title = Column(String(64), nullable=True)
    phone = Column(String(32), nullable=True)


class Product(BusinessBase, BaseFields):
    __tablename__ = "products"
    name = Column(String(128), nullable=False)
    code = Column(String(64), nullable=True)
    category = Column(String(64), nullable=True)
    specifications = Column(String(128), nullable=True)
    manufacturer = Column(String(128), nullable=True)


class Zone(BusinessBase, BaseFields):
    __tablename__ = "zones"
    name = Column(String(64), nullable=False)
    code = Column(String(64), nullable=True)
    parent_id = Column(Integer, nullable=True)
    level = Column(Integer, default=1)


class DataDictionary(BusinessBase, BaseFields):
    __tablename__ = "data_dictionary"
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)


class DataDictionaryItem(BusinessBase, BaseFields):
    __tablename__ = "data_dictionary_items"
    dictionary_id = Column(Integer, nullable=False)
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Integer, default=1)


# ──────────────────────────────────────────────
# 销售执行域表（psp.db）
# ──────────────────────────────────────────────

class CoverageAssignment(BusinessBase, BaseFields):
    """覆盖分管"""
    __tablename__ = "coverage_assignments"
    user_id = Column(Integer, nullable=False, index=True)
    hospital_id = Column(Integer, nullable=True, index=True)
    doctor_id = Column(Integer, nullable=True)
    product_id = Column(Integer, nullable=True)
    role = Column(String(32), default="primary")  # primary/assistant
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    # 多源分管扩展
    source_type = Column(String(32), default="territory")  # territory/development/personal/agent
    is_temp = Column(Integer, default=0)  # 是否临时特批
    temp_expires_at = Column(DateTime, nullable=True)  # 临时特批过期时间
    agent_user_id = Column(Integer, nullable=True)  # 代理人 ID


class VisitPlan(BusinessBase, BaseFields):
    """拜访计划"""
    __tablename__ = "visit_plans"
    user_id = Column(Integer, nullable=False, index=True)
    period = Column(String(16), nullable=False)  # YYYY-MM
    target_count = Column(Integer, default=0)
    status = Column(String(16), default="draft", index=True)  # draft/pending/approved/rejected
    submitted_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, nullable=True)
    ai_score = Column(Integer, nullable=True)  # AI 评分 0-100
    ai_suggestion = Column(Text, nullable=True)


class VisitPlanItem(BusinessBase, BaseFields):
    """拜访计划明细"""
    __tablename__ = "visit_plan_items"
    plan_id = Column(Integer, nullable=False, index=True)
    hospital_id = Column(Integer, nullable=True)
    doctor_id = Column(Integer, nullable=True)
    product_id = Column(Integer, nullable=True)
    planned_date = Column(Date, nullable=True)
    priority = Column(String(16), default="medium")  # high/medium/low
    visit_type = Column(String(32), default="academic")  # academic/daily/meeting
    remark = Column(Text, nullable=True)


class VisitRecord(BusinessBase, BaseFields):
    """拜访记录"""
    __tablename__ = "visit_records"
    user_id = Column(Integer, nullable=False, index=True)
    plan_id = Column(Integer, nullable=True)
    plan_item_id = Column(Integer, nullable=True)
    hospital_id = Column(Integer, nullable=True, index=True)
    doctor_id = Column(Integer, nullable=True)
    product_id = Column(Integer, nullable=True)
    visit_date = Column(Date, nullable=False)
    visit_type = Column(String(32), default="academic")
    duration_minutes = Column(Integer, default=30)
    location = Column(String(128), nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(16), default="completed")
    ai_extracted = Column(Integer, default=0)
    # 学术推广证据链字段（v2.1 合规适配，对应《医药代表管理办法》第 21 条 + 第 26 条三流合一）
    meeting_protocol_no = Column(String(64), nullable=True, index=True)  # 会议协议编号
    checkin_evidence = Column(JSON, nullable=True)  # 签到证据（时间/地点/照片URL/二维码核验）
    expense_voucher = Column(JSON, nullable=True)  # 费用凭证（发票号/金额/附件URL）
    is_academic_activity = Column(Integer, default=0, index=True)  # 是否学术推广活动（区分于日常拜访）
    activity_approval_id = Column(Integer, nullable=True)  # 关联的学术活动立项审批 ID（Approval.id）
    adverse_reaction_reported = Column(JSON, nullable=True)  # 不良反应反馈收集（第 21 条第（三）项）


class VisitFeedback(BusinessBase, BaseFields):
    """拜访反馈"""
    __tablename__ = "visit_feedbacks"
    record_id = Column(Integer, nullable=False, index=True)
    sentiment = Column(String(16), default="neutral")  # positive/neutral/negative
    interest_points = Column(JSON, default=list)
    objections = Column(JSON, default=list)
    action_items = Column(JSON, default=list)
    ai_raw_response = Column(Text, nullable=True)


class CoverageMatrix(BusinessBase, BaseFields):
    """覆盖矩阵"""
    __tablename__ = "coverage_matrix"
    hospital_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    visit_count = Column(Integer, default=0)
    last_visit_date = Column(Date, nullable=True)
    coverage_level = Column(String(16), default="none")  # high/medium/low/none
    trend = Column(String(16), default="stable")  # up/down/stable


class BehaviorPointRule(BusinessBase, BaseFields):
    """行为积分规则"""
    __tablename__ = "behavior_point_rules"
    name = Column(String(128), nullable=False)
    action_code = Column(String(64), nullable=False)
    points = Column(Integer, default=1)
    description = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)


class BehaviorPointRecord(BusinessBase, BaseFields):
    """行为积分记录"""
    __tablename__ = "behavior_point_records"
    user_id = Column(Integer, nullable=False, index=True)
    rule_id = Column(Integer, nullable=False)
    record_id = Column(Integer, nullable=True)
    points = Column(Integer, default=0)
    occurred_at = Column(DateTime, default=datetime.utcnow)


class InstructionPointRule(BusinessBase, BaseFields):
    """指令积分规则"""
    __tablename__ = "instruction_point_rules"
    name = Column(String(128), nullable=False)
    action_code = Column(String(64), nullable=False)
    points = Column(Integer, default=1)
    description = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)


class InstructionPointRecord(BusinessBase, BaseFields):
    """指令积分记录"""
    __tablename__ = "instruction_point_records"
    user_id = Column(Integer, nullable=False, index=True)
    rule_id = Column(Integer, nullable=False)
    points = Column(Integer, default=0)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(64), nullable=True)


class WeeklyReport(BusinessBase, BaseFields):
    """周报"""
    __tablename__ = "weekly_reports"
    user_id = Column(Integer, nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    visit_count = Column(Integer, default=0)
    feedback_count = Column(Integer, default=0)
    total_points = Column(Integer, default=0)
    # 培训域字段
    courses_completed = Column(Integer, default=0)
    exams_taken = Column(Integer, default=0)
    credits_earned = Column(Integer, default=0)
    avg_exam_score = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)


# ──────────────────────────────────────────────
# 培训域模型
# ──────────────────────────────────────────────

class Course(BusinessBase, BaseFields):
    """课程"""
    __tablename__ = "courses"
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    course_type = Column(String(32), default="video")  # video/article/pdf/interactive
    category = Column(String(64), nullable=True, index=True)
    difficulty = Column(String(16), default="beginner")  # beginner/intermediate/advanced
    duration_minutes = Column(Integer, default=0)
    cover_image = Column(String(256), nullable=True)
    content_url = Column(String(512), nullable=True)
    tags = Column(JSON, default=list)
    is_published = Column(Integer, default=0, index=True)
    enroll_count = Column(Integer, default=0)
    avg_rating = Column(Integer, default=0)  # 0-100
    # 合规培训标识（v2.1 合规适配，对应《医药代表管理办法》第 9、10 条培训考核）
    is_compliance = Column(Integer, default=0, index=True)  # 是否合规培训课程
    is_mandatory = Column(Integer, default=0)  # 是否强制指派（医药代表上岗前必修）


class CourseEnrollment(BusinessBase, BaseFields):
    """课程选课记录"""
    __tablename__ = "course_enrollments"
    course_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(16), default="enrolled", index=True)  # enrolled/in_progress/completed/dropped
    progress = Column(Integer, default=0)  # 0-100
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    last_position = Column(Integer, default=0)  # 上次学习位置（秒）


class Question(BusinessBase, BaseFields):
    """题库题目"""
    __tablename__ = "questions"
    question_type = Column(String(16), nullable=False)  # single/multiple/judge/fill/short
    content = Column(Text, nullable=False)
    options = Column(JSON, default=list)  # [{"key":"A","text":"..."}]
    answer = Column(JSON, default=list)  # 正确答案 key 列表
    explanation = Column(Text, nullable=True)
    difficulty = Column(String(16), default="medium")  # easy/medium/hard
    category = Column(String(64), nullable=True, index=True)
    points = Column(Integer, default=5)


class Exam(BusinessBase, BaseFields):
    """考试"""
    __tablename__ = "exams"
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, default=60)
    pass_score = Column(Integer, default=60)  # 及格分（百分比）
    question_ids = Column(JSON, default=list)  # 题目 ID 列表
    status = Column(String(16), default="draft", index=True)  # draft/published/closed
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    max_attempts = Column(Integer, default=1)
    attempt_count = Column(Integer, default=0)


class ExamRecord(BusinessBase, BaseFields):
    """考试记录"""
    __tablename__ = "exam_records"
    exam_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(16), default="not_started", index=True)  # not_started/in_progress/submitted/graded
    answers = Column(JSON, default=list)  # [{"question_id":1,"answer":["A"]}]
    score = Column(Integer, nullable=True)  # 0-100
    passed = Column(Integer, nullable=True)  # 0/1
    started_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    ai_comment = Column(Text, nullable=True)


class LearningPath(BusinessBase, BaseFields):
    """学习路径"""
    __tablename__ = "learning_paths"
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    target_role = Column(String(64), nullable=True)  # 目标角色
    stages = Column(JSON, default=list)  # [{"stage":1,"title":"...","course_ids":[1,2],"required":true}]
    total_credits = Column(Integer, default=0)
    enroll_count = Column(Integer, default=0)
    is_published = Column(Integer, default=0, index=True)


class PathEnrollment(BusinessBase, BaseFields):
    """学习路径选课"""
    __tablename__ = "path_enrollments"
    path_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    current_stage = Column(Integer, default=1)
    credits_earned = Column(Integer, default=0)
    status = Column(String(16), default="enrolled", index=True)  # enrolled/completed
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Certificate(BusinessBase, BaseFields):
    """证书"""
    __tablename__ = "certificates"
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(128), nullable=False)
    cert_type = Column(String(32), nullable=True)  # course/exam/path
    source_id = Column(Integer, nullable=True)  # 关联的课程/考试/路径 ID
    score = Column(Integer, nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expire_at = Column(DateTime, nullable=True)
    cert_no = Column(String(64), nullable=True)  # 证书编号


class PersonaLibrary(BusinessBase, BaseFields):
    """角色画像库 — AI 角色结构化管理（N+2 Step1）

    用于 scenario-generator 解析时自动匹配 AI 角色，替代手工填空。
    """
    __tablename__ = "persona_library"
    name = Column(String(128), nullable=False)
    priority = Column(Integer, default=0)  # 优先级，数值越大越优先匹配
    keywords = Column(JSON, default=list)  # 匹配关键词
    exclusion_keywords = Column(JSON, default=list)  # 排除关键词
    default_brief = Column(Text, nullable=True)  # 默认简介
    persona_text = Column(Text, nullable=True)  # 完整人设文本
    persona_type = Column(String(32), default="customer")  # customer/manager/expert
    is_active = Column(Integer, default=1, index=True)


class PracticeScenario(BusinessBase, BaseFields):
    """演练场景"""
    __tablename__ = "practice_scenarios"
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(32), default="visit")  # visit/negotiation/objection/dialogue/ppt_speech
    customer_profile = Column(Text, nullable=True)  # 客户画像（AI 扮演）
    product_id = Column(Integer, nullable=True)
    difficulty = Column(String(16), default="medium")
    target_skills = Column(JSON, default=list)  # 考察技能点
    is_published = Column(Integer, default=0, index=True)
    # 客户关联（基于真实医生画像生成场景）
    doctor_id = Column(Integer, nullable=True, index=True)
    hospital_id = Column(Integer, nullable=True, index=True)
    # N+2 Step2/Step3：剧本解析 + PPT 演讲扩展
    persona_id = Column(Integer, nullable=True, index=True)  # 关联 PersonaLibrary
    ai_role_config = Column(JSON, default=dict)  # AI 角色设定（结构化）
    scoring_rules = Column(JSON, default=list)  # 评分规则 [{dimension, weight, standard}]
    standard_scripts = Column(JSON, default=list)  # 标准话术（拆条）
    knowledge_needs = Column(JSON, default=list)  # 关联知识库文档 ID
    # N+5：培训场景创建工作流生成的上下文 payload（doctor 5 键 + coach 3 键，对用户不可见）
    context_payload = Column(JSON, default=dict)  # {"doctor":{...}, "coach":{...}, "ready": bool}
    # PPT 演讲训战模式字段（N+2 Step3）
    ppt_url = Column(String(512), nullable=True)  # PPT 文件 URL
    ppt_pages = Column(JSON, default=list)  # [{page_no, title, content_text, reference_audio_url, key_points, keywords}]
    coach_prompts = Column(JSON, default=list)  # 教练提示（练习模式可见）
    reference_audio_url = Column(String(512), nullable=True)  # 金牌演讲音频
    pass_score = Column(Integer, default=60)  # 及格分
    scoring_dimensions = Column(JSON, default=list)  # 评分维度 [{key, label, weight}]


class PracticeSession(BusinessBase, BaseFields):
    """演练会话"""
    __tablename__ = "practice_sessions"
    scenario_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(16), default="in_progress", index=True)  # in_progress/completed
    messages = Column(JSON, default=list)  # [{"role":"user/ai","content":"..."}]
    score = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    # 培训活动扩展
    activity_id = Column(Integer, nullable=True, index=True)
    attempt_no = Column(Integer, default=1)  # 第几次尝试


class PPTSpeechSession(BusinessBase, BaseFields):
    """PPT 演讲训战会话（N+2 Step3）

    独立于 PracticeSession，承载逐页录音、问答、雷达评分等 PPT 专属数据。
    """
    __tablename__ = "ppt_speech_sessions"
    scenario_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    activity_id = Column(Integer, nullable=True, index=True)
    mode = Column(String(16), default="practice")  # practice/train
    status = Column(String(16), default="in_progress", index=True)  # in_progress/completed/abandoned
    current_page = Column(Integer, default=1)
    per_page_recordings = Column(JSON, default=list)  # [{page_no, audio_url, duration_ms, transcript}]
    questions = Column(JSON, default=list)  # [{page_no, question, asked_at}]
    answers = Column(JSON, default=list)  # [{question_id, answer_text, audio_url}]
    final_score = Column(Integer, nullable=True)
    radar_scores = Column(JSON, default=dict)  # {dimension_key: score}
    ai_review = Column(Text, nullable=True)  # AI 逐页点评 JSON
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)


# ──────────────────────────────────────────────
# AI 表（psp.db）
# ──────────────────────────────────────────────

class ChatSession(BusinessBase, BaseFields):
    __tablename__ = "chat_sessions"
    user_id = Column(Integer, nullable=False)
    title = Column(String(128), nullable=True)
    agent_name = Column(String(64), nullable=True)
    status = Column(String(32), default="active")


class ChatMessage(BusinessBase, BaseFields):
    __tablename__ = "chat_messages"
    session_id = Column(Integer, nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    meta = Column("metadata", JSON, default=dict)  # DB 列名为 metadata，避开 SQLAlchemy 保留属性
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentDefinition(BusinessBase, BaseFields):
    __tablename__ = "agent_definitions"
    name = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(128), nullable=False)
    domain = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    tools = Column(JSON, default=list)
    few_shot_examples = Column(JSON, default=list)
    domain_filter = Column(JSON, default=list)
    is_active = Column(Integer, default=1)


class SkillDefinition(BusinessBase, BaseFields):
    __tablename__ = "skill_definitions"
    name = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    actions = Column(JSON, default=list)
    is_active = Column(Integer, default=1)


class PromptTemplate(BusinessBase, BaseFields):
    __tablename__ = "prompt_templates"
    name = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    variables = Column(JSON, default=list)
    version = Column(Integer, default=1)
    is_active = Column(Integer, default=1)


class LlmCallLog(BusinessBase, BaseFields):
    __tablename__ = "llm_call_logs"
    provider = Column(String(32), nullable=True)
    model = Column(String(64), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    status = Column(String(16), default="ok")
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)


# ──────────────────────────────────────────────
# AI 原生增强表（psp.db）
# ──────────────────────────────────────────────

class EpisodicMemory(BusinessBase, BaseFields):
    """情景记忆 - 对话片段"""
    __tablename__ = "episodic_memories"
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    importance = Column(Integer, default=5)  # 1-10
    occurred_at = Column(DateTime, default=datetime.utcnow)
    decay_score = Column(Integer, default=100)  # 时间衰减分


class SemanticMemory(BusinessBase, BaseFields):
    """语义记忆 - 用户画像与知识"""
    __tablename__ = "semantic_memories"
    user_id = Column(Integer, nullable=False, index=True)
    category = Column(String(64))  # profile/preference/pattern/skill
    key = Column(String(128))
    value = Column(Text)
    confidence = Column(Integer, default=50)  # 0-100


class ProceduralMemory(BusinessBase, BaseFields):
    """程序记忆 - 策略与流程"""
    __tablename__ = "procedural_memories"
    user_id = Column(Integer, nullable=True)  # null=全局
    strategy_name = Column(String(128))
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    context_pattern = Column(JSON)  # JSON: 触发条件


class IntentFeedback(BusinessBase, BaseFields):
    """意图反馈 - 用户纠正意图分类"""
    __tablename__ = "intent_feedbacks"
    user_id = Column(Integer, nullable=False, index=True)
    query = Column(Text, nullable=False)
    predicted_intent = Column(String(64))
    corrected_intent = Column(String(64))
    ts = Column(DateTime, default=datetime.utcnow)


class ReasoningChain(BusinessBase, BaseFields):
    """推理链"""
    __tablename__ = "reasoning_chains"
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=True)
    query = Column(Text, nullable=False)
    intent = Column(String(64))
    agent_used = Column(String(64))
    steps = Column(JSON, default=list)  # 推理步骤列表
    conclusion = Column(Text)
    confidence = Column(Integer, default=50)  # 0-100
    feedback_rating = Column(Integer, nullable=True)  # 1-5
    feedback_text = Column(Text, nullable=True)
    hallucination_score = Column(Integer, nullable=True)  # 0-100
    reflection_count = Column(Integer, default=0)
    ts = Column(DateTime, default=datetime.utcnow)


class DecisionExecution(BusinessBase, BaseFields):
    """决策执行记录 - 效果追踪"""
    __tablename__ = "decision_executions"
    user_id = Column(Integer, nullable=False, index=True)
    decision_type = Column(String(64))  # visit_plan/training/coverage
    title = Column(String(256))
    description = Column(Text)
    baseline_metrics = Column(JSON)  # 决策前指标快照
    target_metrics = Column(JSON)  # 目标指标
    actual_metrics = Column(JSON)  # 实际结果
    status = Column(String(32), default="planned")  # planned/executing/completed/failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    effectiveness_score = Column(Integer, nullable=True)  # 0-100
    # N+AI原生闭环：效果评估经编排器七步状态机，关联 source 推理链（可解释/可追溯）
    reasoning_chain_id = Column(String(64), nullable=True, index=True)


class AIEvent(BusinessBase, BaseFields):
    """AI 事件记录 - 事件驱动"""
    __tablename__ = "ai_events"
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, default=dict)
    consistency = Column(String(16), default="eventual")  # strong/eventual
    status = Column(String(16), default="pending")  # pending/processing/completed/failed/dead_letter
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class DeadLetter(BusinessBase, BaseFields):
    """死信队列 - Write-Back 重试失败的事件"""
    __tablename__ = "ai_dead_letters"
    event_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, default=dict)
    error_message = Column(Text, nullable=False)
    failed_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Integer, default=0)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, nullable=True)
    resolution_note = Column(Text, nullable=True)


class SuggestionAction(BusinessBase, BaseFields):
    """N+4: 建议行动跟踪 — 建议采纳/忽略/稍后 + 延迟效果评估"""
    __tablename__ = "suggestion_actions"
    suggestion_id = Column(String(64), nullable=False, index=True)
    suggestion_type = Column(String(64), nullable=True)  # coverage_reminder/training_reminder/...
    user_id = Column(Integer, nullable=False, index=True)
    action_type = Column(String(32), nullable=False)  # accepted/ignored/dismissed
    acted_at = Column(DateTime, default=datetime.utcnow)
    outcome_metric = Column(String(64), nullable=True)  # 行动后指标名
    outcome_value = Column(Float, nullable=True)          # 行动后指标值
    feedback_score = Column(Integer, nullable=True)      # 1-5 用户反馈
    evaluated_at = Column(DateTime, nullable=True)       # 延迟评估时间
    evaluate_after = Column(DateTime, nullable=True)      # 预定评估时间（now + 24h）


class AiAgentRun(BusinessBase, BaseFields):
    """Phase B：Agent 运行记录 + ToolLoop checkpoint（可续跑）"""
    __tablename__ = "ai_agent_runs"
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    intent = Column(String(64), nullable=True)
    agent_name = Column(String(64), nullable=True)
    skill_name = Column(String(128), nullable=True)
    status = Column(String(32), default="running", index=True)  # running/completed/aborted/failed
    cursor_round = Column(Integer, default=0)
    max_rounds = Column(Integer, default=2)
    messages = Column(JSON, default=list)       # ToolLoop working_messages
    tools_used = Column(JSON, default=list)
    last_content = Column(Text, nullable=True)
    budget = Column(JSON, default=dict)         # {max_rounds, max_latency_ms, ...}
    trace_id = Column(String(64), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_run_at = Column(DateTime, default=datetime.utcnow)


class ActionLedger(BusinessBase, BaseFields):
    """Phase B：Action Gateway 幂等账本（Command 执行结果）"""
    __tablename__ = "action_ledgers"
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    action_type = Column(String(128), nullable=False, index=True)
    target = Column(String(256), nullable=True)
    status = Column(String(32), default="pending", index=True)  # pending/completed/failed/rejected
    proposal = Column(JSON, default=dict)
    command = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    run_id = Column(String(64), nullable=True, index=True)
    trace_id = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)


class DataLineage(BusinessBase, BaseFields):
    """N+4: 数据流追踪 — 记录数据从 source → target 的流动"""
    __tablename__ = "data_lineage"
    source_type = Column(String(32), nullable=False, index=True)  # collection/training/visit/decision
    source_id = Column(Integer, nullable=True)
    target_type = Column(String(32), nullable=False, index=True)  # profile/insight/kpi
    target_id = Column(Integer, nullable=True)
    transformation = Column(String(64), nullable=False)  # 转换类型
    payload = Column(JSON, default=dict)  # 变换前后值
    user_id = Column(Integer, nullable=True, index=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)


class Diagnosis(BusinessBase, BaseFields):
    """AI 诊断实体（一等语义实体）— 由结构化推理生成并进入状态机"""
    __tablename__ = "diagnoses"
    rep_id = Column(Integer, nullable=False, index=True)
    domain = Column(String(64), nullable=False, index=True)  # coverage/visit/adoption/...
    target_type = Column(String(32), nullable=True)  # hospital/department/doctor/product
    target_id = Column(Integer, nullable=True, index=True)
    summary = Column(Text)
    level = Column(String(16), default="YELLOW", index=True)  # GREEN/YELLOW/RED/BLACK
    confidence = Column(Float, default=0.0)  # 0-1
    status = Column(String(32), default="draft", index=True)  # draft/confirmed/executing/verified/closed
    evidence = Column(JSON, default=list)  # [{source, metric, value, ref}]
    reasoning_trace = Column(JSON, default=list)  # 推理链步骤
    reasoning_chain_id = Column(Integer, nullable=True, index=True)  # 关联 Orchestrator 推理链
    provenance = Column(Text, nullable=True)  # 数据血缘标识（JSON: {mode, model_version, run_id...}）
    trace_id = Column(String(64), nullable=True, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    # OAG Layer 4 借鉴点：置信度档位（GREEN/YELLOW/RED，🟢/🟡/🔴 对齐方案）与结构化校验明细
    confidence_band = Column(String(16), nullable=True, index=True)
    validation_detail = Column(JSON, default=dict)      # 五维校验结论（数值/关系/时间/因果/业务规则）
    # OAG Layer 5 借鉴点：诊断结论→可触发动作最小闭环（关联 ontology/actions 注册表）
    action_suggestion = Column(JSON, default=list)      # [{action, display_name, risk_level, description}]
    # 误判排除闸（方案第五章 O14）：红/黄灯受结构性因素驱动而非代表不力时的标记
    excluded = Column(Integer, default=0, index=True)   # 0=未排除 1=命中排除闸
    excluded_reason = Column(JSON, default=dict)        # {type,label,desc,original_level,evidence}


class Signal(BusinessBase, BaseFields):
    """异常信号实体 — 诊断中识别出的可观测异常"""
    __tablename__ = "signals"
    diagnosis_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=True, index=True)
    severity = Column(String(16), default="medium", index=True)  # high/medium/low
    description = Column(Text)
    clear_condition = Column(Text)  # 信号消除条件
    cleared = Column(Integer, default=0, index=True)  # 0/1
    observed_at = Column(DateTime, default=datetime.utcnow)
    cleared_at = Column(DateTime, nullable=True)


class AttributionChainResult(BusinessBase, BaseFields):
    """L2 关系链推理结果 — 跨对象归因落库（确定性规则 + 可选 LLM 润色）

    仅保存轻量链路 JSON（节点序列 + 经过的 Link + 每跳贡献度），
    不重复存储中间对象，避免写入膨胀。
    """
    __tablename__ = "attribution_chain_results"
    root_type = Column(String(64), nullable=False, index=True)  # User/Hospital/Doctor...
    root_id = Column(Integer, nullable=True, index=True)        # 根对象实例 id
    target_type = Column(String(64), nullable=True, index=True)  # KPIValue/Diagnosis...
    domain = Column(String(64), nullable=True, index=True)
    max_depth = Column(Integer, default=4)
    chain_json = Column(JSON, default=dict)      # {paths|subgraph, root_cause, summary}
    summary = Column(Text)                        # 自然语言摘要（规则模板或 LLM 润色）
    level = Column(String(16), default="YELLOW")  # GREEN/YELLOW/RED
    confidence = Column(Float, default=0.0)       # 0-1
    ai_generated = Column(Integer, default=0, index=True)  # 0=规则 1=AI 润色
    trace_id = Column(String(64), nullable=True, index=True)


class Paradigm(BusinessBase, BaseFields):
    """通用解题范式实体 — 从已闭环有效执行沉淀，可跨代表复用"""
    __tablename__ = "paradigms"
    domain = Column(String(64), nullable=False, index=True)
    problem_type = Column(String(128), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    effective_method = Column(Text)
    evidence_execution_ids = Column(JSON, default=list)
    usage_count = Column(Integer, default=0)
    effectiveness_score = Column(Integer, default=0)  # 0-100
    # N+AI原生闭环：范式由编排器七步状态机沉淀，关联 source 推理链（可解释/可追溯）
    reasoning_chain_id = Column(String(64), nullable=True, index=True)


class InsightChain(BusinessBase, BaseFields):
    """N+4: 洞察因果链 — 3 层因果结构（根因 → 中间因素 → 表象）"""
    __tablename__ = "insight_chains"
    domain = Column(String(32), nullable=False, index=True)
    root_event_type = Column(String(64), nullable=False)
    chain_json = Column(JSON, default=list)  # [{layer, type, dimension, delta, weight, evidence_id}]
    conclusion = Column(Text)
    evidence_ids = Column(JSON, default=list)  # data_lineage IDs
    confidence = Column(Float, default=0.0)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)


class AbilityProfile(BusinessBase, BaseFields):
    """N+4: 用户多维能力画像（5 维）— 跨域身份主线"""
    __tablename__ = "ability_profiles"
    user_id = Column(Integer, nullable=False, index=True)
    dimension = Column(String(32), nullable=False, index=True)  # product_knowledge/visit_skill/customer_relation/compliance/ai_application
    score = Column(Float, default=0.0)  # 0-100
    sample_size = Column(Integer, default=0)  # 证据数量
    last_updated_at = Column(DateTime, default=datetime.utcnow)
    trend_30d = Column(Float, default=0.0)
    decay_factor = Column(Float, default=1.0)
    evidence_json = Column(JSON, default=dict)  # 最近 5 条证据
    __table_args__ = (Index("uniq_ability_user_dim", "user_id", "dimension", unique=True),)


class ProfileHistory(BusinessBase, BaseFields):
    """N+4: 画像变更历史"""
    __tablename__ = "profile_history"
    user_id = Column(Integer, nullable=False, index=True)
    dimension = Column(String(32), nullable=False)
    delta = Column(Float, default=0.0)
    source = Column(String(32), nullable=False)  # training/visit/collection/feedback/ai
    source_id = Column(Integer, nullable=True)
    new_score = Column(Float, default=0.0)
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)


class DecisionRecommendation(BusinessBase, BaseFields):
    """N+4: 决策建议（可派单）— Batch 2.4"""
    __tablename__ = "decision_recommendations"
    title = Column(String(256), nullable=False)
    priority = Column(String(16), default="medium")  # high/medium/low
    domain = Column(String(32), nullable=False, index=True)
    target_user_id = Column(Integer, nullable=True, index=True)
    suggested_action = Column(String(64), nullable=True)  # navigate/notify/schedule
    action_params = Column(JSON, default=dict)  # {url, params, ...}
    insight_chain_id = Column(Integer, nullable=True, index=True)  # 关联 InsightChain
    status = Column(String(16), default="pending", index=True)  # pending/accepted/rejected/expired
    expires_at = Column(DateTime, nullable=True)


# ──────────────────────────────────────────────
# 协同办公表（psp.db）
# ──────────────────────────────────────────────

class Task(BusinessBase, BaseFields):
    """任务"""
    __tablename__ = "tasks"
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(32), default="general")  # general/visit/follow_up/training
    status = Column(String(32), default="pending")  # pending/in_progress/completed/cancelled
    priority = Column(String(16), default="medium")  # high/medium/low
    assignee_id = Column(Integer, nullable=False, index=True)
    creator_id = Column(Integer, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    related_type = Column(String(64), nullable=True)  # visit_plan/record/feedback/course
    related_id = Column(Integer, nullable=True)
    # ──────────────────────────────────────────────
    # F3 任务负载阀门字段（借鉴企业级诊断体系 §9.1）
    # ──────────────────────────────────────────────
    dedup_key = Column(String(128), nullable=True, index=True)  # 去重键 = hash(related_type+related_id+task_type+date)
    merged_from = Column(Text, nullable=True)  # 合并来源（JSON 数组，子任务 id 列表）
    source_project = Column(String(64), nullable=True)  # 来源项目（如 "compliance" / "sales"）
    # ──────────────────────────────────────────────
    # F8 闭环判定字段（借鉴诊断体系 §7.5、§8.4）
    # ──────────────────────────────────────────────
    closure_state = Column(String(16), nullable=True, index=True)  # closed/partial/unresolved（仅在 status=completed 时填充）
    target_metric_json = Column(JSON, nullable=True)  # 量化目标：[{name, value, unit, deadline}]
    achieved_metric_json = Column(JSON, nullable=True)  # 实际达成：[{name, value, source}]
    appeal_state = Column(String(16), default="no_appeal")  # no_appeal/appealed/upheld/overturned
    review_cycle_id = Column(Integer, nullable=True)  # 关联月度复核批次（ClosureReviewCycle.id）


class ClosureReviewCycle(BusinessBase, BaseFields):
    """F8: 月度复核批次（每月 12 日生成）

    对应诊断体系 §7.5：每月同时生成"上月及更早在途计划的复核任务" + "当月新诊断任务"，
    形成"双任务"机制：上月遗留复核 + 当月新诊断同步推进。
    """
    __tablename__ = "closure_review_cycles"
    cycle_month = Column(String(7), nullable=False, index=True)  # YYYY-MM（如 2026-07）
    status = Column(String(16), default="pending")  # pending/in_progress/completed
    total_reviewed = Column(Integer, default=0)
    closed_count = Column(Integer, default=0)
    partial_count = Column(Integer, default=0)
    unresolved_count = Column(Integer, default=0)
    promoted_to_next_month = Column(Integer, default=0)  # 滚入下月数
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class TaskQuotaDrop(BusinessBase, BaseFields):
    """F3: 任务配额丢弃记录（被阀门拦截的任务写入此表，便于审计与回溯）"""
    __tablename__ = "task_quota_drops"
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(256), nullable=False)
    task_type = Column(String(32), default="general")
    priority = Column(String(16), default="medium")
    related_type = Column(String(64), nullable=True)
    related_id = Column(Integer, nullable=True)
    drop_reason = Column(String(64), nullable=False)  # daily_quota_exceeded / active_quota_exceeded
    drop_strategy = Column(String(64), default="priority_then_due")
    source_project = Column(String(64), nullable=True)
    payload_json = Column(Text, nullable=True)  # 原始任务数据 JSON，便于追溯


class Approval(BusinessBase, BaseFields):
    """审批"""
    __tablename__ = "approvals"
    title = Column(String(256), nullable=False)
    approval_type = Column(String(32), default="general")  # visit_plan/expense/leave/sample
    status = Column(String(32), default="pending")  # pending/approved/rejected
    applicant_id = Column(Integer, nullable=False, index=True)
    approver_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    related_type = Column(String(64), nullable=True)
    related_id = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)
    # ──────────────────────────────────────────────
    # F1 审批流 SLA 字段（借鉴企业级诊断体系 §7.3-7.4）
    # ──────────────────────────────────────────────
    submitted_at = Column(DateTime, nullable=True)        # SLA 起算时间（默认 = created_at）
    sla_hours = Column(Integer, default=48)                # SLA 时长（小时）；normal=48, red=168, black=48
    reminder_count = Column(Integer, default=0)           # 已发送提醒次数
    escalation_level = Column(Integer, default=0)         # 升级层级（0/1/2）
    escalated_to = Column(Integer, nullable=True)          # 升级到的审批人 user_id
    auto_approved = Column(Integer, default=0)             # 是否默认同意（0/1）
    reject_count = Column(Integer, default=0)              # 打回次数（打回时 submitted_at 重置）


class Announcement(BusinessBase, BaseFields):
    """公告"""
    __tablename__ = "announcements"
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    ann_type = Column(String(32), default="info")  # info/warning/urgent
    publisher_id = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)
    is_pinned = Column(Integer, default=0)
    view_count = Column(Integer, default=0)


# ──────────────────────────────────────────────
# 知识库表（psp.db）
# ──────────────────────────────────────────────

class KnowledgeDocument(BusinessBase, BaseFields):
    """知识文档"""
    __tablename__ = "knowledge_documents"
    title = Column(String(256), nullable=False)
    category = Column(String(64), nullable=True)  # product/clinical/compliance/sales/other
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    tags = Column(String(512), nullable=True)  # 逗号分隔
    author_id = Column(Integer, nullable=True)
    author_name = Column(String(64), nullable=True)
    view_count = Column(Integer, default=0)
    is_published = Column(Integer, default=1)


class FaqItem(BusinessBase, BaseFields):
    """常见问题"""
    __tablename__ = "faq_items"
    question = Column(String(512), nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(64), nullable=True)  # product/clinical/compliance/sales/other
    sort_order = Column(Integer, default=0)
    view_count = Column(Integer, default=0)


# ──────────────────────────────────────────────
# F7: 知识蒸馏 + 人审发布（借鉴诊断体系 §8.1-8.3）
# ──────────────────────────────────────────────

class KnowledgeItem(BusinessBase, BaseFields):
    """F7: 知识蒸馏项

    AI 蒸馏产生的候选知识项，经人审后发布为正式知识。
    沉淀对象：rule/case/experience/discussion/trend。
    知识分层：enterprise/domain/org/position/compliance。
    """
    __tablename__ = "knowledge_items"
    title = Column(String(256), nullable=False)
    category = Column(String(32), nullable=False, index=True)  # rule/case/experience/discussion/trend
    knowledge_space = Column(String(32), default="domain")  # enterprise/domain/org/position/compliance
    # 蒸馏内容
    applicable_scene = Column(Text, nullable=True)  # 适用场景
    preconditions = Column(JSON, default=list)  # 前置条件
    root_cause_tags = Column(JSON, default=list)  # 根因标签
    action_steps = Column(JSON, default=list)  # 执行步骤
    target_metrics = Column(JSON, default=list)  # 目标指标
    observation_period_days = Column(Integer, default=30)  # 观察周期
    evidence_json = Column(JSON, default=list)  # 证据（来源案例 task_id 列表）
    # 人审与发布
    status = Column(String(16), default="candidate", index=True)  # candidate/approved/published/rejected/retired
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    # 有效性评分
    validity_score = Column(Float, default=0.0)  # 0-1
    success_samples = Column(Integer, default=0)
    failure_samples = Column(Integer, default=0)
    # 来源
    source_cases_json = Column(JSON, default=list)  # 来源闭环案例 task_id 列表
    distilled_by = Column(String(32), default="ai")  # ai/human
    distilled_at = Column(DateTime, default=datetime.utcnow)
    # 权限：继承来源案例的最高敏感级
    sensitivity_level = Column(String(16), default="normal")  # normal/sensitive/confidential


class KnowledgeReview(BusinessBase, BaseFields):
    """F7: 知识人审记录"""
    __tablename__ = "knowledge_reviews"
    item_id = Column(Integer, nullable=False, index=True)
    reviewer_id = Column(Integer, nullable=False)
    decision = Column(String(16), nullable=False)  # approve/reject/request_revision/publish
    comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# 业务应用表（psp.db）
# ──────────────────────────────────────────────

class Meeting(BusinessBase, BaseFields):
    """会议/活动"""
    __tablename__ = "meetings"
    title = Column(String(256), nullable=False)
    meeting_type = Column(String(32), default="academic")  # academic/conference/product_launch/department
    status = Column(String(32), default="planned")  # planned/ongoing/completed/cancelled
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    location = Column(String(256), nullable=True)
    organizer_id = Column(Integer, nullable=True)
    attendees_count = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    product_id = Column(Integer, nullable=True)
    hospital_id = Column(Integer, nullable=True)


class ForumTopic(BusinessBase, BaseFields):
    """论坛话题"""
    __tablename__ = "forum_topics"
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=True)
    category = Column(String(64), nullable=True)  # clinical/sales/compliance/product/general
    author_id = Column(Integer, nullable=False)
    author_name = Column(String(64), nullable=True)
    views = Column(Integer, default=0)
    replies_count = Column(Integer, default=0)
    is_pinned = Column(Integer, default=0)
    last_reply_at = Column(DateTime, nullable=True)


class AIInsightCache(BusinessBase, BaseFields):
    """AI 洞察缓存表 - 定时预生成的领域洞察

    每个 (tenant_id, user_id, domain) 每天生成一条记录，
    /ai-insights 端点直接查询此表，避免实时调用 LLM。
    """
    __tablename__ = "ai_insight_cache"
    domain = Column(String(32), nullable=False)  # sales/training/decision/collab/knowledge/...
    user_id = Column(Integer, nullable=True)  # NULL 表示租户级洞察
    insight_date = Column(Date, nullable=False)  # 洞察日期（每天一条）
    summary = Column(Text, nullable=True)  # 一句话摘要
    insights_json = Column(Text, nullable=True)  # JSON: [{type, level, message}]
    recommendations_json = Column(Text, nullable=True)  # JSON: ["建议1", "建议2"]
    risk_alerts_json = Column(Text, nullable=True)  # JSON: [{...}]
    generated_by = Column(String(32), default="preset")  # preset/llm
    generation_ms = Column(Integer, default=0)  # 生成耗时（毫秒）
    # N+3 Step3：历史周期时间游标，NULL 表示当期，非 NULL 表示按历史截止点重算
    period_end = Column(Date, nullable=True)
    # ──────────────────────────────────────────────
    # F2 AI 输出结构化 Schema 字段（借鉴企业级诊断体系 §4.1、§11.4）
    # ──────────────────────────────────────────────
    evidence_json = Column(Text, nullable=True)              # 证据 JSON（事实证据数组）
    provenance_json = Column(Text, nullable=True)            # 血缘 JSON（run_id/model_version/data_cutoff/rule_versions）
    trace_id = Column(String(64), nullable=True, index=True)  # 追踪 ID（UUID）
    confidence = Column(Float, default=0.0)                   # 整体置信度 0-1
    human_review_required = Column(Integer, default=0)        # 是否需人审（0/1）

    __table_args__ = (
        Index("idx_insight_lookup", "tenant_id", "domain", "user_id", "insight_date", "period_end"),
    )


# ──────────────────────────────────────────────
# F4 绩效边界配置表（借鉴企业级诊断体系 §10.3、附录 A.D.23-24）
#   原则：绩效联动只记录可控流程行为（逾期、拒不反馈等），不因灯色本身自动扣分/PIP/淘汰
# ──────────────────────────────────────────────

class PerformancePolicy(BusinessBase, BaseFields):
    """绩效边界策略

    表化策略，可通过 API 动态调整，无需重启。
    action_type 枚举：
      - visit_overdue / feedback_refused / plan_not_submitted / approval_overdue（可控行为）
      - light_color_change / business_result_not_achieved / ai_auto_judgment / rule_violation（不可控）
    """
    __tablename__ = "performance_policies"
    action_type = Column(String(64), nullable=False, unique=True, index=True)
    allow_link_performance = Column(Integer, default=0)  # 0=禁止联动绩效，1=允许
    description = Column(String(256), nullable=True)
    updated_by = Column(Integer, nullable=True)


# ──────────────────────────────────────────────
# F6 数据质量门禁表（借鉴企业级诊断体系 §5.5）
#   完整度 <60% 数据断点 / 三档降级（pass/delay/partial_cancel/cancel）
# ──────────────────────────────────────────────

class DataQualityGate(BusinessBase, BaseFields):
    """数据质量门禁配置

    每个域（sales/training/decision/compliance）配置一个门禁，
    在 AI 洞察生成前校验完整度，决定是否生成 / 延期 / 取消。
    """
    __tablename__ = "data_quality_gates"
    domain = Column(String(32), nullable=False, unique=True, index=True)
    completeness_threshold = Column(Float, default=0.60)  # 完整度阈值，低于此值判定为数据断点
    timeliness_delay_days = Column(Integer, default=3)  # 允许延期天数
    timeliness_partial_days = Column(Integer, default=7)  # 部分取消天数阈值
    timeliness_cancel_days = Column(Integer, default=7)  # 完全取消天数阈值
    enabled = Column(Integer, default=1, index=True)
    last_check_at = Column(DateTime, nullable=True)
    last_completeness = Column(Float, nullable=True)
    last_decision = Column(String(32), nullable=True)  # pass/delay/partial_cancel/cancel


# ──────────────────────────────────────────────
# F5 规则版本化表（借鉴企业级诊断体系 §6.5、§7.4）
#   草稿→影子运行→灰度→正式→回滚 完整生命周期
# ──────────────────────────────────────────────

class RuleVersionHistory(BusinessBase, BaseFields):
    """F5: 规则版本变更历史

    每次发布/影子/提升/回滚都记一条，支持历史回放与审计。
    snapshot_json 保存当时规则的完整字段，diff_json 记录与上一版本的差异。
    """
    __tablename__ = "rule_version_histories"
    rule_code = Column(String(32), nullable=False, index=True)
    rule_id = Column(Integer, nullable=False, index=True)  # 当时版本的 rule.id
    version = Column(String(16), nullable=False)
    action = Column(String(16), nullable=False)  # created/published/shadow/promoted/retired/rollback
    snapshot_json = Column(JSON, default=dict)  # 当时规则的完整字段快照
    diff_json = Column(JSON, default=dict)  # 与上一版本的差异
    actor_id = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class RuleShadowRun(BusinessBase, BaseFields):
    """F5: 影子运行结果

    新版本不生产生效，仅记录命中结果，对比基准版本统计差异。
    异步执行：通过 insight_scheduler 每分钟推进 100 条事件。
    """
    __tablename__ = "rule_shadow_runs"
    rule_code = Column(String(32), nullable=False, index=True)
    new_rule_id = Column(Integer, nullable=False)
    baseline_rule_id = Column(Integer, nullable=False)  # 对比基准（当前 published 版本）
    status = Column(String(16), default="running")  # running/completed/failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    matched_count = Column(Integer, default=0)  # 新版本命中数
    baseline_count = Column(Integer, default=0)  # 基准命中数
    delta_count = Column(Integer, default=0)  # 差异
    sample_events_json = Column(JSON, default=list)  # 抽样事件对比（最多 50 条）
    summary = Column(Text, nullable=True)


# ──────────────────────────────────────────────
# Ontology 表（psp_ontology.db）
# ──────────────────────────────────────────────

class ObjectDefinition(OntologyBase):
    __tablename__ = "object_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(128), nullable=False)
    domain = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    schema = Column(JSON, default=dict)
    is_active = Column(Integer, default=1)
    # 本体 DB 化：租户级覆盖层。NULL = 全局基线（所有租户继承）
    tenant_id = Column(String(64), nullable=True, index=True)
    # 声明顺序，保证从 DB 加载后与 seed 常量顺序一致（前端展示依赖顺序稳定）
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class LinkDefinition(OntologyBase):
    __tablename__ = "link_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    display_name = Column(String(128), nullable=False)
    source_object = Column(String(64), nullable=False)
    target_object = Column(String(64), nullable=False)
    cardinality = Column(String(32), default="1:N")
    description = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)
    tenant_id = Column(String(64), nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActionDefinition(OntologyBase):
    __tablename__ = "action_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(128), nullable=False)
    # domain 是 list_actions(domain=...) 的过滤依据，此前缺列导致 DB 无法无损回放常量
    domain = Column(String(64), nullable=True)
    input_schema = Column(JSON, default=dict)
    output_schema = Column(JSON, default=dict)
    risk_level = Column(String(4), default="L1")  # L1-L4
    permission_required = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)
    tenant_id = Column(String(64), nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActionExecution(OntologyBase):
    __tablename__ = "action_executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    action_name = Column(String(64), nullable=False)
    input = Column(JSON, default=dict)
    output = Column(JSON, default=dict)
    status = Column(String(16), default="ok")
    executed_by = Column(Integer, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RolePermissionDefinition(OntologyBase):
    """RBAC 角色权限矩阵（原 ontology/permissions.py 的 ROLE_PERMISSIONS 硬编码）

    与本体同源问题：权限矩阵此前只能改代码 + 重启。迁入元数据表后可按租户覆盖。
    tenant_id 为 NULL 表示全局基线；同一 (tenant_id, role) 的多行构成该角色权限集。
    """
    __tablename__ = "role_permission_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(64), nullable=False, index=True)
    permission = Column(String(128), nullable=False)
    tenant_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        Index("uniq_role_perm_tenant", "role", "permission", "tenant_id", unique=True),
    )


class ObjectPermissionDefinition(OntologyBase):
    """OBAC Object 级权限声明（原 OBJECT_PERMISSIONS 硬编码）

    每行表示「role 对 object_name 拥有 access 权限」。
    """
    __tablename__ = "object_permission_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    object_name = Column(String(64), nullable=False, index=True)
    access = Column(String(32), nullable=False)  # read/write/approve/delete...
    role = Column(String(64), nullable=False)
    tenant_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        Index("uniq_obj_perm_tenant", "object_name", "access", "role", "tenant_id",
              unique=True),
    )


class RoleDefinition(OntologyBase):
    """角色展示信息（原 ROLE_DEFINITIONS 硬编码）"""
    __tablename__ = "role_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        Index("uniq_role_def_tenant", "code", "tenant_id", unique=True),
    )


class OntologyChangeLog(OntologyBase):
    __tablename__ = "ontology_change_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(Integer, nullable=False)
    change_type = Column(String(16), nullable=False)
    before = Column(JSON, default=dict)
    after = Column(JSON, default=dict)
    changed_by = Column(Integer, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OntologyAiAccess(OntologyBase):
    __tablename__ = "ontology_ai_access"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(64), nullable=False)
    object_name = Column(String(64), nullable=False)
    access_level = Column(String(16), default="read")


class AiConversationLog(OntologyBase):
    __tablename__ = "ai_conversation_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=True)
    user_id = Column(Integer, nullable=True)
    agent_name = Column(String(64), nullable=True)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    actions_called = Column(JSON, default=list)
    references = Column(JSON, default=list)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)


# ──────────────────────────────────────────────
# 数据采集域表（psp.db）
# ──────────────────────────────────────────────

class CollectionProject(BusinessBase, BaseFields):
    """数据采集项目"""
    __tablename__ = "collection_projects"
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    project_type = Column(String(32), default="plan")  # plan/survey/profile
    period_type = Column(String(16), default="monthly")  # daily/weekly/monthly/quarterly/yearly/once
    status = Column(String(16), default="draft", index=True)  # draft/active/paused/completed
    zone_ids = Column(JSON, default=list)  # 目标区划 ID 列表
    template_id = Column(Integer, nullable=True)
    related_project_id = Column(Integer, nullable=True)  # 关联项目（结果填报→目标规划）
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)


class CollectionTemplate(BusinessBase, BaseFields):
    """数据采集模板"""
    __tablename__ = "collection_templates"
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    fields = Column(JSON, default=list)  # [{key, label, type, required, options, default, min, max}]
    version = Column(Integer, default=1)
    is_active = Column(Integer, default=1)
    # N+4 Batch 2.2: 规则引擎扩展字段
    rules_json = Column(JSON, default=dict)  # {derived_fields:[], cross_field_rules:[], ability_impact:[]}


class CollectionItem(BusinessBase, BaseFields):
    """数据项"""
    __tablename__ = "collection_items"
    project_id = Column(Integer, nullable=False, index=True)
    template_id = Column(Integer, nullable=True)
    zone_id = Column(Integer, nullable=True, index=True)
    period_code = Column(String(32), nullable=True)  # 2026-07 / 2026-W28 / 2026-Q3
    submitter_id = Column(Integer, nullable=True)
    reviewer_id = Column(Integer, nullable=True)
    status = Column(String(16), default="pending_edit", index=True)
    # pending_edit → edited → pending_review → reviewed → locked → published
    values = Column(JSON, default=dict)  # {field_key: value}
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)


class ProjectTodo(BusinessBase, BaseFields):
    """项目待办任务"""
    __tablename__ = "project_todos"
    project_id = Column(Integer, nullable=False, index=True)
    item_id = Column(Integer, nullable=True, index=True)  # 关联 CollectionItem
    zone_id = Column(Integer, nullable=True)
    assignee_id = Column(Integer, nullable=False, index=True)
    period_code = Column(String(32), nullable=True)
    status = Column(String(16), default="pending", index=True)  # pending/completed/expired
    edit_mode = Column(String(16), default="grid_edit")  # ai_dialog/grid_edit
    dialog_session_id = Column(Integer, nullable=True)  # 关联 ChatSession
    submitted_at = Column(DateTime, nullable=True)
    submit_data = Column(JSON, default=dict)


# ──────────────────────────────────────────────
# 培训活动域表（psp.db）
# ──────────────────────────────────────────────

class TrainingActivity(BusinessBase, BaseFields):
    """培训活动"""
    __tablename__ = "training_activities"
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(16), default="draft", index=True)  # draft/ongoing/ended/off_shelf
    domain = Column(String(64), nullable=True)  # 业务域
    product_id = Column(Integer, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    visible_scope = Column(JSON, default=dict)  # {zones: [], roles: []}
    open_practice = Column(Integer, default=1)  # 是否开放练习模式
    open_train = Column(Integer, default=1)  # 是否开放训战模式
    pass_score = Column(Integer, default=60)
    created_by = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)
    off_shelf_at = Column(DateTime, nullable=True)


class ActivityScenarioRel(BusinessBase, BaseFields):
    """活动-场景关联表"""
    __tablename__ = "activity_scenario_rels"
    activity_id = Column(Integer, nullable=False, index=True)
    scenario_id = Column(Integer, nullable=False, index=True)
    sort_order = Column(Integer, default=0)

    __table_args__ = (
        Index("uniq_activity_scenario", "activity_id", "scenario_id", unique=True),
    )


class ExperiencePoint(BusinessBase, BaseFields):
    """经验值记录"""
    __tablename__ = "experience_points"
    user_id = Column(Integer, nullable=False, index=True)
    scenario_id = Column(Integer, nullable=True)
    activity_id = Column(Integer, nullable=True, index=True)
    points = Column(Integer, default=0)
    source = Column(String(16), default="train")  # train/practice（仅 train 累计）
    earned_at = Column(DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# 通知中心域表（psp.db）
# ──────────────────────────────────────────────

class NotificationRule(BusinessBase, BaseFields):
    """通知催促规则"""
    __tablename__ = "notification_rules"
    activity_id = Column(Integer, nullable=True, index=True)
    scenario_id = Column(Integer, nullable=True)
    rule_name = Column(String(128), nullable=False)
    deadline = Column(DateTime, nullable=True)  # 截止时间
    windows = Column(JSON, default=list)  # ["D-3", "D-2", "D-1"]
    frequency = Column(String(16), default="daily")  # daily/hourly
    send_times = Column(JSON, default=list)  # ["10:00", "16:00"]
    channel = Column(String(32), default="in_app")  # in_app/ding_talk/email
    target_user_type = Column(String(32), default="all")  # all/not_completed
    enabled = Column(Integer, default=1, index=True)


class NotificationBatch(BusinessBase, BaseFields):
    """通知发送批次"""
    __tablename__ = "notification_batches"
    rule_id = Column(Integer, nullable=False, index=True)
    trigger_at = Column(DateTime, nullable=False)
    window = Column(String(16), nullable=True)  # D-3/D-2/D-1
    target_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    message_title = Column(String(256), nullable=True)
    message_body = Column(Text, nullable=True)


class NotificationRecipient(BusinessBase, BaseFields):
    """通知接收人记录"""
    __tablename__ = "notification_recipients"
    batch_id = Column(Integer, nullable=False, index=True)
    learner_id = Column(Integer, nullable=False, index=True)
    status = Column(String(16), default="pending")  # pending/sent/failed
    reason = Column(Text, nullable=True)  # 失败原因
    sent_at = Column(DateTime, nullable=True)


# ──────────────────────────────────────────────
# 合规管理表（v2.1 合规适配，对应《医药代表管理办法》）
# ──────────────────────────────────────────────

class PharmaRepProfile(BusinessBase, BaseFields):
    """医药代表资质档案

    对应《医药代表管理办法》第三章备案管理（第 14-18 条）：
    - 第 15 条备案信息 8 项内容
    - 第 16 条唯一备案号
    - 第 17 条 30 日变更/删除时效
    """
    __tablename__ = "pharma_rep_profiles"
    user_id = Column(Integer, nullable=False, index=True)  # 关联 users.id
    # 第 15 条第（三）项：身份信息
    id_card_type = Column(String(16), nullable=True)  # 身份证件种类
    id_card_no = Column(String(64), nullable=True)  # 身份证件号码
    gender = Column(String(8), nullable=True)  # 性别
    photo_url = Column(String(512), nullable=True)  # 照片 URL
    # 第 15 条第（三）项：学历与专业
    education_level = Column(String(16), nullable=True)  # 学历（大专/本科/硕士/博士）
    major = Column(String(64), nullable=True)  # 所学专业（医学/药学/相关专业）
    # 第 15 条第（四）项：劳动合同/授权书起止日期
    contract_start = Column(Date, nullable=True)
    contract_end = Column(Date, nullable=True)
    # 第 15 条第（五）项：推广药品类别和治疗领域
    drug_categories = Column(JSON, default=list)  # ["心血管", "抗肿瘤", ...]
    therapeutic_areas = Column(JSON, default=list)  # ["肿瘤科", "心内科", ...]
    # 第 15 条第（六）项：推广区域
    authorized_regions = Column(JSON, default=list)  # ["北京市", "上海市", ...]
    # 第 15 条第（七）项：真实性声明
    authenticity_statement = Column(Text, nullable=True)  # 持有人真实性声明文本
    statement_signed_at = Column(DateTime, nullable=True)
    # 第 15 条第（八）项：合规承诺书签署（关联 compliance_commitments.id）
    commitment_id = Column(Integer, nullable=True)
    # 第 16 条：全国统一备案号
    registration_no = Column(String(64), nullable=True, unique=True, index=True)
    registration_status = Column(String(16), default="draft", index=True)  # draft/submitted/confirmed/revoked/deleted
    registered_at = Column(DateTime, nullable=True)
    # 第 17 条：30 日变更/删除时效
    last_change_at = Column(DateTime, nullable=True)  # 最后一次备案变更时间
    revoke_scheduled_at = Column(DateTime, nullable=True)  # 计划删除时间（停止授权 30 日内）
    # 商业贿赂记录（第 11 条第（一）项核查）
    has_bribery_record = Column(Integer, default=0, index=True)
    bribery_record_detail = Column(Text, nullable=True)


class ComplianceCommitment(BusinessBase, BaseFields):
    """合规承诺书签署记录

    对应《医药代表管理办法》第 9、10 条培训考核 + 第 15 条第（八）项合规承诺书：
    - 培训-考核-承诺闭环
    - 医药代表上岗前必须完成三件套：合规培训 + 考核合格 + 承诺书签署
    """
    __tablename__ = "compliance_commitments"
    user_id = Column(Integer, nullable=False, index=True)  # 签署人（医药代表）
    commitment_type = Column(String(32), nullable=False, index=True)  # onboarding(上岗)/annual(年度)/specific(专项)
    # 关联的合规培训
    course_id = Column(Integer, nullable=True)  # 关联 Course.id（is_compliance=1）
    exam_record_id = Column(Integer, nullable=True)  # 关联 ExamRecord.id（考核合格证明）
    # 承诺书内容
    commitment_text = Column(Text, nullable=True)  # 承诺书正文
    version = Column(String(16), nullable=True)  # 承诺书版本号
    # 签署信息
    signed_at = Column(DateTime, nullable=True)  # 签署时间
    signer_ip = Column(String(64), nullable=True)  # 签署 IP
    signer_ua = Column(String(256), nullable=True)  # 签署 User-Agent
    # 不可篡改存证
    signature_hash = Column(String(64), nullable=True, index=True)  # 承诺书内容+签署时间+用户ID 的 SHA-256
    audit_log_id = Column(Integer, nullable=True)  # 关联 AuditLog.id（链式证据）
    # 状态
    status = Column(String(16), default="pending", index=True)  # pending/signed/revoked/expired
    expires_at = Column(DateTime, nullable=True)  # 过期时间（如年度承诺书）


# ──────────────────────────────────────────────
# v2.2 Phase 2 合规体系扩展（《医药代表管理办法》中等合规）
# ──────────────────────────────────────────────

class PartnerOrganization(BusinessBase, BaseFields):
    """CSO 委托合作机构 / 专业组织实体

    对应《医药代表管理办法》第 8 条 CSO 委托管理 + 第 12 条 CSO 4 项禁止行为。
    持有人可委托 CSO 进行医药代表管理，但需签订管理协议 + 授权书。
    """
    __tablename__ = "partner_organizations"
    name = Column(String(128), nullable=False)  # 机构名称
    org_code = Column(String(64), nullable=True, index=True)  # 统一社会信用代码
    org_type = Column(String(32), default="cso")  # cso/professional_org/other
    legal_person = Column(String(64), nullable=True)  # 法定代表人
    contact_name = Column(String(64), nullable=True)  # 联系人
    contact_phone = Column(String(32), nullable=True)
    contact_email = Column(String(128), nullable=True)
    address = Column(String(256), nullable=True)
    # 资质
    business_license_url = Column(String(512), nullable=True)  # 营业执照
    medical_license_url = Column(String(512), nullable=True)  # 药品经营许可证
    # 状态
    status = Column(String(16), default="pending", index=True)  # pending/active/suspended/terminated
    activated_at = Column(DateTime, nullable=True)
    terminated_at = Column(DateTime, nullable=True)
    # 信用评级（Phase 3 扩展）
    credit_score = Column(Integer, default=100)
    is_blacklisted = Column(Integer, default=0, index=True)


class ManagementAgreement(BusinessBase, BaseFields):
    """医药代表管理协议（持有人与 CSO 之间）

    对应《医药代表管理办法》第 8 条：委托 CSO 时需签订医药代表管理协议。
    """
    __tablename__ = "management_agreements"
    partner_org_id = Column(Integer, nullable=False, index=True)  # 关联 PartnerOrganization.id
    agreement_no = Column(String(64), nullable=True, index=True)  # 协议编号
    title = Column(String(256), nullable=True)
    # 协议期限
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    # 协议范围
    authorized_regions = Column(JSON, default=list)  # 授权区域列表
    authorized_drug_categories = Column(JSON, default=list)  # 授权药品类别
    authorized_therapeutic_areas = Column(JSON, default=list)  # 授权治疗领域
    # 协议文件
    agreement_file_url = Column(String(512), nullable=True)  # 协议正本
    supplementary_files = Column(JSON, default=list)  # 补充协议列表
    # 状态
    status = Column(String(16), default="draft", index=True)  # draft/active/expired/terminated
    signed_at = Column(DateTime, nullable=True)
    # 签署方
    signer_holder = Column(String(64), nullable=True)  # 持有人签署人
    signer_partner = Column(String(64), nullable=True)  # CSO 签署人


class AuthorizationLetter(BusinessBase, BaseFields):
    """医药代表授权书

    对应《医药代表管理办法》第 8 条：CSO 委托时需向医药代表出具授权书。
    授权书须明确授权范围、区域、药品类别、有效期。
    """
    __tablename__ = "authorization_letters"
    user_id = Column(Integer, nullable=False, index=True)  # 被授权的医药代表 user_id
    partner_org_id = Column(Integer, nullable=True, index=True)  # 关联 CSO（直营时为空）
    agreement_id = Column(Integer, nullable=True)  # 关联 ManagementAgreement.id
    letter_no = Column(String(64), nullable=True, index=True)  # 授权书编号
    # 授权范围
    authorized_regions = Column(JSON, default=list)
    authorized_drug_categories = Column(JSON, default=list)
    authorized_therapeutic_areas = Column(JSON, default=list)
    # 授权期限
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    # 文件
    letter_file_url = Column(String(512), nullable=True)
    # 状态
    status = Column(String(16), default="draft", index=True)  # draft/active/expired/revoked
    issued_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoke_reason = Column(Text, nullable=True)


class ComplianceViolationRule(BusinessBase, BaseFields):
    """22 项禁止行为规则配置

    对应《医药代表管理办法》第 11 条持有人 4 项 + 第 12 条 CSO 4 项 +
    第 24 条医药代表 9 项 + 第 25 条医疗机构 5 项 = 共 22 项禁止行为。
    规则引擎在关键节点（学术活动立项/签到/费用核销）触发运行时校验。

    F5 增强（借鉴诊断体系 §6.5、§7.4）：
    - 语义版本号 version + 生效区间 effective_start/end
    - 发布状态 release_state（draft/shadow/grayscale/published/retired）
    - 父版本链 parent_rule_id（用于版本演进追溯）
    - 不允许就地修改，新版本必须经过 草稿→影子运行→正式 流程
    """
    __tablename__ = "compliance_violation_rules"
    code = Column(String(32), nullable=False, index=True)  # 如 A11_1 / A24_3（F5: 去除 unique，允许多版本共存）
    article = Column(String(32), nullable=False)  # 第 11 条 / 第 24 条
    subject = Column(String(32), nullable=False)  # 持有人 / CSO / 医药代表 / 医疗机构
    description = Column(Text, nullable=False)  # 禁止行为描述
    severity = Column(String(16), default="high")  # low/medium/high/critical
    # 触发场景
    trigger_scenes = Column(JSON, default=list)  # 触发场景标签：academic_activity.create / visit_record.submit / expense.submit
    # 检查逻辑
    check_type = Column(String(32), nullable=True)  # keyword/role_blacklist/amount_limit/forbidden_action
    check_config = Column(JSON, default=dict)  # 检查参数（如禁词列表、金额阈值、角色黑名单）
    # 是否启用
    is_active = Column(Integer, default=1, index=True)
    # ──────────────────────────────────────────────
    # F5: 版本化字段（借鉴诊断体系 §6.5、§7.4）
    # ──────────────────────────────────────────────
    version = Column(String(16), default="1.0.0")  # 语义版本号
    effective_start = Column(Date, nullable=True)  # 生效起始日（默认 = created_at）
    effective_end = Column(Date, nullable=True)  # 生效结束日（NULL = 长期有效）
    release_state = Column(String(16), default="published")  # draft/shadow/grayscale/published/retired
    parent_rule_id = Column(Integer, nullable=True)  # 父规则 ID（新版本指向旧版本）

    __table_args__ = (
        Index("uniq_rule_code_version_tenant", "code", "version", "tenant_id", unique=True),
    )


class ComplianceViolationEvent(BusinessBase, BaseFields):
    """违规事件记录

    当 ComplianceViolationRule 被触发时记录违规事件，关联到具体业务实体（学术活动/拜访记录/费用）。
    """
    __tablename__ = "compliance_violation_events"
    rule_code = Column(String(32), nullable=False, index=True)  # 关联 ComplianceViolationRule.code
    rule_article = Column(String(32), nullable=True)
    rule_subject = Column(String(32), nullable=True)
    severity = Column(String(16), default="high", index=True)
    # 违规对象
    actor_id = Column(Integer, nullable=True, index=True)  # 违规主体 user_id
    actor_role = Column(String(32), nullable=True)
    # 业务实体
    entity_type = Column(String(32), nullable=True)  # academic_activity / visit_record / expense / commitment
    entity_id = Column(Integer, nullable=True)
    # 详情
    description = Column(Text, nullable=True)
    evidence_payload = Column(JSON, default=dict)  # 证据快照（触发时的上下文）
    # 处置
    status = Column(String(16), default="open", index=True)  # open/investigating/resolved/dismissed
    handled_by = Column(Integer, nullable=True)  # 处理人 user_id
    handled_at = Column(DateTime, nullable=True)
    handling_result = Column(Text, nullable=True)
    # 关联合规预警
    alert_id = Column(Integer, nullable=True)


class AcademicActivity(BusinessBase, BaseFields):
    """学术推广活动主表

    对应《医药代表管理办法》第 19-22 条学术推广活动管理 + 第 21 条传递信息/协助合理用药/收集反馈。
    全生命周期：立项→审批→协议→签到→费用→反馈→归档
    """
    __tablename__ = "academic_activities"
    title = Column(String(256), nullable=False)
    activity_type = Column(String(32), nullable=False, index=True)  # conference/lecture/ward_round/academic_meeting
    # 主办/承办方
    organizer_id = Column(Integer, nullable=True)  # 主办方 PartnerOrganization.id 或持有人 id
    co_organizers = Column(JSON, default=list)  # 承办方列表
    # 时间地点
    planned_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    location = Column(String(256), nullable=True)
    province = Column(String(32), nullable=True, index=True)
    city = Column(String(32), nullable=True)
    # 参与对象
    target_audience = Column(String(64), nullable=True)  # 医生/药师/学员
    expected_attendees = Column(Integer, default=0)
    actual_attendees = Column(Integer, default=0)
    # 关联实体
    pharma_rep_user_id = Column(Integer, nullable=True, index=True)  # 主办医药代表
    partner_org_id = Column(Integer, nullable=True, index=True)  # 关联 CSO
    agreement_id = Column(Integer, nullable=True)  # 关联管理协议
    authorization_letter_id = Column(Integer, nullable=True)  # 关联授权书
    # 关联业务
    meeting_id = Column(Integer, nullable=True)  # 关联 Meeting.id
    approval_id = Column(Integer, nullable=True)  # 关联 Approval.id
    # 内容
    product_ids = Column(JSON, default=list)  # 涉及药品列表
    therapeutic_areas = Column(JSON, default=list)
    agenda = Column(JSON, default=list)  # 议程
    materials = Column(JSON, default=list)  # 会议材料文件列表
    # 证据链（三流合一）
    meeting_protocol = Column(JSON, default=dict)  # 会议协议子表（协议编号/签署方/扫描件）
    checkin_evidence = Column(JSON, default=list)  # 现场签到证据列表（签到人/时间/定位/照片）
    expense_vouchers = Column(JSON, default=list)  # 费用凭证列表（金额/类型/发票号/扫描件）
    # 反馈
    adverse_reaction_reported = Column(JSON, default=list)  # 不良反应反馈记录（第 21 条第（三）项）
    feedback_summary = Column(Text, nullable=True)
    # 状态
    status = Column(String(16), default="draft", index=True)  # draft/pending_approval/approved/ongoing/completed/archived/cancelled
    current_step = Column(String(32), nullable=True)  # 工作流当前步骤
    gates_passed = Column(JSON, default=list)  # 已通过的门禁列表
    # 合规校验
    onboarding_checked = Column(Integer, default=0)  # 是否已通过上岗三件套校验
    violation_count = Column(Integer, default=0)
    # 财务
    total_expense = Column(Integer, default=0)  # 总费用（分）


class ComplianceAlert(BusinessBase, BaseFields):
    """合规预警

    合规预警源：违规事件触发 / 30 日时效到期 / 备案信息异常。
    decision_service 集成查询，前端预警中心展示。
    """
    __tablename__ = "compliance_alerts"
    alert_type = Column(String(32), nullable=False, index=True)  # violation/deadline/expiry/anomaly
    severity = Column(String(16), default="medium", index=True)  # low/medium/high/critical
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    # 关联对象
    actor_id = Column(Integer, nullable=True, index=True)
    actor_role = Column(String(32), nullable=True)
    entity_type = Column(String(32), nullable=True)
    entity_id = Column(Integer, nullable=True)
    rule_code = Column(String(32), nullable=True, index=True)  # 违规预警时关联规则
    violation_event_id = Column(Integer, nullable=True, index=True)
    # 30 日时效
    deadline_at = Column(DateTime, nullable=True, index=True)  # 截止时间
    days_remaining = Column(Integer, nullable=True)
    # 处置
    status = Column(String(16), default="open", index=True)  # open/acknowledged/dismissed/resolved
    handled_by = Column(Integer, nullable=True)
    handled_at = Column(DateTime, nullable=True)
    handling_result = Column(Text, nullable=True)
    # 是否合规关键
    is_compliance_critical = Column(Integer, default=0, index=True)


# ──────────────────────────────────────────────
# 迁移表
# ──────────────────────────────────────────────

class MigrationLog(BusinessBase):
    __tablename__ = "_migration_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    migration_name = Column(String(128), unique=True, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(Text, nullable=True)


# ──────────────────────────────────────────────
# Phase 3 合规专项表（公示 / 监管报送 / 年度审计）
# 对应《医药代表管理办法》第 13 条（备案信息公示）、
# 第 26 条（监管报送与全过程留痕）、企业年度合规审计要求。
# ──────────────────────────────────────────────

class PublicDisclosure(BusinessBase, BaseFields):
    """合规公示：将违规处置结果、备案异常等需对社会/监管公开的信息登记。"""
    __tablename__ = "public_disclosures"
    # 公示类别：violation_disposal（违规处置）/ registration_anomaly（备案异常）/ commitment_breach（承诺违约）
    category = Column(String(32), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    # 关联对象：如 violation_event_id / pharma_rep_profile_id
    ref_type = Column(String(64), nullable=True)
    ref_id = Column(Integer, nullable=True)
    # 公示内容（结构化摘要，避免直接暴露 PII，仅脱敏后展示）
    content = Column(JSON, default=dict)
    disclosed_level = Column(String(16), default="internal", nullable=False)  # internal / public
    published_at = Column(DateTime, nullable=True)  # 实际对外公示时间，NULL=草稿
    expired_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="draft", index=True)  # draft / published / withdrawn
    published_by = Column(Integer, nullable=True)


class RegulatorySubmission(BusinessBase, BaseFields):
    """监管报送记录：向药监/卫健部门报送的合规数据包（按年/季/月维度）。"""
    __tablename__ = "regulatory_submissions"
    period_type = Column(String(16), nullable=False, index=True)  # year / quarter / month
    period_value = Column(String(16), nullable=False, index=True)  # 如 "2026" / "2026-Q2" / "2026-08"
    submission_type = Column(String(32), nullable=False, index=True)  # violation_summary / activity_summary / annual
    # 报送载体：结构化数据（对接外部监管平台格式，这里以 JSON 通用包承载）
    payload = Column(JSON, default=dict)
    format = Column(String(16), default="json", nullable=False)  # json / csv / xml
    status = Column(String(16), default="pending", index=True)  # pending / submitted / accepted / rejected
    submitted_at = Column(DateTime, nullable=True)
    submitted_by = Column(Integer, nullable=True)
    external_ref = Column(String(128), nullable=True)  # 监管平台回执号


class AnnualComplianceAudit(BusinessBase, BaseFields):
    """年度合规审计聚合：基于 AuditLog 证据链 + 违规记录 + 公示 生成的年度审计报告。"""
    __tablename__ = "annual_compliance_audits"
    year = Column(Integer, nullable=False, index=True)
    # 审计范围与结论
    scope = Column(String(256), nullable=True)
    # 聚合指标快照
    metrics = Column(JSON, default=dict)
    # 审计链完整性验证结果（复用 AuditLog 链式哈希）
    chain_integrity = Column(JSON, default=dict)
    conclusion = Column(String(32), default="pending", nullable=False)  # pending / pass / conditional / fail
    audit_by = Column(Integer, nullable=True)
    audited_at = Column(DateTime, nullable=True)
    report_path = Column(String(256), nullable=True)  # 导出报告存储路径（可选）


# ──────────────────────────────────────────────
# 引擎 & Session
# ──────────────────────────────────────────────

from sqlalchemy.pool import QueuePool


def make_engine(backend: str, db_path: str, explicit_url: str = "") -> "Engine":
    """引擎抽象工厂（蓝图片段 3.3）：SQLite(demo) / PostgreSQL(生产) 可切换。

    - backend="sqlite"（默认）：用 db_path 构造文件型引擎，保留 check_same_thread 兼容。
    - backend="postgresql"：用 explicit_url（BUSINESS_DATABASE_URL）构造，启用连接池。
    表结构由 Alembic / create_all 统一管理，与后端类型无关。
    """
    if backend == "postgresql":
        if not explicit_url:
            raise RuntimeError("DB_BACKEND=postgresql 但 BUSINESS_DATABASE_URL 未配置")
        return create_engine(
            explicit_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
    # 默认 sqlite：保留 demo 行为，不破坏现有部署
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )
    # WAL 模式：读写不再互斥（rollback-journal 下写锁会阻塞读，30s 忙等
    # 曾导致 GET 请求卡死）；synchronous=NORMAL 为 WAL 推荐档位。
    # 参考 backend/middleware/logging.py 记录的 31045ms 案例（2026-08）。
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_wal_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
    return engine


business_engine = make_engine(settings.DB_BACKEND, settings.DB_PATH, settings.BUSINESS_DATABASE_URL)

# 第 14 批：业务库与本体库共用同一引擎（同一物理库，单一 Alembic 树，
# 单一启动期 schema 验证）。`OntologySessionLocal` / `get_ontology_db()` 保留
# 别名实现仅为兼容现有调用点，新代码请用 BusinessSessionLocal / get_db()。
ontology_engine = business_engine

BusinessSessionLocal = sessionmaker(bind=business_engine, autoflush=False, expire_on_commit=False)
# 别名 SessionLocal（第 14 批：双库合一，下游 import 用法无需任何改动）
OntologySessionLocal = BusinessSessionLocal


def get_db():
    """业务数据库 session 依赖注入（含本体表，schema 与 business 共用一库）"""
    db = BusinessSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 第 14 批：保留 get_ontology_db 别名实现，与 get_db() 走同一 SessionLocal。
def get_ontology_db():
    """本体数据库 session 依赖注入（已与业务库合一，等价于 get_db()）。"""
    db = BusinessSessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_ontology_to_orm(ontology_db: Session | None = None) -> dict:
    """单一本体源收敛：把 ontology/*.py 的权威常量 upsert 进 Ontology ORM 表

    背景（蓝图片段 1.1 / 1.3）：历史上 ObjectDefinition/LinkDefinition/ActionDefinition
    等 ORM 表是「空壳」（建表但无写入），真正的本体是 ontology/*.py 的 Python 常量。
    本函数让常量为权威源，启动时把其同步进 ORM 表，并写 OntologyChangeLog，使：
      1) 两套存储保持单一事实源（常量驱动 ORM，而非双写）；
      2) 空壳 ORM 表变活，可作为本体变更审计落点（OntologyChangeLog）。
    本函数向后兼容：不改动任何常量或表结构，仅做幂等 upsert + 变更日志。
    """
    # 直接读 seed 常量：本函数是「seed → DB」的写入方向，
    # 不能经 registry（registry 读 DB），否则形成权威源自反馈闭环。
    from ontology.objects import OBJECTS
    from ontology.links import LINKS
    from ontology.actions import ACTIONS
    own = ontology_db is None
    db = ontology_db or OntologySessionLocal()
    stats = {"objects": 0, "links": 0, "actions": 0, "changes": 0}
    try:
        # ── Object ──
        # 仅同步全局基线行（tenant_id IS NULL），租户覆盖项由运营侧维护，不被 seed 覆写
        existing_obj = {
            o.name: o for o in db.query(ObjectDefinition)
            .filter(ObjectDefinition.tenant_id.is_(None)).all()
        }
        for idx, o in enumerate(OBJECTS):
            name = o["name"]
            payload = {
                "display_name": o.get("display_name", name),
                "domain": o.get("domain"),
                "description": o.get("description", ""),
                "schema": {"fields": o.get("fields", []), "actions": o.get("actions", [])},
                "sort_order": idx,
            }
            if name in existing_obj:
                rec = existing_obj[name]
                before = {"display_name": rec.display_name, "domain": rec.domain, "schema": rec.schema}
                changed = False
                for k, v in payload.items():
                    if getattr(rec, k) != v:
                        setattr(rec, k, v)
                        changed = True
                if changed:
                    db.add(OntologyChangeLog(entity_type="object", entity_id=rec.id,
                                             change_type="update", before=before, after=payload))
                    stats["changes"] += 1
            else:
                rec = ObjectDefinition(name=name, **payload)
                db.add(rec)
                db.flush()
                db.add(OntologyChangeLog(entity_type="object", entity_id=rec.id,
                                         change_type="create", after=payload))
                stats["changes"] += 1
            stats["objects"] += 1

        # ── Link ──
        existing_link = {
            (l.source_object, l.name, l.target_object): l
            for l in db.query(LinkDefinition).filter(LinkDefinition.tenant_id.is_(None)).all()
        }
        for idx, l in enumerate(LINKS):
            key = (l.get("source_object"), l.get("name"), l.get("target_object"))
            payload = {
                "display_name": l.get("display_name", l.get("name")),
                "cardinality": l.get("cardinality", "1:N"),
                "description": l.get("description", ""),
                "sort_order": idx,
            }
            if key in existing_link:
                rec = existing_link[key]
                before = {"display_name": rec.display_name, "cardinality": rec.cardinality}
                changed = False
                for k, v in payload.items():
                    if getattr(rec, k) != v:
                        setattr(rec, k, v)
                        changed = True
                if changed:
                    db.add(OntologyChangeLog(entity_type="link", entity_id=rec.id,
                                             change_type="update", before=before, after=payload))
                    stats["changes"] += 1
            else:
                rec = LinkDefinition(source_object=l.get("source_object"), name=l.get("name"),
                                     target_object=l.get("target_object"), **payload)
                db.add(rec)
                db.flush()
                db.add(OntologyChangeLog(entity_type="link", entity_id=rec.id,
                                         change_type="create", after=payload))
                stats["changes"] += 1
            stats["links"] += 1

        # ── Action ──
        existing_act = {
            a.name: a for a in db.query(ActionDefinition)
            .filter(ActionDefinition.tenant_id.is_(None)).all()
        }
        for idx, a in enumerate(ACTIONS):
            name = a["name"]
            payload = {
                "display_name": a.get("display_name", name),
                "domain": a.get("domain"),
                "input_schema": a.get("input_schema", {}),
                "output_schema": a.get("output_schema", {}),
                "risk_level": a.get("risk_level", "L1"),
                "permission_required": a.get("permission_required"),
                "description": a.get("description", ""),
                "sort_order": idx,
            }
            if name in existing_act:
                rec = existing_act[name]
                before = {"display_name": rec.display_name, "risk_level": rec.risk_level}
                changed = False
                for k, v in payload.items():
                    if getattr(rec, k) != v:
                        setattr(rec, k, v)
                        changed = True
                if changed:
                    db.add(OntologyChangeLog(entity_type="action", entity_id=rec.id,
                                             change_type="update", before=before, after=payload))
                    stats["changes"] += 1
            else:
                rec = ActionDefinition(name=name, **payload)
                db.add(rec)
                db.flush()
                db.add(OntologyChangeLog(entity_type="action", entity_id=rec.id,
                                         change_type="create", after=payload))
                stats["changes"] += 1
            stats["actions"] += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if own:
            db.close()

    # seed 落库后刷新运行时缓存，使 registry 立即以 DB 为权威源
    try:
        from ontology.registry import registry as _ontology_registry
        stats["cache"] = _ontology_registry.reload()
    except Exception as e:  # 缓存刷新失败不影响 seed 结果
        import logging
        logging.getLogger(__name__).warning("[ontology] seed 后刷新缓存失败: %s", e)

    return stats


# ──────────────────────────────────────────────
# 迁移系统
# ──────────────────────────────────────────────

def run_migrations():
    """建表兜底。

    schema 演进已全部由 Alembic 接管（backend/alembic/versions/），
    这里只保留 `create_all` 作为兜底：正常启动路径下 Alembic 已把单库升到 head，
    `create_all` 对已存在的表是 no-op；仅在极端情况（如迁移被跳过）下补建表，
    保证后续 seed 不会因缺表而失败。

    第 14 批：业务库与本体库共用同一 engine，双 metadata.create_all 走同一连接。
    历史上这里维护过一套自制迁移表（MigrationLog + 手写 ALTER），
    已废弃——它与 Alembic 并存会互相打架（例如重新加回 Alembic 刚删除的列）。
    """
    BusinessBase.metadata.create_all(business_engine)
    OntologyBase.metadata.create_all(business_engine)


# ──────────────────────────────────────────────
# 初始化 & 种子数据
# ──────────────────────────────────────────────

def seed_default_data():
    """创建默认租户、角色、用户"""
    db = BusinessSessionLocal()
    try:
        # 默认租户
        if not db.query(Tenant).filter(Tenant.code == "demo").first():
            tenant = Tenant(code="demo", name="Demo制药", settings={}, is_active=1)
            db.add(tenant)
            db.flush()

            # 默认角色
            roles_data = [
                ("admin", "平台管理员", ["*"]),
                ("sales_rep", "医药代表", ["visit_plan.read", "visit_plan.write", "visit_record.read", "visit_record.write", "compliance.read"]),
                ("regional_manager", "区域经理", ["visit_plan.read", "visit_plan.write", "visit_plan.approve", "visit_record.read", "compliance.read"]),
                ("sales_director", "销售总监", ["*"]),
                ("training_manager", "培训经理", ["course.read", "course.write", "exam.read", "exam.write", "compliance.read"]),
                ("trainer", "培训师", ["course.read", "course.write", "compliance.read"]),
                ("marketing_manager", "市场经理", ["knowledge.read", "knowledge.write", "compliance.read", "compliance.write"]),
                ("medical_manager", "医学经理", ["knowledge.read", "knowledge.write", "compliance.read", "compliance.write"]),
                ("kol_coordinator", "KOL协调员", ["crm.read", "crm.write", "compliance.read"]),
                ("im_coordinator", "IM协调员", ["cfm.read", "cfm.write", "compliance.read", "compliance.write"]),
                ("auditor", "审计员", ["audit.read", "compliance.read"]),
                ("platform_admin", "平台管理员", ["platform.read", "platform.write", "compliance.read", "compliance.write"]),
            ]
            role_map = {}
            for code, name, perms in roles_data:
                role = Role(tenant_id=str(tenant.id), name=name, code=code, permissions=perms)
                db.add(role)
                db.flush()
                role_map[code] = role

            # 默认用户 admin / demo123
            admin = User(
                tenant_id=str(tenant.id),
                username="admin",
                email="admin@demo.com",
                password_hash=hash_password("demo123"),
                display_name="管理员",
                role_id=role_map["admin"].id,
                is_active=1,
            )
            db.add(admin)
            db.commit()
            print(f"[seed] 默认租户 demo、用户 admin/demo123 已创建")

        # 销售执行域种子数据（检查是否已有医院数据，避免重复插入）
        tenant = db.query(Tenant).filter(Tenant.code == "demo").first()
        if tenant and not db.query(Hospital).filter(Hospital.tenant_id == str(tenant.id)).first():
            tid = str(tenant.id)
            # 主数据
            hospital1 = Hospital(tenant_id=tid, name="市第一人民医院", code="H001", level="三甲", province="江苏", city="南京", district="鼓楼区", address="广州路300号")
            hospital2 = Hospital(tenant_id=tid, name="市第二医院", code="H002", level="三甲", province="江苏", city="南京", district="玄武区")
            hospital3 = Hospital(tenant_id=tid, name="社区卫生服务中心", code="H003", level="社区", province="江苏", city="南京", district="秦淮区")
            db.add_all([hospital1, hospital2, hospital3])
            db.flush()

            doctor1 = Doctor(tenant_id=tid, name="王教授", hospital_id=hospital1.id, department="心内科", title="主任医师", phone="13800001111")
            doctor2 = Doctor(tenant_id=tid, name="李主任", hospital_id=hospital1.id, department="心内科", title="副主任医师")
            doctor3 = Doctor(tenant_id=tid, name="张医生", hospital_id=hospital2.id, department="神经内科", title="主治医师")
            doctor4 = Doctor(tenant_id=tid, name="刘医生", hospital_id=hospital2.id, department="消化内科", title="主治医师")
            doctor5 = Doctor(tenant_id=tid, name="陈医生", hospital_id=hospital3.id, department="全科", title="副主任医师")
            db.add_all([doctor1, doctor2, doctor3, doctor4, doctor5])
            db.flush()

            product1 = Product(tenant_id=tid, name="心血通", code="P001", category="心血管", specifications="10mg×28", manufacturer="辉瑞")
            product2 = Product(tenant_id=tid, name="脑复康", code="P002", category="神经", specifications="5mg×30", manufacturer="恒瑞")
            product3 = Product(tenant_id=tid, name="胃复安", code="P003", category="消化", specifications="20mg×14", manufacturer="扬子江")
            db.add_all([product1, product2, product3])
            db.flush()

            zone1 = Zone(tenant_id=tid, name="南京中心区", code="Z001", level=2)
            db.add(zone1)
            db.flush()

            # 覆盖分配
            cov1 = CoverageAssignment(tenant_id=tid, user_id=1, hospital_id=hospital1.id, doctor_id=doctor1.id, product_id=product1.id, role="primary", start_date=date.today())
            cov2 = CoverageAssignment(tenant_id=tid, user_id=1, hospital_id=hospital2.id, doctor_id=doctor3.id, product_id=product2.id, role="primary", start_date=date.today())
            db.add_all([cov1, cov2])
            db.flush()

            # 拜访计划
            plan1 = VisitPlan(tenant_id=tid, user_id=1, period="2026-07", target_count=15, status="draft")
            plan2 = VisitPlan(tenant_id=tid, user_id=1, period="2026-06", target_count=12, status="approved", approved_by=1, approved_at=datetime.utcnow(), ai_score=85, ai_suggestion="覆盖良好，建议加强 H2 神经内科")
            db.add_all([plan1, plan2])
            db.flush()

            # 拜访计划明细
            item1 = VisitPlanItem(tenant_id=tid, plan_id=plan2.id, hospital_id=hospital1.id, doctor_id=doctor1.id, product_id=product1.id, planned_date=date(2026, 6, 10), priority="high", visit_type="academic")
            item2 = VisitPlanItem(tenant_id=tid, plan_id=plan2.id, hospital_id=hospital2.id, doctor_id=doctor3.id, product_id=product2.id, planned_date=date(2026, 6, 15), priority="medium", visit_type="daily")
            item3 = VisitPlanItem(tenant_id=tid, plan_id=plan2.id, hospital_id=hospital1.id, doctor_id=doctor2.id, product_id=product1.id, planned_date=date(2026, 6, 20), priority="high", visit_type="academic")
            db.add_all([item1, item2, item3])
            db.flush()

            # 拜访记录（5 条）
            record1 = VisitRecord(tenant_id=tid, user_id=1, plan_id=plan2.id, plan_item_id=item1.id, hospital_id=hospital1.id, doctor_id=doctor1.id, product_id=product1.id, visit_date=date(2026, 6, 10), visit_type="academic", duration_minutes=45, location="市第一人民医院心内科", summary="与王教授讨论心血通最新临床数据，对方关注药物相互作用。")
            record2 = VisitRecord(tenant_id=tid, user_id=1, plan_id=plan2.id, plan_item_id=item2.id, hospital_id=hospital2.id, doctor_id=doctor3.id, product_id=product2.id, visit_date=date(2026, 6, 15), visit_type="daily", duration_minutes=20, location="市第二医院神经内科", summary="张医生询问脑复康剂量调整方案。")
            record3 = VisitRecord(tenant_id=tid, user_id=1, plan_id=plan2.id, plan_item_id=item3.id, hospital_id=hospital1.id, doctor_id=doctor2.id, product_id=product1.id, visit_date=date(2026, 6, 20), visit_type="academic", duration_minutes=60, location="市第一人民医院心内科", summary="李主任对心血通疗效表示认可，建议科室试用。")
            record4 = VisitRecord(tenant_id=tid, user_id=1, hospital_id=hospital2.id, doctor_id=doctor4.id, product_id=product3.id, visit_date=date(2026, 6, 25), visit_type="daily", duration_minutes=25, location="市第二医院消化内科", summary="刘医生反馈胃复安效果不错。")
            record5 = VisitRecord(tenant_id=tid, user_id=1, hospital_id=hospital3.id, doctor_id=doctor5.id, product_id=product1.id, visit_date=date(2026, 6, 28), visit_type="meeting", duration_minutes=40, location="社区卫生服务中心", summary="陈医生参加心血通学术沙龙。")
            db.add_all([record1, record2, record3, record4, record5])
            db.flush()

            # 拜访反馈（3 条）
            fb1 = VisitFeedback(tenant_id=tid, record_id=record1.id, sentiment="neutral", interest_points=["临床数据", "药物相互作用"], objections=["副作用"], action_items=["寄送最新临床指南", "3周后回访"])
            fb2 = VisitFeedback(tenant_id=tid, record_id=record2.id, sentiment="positive", interest_points=["剂量方案"], objections=[], action_items=["提供剂量调整手册"])
            fb3 = VisitFeedback(tenant_id=tid, record_id=record3.id, sentiment="positive", interest_points=["疗效认可", "科室试用"], objections=[], action_items=["安排科室宣讲", "提供试用装"])
            db.add_all([fb1, fb2, fb3])
            db.flush()

            # 覆盖矩阵
            matrix1 = CoverageMatrix(tenant_id=tid, hospital_id=hospital1.id, product_id=product1.id, visit_count=2, last_visit_date=date(2026, 6, 20), coverage_level="high", trend="up")
            matrix2 = CoverageMatrix(tenant_id=tid, hospital_id=hospital1.id, product_id=product2.id, visit_count=0, last_visit_date=None, coverage_level="none", trend="stable")
            matrix3 = CoverageMatrix(tenant_id=tid, hospital_id=hospital2.id, product_id=product1.id, visit_count=0, last_visit_date=None, coverage_level="none", trend="stable")
            matrix4 = CoverageMatrix(tenant_id=tid, hospital_id=hospital2.id, product_id=product2.id, visit_count=1, last_visit_date=date(2026, 6, 15), coverage_level="medium", trend="up")
            matrix5 = CoverageMatrix(tenant_id=tid, hospital_id=hospital2.id, product_id=product3.id, visit_count=1, last_visit_date=date(2026, 6, 25), coverage_level="medium", trend="up")
            matrix6 = CoverageMatrix(tenant_id=tid, hospital_id=hospital3.id, product_id=product1.id, visit_count=1, last_visit_date=date(2026, 6, 28), coverage_level="low", trend="up")
            db.add_all([matrix1, matrix2, matrix3, matrix4, matrix5, matrix6])
            db.flush()

            # 行为积分规则
            rule1 = BehaviorPointRule(tenant_id=tid, name="完成拜访", action_code="complete_visit", points=5, description="每次完成拜访记录")
            rule2 = BehaviorPointRule(tenant_id=tid, name="学术拜访", action_code="academic_visit", points=3, description="学术形式拜访额外加分")
            rule3 = BehaviorPointRule(tenant_id=tid, name="获得正面反馈", action_code="positive_feedback", points=10, description="获得医生正面反馈")
            db.add_all([rule1, rule2, rule3])
            db.flush()

            # 行为积分记录（5 条）
            bpr1 = BehaviorPointRecord(tenant_id=tid, user_id=1, rule_id=rule1.id, record_id=record1.id, points=5, occurred_at=datetime(2026, 6, 10, 10, 30))
            bpr2 = BehaviorPointRecord(tenant_id=tid, user_id=1, rule_id=rule2.id, record_id=record1.id, points=3, occurred_at=datetime(2026, 6, 10, 10, 31))
            bpr3 = BehaviorPointRecord(tenant_id=tid, user_id=1, rule_id=rule1.id, record_id=record2.id, points=5, occurred_at=datetime(2026, 6, 15, 14, 0))
            bpr4 = BehaviorPointRecord(tenant_id=tid, user_id=1, rule_id=rule1.id, record_id=record3.id, points=5, occurred_at=datetime(2026, 6, 20, 15, 0))
            bpr5 = BehaviorPointRecord(tenant_id=tid, user_id=1, rule_id=rule3.id, record_id=record3.id, points=10, occurred_at=datetime(2026, 6, 20, 15, 5))
            db.add_all([bpr1, bpr2, bpr3, bpr4, bpr5])

            db.commit()
            print(f"[seed] 销售执行域种子数据已创建")

        # 培训域种子数据（检查是否已有课程数据，避免重复插入）
        if tenant and not db.query(Course).filter(Course.tenant_id == str(tenant.id)).first():
            tid = str(tenant.id)
            # 5 门课程
            course1 = Course(tenant_id=tid, title="产品知识进阶", description="心血管产品线核心机制、适应症与临床数据解读。", course_type="video", category="产品知识", difficulty="intermediate", duration_minutes=45, cover_image=None, content_url="https://example.com/c1", tags=["心血管", "临床"], is_published=1, enroll_count=2, avg_rating=88)
            course2 = Course(tenant_id=tid, title="高效拜访技巧", description="医药代表日常拜访流程、开场、提问与缔结技巧。", course_type="interactive", category="拜访技巧", difficulty="beginner", duration_minutes=30, cover_image=None, content_url="https://example.com/c2", tags=["拜访", "沟通"], is_published=1, enroll_count=1, avg_rating=92)
            course3 = Course(tenant_id=tid, title="医药合规培训", description="医药行业合规要求、学术推广边界与反商业贿赂要点。", course_type="article", category="合规", difficulty="advanced", duration_minutes=60, cover_image=None, content_url="https://example.com/c3", tags=["合规", "法规"], is_published=1, enroll_count=1, avg_rating=85)
            course4 = Course(tenant_id=tid, title="医学基础知识", description="药理学、解剖学与病理学基础，适合非医学背景代表。", course_type="pdf", category="医学基础", difficulty="beginner", duration_minutes=90, cover_image=None, content_url="https://example.com/c4", tags=["药理", "基础"], is_published=1, enroll_count=0, avg_rating=78)
            course5 = Course(tenant_id=tid, title="销售话术与异议处理", description="典型客户异议场景与应对话术库。", course_type="video", category="销售技巧", difficulty="intermediate", duration_minutes=40, cover_image=None, content_url="https://example.com/c5", tags=["话术", "异议"], is_published=0, enroll_count=0, avg_rating=80)
            db.add_all([course1, course2, course3, course4, course5])
            db.flush()

            # 5 道题目
            q1 = Question(tenant_id=tid, question_type="single", content="心血通的推荐起始剂量是？", options=[{"key": "A", "text": "5mg"}, {"key": "B", "text": "10mg"}, {"key": "C", "text": "20mg"}, {"key": "D", "text": "40mg"}], answer=["B"], explanation="根据说明书，起始剂量为 10mg/日。", difficulty="easy", category="产品知识", points=5)
            q2 = Question(tenant_id=tid, question_type="multiple", content="以下属于学术拜访特征的有？", options=[{"key": "A", "text": "携带临床文献"}, {"key": "B", "text": "讨论疾病机制"}, {"key": "C", "text": "赠送礼品卡"}, {"key": "D", "text": "邀请科室宣讲"}], answer=["A", "B", "D"], explanation="C 属于违规行为，不属于学术拜访。", difficulty="medium", category="拜访技巧", points=10)
            q3 = Question(tenant_id=tid, question_type="judge", content="医药代表可以向医生承诺药品的具体疗效。", options=[{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}], answer=["B"], explanation="不得做超出说明书的疗效承诺。", difficulty="easy", category="合规", points=5)
            q4 = Question(tenant_id=tid, question_type="fill", content="心血通的主要活性成分是____。", options=[], answer=["氨氯地平"], explanation="氨氯地平为二氢吡啶类钙通道阻滞剂。", difficulty="hard", category="产品知识", points=8)
            q5 = Question(tenant_id=tid, question_type="single", content="面对医生提出副作用担忧时，首选的应对策略是？", options=[{"key": "A", "text": "强调发生率很低"}, {"key": "B", "text": "提供临床数据并记录反馈"}, {"key": "C", "text": "转移话题"}, {"key": "D", "text": "建议自行停药"}], answer=["B"], explanation="应以数据回应并记录，必要时移交医学部。", difficulty="medium", category="销售技巧", points=5)
            db.add_all([q1, q2, q3, q4, q5])
            db.flush()

            # 2 场考试（1 draft 1 published）
            exam1 = Exam(tenant_id=tid, title="产品知识测试", description="心血通产品知识综合测评。", duration_minutes=30, pass_score=60, question_ids=[q1.id, q4.id], status="published", start_at=datetime(2026, 7, 1), end_at=datetime(2026, 12, 31), max_attempts=2, attempt_count=1)
            exam2 = Exam(tenant_id=tid, title="拜访技巧考核", description="日常拜访技巧与合规综合考核。", duration_minutes=45, pass_score=70, question_ids=[q2.id, q3.id, q5.id], status="draft", start_at=None, end_at=None, max_attempts=1, attempt_count=0)
            db.add_all([exam1, exam2])
            db.flush()

            # 1 条考试记录（已提交，分数 80，通过）
            exam_record1 = ExamRecord(tenant_id=tid, exam_id=exam1.id, user_id=1, status="submitted", answers=[{"question_id": q1.id, "answer": ["B"]}, {"question_id": q4.id, "answer": ["氨氯地平"]}], score=80, passed=1, started_at=datetime(2026, 7, 5, 10, 0), submitted_at=datetime(2026, 7, 5, 10, 25), ai_comment="产品知识掌握良好，建议加强成分机制学习。")
            db.add(exam_record1)
            db.flush()

            # 2 条学习路径（各含 2 阶段）
            path1 = LearningPath(tenant_id=tid, title="新代表入职路径", description="入职 30 天标准化学习路径。", target_role="sales_rep", stages=[{"stage": 1, "title": "基础准备", "course_ids": [course2.id, course4.id], "required": True}, {"stage": 2, "title": "产品与合规", "course_ids": [course1.id, course3.id], "required": True}], total_credits=20, enroll_count=1, is_published=1)
            path2 = LearningPath(tenant_id=tid, title="进阶销售路径", description="晋升资深代表的进阶能力培养。", target_role="regional_manager", stages=[{"stage": 1, "title": "客户深度经营", "course_ids": [course5.id], "required": True}, {"stage": 2, "title": "团队与合规", "course_ids": [course3.id, course1.id], "required": False}], total_credits=30, enroll_count=0, is_published=1)
            db.add_all([path1, path2])
            db.flush()

            # 1 条路径选课（进行中，阶段 1）
            path_enroll1 = PathEnrollment(tenant_id=tid, path_id=path1.id, user_id=1, current_stage=1, credits_earned=5, status="enrolled", enrolled_at=datetime(2026, 7, 1), completed_at=None)
            db.add(path_enroll1)
            db.flush()

            # 2 条证书
            cert1 = Certificate(tenant_id=tid, user_id=1, title="产品知识测试通过证书", cert_type="exam", source_id=exam1.id, score=80, issued_at=datetime(2026, 7, 5, 10, 30), expire_at=datetime(2027, 7, 5), cert_no="CERT-EXAM-2026-0001")
            cert2 = Certificate(tenant_id=tid, user_id=1, title="高效拜访技巧结业证书", cert_type="course", source_id=course2.id, score=92, issued_at=datetime(2026, 6, 20, 16, 0), expire_at=None, cert_no="CERT-COURSE-2026-0007")
            db.add_all([cert1, cert2])
            db.flush()

            # 2 个演练场景
            scenario1 = PracticeScenario(tenant_id=tid, title="初次拜访心内科主任", description="向三甲医院心内科主任介绍心血通，建立信任。", scenario_type="visit", customer_profile="55岁心内科主任，学术严谨，关注临床数据与药物相互作用。", product_id=1, difficulty="medium", target_skills=["开场", "需求探寻", "数据呈现"], is_published=1)
            scenario2 = PracticeScenario(tenant_id=tid, title="异议处理：价格偏高", description="医生反馈产品价格高于竞品，需专业应对。", scenario_type="objection", customer_profile="40岁副主任医师，关注性价比，常用竞品。", product_id=1, difficulty="hard", target_skills=["异议处理", "价值塑造", "缔结"], is_published=1)
            db.add_all([scenario1, scenario2])
            db.flush()

            # 2 条课程选课（1 进行中 1 已完成）
            enroll1 = CourseEnrollment(tenant_id=tid, course_id=course1.id, user_id=1, status="in_progress", progress=45, enrolled_at=datetime(2026, 7, 2), completed_at=None, last_position=620)
            enroll2 = CourseEnrollment(tenant_id=tid, course_id=course2.id, user_id=1, status="completed", progress=100, enrolled_at=datetime(2026, 6, 15), completed_at=datetime(2026, 6, 20, 16, 0), last_position=0)
            db.add_all([enroll1, enroll2])

            db.commit()
            print(f"[seed] 培训域种子数据已创建")

        # 协同办公域种子数据
        if tenant and not db.query(Task).filter(Task.tenant_id == str(tenant.id)).first():
            tid = str(tenant.id)
            today = date.today()
            # 5 条任务（不同状态/优先级/类型）
            task1 = Task(tenant_id=tid, title="跟进张主任对心血通的反馈", description="张主任对上次拜访中提到的药物相互作用存疑，需提供补充资料。", task_type="follow_up", status="in_progress", priority="high", assignee_id=1, creator_id=1, due_date=today + timedelta(days=2), related_type="visit_record", related_id=1)
            task2 = Task(tenant_id=tid, title="提交本月拜访计划", description="整理本月覆盖医院的拜访计划并提交审批。", task_type="visit", status="pending", priority="high", assignee_id=1, creator_id=1, due_date=today + timedelta(days=1))
            task3 = Task(tenant_id=tid, title="完成医药合规培训", description="2026 年度合规培训，需在月底前完成。", task_type="training", status="pending", priority="medium", assignee_id=1, creator_id=1, due_date=today + timedelta(days=10), related_type="course", related_id=3)
            task4 = Task(tenant_id=tid, title="整理李医生异议处理要点", description="汇总上次拜访中李医生提出的 3 个价格异议，输出应对话术。", task_type="general", status="completed", priority="medium", assignee_id=1, creator_id=1, due_date=today - timedelta(days=3), completed_at=datetime.utcnow() - timedelta(days=4))
            task5 = Task(tenant_id=tid, title="预约下周科室宣讲", description="联系心内科护士长，预约下周五的科室宣讲会议。", task_type="general", status="pending", priority="low", assignee_id=1, creator_id=1, due_date=today + timedelta(days=7))
            db.add_all([task1, task2, task3, task4, task5])
            db.flush()

            # 3 条审批（含 pending/approved）
            appr1 = Approval(tenant_id=tid, title="7 月拜访计划审批", approval_type="visit_plan", status="pending", applicant_id=1, approver_id=None, content="覆盖 6 家医院、12 位医生，共 18 次拜访，重点客户为心内科张主任。", related_type="visit_plan", related_id=1, reviewed_at=None, review_comment=None)
            appr2 = Approval(tenant_id=tid, title="差旅费用报销 - 6 月", approval_type="expense", status="approved", applicant_id=1, approver_id=1, content="6 月外埠拜访产生差旅费用合计 ¥3,280，含交通 ¥2,100、住宿 ¥1,180。", related_type=None, related_id=None, reviewed_at=datetime.utcnow() - timedelta(days=5), review_comment="费用合理，予以报销。")
            appr3 = Approval(tenant_id=tid, title="样品申请 - 心血通", approval_type="sample", status="pending", applicant_id=1, approver_id=None, content="为下周科室宣讲申请心血通样品 20 盒。", related_type=None, related_id=None, reviewed_at=None, review_comment=None)
            db.add_all([appr1, appr2, appr3])
            db.flush()

            # 3 条公告
            ann1 = Announcement(tenant_id=tid, title="2026 年度医药合规培训通知", content="各位同事：2026 年度医药合规培训已上线，请于 7 月 31 日前完成学习与考试。合规是底线，请务必重视。", ann_type="urgent", publisher_id=1, published_at=datetime.utcnow() - timedelta(days=2), is_pinned=1, view_count=42)
            ann2 = Announcement(tenant_id=tid, title="新产品心血通上市启动会", content="心血通上市启动会将于本周五下午 14:00 在总部会议室召开，请销售与市场团队准时出席。", ann_type="info", publisher_id=1, published_at=datetime.utcnow() - timedelta(days=5), is_pinned=0, view_count=28)
            ann3 = Announcement(tenant_id=tid, title="Q3 销售目标下达", content="Q3 区域销售目标已下达至各办事处，请登录系统查看本区域分解指标，并于 7 月 15 日前反馈执行计划。", ann_type="info", publisher_id=1, published_at=datetime.utcnow() - timedelta(days=7), is_pinned=0, view_count=65)
            db.add_all([ann1, ann2, ann3])

            db.commit()
            print(f"[seed] 协同办公域种子数据已创建")

        # 知识库域种子数据
        if tenant and not db.query(KnowledgeDocument).filter(KnowledgeDocument.tenant_id == str(tenant.id)).first():
            tid = str(tenant.id)
            # 6 篇知识文档（不同分类）
            doc1 = KnowledgeDocument(tenant_id=tid, title="心血通产品手册（2026 版）", category="product", content="【药品名称】心血通（氨氯地平片）\n【适应症】高血压、稳定性心绞痛\n【用法用量】口服，起始剂量 10mg/日，最大 40mg/日\n【禁忌】对二氢吡啶类过敏者禁用\n【不良反应】常见头痛、水肿、潮红", summary="心血通 2026 版产品手册，涵盖适应症、用法、禁忌与不良反应。", tags="心血管,氨氯地平,产品手册", author_id=1, author_name="产品部", view_count=128, is_published=1)
            doc2 = KnowledgeDocument(tenant_id=tid, title="氨氯地平临床数据汇总", category="clinical", content="基于 12 项 RCT 研究的 Meta 分析：氨氯地平 10mg/日可使收缩压平均下降 12.3mmHg，舒张压下降 7.8mmHg，与 ACEI 联用可显著减少心血管事件 22%。常见不良反应为外周水肿（9.3%）与头痛（5.8%）。", summary="氨氯地平 12 项 RCT Meta 分析，含降压效果与联合用药数据。", tags="临床数据,Meta分析,降压", author_id=1, author_name="医学部", view_count=86, is_published=1)
            doc3 = KnowledgeDocument(tenant_id=tid, title="医药代表合规行为指南", category="compliance", content="一、不得向医生承诺超出说明书的疗效\n二、禁止以任何形式赠送礼品卡、现金等\n三、学术会议需经合规部备案\n四、接待标准严格执行公司差旅政策\n五、所有拜访记录需真实、完整、可追溯", summary="医药代表日常合规行为 5 大要点，违规将触发纪律处分。", tags="合规,行为指南,学术推广", author_id=1, author_name="合规部", view_count=203, is_published=1)
            doc4 = KnowledgeDocument(tenant_id=tid, title="心内科客户画像与沟通策略", category="sales", content="心内科主任级客户通常学术严谨，关注循证医学证据，沟通时建议：\n1. 开场即抛出关键临床数据\n2. 避免营销话术，多用机制与数据\n3. 对异议采用\"数据+记录+反馈\"三步法\n4. 适时邀请参加学术会议", summary="心内科主任沟通策略 4 步法，适配学术型客户。", tags="心内科,客户画像,沟通策略", author_id=1, author_name="销售部", view_count=95, is_published=1)
            doc5 = KnowledgeDocument(tenant_id=tid, title="竞品对比：氨氯地平 vs 硝苯地平", category="product", content="氨氯地平（心血通）与硝苯地平对比：\n- 半衰期：氨氯地平 35h vs 硝苯地平 2h\n- 波谷效应：氨氯地平平稳 vs 硝苯地平波动大\n- 水肿发生率：氨氯地平 9.3% vs 硝苯地平 12.8%\n- 依从性：氨氯地平 QD vs 硝苯地平 BID/TID", summary="氨氯地平与硝苯地平 4 维度对比，凸显半衰期与依从性优势。", tags="竞品,氨氯地平,硝苯地平", author_id=1, author_name="产品部", view_count=74, is_published=1)
            doc6 = KnowledgeDocument(tenant_id=tid, title="科室宣讲 SOP", category="sales", content="科室宣讲标准流程：\n1. 提前 2 周与护士长确认时间与场地\n2. 准备 PPT、样品、临床文献\n3. 宣讲时长 20-30 分钟，预留 10 分钟答疑\n4. 会后 3 个工作日内提交会议纪要与反馈", summary="科室宣讲 4 步 SOP，含准备、执行、会后跟进。", tags="科室宣讲,SOP,学术推广", author_id=1, author_name="市场部", view_count=61, is_published=1)
            db.add_all([doc1, doc2, doc3, doc4, doc5, doc6])
            db.flush()

            # 6 条 FAQ
            faq1 = FaqItem(tenant_id=tid, question="心血通与 ACEI 可以联合使用吗？", answer="可以。氨氯地平与 ACEI 联合是高血压治疗的优选方案，临床数据显示联用可减少心血管事件 22%。需注意监测血压与肾功能。", category="product", sort_order=1, view_count=45)
            faq2 = FaqItem(tenant_id=tid, question="医生反馈水肿明显，如何处理？", answer="外周水肿是氨氯地平的常见不良反应（发生率 9.3%）。建议：1) 确认剂量是否过高；2) 联合 ACEI 可减轻水肿；3) 严重时建议医生调整剂量或换药。所有反馈需记录至系统。", category="clinical", sort_order=2, view_count=38)
            faq3 = FaqItem(tenant_id=tid, question="拜访时可以送医生礼品卡吗？", answer="不可以。公司严禁以任何形式向医生赠送礼品卡、现金或等价物，属于商业贿赂行为，将触发纪律处分。学术推广仅限临床文献、样品（需审批）等合规物品。", category="compliance", sort_order=3, view_count=72)
            faq4 = FaqItem(tenant_id=tid, question="如何申请科室宣讲样品？", answer="在协同办公-审批中提交\"样品申请\"，填写数量与用途，经区域经理审批后由库房发货。样品使用情况需在会后纪要中反馈。", category="sales", sort_order=4, view_count=29)
            faq5 = FaqItem(tenant_id=tid, question="拜访记录提交后可以修改吗？", answer="已提交的拜访记录在审批前可修改；审批通过后如需修改，需提交修改申请并说明原因。所有修改记录均会留存审计日志。", category="sales", sort_order=5, view_count=51)
            faq6 = FaqItem(tenant_id=tid, question="合规培训考试未通过怎么办？", answer="合规培训考试有 2 次机会。首次未通过可重新学习后参加补考；2 次均未通过需联系培训经理安排面授辅导，并在完成后重新考试。", category="compliance", sort_order=6, view_count=33)
            db.add_all([faq1, faq2, faq3, faq4, faq5, faq6])

            db.commit()
            print(f"[seed] 知识库域种子数据已创建")

        # 业务应用域种子数据（会议+论坛）
        if tenant and not db.query(Meeting).filter(Meeting.tenant_id == str(tenant.id)).first():
            tid = str(tenant.id)
            today = date.today()
            # 4 场会议
            m1 = Meeting(tenant_id=tid, title="心血通上市启动会", meeting_type="product_launch", status="completed", start_date=date(2026, 6, 15), end_date=date(2026, 6, 15), location="总部会议室 A", organizer_id=1, attendees_count=45, description="心血通新产品上市启动会，涵盖产品定位、市场策略与销售目标。", product_id=1)
            m2 = Meeting(tenant_id=tid, title="心内科科室宣讲 - 市第一人民医院", meeting_type="department", status="planned", start_date=today + timedelta(days=7), end_date=today + timedelta(days=7), location="市第一人民医院心内科", organizer_id=1, attendees_count=20, description="向心内科团队介绍心血通最新临床数据与用药方案。", product_id=1, hospital_id=1)
            m3 = Meeting(tenant_id=tid, title="2026 全国心血管学术大会", meeting_type="conference", status="planned", start_date=today + timedelta(days=30), end_date=today + timedelta(days=32), location="上海国际会议中心", organizer_id=1, attendees_count=500, description="参加全国心血管学术大会，展示心血通临床研究成果。", product_id=1)
            m4 = Meeting(tenant_id=tid, title="Q3 销售区域总结会", meeting_type="academic", status="ongoing", start_date=today, end_date=today, location="线上会议", organizer_id=1, attendees_count=12, description="Q3 各区域销售业绩总结与 Q4 策略规划。")
            db.add_all([m1, m2, m3, m4])
            db.flush()

            # 5 个论坛话题
            t1 = ForumTopic(tenant_id=tid, title="心血通与 ACEI 联合用药的临床经验分享", content="近期在临床拜访中发现，多位医生对心血通与 ACEI 联合使用感兴趣。分享一些临床数据和实际案例，欢迎大家讨论。", category="clinical", author_id=1, author_name="管理员", views=156, replies_count=8, is_pinned=1, last_reply_at=datetime.utcnow() - timedelta(days=1))
            t2 = ForumTopic(tenant_id=tid, title="如何应对医生对价格的异议？", content="张主任反馈心血通价格高于竞品，大家有什么好的应对话术？", category="sales", author_id=1, author_name="管理员", views=98, replies_count=5, is_pinned=0, last_reply_at=datetime.utcnow() - timedelta(days=3))
            t3 = ForumTopic(tenant_id=tid, title="合规培训常见问题讨论", content="关于学术会议接待标准，大家有什么疑问？请在下方留言。", category="compliance", author_id=1, author_name="管理员", views=72, replies_count=3, is_pinned=0, last_reply_at=datetime.utcnow() - timedelta(days=5))
            t4 = ForumTopic(tenant_id=tid, title="竞品硝苯地平最新动态", content="听说竞品硝苯地平即将推出新剂型，大家有相关信息吗？", category="product", author_id=1, author_name="管理员", views=64, replies_count=2, is_pinned=0, last_reply_at=datetime.utcnow() - timedelta(days=7))
            t5 = ForumTopic(tenant_id=tid, title="新代表入职经验交流", content="欢迎新入职的同事们！在这里分享入职心得和遇到的问题。", category="general", author_id=1, author_name="管理员", views=45, replies_count=4, is_pinned=0, last_reply_at=datetime.utcnow() - timedelta(days=10))
            db.add_all([t1, t2, t3, t4, t5])

            db.commit()
            print(f"[seed] 业务应用域种子数据已创建")
    finally:
        db.close()


def init_db():
    """初始化数据库：建表 + 迁移 + 种子"""
    settings.ensure_dirs()
    BusinessBase.metadata.create_all(business_engine)
    # 第 14 批：本体表与业务表处于同一物理库，create_all 走同一 engine
    OntologyBase.metadata.create_all(business_engine)
    run_migrations()
    seed_default_data()
