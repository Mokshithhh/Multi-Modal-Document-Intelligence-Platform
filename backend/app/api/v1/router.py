from fastapi import APIRouter

from app.api.v1 import admin, auth, chat, documents

router = APIRouter()
router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(chat.router)
router.include_router(admin.router)
