import asyncio
import logging
from fashion_pipeline.worker.consumer import FashionGPUWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("worker.main")


async def main():
    logger.info("Booting Fashion GPU Worker Service...")
    worker = FashionGPUWorker()
    try:
        await worker.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received exit signal, shutting down...")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
