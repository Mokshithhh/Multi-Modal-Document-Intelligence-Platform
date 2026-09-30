import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pgvector.sqlalchemy import Vector
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import SessionFactory, engine
from app.models import Base
from app.services.documents import ingest_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def _ingestion_worker(redis: Redis) -> None:
    while True:
        try:
            job = await redis.brpop("ingestion:queue", timeout=5)
            if job:
                try:
                    await ingest_document(UUID(job[1]))
                except ValueError:
                    logger.exception("Ignoring malformed ingestion job: %s", job[1])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ingestion worker encountered an error")
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url, decode_responses=True, health_check_interval=30)
    app.state.redis = redis
    try:
        await redis.ping()
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)
        worker = asyncio.create_task(_ingestion_worker(redis), name="document-ingestion-worker")
        yield
    finally:
        if "worker" in locals():
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        await redis.aclose()
        await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        await app.state.redis.ping()
    except Exception as exc:
        logger.warning("Health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="A backing service is unavailable") from None
    return {"status": "ok", "database": "ok", "redis": "ok"}
