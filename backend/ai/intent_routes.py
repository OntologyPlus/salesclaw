"""意图路由配置（B3 配置化抽取）

从 orchestrator.py 迁移而来的意图路由常量：
- INTENT_KEYWORDS：关键词 → 意图映射
- DOMAIN_AGENT_MAP：domain → Agent 名称映射
- INTENT_SKILL_MAP：意图 → Skill 名称映射
- INTENT_RESPONSES：意图 → Mock 默认响应模板

新增工具函数：
- validate_routes()：检测关键词冲突（同一关键词出现在多个意图）
- get_intent_config(intent_name)：统一查询入口
"""
from typing import Any


# ──────────────────────────────────────────────
# 意图关键词映射表
# ──────────────────────────────────────────────

INTENT_KEYWORDS = [
    # (关键词列表, 意图名, domain)
    (["拜访", "visit", "见客户", "客户拜访"], "visit", "sales"),
    (["覆盖", "空白", "coverage", "潜力", "分管"], "coverage", "sales"),
    (["反馈", "feedback", "客户反馈", "意见"], "feedback", "sales"),
    (["积分", "score", "排行榜", "行为积分", "指令积分"], "scoring", "sales"),
    (["roi", "投入产出", "回报"], "roi", "sales"),
    (["矩阵", "matrix", "相关性"], "matrix", "sales"),
    (["kol", "koc", "意见领袖"], "kol", "sales"),
    (["课程", "培训", "course", "学习", "学什么"], "course", "training"),
    (["考试", "组卷", "阅卷", "exam", "题库"], "exam", "training"),
    (["直播", "live", "直播课"], "live", "training"),
    (["学习路径", "路径", "path", "进度"], "path", "training"),
    (["演练", "场景", "drill", "role play", "角色扮演"], "scene", "training"),
    (["练习", "practice", "实战"], "practice", "training"),
    (["kpi", "指标", "绩效"], "kpi", "decision"),
    (["归因", "attribution", "贡献"], "attribution", "decision"),
    (["模拟", "what-if", "simulation", "推演"], "simulation", "decision"),
    (["预警", "alert", "异常", "警告"], "alert", "decision"),
    (["待办", "todo", "task", "任务"], "task", "collab"),
    (["审批", "approve", "approval", "驳回"], "approval", "collab"),
    (["报告", "ppt", "周报", "月报", "report"], "report", "collab"),
    (["会议", "meeting", "议程", "cfm"], "meeting", "collab"),
    (["知识", "wiki", "文档", "knowledge"], "knowledge", "knowledge"),
    (["rag", "问答", "检索"], "rag", "knowledge"),
    (["外发", "outsend", "分享链接"], "outsend", "knowledge"),
    # 本体论+AI原生改造：诊断/归因结构化推理意图
    (["诊断", "diagnose", "诊断一下", "做一个诊断", "分析一下问题"], "diagnose", "decision"),
    (["归因", "attribution", "贡献分析", "根因", "为什么下降", "为什么下滑"], "attribute", "decision"),
    # N+AI原生闭环：范式沉淀 / 效果归因评估 / 主动建议 / AI洞察 四类推理意图
    (["沉淀范式", "derive_paradigm", "提炼范式", "沉淀方法论"], "derive_paradigm", "decision"),
    (["效果评估", "evaluate", "成效归因", "达成率分析", "为什么达成", "是否达标"], "evaluate", "decision"),
    (["主动建议", "suggest", "给我建议", "下一步做什么", "推荐行动"], "suggest", "decision"),
    (["洞察", "insight", "智能洞察", "生成洞察", "分析趋势"], "insight", "decision"),
    # N+3 Step4：辖区数据查询意图
    (["辖区", "territory", "达成率", "辖区本周", "辖区本月", "辖区数据"], "territory", "sales"),
    # N+5：培训场景创建（AI 原生工作流 Skill）
    (["创建场景", "新建场景", "建一个场景", "create scenario", "场景创建", "创建培训场景", "设计场景"], "scenario-create", "training"),
]


# ──────────────────────────────────────────────
# domain → Agent 名称映射
# ──────────────────────────────────────────────

DOMAIN_AGENT_MAP = {
    "global": "Supervisor",
    "sales": "SalesAgent",
    "training": "TrainingAgent",
    "decision": "DecisionAgent",
    "collab": "CollabAgent",
    "knowledge": "KnowledgeAgent",
}


# ──────────────────────────────────────────────
# 意图 → Skill 名称映射（覆盖全部 24 个意图）
# ──────────────────────────────────────────────

INTENT_SKILL_MAP = {
    "visit": "visit-planner",
    "coverage": "coverage-analyzer",
    "feedback": "feedback-extractor",
    "scoring": "scoring-analyzer",
    "roi": "roi-analyzer",
    "matrix": "matrix-builder",
    "kol": "kol-analyzer",
    "course": "course-recommender",
    "exam": "exam-generator",
    "live": "live-scheduler",
    "path": "path-optimizer",
    "scene": "scenario-generator",
    "practice": "practice-coach",
    "kpi": "kpi-monitor",
    "attribution": "attribution-analyzer",
    "simulation": "what-if-simulator",
    "alert": "alert-manager",
    "task": "task-prioritizer",
    "approval": "approval-assistant",
    "meeting": "meeting-organizer",
    "report": "report-builder",
    "knowledge": "rag-qa",
    "rag": "rag-qa",
    "outsend": "content-outsender",
    "territory": "territory-reporter",
    "diagnose": "diagnosis-engine",
    "attribute": "attribution-analyzer",
    # N+AI原生闭环：四类推理意图对应 skill
    "derive_paradigm": "paradigm-distiller",
    "evaluate": "effect-evaluator",
    "suggest": "proactive-advisor",
    "insight": "insight-generator",
    # N+5：培训场景创建工作流
    "scenario-create": "scenario-generator",
}


# ──────────────────────────────────────────────
# 意图 → 默认 Mock 响应模板
# ──────────────────────────────────────────────

INTENT_RESPONSES = {
    "visit": (
        "我已为您分析本周拜访情况。\n"
        "- 建议优先拜访 3 家三甲医院的 5 位核心医生\n"
        "- 其中 2 位医生近 30 天未拜访，需重点关注\n"
        "- 推荐话题：最新临床数据、产品安全性更新\n"
        "是否需要我帮您生成详细的拜访计划？"
    ),
    "coverage": (
        "覆盖分析完成。\n"
        "- 您的区域内共有 45 家医院，已覆盖 32 家（71%）\n"
        "- 存在 13 家空白点，其中 5 家为潜力三甲医院\n"
        "- 建议本季度新增覆盖 3 家\n"
        "是否需要查看详细的覆盖矩阵？"
    ),
    "feedback": (
        "已从近期拜访记录中抽取关键反馈。\n"
        "- 正面反馈占比 62%（上升 8%）\n"
        "- 主要关注点：疗效、安全性、价格\n"
        "- 1 位医生提出不良反应疑问，建议医学部跟进\n"
        "是否需要查看完整反馈报告？"
    ),
    "scoring": (
        "积分排行已更新。\n"
        "- 您的行为积分：87 分（区域第 3）\n"
        "- 指令积分：92 分（区域第 1）\n"
        "- 本周可冲刺的行为积分项：拜访完成率、客户覆盖\n"
        "是否需要查看详细积分明细？"
    ),
    "roi": (
        "ROI 分析完成。\n"
        "- 本季度投入产出比：1:3.2\n"
        "- 最优渠道：线下拜访（ROI 4.1）\n"
        "- 待优化：会议投入（ROI 1.8）\n"
        "是否需要查看完整 ROI 报告？"
    ),
    "matrix": (
        "覆盖矩阵已生成。\n"
        "- 代表 × 医院 × 产品 三维矩阵\n"
        "- 高相关：产品 A 与三甲医院\n"
        "- 低相关：产品 C 与社区医院\n"
        "是否需要导出矩阵详情？"
    ),
    "course": (
        "根据您的画像，推荐以下课程：\n"
        "1. 《产品知识进阶》- 必修\n"
        "2. 《高效拜访技巧》- 推荐\n"
        "3. 《客户关系管理》- 推荐\n"
        "是否需要立即报名其中一门？"
    ),
    "exam": (
        "已为您生成模拟试卷。\n"
        "- 题目数量：20 道（单选 10 + 多选 5 + 案例 5）\n"
        "- 难度：中等\n"
        "- 预计用时：30 分钟\n"
        "是否需要开始考试？"
    ),
    "live": (
        "近期直播课程：\n"
        "- 《Q3 产品策略解读》- 周三 14:00\n"
        "- 《合规销售实务》- 周五 10:00\n"
        "是否需要加入直播提醒？"
    ),
    "path": (
        "您的学习路径优化建议：\n"
        "- 当前进度：65%\n"
        "- 建议下一步：完成《客户分析》章节\n"
        "- 预计 2 周内可完成全部路径\n"
        "是否需要调整学习计划？"
    ),
    "scene": (
        "已为您生成演练场景：\n"
        "- 场景：向三甲医院主任介绍新产品\n"
        "- 角色：销售代表 vs 主任（AI 扮演）\n"
        "- 难度：中等\n"
        "是否需要开始演练？"
    ),
    "kpi": (
        "KPI 监控概览：\n"
        "- 拜访达成率：92%（目标 90%，达标）\n"
        "- 覆盖率：71%（目标 80%，差距 9%）\n"
        "- 客户满意度：4.3/5（目标 4.0，达标）\n"
        "是否需要查看详细 KPI 拆解？"
    ),
    "attribution": (
        "归因分析完成：\n"
        "- 拜访频次贡献度：38%\n"
        "- 客户画像匹配度：27%\n"
        "- 产品话题相关性：21%\n"
        "- 其他：14%\n"
        "是否需要查看完整归因报告？"
    ),
    "simulation": (
        "What-if 模拟结果：\n"
        "- 场景：拜访频次 +20%\n"
        "- 预期 KPI 提升：+8.5%\n"
        "- 资源投入：+15%\n"
        "- 净收益：正向\n"
        "是否需要保存该模拟场景？"
    ),
    "alert": (
        "当前预警：\n"
        "- [高] 区域 B 覆盖率低于阈值（65%）\n"
        "- [中] 客户 C 反馈异常，需跟进\n"
        "- [低] 周报提交延迟\n"
        "是否需要分发预警给相关负责人？"
    ),
    "task": (
        "您的待办清单：\n"
        "1. [今日] 提交本周拜访计划\n"
        "2. [明日] 跟进客户 C 的反馈\n"
        "3. [本周] 完成《产品知识》课程\n"
        "是否需要创建新的待办？"
    ),
    "approval": (
        "待审批事项：\n"
        "1. 张三的本周拜访计划（建议：通过）\n"
        "2. 李四的差旅报销（建议：通过）\n"
        "3. 王五的样品申请（建议：补充说明）\n"
        "是否需要批量审批？"
    ),
    "knowledge": (
        "知识库检索结果：\n"
        "1. 《产品 A 临床数据汇编》\n"
        "2. 《竞品对比分析》\n"
        "3. 《合规销售指引》\n"
        "是否需要查看某篇文档详情？"
    ),
    "rag": (
        "基于知识库的回答：\n"
        "根据《产品 A 说明书》，该产品的适应症为...\n"
        "建议剂量为...\n"
        "常见不良反应包括...\n"
        "引用来源：《产品 A 说明书》第 3 页"
    ),
    "outsend": (
        "外发链接已生成：\n"
        "- 链接：https://demo.com/s/abc123\n"
        "- 有效期：7 天\n"
        "- 访问次数：不限\n"
        "是否需要设置访问密码？"
    ),
    "meeting": (
        "近期会议：\n"
        "1. 全国销售大会 - 8月15日\n"
        "2. 区域经验分享会 - 8月20日\n"
        "3. 产品发布会 - 9月1日\n"
        "是否需要加入会议日程？"
    ),
    "kol": (
        "KOL 画像分析：\n"
        "- 主任 A：核心 KOL，影响力高\n"
        "- 教授 B：潜力 KOL，学术活跃\n"
        "- 院长 C：战略 KOL，决策权大\n"
        "是否需要查看 KOL 合作建议？"
    ),
    "report": (
        "报告生成完成：\n"
        "- 类型：周报\n"
        "- 周期：本周\n"
        "- 关键指标：拜访 23 次、覆盖率 71%、KPI 达标\n"
        "是否需要导出为 PPT？"
    ),
    "scenario-create": (
        "好的，我们将通过对话式工作流创建培训场景。\n"
        "- 我会先拉取场景配置（场景主题/业务领域/受训对象）\n"
        "- 然后采集关键信息（医生画像/最佳实践点/品种）\n"
        "- 接着生成标题与背景供您确认\n"
        "- 再推荐并锁定知识条目\n"
        "- 最后生成上下文 Payload 并落库\n"
        "请告诉我您希望的场景主题（如：拜访、议价、异议处理、对话）。"
    ),
    # 结构化诊断输出（mock 模式也返回 JSON，供解析为 Diagnosis/Signal 实体）
    "diagnose": (
        '{"summary":"该代表在覆盖域存在明显缺口，重点医院拜访频次不足导致处方转化停滞。",'
        '"level":"YELLOW","confidence":0.78,"domain":"coverage",'
        '"signals":['
        '{"name":"覆盖空白点","category":"coverage_gap","severity":"high","description":"5家潜力三甲医院近30天未拜访","clear_condition":"近30天至少完成1次有效拜访"},'
        '{"name":"拜访衰减","category":"visit_decay","severity":"medium","description":"周拜访次数环比下降22%","clear_condition":"连续两周拜访达标"},'
        '{"name":"处方停滞","category":"rx_stall","severity":"medium","description":"核心医生处方量连续两周期持平","clear_condition":"处方量环比提升≥5%"}'
        '],'
        '"evidence":['
        '{"source":"visit_log","metric":"visit_count_30d","value":"12","ref":"visit_plan"},'
        '{"source":"rx_data","metric":"rx_trend","value":"flat","ref":"prescription"}'
        '],'
        '"reasoning_trace":['
        '{"step":1,"thought":"聚合近30天拜访与处方数据","tool":"sql_aggregate","observation":"覆盖缺口显著"},'
        '{"step":2,"thought":"定位缺口医院与衰减趋势","tool":"trend_analysis","observation":"5家三甲未覆盖"},'
        '{"step":3,"thought":"推导处方停滞归因","tool":"correlation","observation":"拜访-处方正相关"}'
        ']}'
    ),
    # 结构化归因输出（mock 模式返回 JSON）
    "attribute": (
        '{"summary":"拜访频次不足是覆盖率差距的主要归因因素，其次为客户画像匹配度偏低。",'
        '"level":"YELLOW","confidence":0.82,"domain":"attribution",'
        '"factors":['
        '{"name":"拜访频次不足","contribution":0.41,"direction":"negative","evidence":"visit_count_30d 低于阈值"},'
        '{"name":"客户画像匹配度低","contribution":0.27,"direction":"negative","evidence":"profile_match<0.6"},'
        '{"name":"产品话题相关性弱","contribution":0.18,"direction":"negative","evidence":"topic_relevance<0.5"},'
        '{"name":"竞品挤压","contribution":0.14,"direction":"negative","evidence":"competitor_share_up"}'
        '],'
        '"root_cause":"拜访频次不足导致覆盖缺口",'
        '"evidence":['
        '{"source":"attribution_model","metric":"contrib_visit","value":"0.41","ref":"attribution"},'
        '{"source":"profile","metric":"match_score","value":"0.58","ref":"ability_profile"}'
        ']}'
    ),
    # 范式沉淀结构化输出（经编排器七步状态机，落 Paradigm 实体 + reasoning_chain_id）
    "derive_paradigm": (
        '{"summary":"已将该闭环执行沉淀为可复用解题范式：以覆盖缺口定位为切入，通过高频拜访+学术证据组合撬动处方转化。",'
        '"problem_type":"coverage_gap","title":"三甲覆盖缺口攻坚范式","effective_method":"高频拜访+学术证据双轮驱动，先定位缺口医院再逐院突破",'
        '"effectiveness_score":0.86,"evidence_execution_ids":[],'
        '"reasoning_trace":['
        '{"step":1,"thought":"评估该执行是否可闭环复用","tool":"paradigm_distill","observation":"达成率≥80% 且证据充分"},'
        '{"step":2,"thought":"抽取可迁移方法论","tool":"pattern_extract","observation":"高频拜访+学术证据组合"},'
        '{"step":3,"thought":"写入 Paradigm 本体并关联 source 推理链","tool":"persist_paradigm","observation":"范式已沉淀"}'
        ']}'
    ),
    # 效果归因评估结构化输出（经编排器七步状态机，落 DecisionExecution.reasoning_chain_id）
    "evaluate": (
        '{"summary":"该决策执行整体达成，覆盖与处方指标均超目标，但客户满意度略低于预期，为主要扣分项。",'
        '"achievement_rate":0.94,"verdict":"partial_achieved",'
        '"reasons":['
        '{"factor":"拜访达成率","status":"above_target","contribution":0.46,"detail":"实际 23 次 vs 目标 20 次"},'
        '{"factor":"处方转化","status":"above_target","contribution":0.33,"detail":"环比 +12%"},'
        '{"factor":"客户满意度","status":"below_target","contribution":-0.15,"detail":"4.3 vs 目标 4.5"}'
        '],'
        '"reasoning_trace":['
        '{"step":1,"thought":"对比 baseline/target/actual 三组指标","tool":"metric_compare","observation":"两升一降"},'
        '{"step":2,"thought":"推导达成与未达成根因","tool":"root_cause","observation":"拜访与处方驱动达成"},'
        '{"step":3,"thought":"生成可解释评估结论","tool":"persist_evaluate","observation":"关联 source 推理链"}'
        ']}'
    ),
    # 主动建议结构化输出（经编排器七步状态机，统一 provenance）
    "suggest": (
        '{"summary":"基于当前辖区与反馈数据，建议优先处理覆盖缺口与培训到期两项。",'
        '"suggestions":['
        '{"type":"coverage_reminder","title":"3 家三甲近 30 天未拜访","priority":"high","action":{"type":"navigate","target":"/sales/plans"}},'
        '{"type":"training_reminder","title":"合规培训 5 天后到期","priority":"medium","action":{"type":"navigate","target":"/training/courses"}},'
        '{"type":"feedback_followup","title":"1 条负面反馈待处理","priority":"high","action":{"type":"navigate","target":"/sales/feedback"}}'
        '],'
        '"reasoning_trace":['
        '{"step":1,"thought":"扫描多源数据模式","tool":"data_scan","observation":"覆盖/培训/反馈三类信号"},'
        '{"step":2,"thought":"按优先级排序建议","tool":"prioritize","observation":"高危优先"},'
        '{"step":3,"thought":"生成可解释建议并落 provenance","tool":"persist_suggest","observation":"建议已生成"}'
        ']}'
    ),
    # AI 洞察结构化输出（经编排器七步状态机，统一 provenance）
    "insight": (
        '{"summary":"辖区整体健康度良好，覆盖率与拜访达标，但客户满意度存在下滑趋势需关注。",'
        '"insights":['
        '{"type":"trend","level":"info","message":"拜访达成率环比 +8%，保持上升"},'
        '{"type":"risk","level":"warning","message":"客户满意度近两周下降 0.2 分，需排查"},'
        '{"type":"opportunity","level":"info","message":"5 家潜力三甲待覆盖，转化空间大"}'
        '],'
        '"recommendations":["优先补覆盖缺口","发起满意度回访"],'
        '"risk_alerts":[],'
        '"reasoning_trace":['
        '{"step":1,"thought":"聚合跨域指标","tool":"aggregate","observation":"多维指标就绪"},'
        '{"step":2,"thought":"识别趋势与风险","tool":"trend_detect","observation":"满意度下滑信号"},'
        '{"step":3,"thought":"生成洞察并落 provenance","tool":"persist_insight","observation":"洞察已生成"}'
        ']}'
    ),
}


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def validate_routes() -> list[dict]:
    """检测关键词冲突（同一关键词出现在多个意图）

    Returns:
        冲突列表，每项 {keyword, intents: [intent_name, ...]}
        空列表表示无冲突
    """
    keyword_intents: dict[str, list[str]] = {}
    for keywords, intent_name, _ in INTENT_KEYWORDS:
        for kw in keywords:
            keyword_intents.setdefault(kw, []).append(intent_name)

    conflicts = []
    for kw, intents in keyword_intents.items():
        unique_intents = list(set(intents))
        if len(unique_intents) > 1:
            conflicts.append({"keyword": kw, "intents": unique_intents})
    return conflicts


def get_intent_config(intent_name: str) -> dict[str, Any]:
    """统一查询意图配置

    Returns:
        {intent, domain, agent, skill, mock_response}
    """
    # 找 domain
    domain = None
    for keywords, name, dom in INTENT_KEYWORDS:
        if name == intent_name:
            domain = dom
            break

    # 找 agent
    agent = DOMAIN_AGENT_MAP.get(domain or "global", "Supervisor")

    # 找 skill
    skill = INTENT_SKILL_MAP.get(intent_name)

    # 找 mock response
    mock_response = INTENT_RESPONSES.get(intent_name, "")

    return {
        "intent": intent_name,
        "domain": domain,
        "agent": agent,
        "skill": skill,
        "mock_response": mock_response,
    }


__all__ = [
    "INTENT_KEYWORDS",
    "DOMAIN_AGENT_MAP",
    "INTENT_SKILL_MAP",
    "INTENT_RESPONSES",
    "validate_routes",
    "get_intent_config",
]
