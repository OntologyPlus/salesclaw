"""数据采集 API - 项目/数据项/模板/待办"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.pagination import PageParams
from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import collection_service
from .schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ItemSubmitRequest,
    RejectRequest,
    TemplateCreateRequest,
    TodoBatchDeleteRequest,
)

router = APIRouter(prefix="/collection")


# ──────────────────────────────────────────────
# 项目管理
# ──────────────────────────────────────────────

@router.post("/projects")
async def create_project(
    req: ProjectCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建采集项目"""
    return unified_response(collection_service.create_project(db, user.tenant_id, req.model_dump()))


@router.get("/projects")
async def list_projects(
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """采集项目列表"""
    return unified_response(collection_service.list_projects(
        db, user.tenant_id, status, keyword, PageParams(page=page, page_size=page_size)
    ))


@router.get("/projects/{project_id}")
async def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """采集项目详情"""
    return unified_response(collection_service.get_project(db, user.tenant_id, project_id))


@router.put("/projects/{project_id}")
async def update_project(
    project_id: int,
    req: ProjectUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新采集项目"""
    return unified_response(collection_service.update_project(db, user.tenant_id, project_id, req.model_dump()))


@router.post("/projects/{project_id}/generate-items")
async def generate_items(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按项目 zone_ids 生成数据项"""
    count = collection_service.generate_items(db, user.tenant_id, project_id)
    return unified_response({"created": count})


@router.post("/projects/{project_id}/regenerate-todos")
async def regenerate_todos(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """重新生成项目待办"""
    count = collection_service.regenerate_todos(db, user.tenant_id, project_id)
    return unified_response({"created": count})


# ──────────────────────────────────────────────
# 数据项管理
# ──────────────────────────────────────────────

@router.get("/items")
async def list_items(
    project_id: int = Query(...),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """数据项列表"""
    return unified_response(collection_service.list_items(
        db, user.tenant_id, project_id, status, PageParams(page=page, page_size=page_size)
    ))


@router.get("/items/{item_id}")
async def get_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """数据项详情"""
    return unified_response(collection_service.get_item(db, user.tenant_id, item_id))


@router.post("/items/{item_id}/submit")
async def submit_item(
    item_id: int,
    req: ItemSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交数据项"""
    return unified_response(collection_service.submit_item(db, user.tenant_id, item_id, user.id, req.values))


@router.post("/items/{item_id}/withdraw")
async def withdraw_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """撤回数据项"""
    return unified_response(collection_service.withdraw_item(db, user.tenant_id, item_id, user.id))


@router.post("/items/{item_id}/approve")
async def approve_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批准数据项"""
    return unified_response(collection_service.approve_item(db, user.tenant_id, item_id, user.id))


@router.post("/items/{item_id}/reject")
async def reject_item(
    item_id: int,
    req: RejectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """驳回数据项"""
    return unified_response(collection_service.reject_item(db, user.tenant_id, item_id, user.id, req.reason))


@router.post("/items/{item_id}/lock")
async def lock_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """锁定数据项"""
    return unified_response(collection_service.lock_item(db, user.tenant_id, item_id))


@router.post("/items/{item_id}/publish")
async def publish_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发布数据项"""
    return unified_response(collection_service.publish_item(db, user.tenant_id, item_id))


@router.post("/items/{item_id}/unpublish")
async def unpublish_item(
    item_id: int,
    req: RejectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下架数据项"""
    return unified_response(collection_service.unpublish_item(db, user.tenant_id, item_id, req.reason))


# ──────────────────────────────────────────────
# 模板管理
# ──────────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """采集模板列表"""
    return unified_response(collection_service.list_templates(
        db, user.tenant_id, PageParams(page=page, page_size=page_size)
    ))


@router.post("/templates")
async def create_template(
    req: TemplateCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建采集模板"""
    return unified_response(collection_service.create_template(db, user.tenant_id, req.model_dump()))


# ──────────────────────────────────────────────
# 待办任务管理
# ──────────────────────────────────────────────

@router.get("/todos")
async def list_todos(
    project_id: Optional[int] = Query(None),
    assignee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """待办列表"""
    return unified_response(collection_service.list_todos(
        db, user.tenant_id, project_id, assignee_id, status,
        PageParams(page=page, page_size=page_size)
    ))


@router.get("/todos/{todo_id}")
async def get_todo(todo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """待办详情"""
    return unified_response(collection_service.get_todo(db, user.tenant_id, todo_id))


@router.get("/todos/{todo_id}/dialog")
async def get_todo_dialog(todo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查看待办 AI 对话记录"""
    return unified_response(collection_service.get_todo_dialog(db, user.tenant_id, todo_id))


@router.get("/todos/{todo_id}/submissions")
async def get_todo_submissions(todo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查看待办提交数据"""
    return unified_response(collection_service.get_todo_submissions(db, user.tenant_id, todo_id))


@router.post("/todos/batch-delete")
async def batch_delete_todos(
    req: TodoBatchDeleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量删除待办"""
    count = collection_service.delete_todos(db, user.tenant_id, req.todo_ids)
    return unified_response({"deleted": count})
