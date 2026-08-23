"""数据采集引擎服务层

提供数据采集项目管理、数据项状态机、模板管理、项目待办任务能力。
状态机: pending_edit → edited → pending_review → reviewed → locked → published
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, ValidationError, DataConflictError
from core.pagination import PageParams, paginate
from database import (
    CollectionProject, CollectionTemplate, CollectionItem, ProjectTodo,
    ChatSession, ChatMessage, Zone, User,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _fmt(dt) -> str:
    """格式化日期时间"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _compute_period_code(period_type: str, dt: datetime = None) -> str:
    """根据周期类型计算 period_code"""
    dt = dt or datetime.utcnow()
    if period_type == "daily":
        return dt.strftime("%Y-%m-%d")
    elif period_type == "weekly":
        return dt.strftime("%Y-W%U")
    elif period_type == "monthly":
        return dt.strftime("%Y-%m")
    elif period_type == "quarterly":
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}"
    elif period_type == "yearly":
        return dt.strftime("%Y")
    return None  # once


# ──────────────────────────────────────────────
# 序列化
# ──────────────────────────────────────────────

def _serialize_project(p: CollectionProject) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "project_type": p.project_type,
        "period_type": p.period_type,
        "status": p.status,
        "zone_ids": p.zone_ids or [],
        "template_id": p.template_id,
        "related_project_id": p.related_project_id,
        "started_at": _fmt(p.started_at),
        "ended_at": _fmt(p.ended_at),
        "created_at": _fmt(p.created_at),
        "updated_at": _fmt(p.updated_at),
    }


def _serialize_item(i: CollectionItem) -> dict:
    return {
        "id": i.id,
        "project_id": i.project_id,
        "template_id": i.template_id,
        "zone_id": i.zone_id,
        "period_code": i.period_code,
        "submitter_id": i.submitter_id,
        "reviewer_id": i.reviewer_id,
        "status": i.status,
        "values": i.values or {},
        "submitted_at": _fmt(i.submitted_at),
        "reviewed_at": _fmt(i.reviewed_at),
        "review_comment": i.review_comment,
        "locked_at": _fmt(i.locked_at),
        "published_at": _fmt(i.published_at),
        "created_at": _fmt(i.created_at),
        "updated_at": _fmt(i.updated_at),
    }


def _serialize_template(t: CollectionTemplate) -> dict:
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "fields": t.fields or [],
        "version": t.version,
        "is_active": t.is_active,
        "created_at": _fmt(t.created_at),
    }


def _serialize_todo(t: ProjectTodo) -> dict:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "item_id": t.item_id,
        "zone_id": t.zone_id,
        "assignee_id": t.assignee_id,
        "period_code": t.period_code,
        "status": t.status,
        "edit_mode": t.edit_mode,
        "dialog_session_id": t.dialog_session_id,
        "submitted_at": _fmt(t.submitted_at),
        "submit_data": t.submit_data or {},
        "created_at": _fmt(t.created_at),
        "updated_at": _fmt(t.updated_at),
    }


# ──────────────────────────────────────────────
# 项目管理
# ──────────────────────────────────────────────

def create_project(db: Session, tenant_id: str, data: dict) -> dict:
    """创建采集项目"""
    if not data.get("code"):
        raise ValidationError("code 不能为空")
    if not data.get("name"):
        raise ValidationError("name 不能为空")
    project = CollectionProject(
        tenant_id=tenant_id,
        code=data["code"],
        name=data["name"],
        project_type=data.get("project_type", "plan"),
        period_type=data.get("period_type", "monthly"),
        status=data.get("status", "draft"),
        zone_ids=data.get("zone_ids") or [],
        template_id=data.get("template_id"),
        related_project_id=data.get("related_project_id"),
        started_at=data.get("started_at"),
        ended_at=data.get("ended_at"),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _serialize_project(project)


def list_projects(db: Session, tenant_id: str, status: str = None,
                  keyword: str = None, page_params: PageParams = None) -> dict:
    """列表查询采集项目"""
    q = db.query(CollectionProject).filter(
        CollectionProject.tenant_id == tenant_id,
        CollectionProject.is_deleted == 0,
    )
    if status:
        q = q.filter(CollectionProject.status == status)
    if keyword:
        q = q.filter(CollectionProject.name.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(CollectionProject.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(CollectionProject.id.desc())
    projects = q.all()
    items = [_serialize_project(p) for p in projects]
    return paginate(items, total, page_params or PageParams())


def get_project(db: Session, tenant_id: str, project_id: int) -> dict:
    """获取采集项目详情"""
    project = db.query(CollectionProject).filter(
        CollectionProject.tenant_id == tenant_id,
        CollectionProject.is_deleted == 0,
        CollectionProject.id == project_id,
    ).first()
    if not project:
        raise NotFoundError("采集项目不存在")
    return _serialize_project(project)


def update_project(db: Session, tenant_id: str, project_id: int, data: dict) -> dict:
    """更新采集项目"""
    project = db.query(CollectionProject).filter(
        CollectionProject.tenant_id == tenant_id,
        CollectionProject.is_deleted == 0,
        CollectionProject.id == project_id,
    ).first()
    if not project:
        raise NotFoundError("采集项目不存在")
    for field in ["code", "name", "project_type", "period_type", "status",
                  "zone_ids", "template_id", "related_project_id", "started_at", "ended_at"]:
        if field in data and data[field] is not None:
            setattr(project, field, data[field])
    db.commit()
    db.refresh(project)
    return _serialize_project(project)


def generate_items(db: Session, tenant_id: str, project_id: int) -> int:
    """按项目 zone_ids 生成数据项

    对每个 zone_id 生成一条 CollectionItem，若同周期已存在则跳过。
    """
    project = db.query(CollectionProject).filter(
        CollectionProject.tenant_id == tenant_id,
        CollectionProject.is_deleted == 0,
        CollectionProject.id == project_id,
    ).first()
    if not project:
        raise NotFoundError("采集项目不存在")
    zone_ids = project.zone_ids or []
    if not zone_ids:
        raise ValidationError("项目未配置 zone_ids")
    period_code = _compute_period_code(project.period_type)
    created = 0
    for zone_id in zone_ids:
        existing_q = db.query(CollectionItem).filter(
            CollectionItem.tenant_id == tenant_id,
            CollectionItem.is_deleted == 0,
            CollectionItem.project_id == project_id,
            CollectionItem.zone_id == zone_id,
        )
        if period_code:
            existing_q = existing_q.filter(CollectionItem.period_code == period_code)
        if existing_q.first():
            continue
        item = CollectionItem(
            tenant_id=tenant_id,
            project_id=project_id,
            template_id=project.template_id,
            zone_id=zone_id,
            period_code=period_code,
            status="pending_edit",
            values={},
        )
        db.add(item)
        created += 1
    db.commit()
    return created


# ──────────────────────────────────────────────
# 数据项管理（状态机）
# pending_edit → edited → pending_review → reviewed → locked → published
# ──────────────────────────────────────────────

def list_items(db: Session, tenant_id: str, project_id: int,
               status: str = None, page_params: PageParams = None) -> dict:
    """列表查询数据项"""
    q = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.project_id == project_id,
    )
    if status:
        q = q.filter(CollectionItem.status == status)
    total = q.count()
    if page_params:
        q = q.order_by(CollectionItem.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(CollectionItem.id.desc())
    items = q.all()
    return paginate([_serialize_item(i) for i in items], total, page_params or PageParams())


def get_item(db: Session, tenant_id: str, item_id: int) -> dict:
    """获取数据项详情"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    return _serialize_item(item)


def submit_item(db: Session, tenant_id: str, item_id: int,
                user_id: int, values: dict) -> dict:
    """提交数据项: pending_edit/edited → pending_review"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status not in ("pending_edit", "edited"):
        raise ValidationError(f"当前状态 {item.status} 不允许提交，仅 pending_edit/edited 可提交")
    item.status = "pending_review"
    item.values = values or {}
    item.submitter_id = user_id
    item.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def withdraw_item(db: Session, tenant_id: str, item_id: int, user_id: int) -> dict:
    """撤回数据项: pending_review → edited"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status != "pending_review":
        raise ValidationError(f"当前状态 {item.status} 不允许撤回，仅 pending_review 可撤回")
    item.status = "edited"
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def approve_item(db: Session, tenant_id: str, item_id: int, reviewer_id: int) -> dict:
    """批准数据项: pending_review → reviewed"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status != "pending_review":
        raise ValidationError(f"当前状态 {item.status} 不允许批准，仅 pending_review 可批准")
    item.status = "reviewed"
    item.reviewer_id = reviewer_id
    item.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def reject_item(db: Session, tenant_id: str, item_id: int,
                reviewer_id: int, reason: str) -> dict:
    """驳回数据项: pending_review → edited"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status != "pending_review":
        raise ValidationError(f"当前状态 {item.status} 不允许驳回，仅 pending_review 可驳回")
    item.status = "edited"
    item.reviewer_id = reviewer_id
    item.reviewed_at = datetime.utcnow()
    item.review_comment = reason
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def lock_item(db: Session, tenant_id: str, item_id: int) -> dict:
    """锁定数据项: reviewed → locked"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status != "reviewed":
        raise ValidationError(f"当前状态 {item.status} 不允许锁定，仅 reviewed 可锁定")
    item.status = "locked"
    item.locked_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def publish_item(db: Session, tenant_id: str, item_id: int) -> dict:
    """发布数据项: locked → published

    N+4 Batch 2.2 升级：发布前执行规则引擎
    1. validate_item_values（error 阻断）
    2. compute_derived_fields（自动派生）
    3. check_cross_field_rules（仅警告）
    4. apply_ability_impact（回写画像）
    5. record_lineage（数据流追踪）
    """
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status != "locked":
        raise ValidationError(f"当前状态 {item.status} 不允许发布，仅 locked 可发布")

    # N+4: 规则引擎执行
    violations = validate_item_values(db, tenant_id, item_id)
    blocking = [v for v in violations if v.get("level") == "error"]
    if blocking:
        msgs = "; ".join(f"{v.get('field', '?')}: {v.get('message', '')}" for v in blocking)
        raise ValidationError(f"校验未通过，拒绝发布: {msgs}")

    # 派生字段计算
    compute_derived_fields(db, tenant_id, item_id)

    # 回写画像（通过 ProfileServicePort，不直接 import）
    apply_ability_impact(db, tenant_id, item_id)

    # 记录 lineage
    try:
        from core.service_registry import registry
        from core.service_ports import DataLineageServicePort
        lineage_svc = registry.get(DataLineageServicePort)
        if lineage_svc is not None and item.submitter_id:
            lineage_svc.record_lineage(
                db,
                source={"type": "collection", "id": item_id},
                target={"type": "kpi", "id": None, "field": "collection_published"},
                transformation="collection_published",
                user_id=item.submitter_id,
                tenant_id=tenant_id,
            )
    except Exception:
        pass

    item.status = "published"
    item.published_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    # 发布事件（Batch 3.1 监听）
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            "collection_item_published",
            {"item_id": item_id, "user_id": item.submitter_id, "tenant_id": tenant_id},
            tenant_id=tenant_id,
            consistency="eventual",
            affected_domains=["profile", "training"],
        )
    except Exception:
        pass

    return _serialize_item(item)


# ──────────────────────────────────────────────
# N+4 Batch 2.2: 采集域规则引擎
# 实现 CollectionServicePort：validate_item_values / compute_derived_fields /
#   check_cross_field_rules / apply_ability_impact
# 跨域调用通过 registry.get(CollectionServicePort) 调用本组函数。
# ──────────────────────────────────────────────

def validate_item_values(db: Session, tenant_id: str, item_id: int) -> list:
    """字段级校验 + 跨字段规则

    Returns:
        [{field, rule, message, level}]，level='error' 时拒绝提交，'warning' 仅提示
    """
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        return [{"field": "_", "rule": "not_found", "message": "数据项不存在", "level": "error"}]

    template = None
    if item.template_id:
        template = db.query(CollectionTemplate).filter(
            CollectionTemplate.id == item.template_id,
            CollectionTemplate.is_deleted == 0,
        ).first()

    violations = []
    values = item.values or {}

    # 1. 字段级校验
    if template and template.fields:
        for field in template.fields:
            key = field.get("key")
            if not key:
                continue
            val = values.get(key)
            # required 校验
            if field.get("required") and (val is None or val == ""):
                violations.append({
                    "field": key, "rule": "required",
                    "message": f"{field.get('label', key)} 为必填项",
                    "level": "error",
                })
                continue
            if val is None or val == "":
                continue
            # 数值范围校验
            if field.get("type") == "number":
                try:
                    num_val = float(val)
                    if "min" in field and num_val < field["min"]:
                        violations.append({
                            "field": key, "rule": "min",
                            "message": f"{field.get('label', key)} 不能小于 {field['min']}",
                            "level": "error",
                        })
                    if "max" in field and num_val > field["max"]:
                        violations.append({
                            "field": key, "rule": "max",
                            "message": f"{field.get('label', key)} 不能大于 {field['max']}",
                            "level": "error",
                        })
                except (ValueError, TypeError):
                    violations.append({
                        "field": key, "rule": "type",
                        "message": f"{field.get('label', key)} 必须为数字",
                        "level": "error",
                    })

    # 2. 跨字段规则
    if template and template.rules_json:
        rules = template.rules_json.get("cross_field_rules", []) or []
        violations.extend(check_cross_field_rules(values, rules))

    return violations


def compute_derived_fields(db: Session, tenant_id: str, item_id: int) -> dict:
    """派生字段自动计算（如 avg_visit_per_doctor = visits_count / unique_doctors_count）

    Returns:
        {field: value} 计算出的派生字段
    """
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item or not item.template_id:
        return {}

    template = db.query(CollectionTemplate).filter(
        CollectionTemplate.id == item.template_id,
        CollectionTemplate.is_deleted == 0,
    ).first()
    if not template or not template.rules_json:
        return {}

    derived_rules = template.rules_json.get("derived_fields", []) or []
    values = dict(item.values or {})
    derived = {}

    for rule in derived_rules:
        key = rule.get("key")
        formula = rule.get("formula")
        if not key or not formula:
            continue
        try:
            # 安全求值：仅支持字段名 + 算术运算
            val = _safe_arithmetic(formula, values)
            if val is not None:
                derived[key] = val
                values[key] = val
        except Exception:
            continue

    if derived:
        # 写回 item.values
        item.values = values
        db.commit()

    return derived


def check_cross_field_rules(values: dict, rules: list) -> list:
    """跨字段规则校验（独立纯函数）

    Args:
        values: 字段值 dict
        rules: 规则列表 [{name, when, warning}]

    Returns:
        [{rule, warning, level}]（level 始终为 'warning'）
    """
    violations = []
    for rule in rules or []:
        try:
            if _safe_eval(rule.get("when", "False"), values):
                violations.append({
                    "rule": rule.get("name", "unnamed"),
                    "warning": rule.get("warning", ""),
                    "level": "warning",
                })
        except Exception:
            continue
    return violations


def apply_ability_impact(db: Session, tenant_id: str, item_id: int) -> dict:
    """发布后回写画像 — 通过 registry.get(ProfileServicePort) 调用，不直接 import

    Returns:
        {applied: int, skipped: int} 或 {ok=False, error}
    """
    from core.service_registry import registry
    from core.service_ports import ProfileServicePort

    profile_svc = registry.get(ProfileServicePort)
    if profile_svc is None:
        return {"ok": False, "error": "ProfileService 未注册"}

    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item or not item.submitter_id or not item.template_id:
        return {"ok": False, "error": "数据项缺少 submitter 或 template"}

    template = db.query(CollectionTemplate).filter(
        CollectionTemplate.id == item.template_id,
        CollectionTemplate.is_deleted == 0,
    ).first()
    if not template or not template.rules_json:
        return {"ok": True, "applied": 0, "skipped": 0, "reason": "无 ability_impact 规则"}

    impacts = template.rules_json.get("ability_impact", []) or []
    applied = 0
    skipped = 0
    values = item.values or {}

    for impact in impacts:
        key = impact.get("key")
        dimension = impact.get("dimension")
        weight = impact.get("weight", 0.5)
        if not key or not dimension:
            skipped += 1
            continue
        val = values.get(key)
        if val is None:
            skipped += 1
            continue
        try:
            # 以字段值 * weight 作为 delta
            delta = float(val) * weight
            profile_svc.update_ability_score(
                db, item.submitter_id, dimension, delta,
                source="collection", source_id=item_id,
                evidence={"field": key, "value": val, "weight": weight},
                tenant_id=tenant_id,
            )
            applied += 1
        except Exception:
            skipped += 1

    return {"ok": True, "applied": applied, "skipped": skipped}


def _safe_eval(expr: str, context: dict) -> bool:
    """受限表达式求值（仅支持字段名 + 数字 + 比较运算）

    用于 cross_field_rules 的 when 表达式，如 "achievement_rate < 60"
    """
    import ast
    allowed_nodes = (
        ast.Expression, ast.BoolOp, ast.Compare, ast.Name,
        ast.Constant, ast.And, ast.Or,
        ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
    )
    tree = ast.parse(expr, mode='eval')
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"不允许的表达式节点: {type(node).__name__}")
    return bool(eval(compile(tree, '<rule>', 'eval'), {"__builtins__": {}}, context))


def _safe_arithmetic(formula: str, context: dict):
    """受限算术求值（支持字段名 + 数字 + 算术运算符）

    用于派生字段计算，如 "visits_count / unique_doctors_count"
    """
    import ast
    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.Name, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    )
    tree = ast.parse(formula, mode='eval')
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"不允许的表达式节点: {type(node).__name__}")
    try:
        return eval(compile(tree, '<formula>', 'eval'), {"__builtins__": {}}, context)
    except (ZeroDivisionError, TypeError, NameError):
        return None


def unpublish_item(db: Session, tenant_id: str, item_id: int, reason: str) -> dict:
    """下架数据项: published → edited"""
    item = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError("数据项不存在")
    if item.status != "published":
        raise ValidationError(f"当前状态 {item.status} 不允许下架，仅 published 可下架")
    item.status = "edited"
    item.review_comment = reason
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


# ──────────────────────────────────────────────
# 模板管理
# ──────────────────────────────────────────────

def list_templates(db: Session, tenant_id: str, page_params: PageParams = None) -> dict:
    """列表查询采集模板"""
    q = db.query(CollectionTemplate).filter(
        CollectionTemplate.tenant_id == tenant_id,
        CollectionTemplate.is_deleted == 0,
    )
    total = q.count()
    if page_params:
        q = q.order_by(CollectionTemplate.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(CollectionTemplate.id.desc())
    templates = q.all()
    return paginate([_serialize_template(t) for t in templates], total, page_params or PageParams())


def create_template(db: Session, tenant_id: str, data: dict) -> dict:
    """创建采集模板"""
    if not data.get("code"):
        raise ValidationError("code 不能为空")
    if not data.get("name"):
        raise ValidationError("name 不能为空")
    template = CollectionTemplate(
        tenant_id=tenant_id,
        code=data["code"],
        name=data["name"],
        fields=data.get("fields") or [],
        version=data.get("version", 1),
        is_active=data.get("is_active", 1),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _serialize_template(template)


# ──────────────────────────────────────────────
# 待办任务管理
# ──────────────────────────────────────────────

def list_todos(db: Session, tenant_id: str, project_id: int = None,
               assignee_id: int = None, status: str = None,
               page_params: PageParams = None) -> dict:
    """列表查询项目待办"""
    q = db.query(ProjectTodo).filter(
        ProjectTodo.tenant_id == tenant_id,
        ProjectTodo.is_deleted == 0,
    )
    if project_id:
        q = q.filter(ProjectTodo.project_id == project_id)
    if assignee_id:
        q = q.filter(ProjectTodo.assignee_id == assignee_id)
    if status:
        q = q.filter(ProjectTodo.status == status)
    total = q.count()
    if page_params:
        q = q.order_by(ProjectTodo.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(ProjectTodo.id.desc())
    todos = q.all()
    return paginate([_serialize_todo(t) for t in todos], total, page_params or PageParams())


def get_todo(db: Session, tenant_id: str, todo_id: int) -> dict:
    """获取待办详情"""
    todo = db.query(ProjectTodo).filter(
        ProjectTodo.tenant_id == tenant_id,
        ProjectTodo.is_deleted == 0,
        ProjectTodo.id == todo_id,
    ).first()
    if not todo:
        raise NotFoundError("待办任务不存在")
    return _serialize_todo(todo)


def get_todo_dialog(db: Session, tenant_id: str, todo_id: int) -> dict:
    """反查 AI 对话记录: ChatSession + ChatMessage"""
    todo = db.query(ProjectTodo).filter(
        ProjectTodo.tenant_id == tenant_id,
        ProjectTodo.is_deleted == 0,
        ProjectTodo.id == todo_id,
    ).first()
    if not todo:
        raise NotFoundError("待办任务不存在")
    session_id = todo.dialog_session_id
    if not session_id:
        return {"todo_id": todo_id, "session": None, "messages": []}
    session = db.query(ChatSession).filter(
        ChatSession.tenant_id == tenant_id,
        ChatSession.is_deleted == 0,
        ChatSession.id == session_id,
    ).first()
    messages = db.query(ChatMessage).filter(
        ChatMessage.tenant_id == tenant_id,
        ChatMessage.is_deleted == 0,
        ChatMessage.session_id == session_id,
    ).order_by(ChatMessage.ts.asc()).all()
    return {
        "todo_id": todo_id,
        "session": {
            "id": session.id,
            "title": session.title,
            "agent_name": session.agent_name,
            "status": session.status,
            "created_at": _fmt(session.created_at),
        } if session else None,
        "messages": [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "meta": m.meta or {},
            "ts": _fmt(m.ts),
        } for m in messages],
    }


def get_todo_submissions(db: Session, tenant_id: str, todo_id: int) -> dict:
    """查看待办提交数据"""
    todo = db.query(ProjectTodo).filter(
        ProjectTodo.tenant_id == tenant_id,
        ProjectTodo.is_deleted == 0,
        ProjectTodo.id == todo_id,
    ).first()
    if not todo:
        raise NotFoundError("待办任务不存在")
    return {
        "todo_id": todo_id,
        "status": todo.status,
        "submit_data": todo.submit_data or {},
        "submitted_at": _fmt(todo.submitted_at),
    }


def delete_todos(db: Session, tenant_id: str, todo_ids: list) -> int:
    """批量删除待办: 仅 pending 可删"""
    if not todo_ids:
        return 0
    todos = db.query(ProjectTodo).filter(
        ProjectTodo.tenant_id == tenant_id,
        ProjectTodo.is_deleted == 0,
        ProjectTodo.id.in_(todo_ids),
    ).all()
    deleted = 0
    for t in todos:
        if t.status != "pending":
            raise ValidationError(f"待办 {t.id} 状态为 {t.status}，仅 pending 可删除")
        t.is_deleted = 1
        t.deleted_at = datetime.utcnow()
        deleted += 1
    db.commit()
    return deleted


def regenerate_todos(db: Session, tenant_id: str, project_id: int) -> int:
    """重新生成待办: 删 pending + 重新生成

    1. 软删除项目下所有 pending 待办
    2. 查询 pending_edit/edited 状态的数据项
    3. 为每个数据项生成一条 pending 待办
    """
    project = db.query(CollectionProject).filter(
        CollectionProject.tenant_id == tenant_id,
        CollectionProject.is_deleted == 0,
        CollectionProject.id == project_id,
    ).first()
    if not project:
        raise NotFoundError("采集项目不存在")
    # 1. 软删除所有 pending 待办
    pending_todos = db.query(ProjectTodo).filter(
        ProjectTodo.tenant_id == tenant_id,
        ProjectTodo.is_deleted == 0,
        ProjectTodo.project_id == project_id,
        ProjectTodo.status == "pending",
    ).all()
    for t in pending_todos:
        t.is_deleted = 1
        t.deleted_at = datetime.utcnow()
    # 2. 查询待填报/已编辑的数据项
    items = db.query(CollectionItem).filter(
        CollectionItem.tenant_id == tenant_id,
        CollectionItem.is_deleted == 0,
        CollectionItem.project_id == project_id,
        CollectionItem.status.in_(["pending_edit", "edited"]),
    ).all()
    # 3. 为每个数据项生成待办
    created = 0
    for item in items:
        assignee_id = _resolve_assignee(db, tenant_id, item, project)
        todo = ProjectTodo(
            tenant_id=tenant_id,
            project_id=project_id,
            item_id=item.id,
            zone_id=item.zone_id,
            assignee_id=assignee_id,
            period_code=item.period_code,
            status="pending",
            edit_mode="grid_edit",
        )
        db.add(todo)
        created += 1
    db.commit()
    return created


def _resolve_assignee(db: Session, tenant_id: str, item: CollectionItem,
                      project: CollectionProject) -> int:
    """解析待办指派人: 优先数据项 submitter_id → zone 用户 → 项目创建人"""
    if item.submitter_id:
        return item.submitter_id
    if item.zone_id:
        user = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.is_deleted == 0,
            User.is_active == 1,
            User.zone_id == item.zone_id,
        ).first()
        if user:
            return user.id
    return project.created_by or 0
