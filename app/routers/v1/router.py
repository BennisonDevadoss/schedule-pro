from fastapi import APIRouter

from .chat_router import chat_router
from .session_router import session_router
from .calendar_router import calendar_router
from .datasource_router import datasource_router, knowledgebase_datasource_router
from .knowledgebase_router import knowledgebase_router
from .conversation_router import conversation_router

v1_router = APIRouter(prefix="/v1", tags=["v1"])

v1_router.include_router(chat_router)
v1_router.include_router(session_router)
v1_router.include_router(calendar_router)
v1_router.include_router(datasource_router)  # Legacy endpoints
v1_router.include_router(knowledgebase_datasource_router)  # Enterprise standard
v1_router.include_router(knowledgebase_router)
v1_router.include_router(conversation_router)
