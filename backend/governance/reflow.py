"""候选回流 — 治理平面的收口段（第七批）。

把 governance.review 已核准的候选，写回本体权威源，闭合
「ingest 抽取 → 审核队列 → 核准 → 回流本体」全链路。

回流策略（保守、可验证、零外部依赖）：
    - entity 候选 → upsert `object_definitions`（name=f"{type}:{mention}"），
      作为新的本体对象类型落库，再 reload 到内存权威源。
    - relation 候选 → upsert `link_definitions`（按 predicate 找/建链接），
      源/目标对象取自两端 entity 候选的类型；任一端缺失则跳过并记 note。
    - 回流前后可选调用 versioning.capture 打快照，并全程 provenance.track 溯源。
    - 任何单条失败非阻断，整体返回汇总。

复用：database.OntologySessionLocal（本体库）、ontology.registry（reload）、
      versioning.manager（快照）、provenance.manager（溯源）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReflowResult:
    reviewed: int = 0
    entity_upserted: int = 0
    link_upserted: int = 0
    skipped: int = 0
    failed: int = 0
    notes: list[str] = field(default_factory=list)
    snapshot_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "reviewed": self.reviewed,
            "entity_upserted": self.entity_upserted,
            "link_upserted": self.link_upserted,
            "skipped": self.skipped,
            "failed": self.failed,
            "notes": self.notes,
            "snapshot_id": self.snapshot_id,
        }


def _obj_name(payload: dict) -> str:
    return f"{payload.get('entity_type','Unknown')}:{payload.get('mention','')}"


def reflow_approved(
    store,
    *,
    tenant_id: Optional[str] = None,
    version_manager=None,
    registry=None,
    mgr=None,
    capture_version: bool = True,
) -> ReflowResult:
    """把审核队列里 approved 的候选回流到本体库。

    Args:
        store: Neo4jCandidateStore 实例（duck-typed，仅需 list_approved 即可）
        tenant_id: 租户隔离（写库时落到 object/link 的 tenant_id）
        version_manager: 可选 versioning.VersionManager，传入则在回流前打快照
        registry: 可选 ontology.registry，默认全局单例；回流后 reload()
        mgr: 可选 ProvenanceManager，传入则溯源整段回流活动
        capture_version: 是否打快照（需 version_manager）
    """
    from ontology.registry import registry as _registry
    from provenance.manager import ProvenanceManager

    registry = registry or _registry
    mgr = mgr or ProvenanceManager()
    res = ReflowResult()

    # 取核准候选
    approved = store.list_approved()
    res.reviewed = len(approved)
    if not approved:
        res.notes.append("无核准候选，跳过回流")
        return res

    # 先建 entity_id -> (type, name) 映射，供 relation 解析两端
    entity_by_id = {
        c.payload.get("entity_id"): c.payload
        for c in approved if c.kind == "entity"
    }

    from database import OntologySessionLocal

    with _ReflowActivity(mgr) as act:
        with OntologySessionLocal() as db:
            for c in approved:
                try:
                    if c.kind == "entity":
                        name = _obj_name(c.payload)
                        _upsert_object(db, name, c.payload, tenant_id)
                        res.entity_upserted += 1
                    elif c.kind == "relation":
                        ok = _upsert_link(db, c.payload, entity_by_id, tenant_id)
                        if ok:
                            res.link_upserted += 1
                        else:
                            res.skipped += 1
                            res.notes.append(
                                f"relation {c.candidate_id} 两端实体缺失，已跳过")
                except Exception as e:
                    res.failed += 1
                    res.notes.append(f"{c.candidate_id} 回流失败: {e}")
                    logger.warning("候选回流失败 %s: %s", c.candidate_id, e)

            db.commit()

        # 回流后刷新内存权威源
        try:
            registry.reload()
            res.notes.append("registry.reload() 成功")
        except Exception as e:
            res.notes.append(f"registry.reload() 失败: {e}")

        # 可选打快照（以当前内存权威源为内容，记录回流时刻的本体形态）
        if capture_version and version_manager is not None:
            try:
                snap = version_manager.capture(
                    objects=registry.list_objects(),
                    links=registry.list_links(),
                    actions=registry.list_actions(),
                    authored_by="governance.reflow",
                    note="候选回流快照",
                )
                res.snapshot_id = snap.version_id
            except Exception as e:
                res.notes.append(f"版本快照失败: {e}")

    return res


# ── 内部 ──
def _upsert_object(db, name: str, payload: dict, tenant_id: str) -> None:
    from database import ObjectDefinition
    row = db.query(ObjectDefinition).filter_by(name=name, tenant_id=tenant_id).first()
    if row is None:
        row = ObjectDefinition(name=name, tenant_id=tenant_id)
        db.add(row)
    row.display_name = payload.get("mention", name)
    row.domain = "reflow"
    row.description = f"由候选回流自动创建（来源: {payload.get('document_id','?')}）"
    row.schema = row.schema or {}
    row.is_active = 1


def _upsert_link(db, payload: dict, entity_by_id: dict, tenant_id: str) -> bool:
    from database import LinkDefinition
    subj_id = payload.get("subject")
    obj_id = payload.get("obj")
    subj = entity_by_id.get(subj_id)
    obj = entity_by_id.get(obj_id)
    if not subj or not obj:
        return False  # 两端实体缺失，跳过
    src_type = subj.get("entity_type", "Unknown")
    tgt_type = obj.get("entity_type", "Unknown")
    pred = payload.get("predicate", "related_to")
    name = f"{pred}:{src_type}->{tgt_type}"
    row = db.query(LinkDefinition).filter_by(name=name, tenant_id=tenant_id).first()
    if row is None:
        row = LinkDefinition(name=name, tenant_id=tenant_id)
        db.add(row)
    row.display_name = f"{src_type} {pred} {tgt_type}"
    row.source_object = f"{src_type}:{subj.get('mention','')}"
    row.target_object = f"{tgt_type}:{obj.get('mention','')}"
    row.cardinality = "1:N"
    row.description = f"由候选回流自动创建（来源: {payload.get('document_id','?')}）"
    row.is_active = 1
    return True


class _ReflowActivity:
    """轻量溯源包裹（无 provenance 依赖时退化为 no-op）。"""

    def __init__(self, mgr):
        self._mgr = mgr
        self._act = None
        self._track = None

    def __enter__(self):
        from provenance.manager import track
        self._track = track
        self._act = self._track("governance.reflow", name="reflow_approved",
                                agent_id="governance")
        return self._act.__enter__()

    def __exit__(self, *exc):
        if self._act is not None:
            return self._act.__exit__(*exc)
