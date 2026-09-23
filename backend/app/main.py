"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    chats,
    comparisons,
    contracts,
    dashboard,
    reviews,
    sessions,
    users,
)
from app.core.config import get_settings
from app.core.db import Base, engine
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis, init_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await init_redis()
    yield
    await close_redis()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(users.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(contracts.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(comparisons.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.app_name}
