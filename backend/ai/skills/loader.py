"""三层 Skill 加载器 + OAG 上下文注入

三层加载：
- L1 目录层（启动时加载）：读取所有 SKILL.md 的 YAML frontmatter，构建 skill_catalog
- L2 指令层（路由匹配时加载）：读取匹配 Skill 的 Markdown body
- L3 资源层（按需加载）：读取 references/ 目录下的参考文档

OAG 上下文注入：
- 从 SKILL.md 的 activated_objects/rules/behaviors 构建上下文
- 查询相关业务数据（如 VisitRecord、Hospital 等）
- 返回 {instructions, oag_context: {objects, rules, behaviors, data}}

B9：L1/L2 缓存增加 TTL（默认 10 分钟），SKILL.md 改动无需重启即可生效。
"""
import time
from pathlib import Path
from typing import Any, Optional

import yaml

# SKILL.md 文件所在根目录：backend/ai/skills/definitions/
DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class SkillLoader:
    """三层 Skill 加载器 + OAG 上下文注入"""

    # L3 资源层默认参考文档上限
    MAX_REFERENCES = 20
    # 每个对象默认采样记录数
    DEFAULT_DATA_LIMIT = 30
    # B9：L1/L2 缓存 TTL（秒），超时后下次访问重新加载
    CACHE_TTL_SECONDS = 600

    def __init__(self, definitions_dir: Optional[Path] = None):
        self.definitions_dir = definitions_dir or DEFINITIONS_DIR
        # L1 缓存：catalog 列表
        self._catalog_cache: Optional[list[dict]] = None
        # L2 缓存：skill_name -> skill dict
        self._skill_cache: dict[str, dict] = {}
        # B9：缓存时间戳（monotonic），用于 TTL 判断
        self._catalog_ts: float = 0.0
        self._skill_ts: dict[str, float] = {}

    # ──────────────────────────────────────────────
    # L1 目录层
    # ──────────────────────────────────────────────
    def load_catalog(self) -> list[dict]:
        """L1 加载：扫描 definitions/ 下所有 SKILL.md 的 YAML frontmatter，构建 skill_catalog

        B9：增加 TTL 过期判断，超时后清空缓存重新加载。

        Returns:
            每个 Skill 的元数据 dict 列表，包含 name、display_name、description、
            intent、allowed_tools、phase、metadata、activated_objects、activated_rules、
            activated_behaviors 等字段
        """
        # B9：TTL 过期则清空缓存
        if self._catalog_cache is not None and self._catalog_ts > 0:
            if (time.monotonic() - self._catalog_ts) < self.CACHE_TTL_SECONDS:
                return self._catalog_cache
            # 过期 → 清空，重新加载
            self._catalog_cache = None

        catalog: list[dict] = []
        if not self.definitions_dir.exists():
            self._catalog_cache = catalog
            self._catalog_ts = time.monotonic()
            return catalog

        # 遍历每个子目录，读取 SKILL.md
        for skill_dir in sorted(self.definitions_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8")
                meta = self._parse_yaml_frontmatter(text)
                # 子目录名作为兜底 name
                if not meta.get("name"):
                    meta["name"] = skill_dir.name
                # 记录 skill 所在目录，便于 L2/L3 定位
                meta["dir"] = skill_dir.name
                catalog.append(meta)
            except Exception:
                # 单个 SKILL.md 解析失败不影响整体
                continue

        self._catalog_cache = catalog
        self._catalog_ts = time.monotonic()
        return catalog

    # ──────────────────────────────────────────────
    # L2 指令层
    # ──────────────────────────────────────────────
    def load_skill(self, skill_name: str) -> dict:
        """L2 加载：读取匹配 Skill 的完整内容（L1 元数据 + L2 指令体）

        B9：增加 TTL 过期判断，超时后从缓存移除重新读取。

        Args:
            skill_name: Skill 名称（如 visit-planner）

        Returns:
            {name, metadata, instructions, references}；未找到时返回空 dict
        """
        # B9：TTL 过期则从缓存移除
        if skill_name in self._skill_cache:
            cached_ts = self._skill_ts.get(skill_name, 0.0)
            if (time.monotonic() - cached_ts) < self.CACHE_TTL_SECONDS:
                return self._skill_cache[skill_name]
            # 过期 → 清除该条目，重新加载
            del self._skill_cache[skill_name]

        skill_dir = self.definitions_dir / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return {}

        try:
            text = skill_md.read_text(encoding="utf-8")
        except Exception:
            return {}

        meta = self._parse_yaml_frontmatter(text)
        if not meta.get("name"):
            meta["name"] = skill_name
        body = self._extract_body(text)
        references = self._list_references(skill_dir)

        skill = {
            "name": skill_name,
            "metadata": meta,
            "instructions": body,
            "references": references,
        }
        self._skill_cache[skill_name] = skill
        self._skill_ts[skill_name] = time.monotonic()
        return skill

    # ──────────────────────────────────────────────
    # L3 资源层
    # ──────────────────────────────────────────────
    def load_reference(self, skill_name: str, ref_name: str) -> str:
        """L3 加载：按需读取 references/ 目录下的参考文档内容

        Args:
            skill_name: Skill 名称
            ref_name: 参考文档文件名

        Returns:
            文档文本内容；不存在时返回空字符串
        """
        ref_path = self.definitions_dir / skill_name / "references" / ref_name
        if not ref_path.exists() or not ref_path.is_file():
            return ""
        try:
            return ref_path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _list_references(self, skill_dir: Path) -> list[str]:
        """L3 辅助：列出某个 Skill 的 references/ 目录下的文件名"""
        refs_dir = skill_dir / "references"
        if not refs_dir.exists() or not refs_dir.is_dir():
            return []
        files = [f.name for f in sorted(refs_dir.iterdir()) if f.is_file()]
        return files[: self.MAX_REFERENCES]

    # ──────────────────────────────────────────────
    # OAG 上下文注入
    # ──────────────────────────────────────────────
    def load_skill_context(self, skill_name: str, tenant_id, db) -> dict:
        """加载 Skill（L1+L2）并注入 OAG 上下文

        Args:
            skill_name: Skill 名称
            tenant_id: 租户 ID
            db: 数据库 session

        Returns:
            {instructions, oag_context: {objects, rules, behaviors, data}}；
            Skill 不存在时返回空 dict
        """
        skill = self.load_skill(skill_name)
        if not skill:
            return {}

        meta = skill.get("metadata", {})
        objects = meta.get("activated_objects", []) or []
        rules = meta.get("activated_rules", []) or []
        behaviors = meta.get("activated_behaviors", []) or []

        oag_context = self._build_oag_context(objects, rules, behaviors, tenant_id, db)
        return {
            "instructions": skill.get("instructions", ""),
            "oag_context": oag_context,
        }

    def _build_oag_context(
        self,
        objects: list[str],
        rules: list[str],
        behaviors: list[str],
        tenant_id,
        db,
    ) -> dict:
        """构建 OAG 上下文：对象 + 规则 + 行为 + 相关业务数据快照 + Ontology 定义

        Args:
            objects: 激活的对象名列表（如 VisitRecord、Hospital）
            rules: 激活的规则文本列表
            behaviors: 激活的行为名列表
            tenant_id: 租户 ID
            db: 数据库 session

        Returns:
            {objects, rules, behaviors, data, ontology}，data 为各对象最近业务数据，
            ontology 为从注册表查询的 objects/links/actions 真实定义
        """
        data: dict[str, list[dict]] = {}
        if db is not None and tenant_id is not None and objects:
            data = self._load_object_data(objects, str(tenant_id), db)
        ontology_defs = self._load_ontology_defs(objects, behaviors)
        return {
            "objects": list(objects),
            "rules": list(rules),
            "behaviors": list(behaviors),
            "data": data,
            "ontology": ontology_defs,
        }

    def _load_ontology_defs(self, objects: list[str], behaviors: list[str]) -> dict:
        """从 ontology 注册表查询 objects/links/actions 的真实定义

        Args:
            objects: 激活的对象名列表
            behaviors: 激活的行为名列表（对应 Action 名称）

        Returns:
            {objects: [...], links: [...], actions: [...]}；查询失败返回空 dict
        """
        try:
            from ontology import OBJECT_MAP, LINK_MAP, ACTION_MAP
        except ImportError:
            return {}

        # 查询激活对象的定义
        obj_defs = []
        for name in objects:
            obj = OBJECT_MAP.get(name)
            if obj:
                obj_defs.append({
                    "name": obj.get("name"),
                    "display_name": obj.get("display_name"),
                    "domain": obj.get("domain"),
                    "fields": obj.get("fields", []),
                    "actions": obj.get("actions", []),
                })

        # 查询相关 Link（source 或 target 在激活对象中）
        obj_name_set = set(objects)
        related_links = []
        for link_name, link in LINK_MAP.items():
            if (link.get("source_object") in obj_name_set
                    or link.get("target_object") in obj_name_set):
                related_links.append({
                    "name": link.get("name"),
                    "source": link.get("source_object"),
                    "target": link.get("target_object"),
                    "cardinality": link.get("cardinality"),
                })

        # 查询激活行为对应的 Action 定义
        action_defs = []
        for behavior in behaviors:
            action = ACTION_MAP.get(behavior)
            if action:
                action_defs.append({
                    "name": action.get("name"),
                    "risk_level": action.get("risk_level"),
                    "description": action.get("description"),
                })

        return {
            "objects": obj_defs,
            "links": related_links,
            "actions": action_defs,
        }

    def _load_object_data(self, objects: list[str], tid: str, db) -> dict[str, list[dict]]:
        """根据激活的对象名加载相关业务数据快照

        每个对象最多采样 DEFAULT_DATA_LIMIT 条记录，按最近创建时间倒序。
        """
        # 延迟导入，避免模块加载时强依赖
        from database import (
            VisitRecord, VisitPlan, Hospital, Doctor, Product,
            CoverageAssignment, VisitFeedback, Course, CourseEnrollment,
            KnowledgeDocument, FaqItem,
        )

        limit = self.DEFAULT_DATA_LIMIT
        # 对象名 -> 查询函数映射
        object_queries = {
            "VisitRecord": lambda: db.query(VisitRecord).filter(
                VisitRecord.tenant_id == tid, VisitRecord.is_deleted == 0,
            ).order_by(VisitRecord.visit_date.desc()).limit(limit).all(),
            "VisitPlan": lambda: db.query(VisitPlan).filter(
                VisitPlan.tenant_id == tid, VisitPlan.is_deleted == 0,
            ).order_by(VisitPlan.created_at.desc()).limit(limit).all(),
            "Hospital": lambda: db.query(Hospital).filter(
                Hospital.tenant_id == tid, Hospital.is_deleted == 0,
            ).limit(limit).all(),
            "Doctor": lambda: db.query(Doctor).filter(
                Doctor.tenant_id == tid, Doctor.is_deleted == 0,
            ).limit(limit).all(),
            "Product": lambda: db.query(Product).filter(
                Product.tenant_id == tid, Product.is_deleted == 0,
            ).limit(limit).all(),
            "CoverageAssignment": lambda: db.query(CoverageAssignment).filter(
                CoverageAssignment.tenant_id == tid, CoverageAssignment.is_deleted == 0,
            ).limit(limit).all(),
            "VisitFeedback": lambda: db.query(VisitFeedback).filter(
                VisitFeedback.tenant_id == tid, VisitFeedback.is_deleted == 0,
            ).order_by(VisitFeedback.created_at.desc()).limit(limit).all(),
            "Course": lambda: db.query(Course).filter(
                Course.tenant_id == tid, Course.is_deleted == 0, Course.is_published == 1,
            ).limit(limit).all(),
            "CourseEnrollment": lambda: db.query(CourseEnrollment).filter(
                CourseEnrollment.tenant_id == tid, CourseEnrollment.is_deleted == 0,
            ).order_by(CourseEnrollment.enrolled_at.desc()).limit(limit).all(),
            "KnowledgeDocument": lambda: db.query(KnowledgeDocument).filter(
                KnowledgeDocument.tenant_id == tid, KnowledgeDocument.is_deleted == 0,
                KnowledgeDocument.is_published == 1,
            ).limit(limit).all(),
            "FaqItem": lambda: db.query(FaqItem).filter(
                FaqItem.tenant_id == tid, FaqItem.is_deleted == 0,
            ).limit(limit).all(),
        }

        result: dict[str, list[dict]] = {}
        for obj_name in objects:
            query_fn = object_queries.get(obj_name)
            if query_fn is None:
                result[obj_name] = []
                continue
            try:
                records = query_fn()
                result[obj_name] = [self._serialize(r) for r in records]
            except Exception:
                # 查询异常时返回空列表，不阻断上下文构建
                result[obj_name] = []
        return result

    # ──────────────────────────────────────────────
    # YAML frontmatter 解析（使用 PyYAML）
    # ──────────────────────────────────────────────
    def _parse_yaml_frontmatter(self, text: str) -> dict:
        """解析 SKILL.md 的 YAML frontmatter

        约定：文件首行为 ---，下一次单独成行的 --- 之间为 YAML 内容。
        解析失败时返回空 dict，保证单个 Skill 解析异常不影响整体加载。
        """
        if not text:
            return {}
        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return {}
        # 找到结束分隔符 ---
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx < 0:
            return {}
        yaml_text = "\n".join(lines[1:end_idx])
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            return {}
        return data if isinstance(data, dict) else {}

    # ──────────────────────────────────────────────
    # Markdown body 提取
    # ──────────────────────────────────────────────
    @staticmethod
    def _extract_body(text: str) -> str:
        """提取 YAML frontmatter 之后的 Markdown body"""
        if not text:
            return ""
        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return text.strip()
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx < 0:
            return text.strip()
        return "\n".join(lines[end_idx + 1:]).strip()

    # ──────────────────────────────────────────────
    # 模型序列化
    # ──────────────────────────────────────────────
    @staticmethod
    def _serialize(obj) -> dict:
        """将 SQLAlchemy 模型实例序列化为 dict（datetime/date 转 ISO 字符串）"""
        if obj is None:
            return {}
        result: dict[str, Any] = {}
        for col in obj.__table__.columns:
            value = getattr(obj, col.name, None)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            result[col.name] = value
        return result


# 全局单例
skill_loader = SkillLoader()


__all__ = ["SkillLoader", "skill_loader", "DEFINITIONS_DIR"]
