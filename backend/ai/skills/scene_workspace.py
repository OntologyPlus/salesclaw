"""培训场景创建工作流草稿工作区

设计要点：
- in-memory 一级缓存（同进程多轮对话复用）+ EpisodicMemory 持久化（跨进程恢复）
- importance=10 标记草稿（区分普通记忆 1-9）
- summary 字段以 "scene_draft:" 前缀标识
- 单 session_id 仅保留最新一条草稿（旧记录软删除）
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class SceneDraft:
    """培训场景创建草稿"""
    session_id: str
    tenant_id: str
    user_id: int
    # Step1 产出
    config: dict = field(default_factory=dict)  # 三列表：{scenario_types, business_domains, trainees}
    # Step2 产出
    collection: dict = field(default_factory=dict)  # {doctor_persona, best_practice_points, drug_name, user_confirmed}
    # Step3 产出
    title_bg: dict = field(default_factory=dict)  # {title, scene_background, user_confirmed}
    # Step4.1 产出
    knowledge: dict = field(default_factory=dict)  # {suggestions, ids, finalized}
    # Step4.2 产出
    context_payload: dict = field(default_factory=dict)  # {doctor:{5键}, coach:{3键}, ready}
    # Step4.3 产出
    submit_confirmed: bool = False
    scenario_id: Optional[int] = None
    # 工作流状态
    current_step: str = "Step1"  # Step1|Step2|Step3|Step4.1|Step4.2|Step4.3|done
    gates_passed: list = field(default_factory=list)  # ["G1","G2",...]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class SceneWorkspace:
    """草稿工作区（in-memory 缓存 + EpisodicMemory 持久化）"""

    # in-memory 一级缓存（同一进程内多轮对话复用）
    _cache: dict = {}  # {session_id: SceneDraft}

    # EpisodicMemory 中草稿的标识
    DRAFT_IMPORTANCE = 10
    DRAFT_SUMMARY_PREFIX = "scene_draft:"

    def load(self, session_id: str, db, tenant_id: str, user_id: int) -> SceneDraft:
        """加载草稿：先查内存，再查 EpisodicMemory"""
        # 1. 内存命中
        if session_id in self._cache:
            return self._cache[session_id]
        # 2. 查 EpisodicMemory
        from database import EpisodicMemory
        mem = db.query(EpisodicMemory).filter(
            EpisodicMemory.tenant_id == str(tenant_id),
            EpisodicMemory.user_id == int(user_id),
            EpisodicMemory.session_id == session_id,
            EpisodicMemory.importance == self.DRAFT_IMPORTANCE,
            EpisodicMemory.is_deleted == 0,
        ).order_by(EpisodicMemory.occurred_at.desc()).first()
        if mem:
            try:
                data = json.loads(mem.content)
                draft = SceneDraft(**data)
                self._cache[session_id] = draft
                return draft
            except Exception:
                pass
        # 3. 新建空 draft
        draft = SceneDraft(
            session_id=session_id, tenant_id=str(tenant_id), user_id=int(user_id),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        self._cache[session_id] = draft
        return draft

    def save(self, draft: SceneDraft, db) -> None:
        """持久化草稿到 EpisodicMemory（upsert 模式：新建最新 + 软删旧的）"""
        from database import EpisodicMemory
        draft.updated_at = datetime.utcnow().isoformat()
        # 更新内存
        self._cache[draft.session_id] = draft
        # 写入 EpisodicMemory
        mem = EpisodicMemory(
            tenant_id=draft.tenant_id,
            user_id=draft.user_id,
            session_id=draft.session_id,
            content=json.dumps(draft.to_dict(), ensure_ascii=False, default=str),
            summary=f"{self.DRAFT_SUMMARY_PREFIX}{draft.current_step}",
            importance=self.DRAFT_IMPORTANCE,
            occurred_at=datetime.utcnow(),
            decay_score=100,
        )
        db.add(mem)
        db.commit()
        # 软删除旧的草稿记录（保留最新一条有效）
        db.query(EpisodicMemory).filter(
            EpisodicMemory.tenant_id == draft.tenant_id,
            EpisodicMemory.user_id == draft.user_id,
            EpisodicMemory.session_id == draft.session_id,
            EpisodicMemory.importance == self.DRAFT_IMPORTANCE,
            EpisodicMemory.id != mem.id,
        ).update({EpisodicMemory.is_deleted: 1})
        db.commit()

    def clear(self, session_id: str, db, tenant_id: str, user_id: int) -> None:
        """create 成功后清理草稿"""
        # 清内存
        self._cache.pop(session_id, None)
        # 软删除 EpisodicMemory
        from database import EpisodicMemory
        db.query(EpisodicMemory).filter(
            EpisodicMemory.tenant_id == str(tenant_id),
            EpisodicMemory.user_id == int(user_id),
            EpisodicMemory.session_id == session_id,
            EpisodicMemory.importance == self.DRAFT_IMPORTANCE,
        ).update({EpisodicMemory.is_deleted: 1})
        db.commit()

    def validate_gate(self, draft: SceneDraft, gate: str) -> tuple:
        """检查门禁 G1-G8，返回 (passed: bool, reason: str)"""
        if gate == "G1":
            return (True, "OK") if draft.tenant_id and draft.user_id else (False, "未登录")
        if gate == "G2":
            cfg = draft.config or {}
            ok = bool(cfg.get("scenario_types") and cfg.get("business_domains") and cfg.get("trainees"))
            return (True, "OK") if ok else (False, "三列表配置为空")
        if gate == "G3":
            coll = draft.collection or {}
            ok = bool(
                coll.get("doctor_persona") and coll.get("best_practice_points")
                and coll.get("drug_name") and coll.get("user_confirmed") is True
            )
            return (True, "OK") if ok else (False, "采集字段未完成或未确认")
        if gate == "G4":
            tb = draft.title_bg or {}
            ok = bool(tb.get("title") and tb.get("scene_background") and tb.get("user_confirmed") is True)
            return (True, "OK") if ok else (False, "标题背景未完成或未确认")
        if gate == "G5":
            kn = draft.knowledge or {}
            ok = bool(kn.get("finalized") is True and kn.get("ids"))
            return (True, "OK") if ok else (False, "知识未锁定")
        if gate == "G6":
            cp = draft.context_payload or {}
            ok = bool(cp.get("ready") is True and cp.get("doctor") and cp.get("coach"))
            return (True, "OK") if ok else (False, "contextPayload 未就绪")
        if gate == "G7":
            return (True, "OK") if draft.submit_confirmed else (False, "用户未确认提交")
        if gate == "G8":
            return (True, "OK") if draft.scenario_id else (False, "未落库")
        return (False, f"未知门禁 {gate}")


# 全局单例
scene_workspace = SceneWorkspace()
