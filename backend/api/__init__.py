"""API 路由聚合"""
from fastapi import APIRouter
from api.auth import router as auth_router
from api.ai import router as ai_router
from api.ontology import router as ontology_router
# 业务域 stubs
from api.sales import router as sales_router
from api.training import router as training_router
from api.decision import router as decision_router
from api.collab import router as collab_router
from api.knowledge import router as knowledge_router
from api.platform import router as platform_router
from api.mdm import router as mdm_router
from api.audit import router as audit_router
from api.observability import router as observability_router
from api.crm import router as crm_router
from api.cfm import router as cfm_router
from api.tools import router as tools_router
from api.portal import router as portal_router
from api.profile import router as profile_router
from api.settings import router as settings_router
from api.collection import router as collection_router
from api.activity import router as activity_router
from api.notification import router as notification_router
# N+2 + N+3 新增路由
from api.persona import router as persona_router
from api.scenario import router as scenario_router
from api.ppt_speech import router as ppt_speech_router
from api.experience import router as experience_router
from api.context import router as context_router
from api.compliance import router as compliance_router
from api.academic import router as academic_router
from api.partner import router as partner_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(ai_router, tags=["ai"])
api_router.include_router(ontology_router, tags=["ontology"])
api_router.include_router(sales_router, tags=["sales"])
api_router.include_router(training_router, tags=["training"])
api_router.include_router(decision_router, tags=["decision"])
api_router.include_router(collab_router, tags=["collab"])
api_router.include_router(knowledge_router, tags=["knowledge"])
api_router.include_router(platform_router, tags=["platform"])
api_router.include_router(mdm_router, tags=["mdm"])
api_router.include_router(audit_router, tags=["audit"])
api_router.include_router(observability_router, tags=["observability"])
api_router.include_router(crm_router, tags=["crm"])
api_router.include_router(cfm_router, tags=["cfm"])
api_router.include_router(tools_router, tags=["tools"])
api_router.include_router(portal_router, tags=["portal"])
api_router.include_router(profile_router, tags=["profile"])
api_router.include_router(settings_router, tags=["settings"])
api_router.include_router(collection_router, tags=["collection"])
api_router.include_router(activity_router, tags=["activity"])
api_router.include_router(notification_router, tags=["notification"])
# N+2 + N+3 新增
api_router.include_router(persona_router, tags=["persona"])
api_router.include_router(scenario_router, tags=["scenario"])
api_router.include_router(ppt_speech_router, tags=["ppt_speech"])
api_router.include_router(experience_router, tags=["experience"])
api_router.include_router(context_router, tags=["context"])
# 合规适配（医药代表管理办法）
api_router.include_router(compliance_router, tags=["compliance"])
api_router.include_router(academic_router, tags=["academic"])
api_router.include_router(partner_router, tags=["partner"])
# 借鉴企业级诊断体系-批次2
from api.data_quality import router as data_quality_router
api_router.include_router(data_quality_router, tags=["data_quality"])
# B 路径：培训效果因果归因
from api.training_effect import router as training_effect_router
api_router.include_router(training_effect_router, tags=["training_effect"])
