import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fashion_pipeline.api.routes import router as jobs_router
from fashion_pipeline.api.kafka_producer import kafka_service
from fashion_pipeline.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing API services...")
    # Initialize DB tables if not present
    try:
        await init_db()
        logger.info("Database schema initialized.")
    except Exception as e:
        logger.warning(f"Could not connect to database on startup: {e}")

    # Start Kafka Producer
    await kafka_service.start()
    yield
    # Shutdown Kafka Producer
    await kafka_service.stop()
    logger.info("API services shut down cleanly.")


app = FastAPI(
    title="Event-Driven Pre-Computed Fashion Vision Pipeline",
    description="Asynchronous, two-phase fashion recognition and outfit parsing engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)


@app.get("/healthz", tags=["System"])
async def healthz():
    return {"status": "ok", "service": "fashion-vision-api"}
