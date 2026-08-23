"""PPT 演讲训战服务（N+2 Step3）

Mock 实现：不真实解析 PPT 文件，仅用占位数据演示逐页演讲 + 问答 + AI 评审流程。
"""
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.exceptions import NotFoundError, ValidationError
from core.pagination import PageParams, paginate
from database import PracticeScenario, PPTSpeechSession

logger = logging.getLogger(__name__)


# PPT 演讲默认评分维度（7 维，参考借鉴文档 §九）
DEFAULT_PPT_DIMENSIONS = [
    {"key": "content_accuracy", "label": "内容准确性与专业度", "weight": 20},
    {"key": "keyword_coverage", "label": "关键词覆盖", "weight": 15},
    {"key": "structure_logic", "label": "结构与逻辑", "weight": 15},
    {"key": "fluency", "label": "表达流畅度", "weight": 15},
    {"key": "qa_response", "label": "互动应对", "weight": 15},
    {"key": "transition", "label": "转场与恢复", "weight": 10},
    {"key": "time_management", "label": "时间管理", "weight": 10},
]


# ──────────────────────────────────────────────
# 序列化
# ──────────────────────────────────────────────

def _serialize_scenario(sc: PracticeScenario) -> dict:
    return {
        "id": sc.id,
        "title": sc.title,
        "scenario_type": sc.scenario_type,
        "description": sc.description,
        "ppt_url": sc.ppt_url,
        "ppt_pages": sc.ppt_pages or [],
        "coach_prompts": sc.coach_prompts or [],
        "reference_audio_url": sc.reference_audio_url,
        "pass_score": sc.pass_score,
        "scoring_dimensions": sc.scoring_dimensions or DEFAULT_PPT_DIMENSIONS,
        "is_published": sc.is_published,
    }


def _serialize_session(s: PPTSpeechSession) -> dict:
    return {
        "id": s.id,
        "scenario_id": s.scenario_id,
        "user_id": s.user_id,
        "activity_id": s.activity_id,
        "mode": s.mode,
        "status": s.status,
        "current_page": s.current_page,
        "per_page_recordings": s.per_page_recordings or [],
        "questions": s.questions or [],
        "answers": s.answers or [],
        "final_score": s.final_score,
        "radar_scores": s.radar_scores or {},
        "ai_review": s.ai_review,
        "started_at": s.started_at.strftime("%Y-%m-%d %H:%M:%S") if s.started_at else None,
        "ended_at": s.ended_at.strftime("%Y-%m-%d %H:%M:%S") if s.ended_at else None,
    }


# ──────────────────────────────────────────────
# PPT 场景管理
# ──────────────────────────────────────────────

def list_ppt_scenarios(db: Session, tenant_id: str, keyword: str = None,
                       page_params: PageParams = None) -> dict:
    """列表查询 PPT 演讲场景"""
    q = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.scenario_type == "ppt_speech",
    )
    if keyword:
        q = q.filter(PracticeScenario.title.like(f"%{keyword}%"))
    total = q.count()
    q = q.order_by(PracticeScenario.id.desc())
    if page_params:
        q = q.offset(page_params.offset()).limit(page_params.effective_page_size())
    return paginate([_serialize_scenario(s) for s in q.all()], total, page_params or PageParams())


def get_ppt_scenario(db: Session, tenant_id: str, scenario_id: int) -> dict:
    sc = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.id == scenario_id,
        PracticeScenario.scenario_type == "ppt_speech",
    ).first()
    if not sc:
        raise NotFoundError("PPT 演讲场景不存在")
    return _serialize_scenario(sc)


def create_ppt_scenario(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """创建 PPT 演讲场景"""
    title = data.get("title")
    if not title:
        raise ValidationError("title 不能为空")
    ppt_url = data.get("ppt_url")
    sc = PracticeScenario(
        tenant_id=tenant_id,
        title=title,
        scenario_type="ppt_speech",
        description=data.get("description"),
        product_id=data.get("product_id"),
        difficulty=data.get("difficulty", "medium"),
        ppt_url=ppt_url,
        ppt_pages=data.get("ppt_pages") or [],
        coach_prompts=data.get("coach_prompts") or [],
        reference_audio_url=data.get("reference_audio_url"),
        pass_score=data.get("pass_score", 60),
        scoring_dimensions=data.get("scoring_dimensions") or DEFAULT_PPT_DIMENSIONS,
        is_published=0,
    )
    db.add(sc)
    db.commit()
    db.refresh(sc)
    # 若提供 ppt_url 但无 ppt_pages，触发 Mock 解析
    if ppt_url and not sc.ppt_pages:
        pages = mock_parse_ppt(ppt_url)
        sc.ppt_pages = pages
        db.commit()
        db.refresh(sc)
    return _serialize_scenario(sc)


def update_ppt_scenario(db: Session, tenant_id: str, scenario_id: int, data: dict) -> dict:
    sc = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.id == scenario_id,
        PracticeScenario.scenario_type == "ppt_speech",
    ).first()
    if not sc:
        raise NotFoundError("PPT 演讲场景不存在")
    if sc.is_published == 1:
        raise ValidationError("已发布场景不可修改")
    for field in ("title", "description", "ppt_url", "ppt_pages", "coach_prompts",
                  "reference_audio_url", "pass_score", "scoring_dimensions", "difficulty"):
        if field in data and data[field] is not None:
            setattr(sc, field, data[field])
    db.commit()
    db.refresh(sc)
    return _serialize_scenario(sc)


def publish_ppt_scenario(db: Session, tenant_id: str, scenario_id: int) -> dict:
    sc = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.id == scenario_id,
        PracticeScenario.scenario_type == "ppt_speech",
    ).first()
    if not sc:
        raise NotFoundError("PPT 演讲场景不存在")
    if not sc.ppt_pages:
        raise ValidationError("PPT 未解析，无法发布")
    sc.is_published = 1
    db.commit()
    db.refresh(sc)
    return _serialize_scenario(sc)


# ──────────────────────────────────────────────
# Mock PPT 解析
# ──────────────────────────────────────────────

def mock_parse_ppt(ppt_url: str) -> list:
    """Mock PPT 解析 — 返回占位页结构

    真实场景应对接 ASR/TTS 或 PPT 解析库，本期仅占位。
    """
    return [
        {
            "page_no": 1,
            "title": "封面页",
            "content_text": "产品名称 | 适应症 | 汇报人",
            "reference_audio_url": None,
            "key_points": ["自我介绍", "产品定位"],
            "keywords": ["产品名", "适应症"],
        },
        {
            "page_no": 2,
            "title": "疾病背景",
            "content_text": "流行病学数据 | 未满足的临床需求",
            "reference_audio_url": None,
            "key_points": ["发病率", "现有治疗局限"],
            "keywords": ["流行病学", "未满足需求"],
        },
        {
            "page_no": 3,
            "title": "产品机制",
            "content_text": "作用机制 | 药代动力学",
            "reference_audio_url": None,
            "key_points": ["MOA", "PK 特征"],
            "keywords": ["机制", "药代"],
        },
        {
            "page_no": 4,
            "title": "临床数据",
            "content_text": "III 期 RCT 主要终点 | 安全性",
            "reference_audio_url": None,
            "key_points": ["主要终点", "安全性"],
            "keywords": ["III 期", "RCT", "安全性"],
        },
        {
            "page_no": 5,
            "title": "总结与问答",
            "content_text": "核心优势 | 下一步计划",
            "reference_audio_url": None,
            "key_points": ["核心优势", "Q&A"],
            "keywords": ["总结", "问答"],
        },
    ]


# ──────────────────────────────────────────────
# PPT 演讲会话
# ──────────────────────────────────────────────

def start_session(db: Session, tenant_id: str, user_id: int,
                  scenario_id: int, mode: str = "practice",
                  activity_id: int = None) -> dict:
    """开始 PPT 演讲会话"""
    sc = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.id == scenario_id,
        PracticeScenario.scenario_type == "ppt_speech",
    ).first()
    if not sc:
        raise NotFoundError("PPT 演讲场景不存在")
    if sc.is_published != 1:
        raise ValidationError("场景未发布")
    if mode not in ("practice", "train"):
        raise ValidationError("mode 取值 practice/train")
    s = PPTSpeechSession(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        user_id=user_id,
        activity_id=activity_id,
        mode=mode,
        status="in_progress",
        current_page=1,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _serialize_session(s)


def submit_page(db: Session, tenant_id: str, session_id: int,
                page_no: int, recording: dict) -> dict:
    """提交单页录音"""
    s = _get_session(db, tenant_id, session_id)
    if s.status != "in_progress":
        raise ValidationError("会话已结束")
    recordings = list(s.per_page_recordings or [])
    # 替换或追加该页录音
    recordings = [r for r in recordings if r.get("page_no") != page_no]
    recordings.append({
        "page_no": page_no,
        "audio_url": recording.get("audio_url"),
        "duration_ms": recording.get("duration_ms", 0),
        "transcript": recording.get("transcript", ""),
    })
    recordings.sort(key=lambda r: r.get("page_no", 0))
    s.per_page_recordings = recordings
    # 推进当前页
    if page_no >= s.current_page:
        s.current_page = page_no + 1
    db.commit()
    db.refresh(s)
    return _serialize_session(s)


def submit_qa(db: Session, tenant_id: str, session_id: int,
              question_id: int, answer: dict) -> dict:
    """提交问答答案"""
    s = _get_session(db, tenant_id, session_id)
    if s.status != "in_progress":
        raise ValidationError("会话已结束")
    answers = list(s.answers or [])
    answers = [a for a in answers if a.get("question_id") != question_id]
    answers.append({
        "question_id": question_id,
        "answer_text": answer.get("answer_text", ""),
        "audio_url": answer.get("audio_url"),
    })
    s.answers = answers
    db.commit()
    db.refresh(s)
    return _serialize_session(s)


def complete_session(db: Session, tenant_id: str, session_id: int) -> dict:
    """完成会话 — Mock AI 评审生成雷达评分与逐页点评"""
    s = _get_session(db, tenant_id, session_id)
    if s.status != "in_progress":
        raise ValidationError("会话已结束")
    sc = db.query(PracticeScenario).filter(
        PracticeScenario.id == s.scenario_id,
        PracticeScenario.tenant_id == tenant_id,
    ).first()
    dimensions = (sc.scoring_dimensions if sc else None) or DEFAULT_PPT_DIMENSIONS
    # Mock 评分：每维度 60~95 之间
    import random
    radar = {d["key"]: random.randint(65, 92) for d in dimensions}
    final_score = sum(radar.values()) // len(radar) if radar else 0
    # Mock 逐页点评
    recordings = s.per_page_recordings or []
    review_pages = []
    for r in recordings:
        review_pages.append({
            "page_no": r.get("page_no"),
            "score": random.randint(60, 95),
            "feedback": f"第{r.get('page_no')}页讲解{'流畅' if random.random() > 0.3 else '需加强'}，关键词覆盖{'充分' if random.random() > 0.4 else '不足'}。",
        })
    ai_review = json.dumps({
        "radar_scores": radar,
        "final_score": final_score,
        "page_reviews": review_pages,
        "summary": "整体表现稳定，建议加强临床数据页的关键词覆盖与转场衔接。",
    }, ensure_ascii=False)
    s.radar_scores = radar
    s.final_score = final_score
    s.ai_review = ai_review
    s.status = "completed"
    s.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(s)
    return _serialize_session(s)


def get_session(db: Session, tenant_id: str, session_id: int) -> dict:
    return _serialize_session(_get_session(db, tenant_id, session_id))


def list_sessions(db: Session, tenant_id: str, user_id: int = None,
                  scenario_id: int = None, status: str = None,
                  page_params: PageParams = None) -> dict:
    q = db.query(PPTSpeechSession).filter(
        PPTSpeechSession.tenant_id == tenant_id,
        PPTSpeechSession.is_deleted == 0,
    )
    if user_id:
        q = q.filter(PPTSpeechSession.user_id == user_id)
    if scenario_id:
        q = q.filter(PPTSpeechSession.scenario_id == scenario_id)
    if status:
        q = q.filter(PPTSpeechSession.status == status)
    total = q.count()
    q = q.order_by(PPTSpeechSession.id.desc())
    if page_params:
        q = q.offset(page_params.offset()).limit(page_params.effective_page_size())
    return paginate([_serialize_session(s) for s in q.all()], total, page_params or PageParams())


def _get_session(db: Session, tenant_id: str, session_id: int) -> PPTSpeechSession:
    s = db.query(PPTSpeechSession).filter(
        PPTSpeechSession.tenant_id == tenant_id,
        PPTSpeechSession.is_deleted == 0,
        PPTSpeechSession.id == session_id,
    ).first()
    if not s:
        raise NotFoundError("演讲会话不存在")
    return s


# ──────────────────────────────────────────────
# N+4 Batch 2.3: 7 维评分引擎
# ──────────────────────────────────────────────

# 7 个评分维度定义
SEVEN_DIMENSIONS = [
    ("content_accuracy", "内容准确性", 0.2),
    ("fluency", "表达流畅度", 0.15),
    ("logic_structure", "逻辑结构", 0.15),
    ("time_management", "时间管理", 0.1),
    ("interaction", "互动应对", 0.15),
    ("transition_recovery", "转场恢复", 0.1),
    ("conclusion", "总结升华", 0.15),
]


def score_session_7d(db: Session, session_id: int) -> dict:
    """7 维评分引擎

    维度：
    1. 内容准确性 (content_accuracy) - 0.2
    2. 表达流畅度 (fluency) - 0.15
    3. 逻辑结构 (logic_structure) - 0.15
    4. 时间管理 (time_management) - 0.1
    5. 互动应对 (interaction) - 0.15
    6. 转场恢复 (transition_recovery) - 0.1
    7. 总结升华 (conclusion) - 0.15

    Args:
        session_id: PPT 演讲会话 ID

    Returns:
        {dimensions: {dim: {score, feedback}}, total_score, passed}
    """
    s = _get_session(db, "default", session_id)

    # 基础信号：从 session 提取
    per_page_recordings = s.per_page_recordings or []
    questions = s.questions or []
    answers = s.answers or []

    # 完成页数
    completed_pages = len([r for r in per_page_recordings if r.get("transcript")])
    page_ratio = completed_pages / max(len(per_page_recordings), 1)

    # QA 互动
    qa_count = min(len(questions), len(answers))

    # transcript 长度信号
    transcript_chars = sum(
        len(r.get("transcript", "") or "")
        for r in per_page_recordings
    )

    # 各维度评分（启发式，可结合 LLM 升级）
    dimensions = {}

    # 1. 内容准确性：基于页数完成度
    acc_score = min(100, 50 + page_ratio * 50)
    dimensions["content_accuracy"] = {
        "score": round(acc_score, 1),
        "feedback": "内容覆盖完整" if page_ratio > 0.8 else "部分页面未覆盖，建议补全",
    }

    # 2. 表达流畅度：基于 transcript 长度
    fl_score = min(100, 40 + transcript_chars / 100)
    dimensions["fluency"] = {
        "score": round(fl_score, 1),
        "feedback": "表达流畅" if fl_score >= 70 else "可加强语气节奏",
    }

    # 3. 逻辑结构：基于页面覆盖均衡性
    logic_score = min(100, 60 + page_ratio * 40)
    dimensions["logic_structure"] = {
        "score": round(logic_score, 1),
        "feedback": "结构清晰" if logic_score >= 70 else "建议强化过渡衔接",
    }

    # 4. 时间管理：mock
    tm_score = 70.0 if transcript_chars > 0 else 50.0
    dimensions["time_management"] = {
        "score": tm_score,
        "feedback": "时间控制适中" if tm_score >= 60 else "需注意时间分配",
    }

    # 5. 互动应对：基于 QA 次数
    ia_score = min(100, 30 + qa_count * 15)
    dimensions["interaction"] = {
        "score": round(ia_score, 1),
        "feedback": "互动积极" if ia_score >= 70 else "可增加互动频次",
    }

    # 6. 转场恢复：mock
    tr_score = 65.0 if qa_count > 0 else 50.0
    dimensions["transition_recovery"] = {
        "score": tr_score,
        "feedback": "转场自然" if tr_score >= 60 else "可优化转场话术",
    }

    # 7. 总结升华：基于整体完成度
    cc_score = min(100, 50 + page_ratio * 30 + qa_count * 5)
    dimensions["conclusion"] = {
        "score": round(cc_score, 1),
        "feedback": "总结到位" if cc_score >= 70 else "建议增强总结的升华",
    }

    # 总分（加权）
    total = sum(
        dimensions[dim[0]]["score"] * dim[2]
        for dim in SEVEN_DIMENSIONS
    )

    # 写回 session（雷达评分 + 最终分数）
    try:
        s.radar_scores = {dim_key: dimensions[dim_key]["score"]
                          for dim_key, _, _ in SEVEN_DIMENSIONS}
        s.final_score = int(total)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "session_id": session_id,
        "dimensions": dimensions,
        "total_score": round(total, 1),
        "passed": total >= 60,
    }
