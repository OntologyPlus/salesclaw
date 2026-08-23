"""会议论坛服务层

提供会议/论坛总览、会议列表、论坛话题列表能力。
数据来源：Meeting + ForumTopic。
"""
from sqlalchemy.orm import Session

from database import Meeting, ForumTopic


# ──────────────────────────────────────────────
# CFM 总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str) -> dict:
    """CFM 总览：会议数、论坛话题数、即将开始的会议、热门话题"""
    meetings_count = db.query(Meeting).filter(
        Meeting.tenant_id == tenant_id,
        Meeting.is_deleted == 0,
    ).count()

    forums_count = db.query(ForumTopic).filter(
        ForumTopic.tenant_id == tenant_id,
        ForumTopic.is_deleted == 0,
    ).count()

    upcoming_meetings = db.query(Meeting).filter(
        Meeting.tenant_id == tenant_id,
        Meeting.is_deleted == 0,
        Meeting.status == "planned",
    ).order_by(Meeting.start_date.asc()).limit(5).all()

    hot_topics = db.query(ForumTopic).filter(
        ForumTopic.tenant_id == tenant_id,
        ForumTopic.is_deleted == 0,
    ).order_by(ForumTopic.views.desc()).limit(5).all()

    return {
        "meetings_count": meetings_count,
        "forums_count": forums_count,
        "upcoming_meetings": [_serialize_meeting(m) for m in upcoming_meetings],
        "hot_topics": [_serialize_topic(t) for t in hot_topics],
    }


# ──────────────────────────────────────────────
# 会议列表
# ──────────────────────────────────────────────

def get_meetings(db: Session, tenant_id: str, status: str = None, meeting_type: str = None,
                 page: int = 1, page_size: int = 20) -> dict:
    """会议列表：支持按状态、类型过滤"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(Meeting).filter(
        Meeting.tenant_id == tenant_id,
        Meeting.is_deleted == 0,
    )
    if status:
        q = q.filter(Meeting.status == status)
    if meeting_type:
        q = q.filter(Meeting.meeting_type == meeting_type)

    total = q.count()
    meetings = q.order_by(Meeting.start_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [_serialize_meeting(m) for m in meetings],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 论坛话题列表
# ──────────────────────────────────────────────

def get_topics(db: Session, tenant_id: str, category: str = None,
               page: int = 1, page_size: int = 20) -> dict:
    """论坛话题列表：支持按分类过滤"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(ForumTopic).filter(
        ForumTopic.tenant_id == tenant_id,
        ForumTopic.is_deleted == 0,
    )
    if category:
        q = q.filter(ForumTopic.category == category)

    total = q.count()
    topics = q.order_by(ForumTopic.is_pinned.desc(), ForumTopic.last_reply_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [_serialize_topic(t) for t in topics],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 序列化辅助
# ──────────────────────────────────────────────

def _serialize_meeting(m: Meeting) -> dict:
    return {
        "id": m.id,
        "title": m.title,
        "meeting_type": m.meeting_type,
        "status": m.status,
        "start_date": str(m.start_date) if m.start_date else None,
        "end_date": str(m.end_date) if m.end_date else None,
        "location": m.location,
        "organizer_id": m.organizer_id,
        "attendees_count": m.attendees_count,
        "description": m.description,
        "product_id": m.product_id,
        "hospital_id": m.hospital_id,
    }


def _serialize_topic(t: ForumTopic) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "content": t.content,
        "category": t.category,
        "author_id": t.author_id,
        "author_name": t.author_name,
        "views": t.views,
        "replies_count": t.replies_count,
        "is_pinned": t.is_pinned,
        "last_reply_at": t.last_reply_at.strftime("%Y-%m-%d %H:%M:%S") if t.last_reply_at else None,
    }


# ──────────────────────────────────────────────
# 会议 CRUD
# ──────────────────────────────────────────────

def _parse_date(s):
    """解析 YYYY-MM-DD 日期字符串"""
    if not s:
        return None
    from datetime import datetime as _dt
    try:
        return _dt.strptime(str(s), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def create_meeting(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """创建会议"""
    meeting = Meeting(
        tenant_id=tenant_id,
        title=data.get("title"),
        meeting_type=data.get("meeting_type", "academic"),
        status=data.get("status", "planned"),
        start_date=_parse_date(data.get("start_date")),
        end_date=_parse_date(data.get("end_date")),
        location=data.get("location"),
        organizer_id=data.get("organizer_id", user_id),
        attendees_count=data.get("attendees_count", 0),
        description=data.get("description"),
        product_id=data.get("product_id"),
        hospital_id=data.get("hospital_id"),
        created_by=user_id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize_meeting(meeting)


def update_meeting(db: Session, tenant_id: str, meeting_id: int, data: dict) -> dict:
    """更新会议"""
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.tenant_id == tenant_id,
        Meeting.is_deleted == 0,
    ).first()
    if not meeting:
        return None

    for field in ["title", "meeting_type", "status", "location", "description",
                  "attendees_count", "product_id", "hospital_id", "organizer_id"]:
        if field in data:
            setattr(meeting, field, data[field])
    if "start_date" in data:
        meeting.start_date = _parse_date(data["start_date"])
    if "end_date" in data:
        meeting.end_date = _parse_date(data["end_date"])

    db.commit()
    db.refresh(meeting)
    return _serialize_meeting(meeting)


def create_topic(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """发起论坛话题"""
    topic = ForumTopic(
        tenant_id=tenant_id,
        title=data.get("title"),
        content=data.get("content"),
        category=data.get("category", "general"),
        author_id=user_id,
        author_name=data.get("author_name"),
        created_by=user_id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)
