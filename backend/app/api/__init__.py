from fastapi import APIRouter

from app.api.ai import router as ai_router
from app.api.engines import router as engines_router
from app.api.health import router as health_router
from app.api.content import router as content_router
from app.api.knowledge import router as knowledge_router
from app.api.pk_engines import router as pk_engines_router
from app.api.projects import router as projects_router
from app.api.reference_data import router as reference_data_router
from app.api.research import router as research_router
from app.api.statistics import router as statistics_router
from app.api.validation import router as validation_router
from app.api.protocol import router as protocol_router
from app.api.regulatory_evidence import router as regulatory_evidence_router
from app.api.study_input import router as study_input_router
from app.api.decision_center import router as decision_center_router
from app.api.research_center import router as research_center_router
from app.api.sample_size_center import router as sample_size_center_router
from app.api.statistics_engine_api import router as statistics_engine_router
from app.api.study_workspace import router as study_workspace_router
from app.api.auth_api import router as auth_router
from app.api.beta_api import router as beta_router
from app.api.field_study_api import router as field_study_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(beta_router)
api_router.include_router(field_study_router)
api_router.include_router(projects_router)
api_router.include_router(engines_router)
api_router.include_router(pk_engines_router)
api_router.include_router(reference_data_router)
api_router.include_router(statistics_router)
api_router.include_router(validation_router)
api_router.include_router(research_router)
api_router.include_router(ai_router)
api_router.include_router(protocol_router)
api_router.include_router(knowledge_router)
api_router.include_router(content_router)
api_router.include_router(regulatory_evidence_router)
api_router.include_router(study_input_router)
api_router.include_router(decision_center_router)
api_router.include_router(research_center_router)
api_router.include_router(sample_size_center_router)
api_router.include_router(statistics_engine_router)
api_router.include_router(study_workspace_router)
