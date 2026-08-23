"""知识库服务层

提供知识文档管理、FAQ 检索能力。
支持按分类浏览、关键词搜索。
"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import KnowledgeDocument, FaqItem


# ──────────────────────────────────────────────
# 知识库总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str) -> dict:
    """知识库总览"""
    total_docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
        KnowledgeDocument.is_published == 1,
    ).count()
    total_faqs = db.query(FaqItem).filter(
        FaqItem.tenant_id == tenant_id, FaqItem.is_deleted == 0,
    ).count()
    total_views = func_sum_views(db, tenant_id)

    # 按分类统计
    categories = {}
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
        KnowledgeDocument.is_published == 1,
    ).all()
    for d in docs:
        cat = d.category or "other"
        categories[cat] = categories.get(cat, 0) + 1

    # 热门文档（按浏览数）
    hot_docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
        KnowledgeDocument.is_published == 1,
    ).order_by(KnowledgeDocument.view_count.desc()).limit(5).all()

    # 最新 FAQ
    recent_faqs = db.query(FaqItem).filter(
        FaqItem.tenant_id == tenant_id, FaqItem.is_deleted == 0,
    ).order_by(FaqItem.view_count.desc(), FaqItem.sort_order.asc()).limit(5).all()

    return {
        "documents_count": total_docs,
        "faqs_count": total_faqs,
        "total_views": total_views,
        "categories": [{"key": k, "count": v} for k, v in sorted(categories.items(), key=lambda x: -x[1])],
        "hot_documents": [_document_to_dict(d) for d in hot_docs],
        "recent_faqs": [_faq_to_dict(f) for f in recent_faqs],
    }


# ──────────────────────────────────────────────
# 知识文档
# ──────────────────────────────────────────────

def get_documents(db: Session, tenant_id: str, category: str = None,
                  keyword: str = None, page: int = 1, page_size: int = 20) -> dict:
    """获取知识文档列表"""
    q = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
        KnowledgeDocument.is_published == 1,
    )
    if category and category != "all":
        q = q.filter(KnowledgeDocument.category == category)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(
            KnowledgeDocument.title.ilike(kw),
            KnowledgeDocument.summary.ilike(kw),
            KnowledgeDocument.tags.ilike(kw),
            KnowledgeDocument.content.ilike(kw),
        ))
    total = q.count()
    docs = q.order_by(KnowledgeDocument.view_count.desc(), KnowledgeDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_document_to_dict(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_document(db: Session, tenant_id: str, doc_id: int) -> dict:
    """获取文档详情（增加浏览数）"""
    d = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
        KnowledgeDocument.id == doc_id,
    ).first()
    if not d:
        return None
    d.view_count = (d.view_count or 0) + 1
    db.commit()
    db.refresh(d)
    return _document_to_dict(d, include_content=True)


def create_document(db: Session, tenant_id: str, author_id: int, author_name: str, data: dict) -> dict:
    """创建知识文档"""
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        title=data.get("title", ""),
        category=data.get("category", "other"),
        content=data.get("content"),
        summary=data.get("summary"),
        tags=data.get("tags"),
        author_id=author_id,
        author_name=author_name,
        view_count=0,
        is_published=data.get("is_published", 1),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _document_to_dict(doc)


# ──────────────────────────────────────────────
# FAQ
# ──────────────────────────────────────────────

def get_faqs(db: Session, tenant_id: str, category: str = None,
             keyword: str = None, page: int = 1, page_size: int = 20) -> dict:
    """获取 FAQ 列表"""
    q = db.query(FaqItem).filter(
        FaqItem.tenant_id == tenant_id, FaqItem.is_deleted == 0,
    )
    if category and category != "all":
        q = q.filter(FaqItem.category == category)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(
            FaqItem.question.ilike(kw),
            FaqItem.answer.ilike(kw),
        ))
    total = q.count()
    faqs = q.order_by(FaqItem.sort_order.asc(), FaqItem.view_count.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_faq_to_dict(f) for f in faqs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_faq(db: Session, tenant_id: str, faq_id: int) -> dict:
    """获取 FAQ 详情（增加浏览数）"""
    f = db.query(FaqItem).filter(
        FaqItem.tenant_id == tenant_id, FaqItem.is_deleted == 0, FaqItem.id == faq_id,
    ).first()
    if not f:
        return None
    f.view_count = (f.view_count or 0) + 1
    db.commit()
    db.refresh(f)
    return _faq_to_dict(f)


# ──────────────────────────────────────────────
# 搜索
# ──────────────────────────────────────────────

def search(db: Session, tenant_id: str, keyword: str, page: int = 1, page_size: int = 20) -> dict:
    """全局搜索：文档 + FAQ"""
    kw = f"%{keyword}%"
    docs_q = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
        KnowledgeDocument.is_published == 1,
        or_(
            KnowledgeDocument.title.ilike(kw),
            KnowledgeDocument.summary.ilike(kw),
            KnowledgeDocument.tags.ilike(kw),
        ),
    )
    faqs_q = db.query(FaqItem).filter(
        FaqItem.tenant_id == tenant_id, FaqItem.is_deleted == 0,
        or_(FaqItem.question.ilike(kw), FaqItem.answer.ilike(kw)),
    )
    docs = docs_q.order_by(KnowledgeDocument.view_count.desc()).limit(page_size).all()
    faqs = faqs_q.order_by(FaqItem.view_count.desc()).limit(page_size).all()
    return {
        "documents": [_document_to_dict(d) for d in docs],
        "faqs": [_faq_to_dict(f) for f in faqs],
        "documents_total": docs_q.count(),
        "faqs_total": faqs_q.count(),
        "keyword": keyword,
    }


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def func_sum_views(db: Session, tenant_id: str) -> int:
    """汇总文档浏览数"""
    from sqlalchemy import func
    return db.query(func.sum(KnowledgeDocument.view_count)).filter(
        KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == 0,
    ).scalar() or 0


def _document_to_dict(d: KnowledgeDocument, include_content: bool = False) -> dict:
    result = {
        "id": d.id,
        "title": d.title,
        "category": d.category,
        "summary": d.summary,
        "tags": d.tags.split(",") if d.tags else [],
        "author_name": d.author_name,
        "view_count": d.view_count,
        "is_published": d.is_published,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
    if include_content:
        result["content"] = d.content
    return result


def _faq_to_dict(f: FaqItem) -> dict:
    return {
        "id": f.id,
        "question": f.question,
        "answer": f.answer,
        "category": f.category,
        "sort_order": f.sort_order,
        "view_count": f.view_count,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
