"""本体成熟度评估服务（吸收参考3 附录C 5 级成熟度模型）

参考3 给出 5 级成熟度模型（L1 混沌 → L5 自治）+ 20 题问卷（0-2 分）。
本系统已有 psp_ontology.db 四层注册表（Object/Link/Action/Permission），
本服务将 20 题问卷的"数据源"改为本系统真实本体常量，避免凭空问卷，
实现"有骨架且有尺子"的成熟度自评。

评分口径：四层（对象/关系/动作/权限），每层 5 题 × 0-2 分 = 满分 10，
归一为 0-100；四层平均得总成熟度分，映射 L1-L5。
"""
from typing import Optional

from ontology import (
    OBJECTS, LINKS, ACTIONS,
    ROLE_PERMISSIONS, OBJECT_PERMISSIONS, ROLE_DEFINITIONS,
)

# ──────────────────────────────────────────────
# 5 级成熟度模型（参考3 附录C）
# ──────────────────────────────────────────────
MATURITY_LEVELS = [
    {"level": 1, "name": "混沌", "range": (0, 20),
     "desc": "本体缺失或大量悬空，无统一语言"},
    {"level": 2, "name": "可见", "range": (21, 40),
     "desc": "有结构但无管控，标注不完整"},
    {"level": 3, "name": "规范", "range": (41, 60),
     "desc": "四层齐备、标注完整（本系统目标）"},
    {"level": 4, "name": "智能", "range": (61, 80),
     "desc": "AI 可推理、运营可度量"},
    {"level": 5, "name": "自治", "range": (81, 100),
     "desc": "动态演化、反模式自愈"},
]


def _level_of(score: int) -> dict:
    for lv in MATURITY_LEVELS:
        lo, hi = lv["range"]
        if lo <= score <= hi:
            return lv
    return MATURITY_LEVELS[-1]


def _safe_ratio(numerator: int, denominator: int) -> float:
    return (numerator / denominator * 100) if denominator > 0 else 0.0


def assess(tenant_id: str = "default") -> dict:
    """本体成熟度自评

    Args:
        tenant_id: 租户 ID（本服务基于静态本体常量，tenant_id 预留用于未来多租户本体）

    Returns:
        {
            score, level, level_name, layer_scores{object,relation,action,permission},
            weak_layers, upgrade_path[]
        }
    """
    layer_scores = {
        "object": _score_object_layer(),
        "relation": _score_relation_layer(),
        "action": _score_action_layer(),
        "permission": _score_permission_layer(),
    }
    total = sum(layer_scores.values()) / len(layer_scores)
    score = round(total)
    lv = _level_of(score)

    weak_layers = [
        name for name, s in layer_scores.items() if s < 60
    ]
    upgrade_path = _build_upgrade_path(score, layer_scores)

    return {
        "score": score,
        "level": lv["level"],
        "level_name": lv["name"],
        "level_desc": lv["desc"],
        "layer_scores": layer_scores,
        "weak_layers": weak_layers,
        "upgrade_path": upgrade_path,
        "questionnaire": _questionnaire_detail(),
    }


# ──────────────────────────────────────────────
# 四层评分（每层 5 题，0-2 分，满分 10 → 归一 0-100）
# ──────────────────────────────────────────────

def _score_object_layer() -> int:
    """对象层：实体覆盖域完整性 / 字段完整性 / display_name / description / 无重复"""
    objs = OBJECTS
    n = len(objs)
    if n == 0:
        return 0
    # Q1 域覆盖完整性：6 域（sales/training/comprehensive/decision/ai/experience）覆盖度
    expected_domains = {"sales", "training", "comprehensive", "decision", "ai", "experience"}
    covered = {o.get("domain") for o in objs}
    q1 = 2 if expected_domains.issubset(covered) else (1 if len(covered & expected_domains) >= 4 else 0)
    # Q2 字段完整性：含 name + domain + description
    q2 = _rate(lambda o: all(o.get(k) for k in ("name", "domain", "description")), objs)
    # Q3 display_name 标注率
    q3 = _rate(lambda o: bool(o.get("display_name")), objs)
    # Q4 description 标注率
    q4 = _rate(lambda o: bool(o.get("description")), objs)
    # Q5 无重复 name
    names = [o.get("name") for o in objs]
    dup = len(names) - len(set(names))
    q5 = 2 if dup == 0 else (1 if dup <= 1 else 0)
    return round((q1 + q2 + q3 + q4 + q5) / 10 * 100)


def _score_relation_layer() -> int:
    """关系层：关系密度 / cardinality / 无悬空 / 双向对称 / 命名规范"""
    links = LINKS
    objs = OBJECTS
    obj_names = {o.get("name") for o in objs}
    n = len(links)
    if n == 0:
        return 0
    # Q1 关系密度 link/object（>=0.5 视为健康）
    density = n / max(len(objs), 1)
    q1 = 2 if density >= 0.5 else (1 if density >= 0.3 else 0)
    # Q2 cardinality 标注率
    q2 = _rate(lambda l: bool(l.get("cardinality")), links)
    # Q3 无悬空（source/target 均存在）
    q3 = _rate(lambda l: l.get("source_object") in obj_names and l.get("target_object") in obj_names, links)
    # Q4 双向对称：存在对应反向 link
    q4 = _rate(lambda l: any(
        x.get("source_object") == l.get("target_object") and x.get("target_object") == l.get("source_object")
        for x in links if x is not l
    ), links)
    # Q5 命名规范（含 _to_ 或 _of_）
    q5 = _rate(lambda l: "_to_" in l.get("name", "") or "_of_" in l.get("name", ""), links)
    return round((q1 + q2 + q3 + q4 + q5) / 10 * 100)


def _score_action_layer() -> int:
    """动作层：域覆盖 / risk_level 标注率 / permission_required 标注率 / 高风动作占比 / 可执行性"""
    actions = ACTIONS
    n = len(actions)
    if n == 0:
        return 0
    expected_domains = {"sales", "training", "comprehensive", "decision", "ai", "experience"}
    covered = {a.get("domain") for a in actions}
    q1 = 2 if expected_domains.issubset(covered) else (1 if len(covered & expected_domains) >= 4 else 0)
    q2 = _rate(lambda a: bool(a.get("risk_level")), actions)
    q3 = _rate(lambda a: a.get("permission_required") is not None, actions)
    # Q4 高风动作（L3/L4）占比（存在即视为有辨识，反之扣分）
    high = [a for a in actions if a.get("risk_level") in ("L3", "L4")]
    q4 = 2 if len(high) > 0 else 0
    # Q5 可执行性（含 handler 或 endpoint 任一）
    q5 = _rate(lambda a: bool(a.get("handler")) or bool(a.get("endpoint")), actions)
    return round((q1 + q2 + q3 + q4 + q5) / 10 * 100)


def _score_permission_layer() -> int:
    """权限层：角色覆盖域 / OBAC 声明率 / 高风动作均有 permission / 无越权 / 回收机制

    ROLE_PERMISSIONS: {role: [perm, ...]}  角色→权限列表
    OBJECT_PERMISSIONS: {object: {access: [role, ...]}}  OBAC Object 级声明
    ROLE_DEFINITIONS: [{code, display_name, description, status?}]  角色定义
    """
    roles = ROLE_PERMISSIONS or {}
    # OBJECT_PERMISSIONS 是 {对象: {访问类型: [角色]}} 结构，
    # 这里摊平为 [{object, access, roles}] 便于按条目计分
    obj_perms = [
        {"object": obj_name, "access": access, "roles": role_list}
        for obj_name, access_map in (OBJECT_PERMISSIONS or {}).items()
        for access, role_list in (access_map or {}).items()
    ]
    role_defs = ROLE_DEFINITIONS or []
    n_roles = len(roles)
    if n_roles == 0:
        return 0
    # Q1 角色覆盖域完整性（基于 ROLE_DEFINITIONS 的 domain 字段，若无则按角色名推断）
    domains_of_role = {r.get("domain") for r in role_defs} if role_defs else set()
    if not domains_of_role:
        # 退化推断：角色名关键词
        kw_map = {
            "sales": "sales", "training": "training", "decision": "decision",
            "ai": "ai", "experience": "experience", "admin": "comprehensive",
        }
        domains_of_role = {kw_map.get(k, "comprehensive") for k in roles.keys()}
    expected_domains = {"sales", "training", "comprehensive", "decision", "ai", "experience"}
    q1 = 2 if expected_domains.issubset(domains_of_role) else (1 if len(domains_of_role & expected_domains) >= 4 else 0)
    # Q2 OBAC Object 级声明率（含 object 字段）
    q2 = _rate(lambda p: bool(p.get("object")), obj_perms) if obj_perms else 2
    # Q3 高风动作（L3/L4）均声明了 permission_required
    # 注：permission_required 是权限码字符串（如 "visit:approve"），非布尔值
    high = [a for a in ACTIONS if a.get("risk_level") in ("L3", "L4")]
    if high:
        ok = sum(1 for a in high if a.get("permission_required"))
        q3 = 2 if ok == len(high) else (1 if ok >= len(high) * 0.7 else 0)
    else:
        q3 = 2
    # Q4 无越权声明（access 类型合法且已绑定角色）
    _valid_access = ("read", "write", "approve", "delete", "deny", "execute", "export")
    q4 = _rate(
        lambda p: p.get("access") in _valid_access and bool(p.get("roles")), obj_perms
    ) if obj_perms else 2
    # Q5 权限回收机制（role 含 status 字段）
    q5 = _rate(lambda r: bool(r.get("status")), role_defs) if role_defs else 2
    return round((q1 + q2 + q3 + q4 + q5) / 10 * 100)


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _rate(pred, items: list) -> int:
    """对 items 应用 pred，返回 0/1/2（0%、<80%、>=80%）"""
    if not items:
        return 0
    ok = sum(1 for it in items if pred(it))
    ratio = ok / len(items)
    if ratio >= 0.8:
        return 2
    elif ratio >= 0.5:
        return 1
    return 0


def _build_upgrade_path(score: int, layer_scores: dict) -> list:
    """根据当前得分与弱层生成升级路径"""
    path = []
    if score < 60:
        path.append("补齐四层本体缺失实体与关系，达到 L3 规范基线")
    if layer_scores["object"] < 60:
        path.append("对象层：补全实体 description/display_name，消除重复实体")
    if layer_scores["relation"] < 60:
        path.append("关系层：补全 cardinality 标注，消除悬空关系，建立双向对称")
    if layer_scores["action"] < 60:
        path.append("动作层：100% 标注 risk_level 与 permission_required，区分高风动作")
    if layer_scores["permission"] < 60:
        path.append("权限层：补全 OBAC Object 级声明，确保高风动作均有权限约束")
    if score >= 60:
        path.append("向 L4 智能演进：接入 AI 推理（InsightChain）量化运营指标")
    return path


def _questionnaire_detail() -> dict:
    """返回 20 题问卷明细（用于前端自评展示）"""
    return {
        "object": [
            "实体覆盖全部 6 业务域", "实体含 name/domain/description 完整字段",
            "实体含 display_name", "实体含 description", "无重复实体",
        ],
        "relation": [
            "关系密度 link/object ≥ 0.5", "关系含 cardinality 标注",
            "无悬空关系（指向不存在实体）", "存在双向对称关系", "关系命名规范（_to_/_of_）",
        ],
        "action": [
            "动作覆盖全部 6 业务域", "动作 100% 标注 risk_level",
            "动作 100% 标注 permission_required", "存在高风动作（L3/L4）辨识",
            "动作具备可执行入口（handler/endpoint）",
        ],
        "permission": [
            "角色覆盖全部 6 业务域", "OBAC Object 级声明完整",
            "高风动作均有 permission_required=true", "无越权声明（is_denied 布尔）",
            "角色含 status 支持回收",
        ],
    }
