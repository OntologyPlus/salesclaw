"""知识库 API - 知识文档、FAQ、智能检索"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user, require_permission
from database import User, Role, get_db
from services import knowledge_service
from .schemas import DocumentCreateRequest

router = APIRouter(prefix="/knowledge")


def _resolve_role_code(user: User, db) -> str:
    """从 user.role_id 联查 roles 表解析真实 role_code。

    注意：User 模型只有 role_id，没有 role_code 字段，此前用
    `getattr(user, "role_code", None) or "admin"` 会永远回退到 admin，
    造成任意登录用户被提权。这里改为正确联查，并默认最小权限 sales_rep。
    """
    if user.role_id:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if role and role.code:
            return role.code
    return "sales_rep"


# ──────────────────────────────────────────────
# 总览
# ──────────────────────────────────────────────

@router.get("/overview")
async def overview(user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    """知识库总览"""
    return unified_response(knowledge_service.get_overview(db, user.tenant_id))


# ──────────────────────────────────────────────
# 知识文档
# ──────────────────────────────────────────────

@router.get("/documents")
async def list_documents(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """知识文档列表"""
    return unified_response(knowledge_service.get_documents(db, user.tenant_id, category, keyword, page, page_size))


@router.get("/documents/{doc_id}")
async def get_document(doc_id: int, user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    """文档详情"""
    result = knowledge_service.get_document(db, user.tenant_id, doc_id)
    if not result:
        return unified_response(code=404, message="文档不存在")
    return unified_response(result)


@router.post("/documents")
async def create_document(req: DocumentCreateRequest, user: User = Depends(require_permission("knowledge.write")), db: Session = Depends(get_db)):
    """创建知识文档"""
    author_name = user.display_name or user.username
    return unified_response(knowledge_service.create_document(db, user.tenant_id, user.id, author_name, req.model_dump()))


# ──────────────────────────────────────────────
# FAQ
# ──────────────────────────────────────────────

@router.get("/faqs")
async def list_faqs(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """FAQ 列表"""
    return unified_response(knowledge_service.get_faqs(db, user.tenant_id, category, keyword, page, page_size))


@router.get("/faqs/{faq_id}")
async def get_faq(faq_id: int, user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    """FAQ 详情"""
    result = knowledge_service.get_faq(db, user.tenant_id, faq_id)
    if not result:
        return unified_response(code=404, message="FAQ 不存在")
    return unified_response(result)


# ──────────────────────────────────────────────
# 搜索
# ──────────────────────────────────────────────

@router.get("/search")
async def search(
    keyword: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """全局搜索：文档 + FAQ"""
    return unified_response(knowledge_service.search(db, user.tenant_id, keyword, page, page_size))


@router.post("/ai-insights")
async def knowledge_ai_insights(
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """AI 知识库洞察（查询预生成缓存）"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="knowledge", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)


# ──────────────────────────────────────────────
# F7: 知识蒸馏 + 人审发布（借鉴诊断体系 §8.1-8.3）
# ──────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import List


class ReviewItemRequest(BaseModel):
    decision: str = Field(..., description="approve/reject/request_revision")
    comment: Optional[str] = None


class SearchKnowledgeRequest(BaseModel):
    query: str = Field(..., description="检索关键词")
    category: Optional[str] = None
    limit: int = Field(10, ge=1, le=50)


@router.post("/distill/run")
async def run_distill(
    user: User = Depends(require_permission("knowledge.write")),
    db: Session = Depends(get_db),
    case_limit: int = Query(20, ge=1, le=100),
):
    """触发蒸馏流程：提取闭环案例 → LLM 蒸馏 → 去重 → 提交人审"""
    from services import knowledge_distill_service
    # 尝试获取 LLM client（可选）
    llm_client = None
    try:
        from ai.llm_client import llm_client as _lc
        llm_client = _lc
    except Exception:
        pass
    result = knowledge_distill_service.run_distill_pipeline(
        db, user.tenant_id, llm_client=llm_client, case_limit=case_limit,
    )
    return unified_response(result)


@router.get("/distill/candidates")
async def list_distill_candidates(
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """列出待审核候选知识项"""
    from services import knowledge_distill_service
    # 获取用户角色
    role = _resolve_role_code(user, db)
    return unified_response(
        knowledge_distill_service.list_candidates(db, user.tenant_id, role, limit)
    )


@router.get("/items")
async def list_knowledge_items(
    category: Optional[str] = Query(None, description="按类别过滤：rule/case/experience/discussion/trend"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """列出已发布知识项（带权限过滤）"""
    from services import knowledge_distill_service
    role = _resolve_role_code(user, db)
    return unified_response(
        knowledge_distill_service.list_items(db, user.tenant_id, role, category, limit)
    )


@router.get("/items/{item_id}")
async def get_knowledge_item(
    item_id: int,
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """查询单条知识项"""
    from services import knowledge_distill_service
    role = _resolve_role_code(user, db)
    return unified_response(
        knowledge_distill_service.get_item(db, user.tenant_id, item_id, role)
    )


@router.post("/items/{item_id}/review")
async def review_knowledge_item(
    item_id: int,
    body: ReviewItemRequest,
    user: User = Depends(require_permission("knowledge.write")),
    db: Session = Depends(get_db),
):
    """人审决策：approve / reject / request_revision"""
    from services import knowledge_distill_service
    return unified_response(
        knowledge_distill_service.review_item(
            db, user.tenant_id, item_id, user.id, body.decision, body.comment or "",
        )
    )


@router.post("/items/{item_id}/publish")
async def publish_knowledge_item(
    item_id: int,
    user: User = Depends(require_permission("knowledge.write")),
    db: Session = Depends(get_db),
):
    """发布知识项（仅 approved 状态可发布，且仅 admin/compliance_officer 可操作）"""
    from services import knowledge_distill_service
    role = _resolve_role_code(user, db)
    if role not in ("admin", "compliance_officer"):
        from core.exceptions import ValidationError
        raise ValidationError("仅 admin 或 compliance_officer 可发布知识项")
    return unified_response(
        knowledge_distill_service.publish_item(db, user.tenant_id, item_id, user.id)
    )


@router.post("/search")
async def search_knowledge(
    body: SearchKnowledgeRequest,
    user: User = Depends(require_permission("knowledge.read")),
    db: Session = Depends(get_db),
):
    """TF-IDF 语义检索（带权限过滤）"""
    from services import knowledge_distill_service
    role = _resolve_role_code(user, db)
    return unified_response(
        knowledge_distill_service.search_items(
            db, user.tenant_id, body.query, role, body.category, body.limit,
        )
    )
