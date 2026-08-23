"""实体与关系抽取 —— 「方法注册表 + 标准化输出」

设计取舍：
    - 不调 LLM（零外部依赖、可离线测试、可审计），用「本体对象名词典 + 正则模式」做规则抽取。
    - 输出三元组 (subject, predicate, object) 对齐 ontology 的 Link 关系，
      但仅作为「候选」，不直写业务表（落内存图 + provenance，待人工/规则审核后回流）。
    - 抽取方法通过 MethodRegistry 注册，未来可无缝替换为 LLM 版（同一接口）。

与 ontology 对齐：实体类型取自 ontology.objects 的 OBJECT 名；
关系类型取自 ontology.links 的 LINK 名（共现启发式）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_EXTRACTORS: dict[str, type] = {}


def register_extractor(name: str):
    def deco(cls):
        _EXTRACTORS[name] = cls
        return cls
    return deco


@dataclass
class Entity:
    entity_id: str
    entity_type: str          # 对齐 ontology OBJECT 名，如 Doctor / Hospital / Product
    mention: str              # 原文提及
    chunk_id: str
    properties: dict = field(default_factory=dict)


@dataclass
class Relation:
    relation_id: str
    subject: str              # Entity.entity_id
    predicate: str            # 对齐 ontology LINK 名
    obj: str                  # Entity.entity_id
    chunk_id: str
    confidence: float = 1.0


@dataclass
class ExtractionResult:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


@register_extractor("rule")
class RuleExtractor:
    """基于本体对象名的词典 + 共现规则抽取。"""

    # 中文实体边界（精准切出「人名/地名 + 职称/机构后缀」）
    # 医生：可选姓氏 + 职称（主任/教授/院长/医生）
    _DOCTOR_RE = re.compile(r"(?:[\u4e00-\u9fa5]{1,3})?(?:主任|教授|院长|医生)")
    # 医院：前缀**仅允许地名/序数字符**（市/省/区/第/一二三…/路街号），
    #       不含任何人称/动词字符，从根本上杜绝吞掉「张医生是市第一医院」整段。
    _HOSPITAL_RE = re.compile(
        r"[一二三四五六七八九十0-9市省区市县镇路街号院栋座东西南北中第]{1,8}医院"
    )
    # 销售：人名/姓 + 代表/经理
    _REP_RE = re.compile(r"(?:[\u4e00-\u9fa5]{1,3})?(?:代表|经理)")
    # 产品/药品
    _PRODUCT_RE = re.compile(r"[\u4e00-\u9fa5]{2,8}(?:产品|药品)")
    _REL_PATTERNS = [
        # (正则, predicate) —— 启发式，命中即认为存在该关系
        (r"(.+?)(?:负责|分管|覆盖).*?(.+?医院)", "covers"),
        (r"(.+?医院).*?(?:位于|地处).*?(.+?(?:省|市|区))", "located_in"),
    ]

    def __init__(self, ontology_objects: Optional[list[dict]] = None,
                 ontology_links: Optional[list[dict]] = None):
        # 默认从 ontology seed 加载，使抽取与本体对齐
        if ontology_objects is None:
            from ontology.objects import OBJECTS
            ontology_objects = OBJECTS
        if ontology_links is None:
            from ontology.links import LINKS
            ontology_links = LINKS
        self.object_names = [o["name"] for o in ontology_objects]
        self.link_names = [l["name"] for l in ontology_links]
        self._ent_counter = 0
        self._rel_counter = 0

    def extract(self, chunks: list) -> ExtractionResult:
        result = ExtractionResult()
        # 1) 实体抽取：按专用正则扫描，避免把整句误判为一个实体
        for chunk in chunks:
            text = chunk.text
            for etype, rx in (
                ("Doctor", self._DOCTOR_RE),
                ("Hospital", self._HOSPITAL_RE),
                ("SalesRep", self._REP_RE),
                ("Product", self._PRODUCT_RE),
            ):
                for m in rx.finditer(text):
                    mention = m.group(0)
                    if any(e.mention == mention and e.chunk_id == chunk.chunk_id
                           for e in result.entities):
                        continue  # 去重同一片段内的重复提及
                    result.entities.append(
                        Entity(entity_id=self._next_entity_id(etype),
                               entity_type=etype, mention=mention,
                               chunk_id=chunk.chunk_id)
                    )
        # 2) 关系抽取：chunk 内共现 + 正则启发式
        ent_by_chunk = {}
        for e in result.entities:
            ent_by_chunk.setdefault(e.chunk_id, []).append(e)
        for chunk in chunks:
            ents = ent_by_chunk.get(chunk.chunk_id, [])
            if len(ents) >= 2:
                self._heuristic_relations(chunk.text, ents, result)
        return result

    # ── 内部 ──
    # 关系动词 → predicate（实体驱动：检查两实体在文本中的相对位置与中间动词）
    _REL_VERBS = [
        ("covers", ("负责", "分管", "覆盖")),
        ("located_in", ("位于", "地处", "坐落在")),
        ("belongs_to", ("属于", "隶属", "归")),
    ]
    # 基于常见业务语义的「主语类型约束」，过滤反方向噪声
    # （规则抽取无句法分析，用类型约束兜底方向正确性）
    _SUBJECT_TYPES = {
        "covers": {"SalesRep", "Doctor"},
        "located_in": {"Hospital"},
        "belongs_to": {"Doctor", "SalesRep", "Product"},
    }

    def _heuristic_relations(self, text: str, ents: list[Entity], result: ExtractionResult) -> None:
        # 收集每个 mention 的所有出现位置
        occ: dict[str, list[int]] = {}
        for e in ents:
            occ.setdefault(e.entity_id, [])
            for m in re.finditer(re.escape(e.mention), text):
                occ[e.entity_id].append(m.start())

        n = len(ents)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ents[i], ents[j]
                if a.mention in b.mention or b.mention in a.mention:
                    continue
                if a.entity_type == b.entity_type:
                    continue
                # 取两实体「所有出现组合中，中间文本最短且 ≤10 字」的一对，
                # 不限定前后顺序（中文主谓宾/宾谓主皆可能），中间含动词即判定。
                best = None  # (gap, pa, pb, between)
                for pa in occ.get(a.entity_id, []):
                    for pb in occ.get(b.entity_id, []):
                        if pa == pb:
                            continue
                        lo, hi = (pa, pb) if pa < pb else (pb, pa)
                        subj, obj = (a, b) if pa < pb else (b, a)
                        between = text[lo + len(subj.mention):hi]
                        if len(between) > 10:
                            continue
                        gap = abs(pa - pb)
                        if best is None or gap < best[0]:
                            best = (gap, pa, pb, between, subj, obj)
                if best is None:
                    continue
                _, _pa, _pb, between, subj, obj = best
                for pred, verbs in self._REL_VERBS:
                    if pred not in self.link_names and pred not in ("covers", "located_in", "belongs_to"):
                        continue
                    if any(v in between for v in verbs):
                        if subj.entity_type not in self._SUBJECT_TYPES.get(pred, set()):
                            continue
                        result.relations.append(
                            Relation(relation_id=self._next_relation_id(),
                                     subject=subj.entity_id, predicate=pred, obj=obj.entity_id,
                                     chunk_id=a.chunk_id)
                        )
                        break

    def _next_entity_id(self, etype: str) -> str:
        self._ent_counter += 1
        return f"{etype}:{self._ent_counter}"

    def _next_relation_id(self) -> str:
        self._rel_counter += 1
        return f"rel:{self._rel_counter}"


def get_extractor(name: str = "rule") -> type:
    """按名获取抽取器类（借鉴 MethodRegistry 的 O(1) 查找）。"""
    if name not in _EXTRACTORS:
        raise KeyError(f"未知抽取器: {name}（已注册: {list(_EXTRACTORS)}）")
    return _EXTRACTORS[name]


# ──────────────────────────────────────────────────────────
# LLM 抽取器（第五批）：同一接口无缝替换规则版
#
# 设计：抽取"文本→结构化候选"的职责委派给可插拔的 LLMProvider。
#   - 默认 provider = TemplateLLMProvider（离线兜底，内部复用规则引擎，
#     保证零外部依赖即可运行、接口与真实 LLM 完全一致）
#   - 生产环境注入真实 LLM provider（实现 LLMProvider 协议，返回 JSON 字符串）
# 抽取产物与 RuleExtractor 同构（Entity/Relation/ExtractionResult），
# 可直填 LightGraph / kg_explorer，不破坏既有运行路径。
# ──────────────────────────────────────────────────────────

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 供应商协议：给 prompt，回文本（期望为 JSON 字符串）。"""

    def complete(self, prompt: str) -> str:
        ...


class TemplateLLMProvider:
    """离线兜底 provider —— 不调任何外部服务，内部复用规则引擎产出结构化结果。

    作用：在尚未接入真实 LLM 时，让 `get_extractor("llm")` 端到端可跑，
    且证明"provider 可插拔"架构成立。生产替换为真实 provider 即可升精度。
    """

    def __init__(self) -> None:
        self._rule = RuleExtractor()

    def complete(self, prompt: str) -> str:
        # 从 prompt 中还原待抽取文本（prompt 末尾的 <TEXT>...</TEXT> 区块）
        import json
        m = re.search(r"<TEXT>(.*?)</TEXT>", prompt, re.S)
        text = m.group(1) if m else prompt
        # 复用规则引擎做"伪 LLM"抽取，序列化为 LLMExtractor 期望的 JSON 形状
        chunks = [type("C", (), {"text": text, "chunk_id": "c1"})()]
        res = self._rule.extract(chunks)
        payload = {
            "entities": [
                {"entity_id": e.entity_id, "entity_type": e.entity_type,
                 "mention": e.mention, "chunk_id": e.chunk_id}
                for e in res.entities
            ],
            "relations": [
                {"relation_id": r.relation_id, "subject": r.subject,
                 "predicate": r.predicate, "obj": r.obj, "chunk_id": r.chunk_id}
                for r in res.relations
            ],
        }
        return json.dumps(payload, ensure_ascii=False)


@register_extractor("llm")
class LLMExtractor:
    """LLM 抽取器：构造 prompt → 调 provider → 解析 JSON 为 ExtractionResult。

    与 RuleExtractor 同接口（extract(chunks) -> ExtractionResult），
    pipeline 可零改动切换：get_extractor("llm")(...).extract(chunks)。
    """

    # 提示词模板：约束 LLM 输出与 ontology 对齐的 JSON
    _PROMPT = (
        '你是医药销售知识图谱抽取器。从文本中抽取实体与关系，'
        '实体类型限定为 Doctor/Hospital/SalesRep/Product，'
        '关系类型限定为 covers/located_in/belongs_to。\n'
        '严格只输出 JSON：{{"entities":[{{"entity_id","entity_type","mention","chunk_id"}}],'
        '"relations":[{{"relation_id","subject","predicate","obj","chunk_id"}}]}}。\n'
        '待抽取文本：\n<TEXT>{text}</TEXT>'
    )

    def __init__(self, provider: Optional[LLMProvider] = None,
                 ontology_objects: Optional[list[dict]] = None,
                 ontology_links: Optional[list[dict]] = None):
        # 默认离线 provider（可离线运行）；生产注入真实 LLM provider
        self._provider = provider or TemplateLLMProvider()
        self._ent_counter = 0
        self._rel_counter = 0
        # 用于校验抽取类型是否对齐本体
        if ontology_objects is None:
            from ontology.objects import OBJECTS
            ontology_objects = OBJECTS
        if ontology_links is None:
            from ontology.links import LINKS
            ontology_links = LINKS
        self._valid_types = {o["name"] for o in ontology_objects}
        # 业务关系白名单：与 RuleExtractor 对齐（本体 LINKS 未含时兜底放行）
        self._valid_links = {l["name"] for l in ontology_links} | {
            "covers", "located_in", "belongs_to",
        }

    def extract(self, chunks: list) -> ExtractionResult:
        import json
        result = ExtractionResult()
        for chunk in chunks:
            prompt = self._PROMPT.format(text=chunk.text)
            raw = self._provider.complete(prompt)
            parsed = self._safe_parse(raw)
            self._merge(chunk.chunk_id, parsed, result)
        return result

    # ── 内部 ──
    def _safe_parse(self, raw: str) -> dict:
        import json
        # 容忍 LLM 在 JSON 前后裹多余文本：截取首个 { 到末个 }
        try:
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1 and e > s:
                return json.loads(raw[s:e + 1])
        except Exception:
            pass
        return {"entities": [], "relations": []}

    def _merge(self, chunk_id: str, parsed: dict, result: ExtractionResult) -> None:
        for e in parsed.get("entities", []):
            etype = e.get("entity_type")
            if etype not in self._valid_types:
                etype = etype or "Unknown"
            result.entities.append(Entity(
                entity_id=e.get("entity_id") or self._next_entity_id(etype),
                entity_type=etype,
                mention=e.get("mention", ""),
                chunk_id=chunk_id,
                properties=e.get("properties", {}) or {},
            ))
        for r in parsed.get("relations", []):
            pred = r.get("predicate")
            if pred not in self._valid_links:
                continue  # 丢弃不对齐本体的关系，保质量
            result.relations.append(Relation(
                relation_id=r.get("relation_id") or self._next_relation_id(),
                subject=r.get("subject", ""),
                predicate=pred,
                obj=r.get("obj", ""),
                chunk_id=chunk_id,
                confidence=r.get("confidence", 1.0),
            ))

    def _next_entity_id(self, etype: str) -> str:
        self._ent_counter += 1
        return f"{etype}:{self._ent_counter}"

    def _next_relation_id(self) -> str:
        self._rel_counter += 1
        return f"rel:{self._rel_counter}"


# ──────────────────────────────────────────────────────────
# 第八批：真实 LLM provider + 本地 NER 兜底 + 组合抽取器
#
# LangChainOpenAIProvider：基于 langchain_openai.ChatOpenAI
#   - 优先用 settings.LLM_*（API_KEY/MODEL/BASE_URL/TEMPERATURE）
#   - 缺失 API key 时降级到 TemplateLLMProvider（保证零密钥可跑）
# LocalNerProvider：仅产出 entities（无关系）
#   - 优先 spaCy(zh_core_web_sm 懒加载)
#   - 退而 GLiNER(零样本 NER)
#   - 都没有则抛错（由调用方决定 fallback）
# LLMWithNerFallbackExtractor（注册名 "llm_ner"）：
#   - 先 LLM；抛错则用 LocalNerProvider 补 entities + RuleExtractor 补 relations
# ──────────────────────────────────────────────────────────

class LangChainOpenAIProvider:
    """基于 LangChain OpenAI 兼容接口的 provider（生产用）。

    兼容 OpenAI / NVIDIA / 其它 OpenAI-compatible 端点（settings.LLM_BASE_URL）。
    缺失 LLM_API_KEY 时自动降级到 TemplateLLMProvider 并 warn。
    """

    def __init__(self, *, model: Optional[str] = None,
                 temperature: float = 0.0,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 fallback: Optional[LLMProvider] = None):
        from config import settings as _s
        self._model = model or _s.LLM_MODEL
        self._temperature = temperature
        self._base_url = base_url if base_url is not None else _s.LLM_BASE_URL
        self._api_key = api_key if api_key is not None else _s.LLM_API_KEY
        self._chat = None
        self._fallback = fallback or TemplateLLMProvider()
        if not self._api_key:
            logger.warning("LLM_API_KEY 未配置，LangChainOpenAIProvider 降级为 TemplateLLMProvider")
            return
        try:
            from langchain_openai import ChatOpenAI
            kwargs = {"model": self._model, "temperature": self._temperature}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._chat = ChatOpenAI(**kwargs)
        except Exception as e:
            logger.warning("ChatOpenAI 初始化失败（降级为 TemplateLLMProvider）: %s", e)
            self._chat = None

    def complete(self, prompt: str) -> str:
        if self._chat is None:
            return self._fallback.complete(prompt)
        try:
            resp = self._chat.invoke(prompt)
            return resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            logger.warning("LLM 调用失败（降级 TemplateLLMProvider）: %s", e)
            return self._fallback.complete(prompt)

    @property
    def is_real(self) -> bool:
        return self._chat is not None


class LocalNerProvider:
    """本地 NER provider（不依赖外部 LLM）。仅返回 entities，无 relations。"""

    def __init__(self, *, prefer: str = "auto"):
        # prefer: "auto" | "spacy" | "gliner"
        self._backend = None
        self._init_error = None
        self._prefer = prefer
        self._init_backend()

    def _init_backend(self) -> None:
        order = []
        if self._prefer == "auto":
            order = ["spacy", "gliner"]
        else:
            order = [self._prefer]
        for b in order:
            try:
                if b == "spacy":
                    import spacy
                    try:
                        nlp = spacy.load("zh_core_web_sm")
                    except OSError:
                        # 缺失模型：尝试懒下载（失败也接受，下一步尝试 gliner）
                        try:
                            from spacy.cli import download as _dl
                            _dl("zh_core_web_sm")
                            nlp = spacy.load("zh_core_web_sm")
                        except Exception as ie:
                            raise RuntimeError(f"spaCy zh 模型不可用: {ie}") from ie
                    self._backend = ("spacy", nlp)
                    logger.info("LocalNerProvider: 使用 spaCy zh_core_web_sm")
                    return
                elif b == "gliner":
                    from gliner import GLiNER
                    # 零样本：标签由调用方传；这里懒加载一个轻量模型
                    model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
                    self._backend = ("gliner", model)
                    logger.info("LocalNerProvider: 使用 GLiNER urchade/gliner_small-v2.1")
                    return
            except Exception as e:
                logger.debug("LocalNerProvider 后端 %s 初始化失败: %s", b, e)
                continue
        self._init_error = "无可用 NER 后端（spaCy/zh 与 gliner 均失败）"

    @property
    def is_available(self) -> bool:
        return self._backend is not None

    @property
    def backend_name(self) -> str:
        return self._backend[0] if self._backend else "none"

    def extract_entities(self, text: str, labels: Optional[list[str]] = None) -> list[dict]:
        """返回 [{"entity_id","entity_type","mention","start","end"}, ...]"""
        if not self.is_available:
            return []
        labels = labels or ["Doctor", "Hospital", "SalesRep", "Product"]
        b, m = self._backend
        ents: list[dict] = []
        if b == "spacy":
            doc = m(text)
            # spaCy 内置 label 映射到业务标签（启发式：PERSON→Doctor, ORG/GPE→Hospital, NORP→SalesRep）
            type_map = {"PERSON": "Doctor", "ORG": "Hospital", "GPE": "Hospital",
                        "LOC": "Hospital", "NORP": "SalesRep", "PRODUCT": "Product"}
            for i, ent in enumerate(doc.ents):
                et = type_map.get(ent.label_, "Unknown")
                if et not in {"Doctor", "Hospital", "SalesRep", "Product"}:
                    et = "Unknown"
                ents.append({
                    "entity_id": f"{et}:{i+1}",
                    "entity_type": et,
                    "mention": ent.text,
                    "start": ent.start_char, "end": ent.end_char,
                })
        elif b == "gliner":
            preds = m.predict_entities(text, labels)
            for i, p in enumerate(preds):
                ents.append({
                    "entity_id": f"{p['label']}:{i+1}",
                    "entity_type": p["label"],
                    "mention": p["text"],
                    "start": int(p.get("start", 0)), "end": int(p.get("end", 0)),
                })
        return ents


@register_extractor("llm_ner")
class LLMWithNerFallbackExtractor:
    """LLM 为主，失败时用本地 NER 补 entities + 规则补 relations。

    注册名 "llm_ner"。与 LLMExtractor / RuleExtractor 同接口：
        extract(chunks) -> ExtractionResult
    """

    def __init__(self, provider: Optional[LLMProvider] = None,
                 ner_provider: Optional[LocalNerProvider] = None,
                 ontology_objects: Optional[list[dict]] = None,
                 ontology_links: Optional[list[dict]] = None):
        # 真实 LLM provider（缺失密钥自动降级为 TemplateLLMProvider）
        if provider is None:
            from config import settings as _s
            if _s.LLM_API_KEY:
                provider = LangChainOpenAIProvider()
            else:
                provider = TemplateLLMProvider()
        self._llm_extractor = LLMExtractor(provider=provider,
                                           ontology_objects=ontology_objects,
                                           ontology_links=ontology_links)
        self._ner = ner_provider or LocalNerProvider()
        self._rule = RuleExtractor(ontology_objects=ontology_objects,
                                   ontology_links=ontology_links)

    def extract(self, chunks: list) -> ExtractionResult:
        # 1) 优先 LLM
        try:
            res = self._llm_extractor.extract(chunks)
            if res.entities or res.relations:
                return res
        except Exception as e:
            logger.warning("LLMExtractor 异常，触发 NER/规则兜底: %s", e)

        # 2) 兜底：本地 NER 补 entities + 规则补 relations
        result = ExtractionResult()
        for chunk in chunks:
            ents = self._ner.extract_entities(chunk.text) if self._ner.is_available else []
            for e in ents:
                result.entities.append(Entity(
                    entity_id=e.get("entity_id") or f"{e.get('entity_type','Unknown')}:x",
                    entity_type=e.get("entity_type", "Unknown"),
                    mention=e.get("mention", ""),
                    chunk_id=chunk.chunk_id,
                    properties={"start": e.get("start"), "end": e.get("end")},
                ))
            # 用规则抽取 relations（基于同 chunk 内的实体）
            rule_res = self._rule.extract([chunk])
            for r in rule_res.relations:
                result.relations.append(Relation(
                    relation_id=r.relation_id, subject=r.subject,
                    predicate=r.predicate, obj=r.obj,
                    chunk_id=chunk.chunk_id, confidence=r.confidence,
                ))
        return result
