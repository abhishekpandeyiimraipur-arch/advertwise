from fastapi import APIRouter
from .stubs import router as stubs_router

router = APIRouter()
router.include_router(stubs_router, prefix="/api")
