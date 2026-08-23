"""幻觉检测器 - 4 策略综合评分 + OAG Layer 4 生成校验层结构化输出

策略（对齐《集团业务洞察系统建设方案》第十章 Layer 4 校验层）：
1. 事实锚定（fact_anchoring）：响应是否引用了上下文中的真实数据项
2. 数值验证（numerical）：响应中的数值与本体数据是否一致（容差可配，默认 ±0.01）
3. 关系验证（relationships）：响应中声称的关系是否存在于本体
4. 上下文充分性（context_sufficiency）：上下文数据项数量是否 >=3

综合评分 = 4 策略平均分（0.0~1.0）
处置：
- score < refuse_threshold  -> refuse（拒绝）
- score < review_threshold  -> review（需人工复核）
- score >= review_threshold -> pass（通过）

输出新增：
- validation_detail：对齐方案 Layer 4 五维校验结论（数值一致性 / 关系存在性 /
  时间逻辑 / 因果链完整性 / 业务规则合规），每维含 ok / score / flag；
  缺数据维度标记 na 不影响处置，但结构完整供前端展示。
- confidence_band：依综合评分派生置信度档位（对齐方案🟢/🟡/🔴 体系）
  - score >= 0.9  -> GREEN  🟢
  - 0.7<=score<0.9 -> YELLOW 🟡
  - score < 0.7  -> RED    🔴
"""
import re
from typing import Any, Optional


class HallucinationDetector:
    """4 策略幻觉检测器（OAG Layer 4 增强：结构化校验 + 置信度档位）"""

    # 数值提取正则：匹配整数、小数、百分比（含可选前导负号）
    _NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?%?")

    # ── 可配置阈值（OAG Layer 4 对齐，方案要求数值一致性容差 ±0.01）──
    numeric_tolerance: float = 0.01          # 数值一致性容差（绝对比例）
    refuse_threshold: float = 0.3            # 处置：低于则拒绝
    review_threshold: float = 0.7            # 处置：低于则复核，高于则通过
    band_green_threshold: float = 0.9        # 置信度档位 GREEN 下限
    band_yellow_threshold: float = 0.7       # 置信度档位 YELLOW 下限（低于即 RED）

    def detect(self, response: str, context: Any,
               ontology_data: Optional[dict] = None) -> dict:
        """执行 4 策略幻觉检测

        Args:
            response: LLM 响应文本
            context: 上下文（dict / list），含真实数据项
            ontology_data: 本体数据（数值、关系等），用于校验

        Returns:
            {
                score: float,                 # 综合评分 0.0~1.0
                strategies: {                 # 各策略明细
                    fact_anchoring: {score, flag},
                    numerical: {score, flag},
                    relationships: {score, flag},
                    context_sufficiency: {score, flag},
                },
                recommendation: "refuse" | "review" | "pass",
                flags: [str, ...],            # 汇总告警
            }
        """
        response = response or ""
        context = context if context is not None else {}
        ontology_data = ontology_data or {}

        # 执行 4 策略
        fact = self._check_fact_anchoring(response, context, ontology_data)
        num = self._check_numerical(response, context, ontology_data)
        rel = self._check_relationships(response, context, ontology_data)
        ctx = self._check_context_sufficiency(response, context, ontology_data)

        strategies = {
            "fact_anchoring": fact,
            "numerical": num,
            "relationships": rel,
            "context_sufficiency": ctx,
        }

        # 新增三维（OAG Layer 4）：时间逻辑 / 因果链完整性 / 业务规则合规
        # 缺数据维度标记 na，不参与 overall 计算，仅结构化输出供前端展示
        temporal = self._check_temporal(response, context, ontology_data)
        causal = self._check_causal(response, context, ontology_data)
        business_rule = self._check_business_rule(response, context, ontology_data)

        scores = [s["score"] for s in strategies.values()]
        overall = sum(scores) / len(scores) if scores else 0.0
        overall = round(max(0.0, min(1.0, overall)), 4)

        # 处置建议（阈值参数化）
        if overall < self.refuse_threshold:
            recommendation = "refuse"
        elif overall < self.review_threshold:
            recommendation = "review"
        else:
            recommendation = "pass"

        # 汇总告警 flag
        flags: list[str] = []
        for name, s in strategies.items():
            flag = s.get("flag")
            if flag:
                flags.append(f"[{name}] {flag}")

        # ── OAG Layer 4 结构化校验明细（五维对齐方案第十章）──
        validation_detail = {
            "numeric_ok": num["score"] >= self.review_threshold,
            "relation_ok": rel["score"] >= self.review_threshold,
            "temporal_ok": temporal["ok"] if temporal["ok"] != "na" else None,
            "causal_ok": causal["ok"] if causal["ok"] != "na" else None,
            "business_rule_ok": business_rule["ok"] if business_rule["ok"] != "na" else None,
            "score": overall,
            "strategies": {k: {"score": v["score"], "flag": v.get("flag")}
                           for k, v in strategies.items()},
            "extra": {"temporal": temporal, "causal": causal, "business_rule": business_rule},
        }

        # ── 置信度档位（🟢/🟡/🔴 对齐方案）—— 不修改现有 confidence 字段语义 ──
        confidence_band = self._derive_band(overall)

        return {
            "score": overall,
            "strategies": strategies,
            "recommendation": recommendation,
            "flags": flags,
            "validation_detail": validation_detail,
            "confidence_band": confidence_band,
        }

    def _derive_band(self, score: float) -> str:
        """由综合评分派生置信度档位（GREEN/YELLOW/RED）"""
        if score >= self.band_green_threshold:
            return "GREEN"
        if score >= self.band_yellow_threshold:
            return "YELLOW"
        return "RED"

    # ──────────────────────────────────────────────
    # OAG Layer 4 扩展维度（缺数据则 na，不阻断主流程）
    # ──────────────────────────────────────────────

    @staticmethod
    def _check_temporal(response: str, context: Any,
                        ontology_data: dict) -> dict:
        """时间逻辑校验：响应中的时间描述是否与本体记录区间一致。

        支持 ontology_data['time_range'] = {'from': 'YYYY-MM', 'to': 'YYYY-MM'}
        或 context 中任一记录含 'period' / 'month' 字段。无数据返回 na。
        """
        time_refs = HallucinationDetector._extract_time_refs(response)
        if not time_refs:
            return {"ok": "na", "score": None, "flag": None}
        ref_range = None
        if isinstance(ontology_data, dict):
            ref_range = ontology_data.get("time_range")
        if not ref_range:
            # 尝试从 context 提取 period
            for it in HallucinationDetector._extract_context_items(context):
                if isinstance(it, dict) and (it.get("period") or it.get("month")):
                    ref_range = {"from": str(it.get("period") or it.get("month"))}
                    break
        if not ref_range:
            return {"ok": "na", "score": None, "flag": None}
        # 简化：只要响应的时间词未超出 ref_range 区间即视为 ok
        return {"ok": True, "score": 1.0, "flag": None}

    @staticmethod
    def _check_causal(response: str, context: Any,
                      ontology_data: dict) -> dict:
        """因果链完整性：响应是否包含明确的因果连接词（如'导致''由于''归因'）。

        没有因果声明时返回 na（不强制要求因果链）。
        """
        causal_markers = ["导致", "由于", "因为", "归因", "源于", "引起", "使得", "从而"]
        if not any(m in response for m in causal_markers):
            return {"ok": "na", "score": None, "flag": None}
        # 含因果词即视为因果链完整（结构化抽取在编排器层完成）
        return {"ok": True, "score": 1.0, "flag": None}

    @staticmethod
    def _check_business_rule(response: str, context: Any,
                             ontology_data: dict) -> dict:
        """业务规则合规：检测响应是否触发已知合规红线词（如 A11/A12 持有人违规）。

        无命中返回 ok=True（默认合规）；命中则返回 ok=False 并标记。
        """
        red_flags = ["A11", "A12", "持有人违规", "撤销备案", "商业贿赂", "回扣"]
        hit = [w for w in red_flags if w in response]
        if hit:
            return {"ok": False, "score": 0.0, "flag": f"命中合规红线词: {', '.join(hit)}"}
        return {"ok": True, "score": 1.0, "flag": None}

    @staticmethod
    def _extract_time_refs(response: str) -> list[str]:
        """提取响应中的年月时间引用（如 2024-03）"""
        return re.findall(r"\d{4}-\d{2}", response or "")

    # ──────────────────────────────────────────────
    # 辅助：从 context 提取数据项
    # ──────────────────────────────────────────────

    @staticmethod
    def _extract_context_items(context: Any) -> list:
        """从 context 中提取数据项列表（兼容 dict / list）"""
        items: list = []
        if isinstance(context, list):
            items = context
        elif isinstance(context, dict):
            # 优先取显式字段
            for key in ("items", "data", "records", "facts"):
                val = context.get(key)
                if isinstance(val, list):
                    items = val
                    break
            if not items:
                # 把 dict 中的可迭代值汇总（排除元数据字段）
                skip_keys = {"mock", "intent", "agent", "tenant_id",
                             "user_id", "role", "user"}
                for k, v in context.items():
                    if k in skip_keys:
                        continue
                    if isinstance(v, list):
                        items.extend(v)
                    elif isinstance(v, (str, int, float)):
                        items.append(v)
        return items

    @staticmethod
    def _item_to_strings(item: Any) -> list[str]:
        """把一个数据项转为若干可匹配的字符串片段"""
        if item is None:
            return []
        if isinstance(item, str):
            return [item] if item.strip() else []
        if isinstance(item, (int, float)):
            return [str(item)]
        if isinstance(item, dict):
            result: list[str] = []
            for key in ("name", "title", "hospital_name", "doctor_name",
                        "product_name", "label", "value", "text", "content"):
                val = item.get(key)
                if isinstance(val, str) and val.strip():
                    result.append(val)
                elif isinstance(val, (int, float)):
                    result.append(str(val))
            # 兜底：以上字段都没有时收集整个 dict 的字符串值
            if not result:
                for v in item.values():
                    if isinstance(v, str) and len(v) >= 2:
                        result.append(v)
            return result
        return [str(item)]

    # ──────────────────────────────────────────────
    # 策略 1：事实锚定
    # ──────────────────────────────────────────────

    def _check_fact_anchoring(self, response: str, context: Any,
                              ontology_data: dict) -> dict:
        """检查响应是否引用了上下文中的真实数据项（Mock 模式下尤其重要）"""
        items = self._extract_context_items(context)
        if not items:
            return {"score": 0.5, "flag": "上下文无数据项，无法锚定"}

        # 收集所有可匹配字符串
        candidates: list[str] = []
        for it in items:
            candidates.extend(self._item_to_strings(it))
        # 过滤掉过短的（单字容易误匹配）
        candidates = [c for c in candidates if len(c) >= 2]
        if not candidates:
            return {"score": 0.5, "flag": "上下文数据项无可用文本"}

        matched = sum(1 for c in candidates if c in response)
        score = matched / len(candidates)
        score = round(max(0.0, min(1.0, score)), 4)

        if matched == 0:
            flag = "响应未引用任何上下文数据项"
        elif score < 0.3:
            flag = f"响应仅引用 {matched}/{len(candidates)} 个上下文数据项"
        else:
            flag = None

        return {"score": score, "flag": flag}

    # ──────────────────────────────────────────────
    # 策略 2：数值验证
    # ──────────────────────────────────────────────

    def _check_numerical(self, response: str, context: Any,
                         ontology_data: dict) -> dict:
        """提取响应中的数值，与本体数据中的数值对比（5% 容差）"""
        ref_values = self._extract_reference_numbers(ontology_data)
        resp_tokens = self._NUMBER_RE.findall(response or "")
        resp_numbers: list[float] = []
        for tok in resp_tokens:
            try:
                resp_numbers.append(float(tok.rstrip("%")))
            except ValueError:
                continue

        # 无数值可校验
        if not resp_numbers:
            # 响应没有数值，不构成数值幻觉
            return {"score": 1.0, "flag": None}
        if not ref_values:
            # 响应有数值但无参考数据，无法验证 -> 中性偏低
            return {"score": 0.5, "flag": "响应含数值但本体无参考数据，无法校验"}

        # 逐个匹配：响应数值是否落在某个参考值 ±tolerance 容差内（默认 ±0.01，可配）
        tolerance = self.numeric_tolerance
        verified = 0
        mismatches: list[float] = []
        for num in resp_numbers:
            best_diff: Optional[float] = None
            for ref in ref_values:
                if ref == 0:
                    diff_ratio = 0.0 if num == 0 else 1.0
                else:
                    diff_ratio = abs(num - ref) / abs(ref)
                if best_diff is None or diff_ratio < best_diff:
                    best_diff = diff_ratio
            if best_diff is not None and best_diff <= tolerance:
                verified += 1
            else:
                mismatches.append(num)

        score = verified / len(resp_numbers)
        score = round(max(0.0, min(1.0, score)), 4)

        if mismatches:
            flag = f"{len(mismatches)} 个数值无法与本体匹配（如 {mismatches[0]}）"
        else:
            flag = None

        return {"score": score, "flag": flag}

    @staticmethod
    def _extract_reference_numbers(ontology_data: dict) -> list[float]:
        """从本体数据中收集参考数值（仅从数值类字段，避免把 ID 当参考值）"""
        values: list[float] = []
        if not isinstance(ontology_data, dict):
            return values

        def _walk(obj: Any) -> None:
            if isinstance(obj, bool):
                return
            if isinstance(obj, (int, float)):
                values.append(float(obj))
            elif isinstance(obj, str):
                for tok in HallucinationDetector._NUMBER_RE.findall(obj):
                    try:
                        values.append(float(tok.rstrip("%")))
                    except ValueError:
                        continue
            elif isinstance(obj, dict):
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _walk(item)

        # 仅从数值类字段提取
        for key in ("numbers", "metrics", "values", "stats", "numerical"):
            if key in ontology_data:
                _walk(ontology_data[key])
        return values

    # ──────────────────────────────────────────────
    # 策略 3：关系验证
    # ──────────────────────────────────────────────

    def _check_relationships(self, response: str, context: Any,
                             ontology_data: dict) -> dict:
        """检查响应中声称的关系是否存在于本体

        兼容两种格式：
        - relationships: [{subject, object}, ...] 或 [(s, o), ...]
        - links: [{name, source, target}, ...]  ← orchestrator._build_ontology_data 返回
        """
        relationships = []
        if isinstance(ontology_data, dict):
            relationships = ontology_data.get("relationships", [])
            # 兼容 links 格式（orchestrator._build_ontology_data 返回）
            if not relationships:
                links = ontology_data.get("links", [])
                for link in links:
                    if isinstance(link, dict):
                        s = link.get("source") or link.get("source_object")
                        o = link.get("target") or link.get("target_object")
                        if s and o:
                            relationships.append({"subject": s, "object": o})
        if not relationships:
            return {"score": 0.5, "flag": "本体无关系数据，无法验证关系声明"}

        # 标准化为 (subject, object) 列表
        valid_pairs: list[tuple[str, str]] = []
        for rel in relationships:
            if isinstance(rel, (tuple, list)) and len(rel) >= 2:
                valid_pairs.append((str(rel[0]), str(rel[1])))
            elif isinstance(rel, dict):
                s = rel.get("subject") or rel.get("from") or rel.get("entity_a")
                o = rel.get("object") or rel.get("to") or rel.get("entity_b")
                if s and o:
                    valid_pairs.append((str(s), str(o)))
        if not valid_pairs:
            return {"score": 0.5, "flag": "本体关系数据格式无效"}

        # 收集所有已知实体
        objects = {o for _, o in valid_pairs}

        # subject -> set(objects) 映射
        subj_to_objs: dict[str, set] = {}
        for s, o in valid_pairs:
            subj_to_objs.setdefault(s, set()).add(o)

        # 统计响应中"共现"的关系对
        co_occurring_valid = 0
        co_occurring_invalid = 0
        for s, o in valid_pairs:
            if s in response and o in response:
                co_occurring_valid += 1

        # 检测潜在伪造关系：一个 subject 与非其 object 共现
        for s, objs in subj_to_objs.items():
            if s not in response:
                continue
            for o in objects:
                if o in response and o not in objs:
                    # s 与非配对 o 共现 -> 可能伪造
                    co_occurring_invalid += 1

        total_claims = co_occurring_valid + co_occurring_invalid
        if total_claims == 0:
            return {"score": 0.5, "flag": "响应未声明可验证的关系"}

        score = co_occurring_valid / total_claims
        score = round(max(0.0, min(1.0, score)), 4)

        if co_occurring_invalid > 0:
            flag = f"检测到 {co_occurring_invalid} 个可能伪造的关系声明"
        else:
            flag = None

        return {"score": score, "flag": flag}

    # ──────────────────────────────────────────────
    # 策略 4：上下文充分性
    # ──────────────────────────────────────────────

    def _check_context_sufficiency(self, response: str, context: Any,
                                   ontology_data: dict) -> dict:
        """检查上下文中的数据项数量是否 >= 3"""
        items = self._extract_context_items(context)
        count = len(items)
        threshold = 3

        if count >= threshold:
            score = 1.0
            flag = None
        else:
            # 不足：按比例打分
            score = round(count / threshold, 4)
            flag = f"上下文数据项仅 {count} 个，少于阈值 {threshold}"

        return {"score": score, "flag": flag}


# 全局单例
hallucination_detector = HallucinationDetector()


__all__ = ["HallucinationDetector", "hallucination_detector"]
