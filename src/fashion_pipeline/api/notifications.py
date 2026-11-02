import asyncio
import json
import logging
from typing import AsyncGenerator
import asyncpg
from fashion_pipeline.config.settings import settings

logger = logging.getLogger(__name__)


from sqlalchemy.engine import make_url

def get_asyncpg_connection_kwargs() -> dict:
    sa_url = make_url(settings.DATABASE_URL)
    return {
        "user": sa_url.username or "postgres",
        "password": sa_url.password or "",
        "database": sa_url.database or "postgres",
        "host": sa_url.host or "localhost",
        "port": sa_url.port or 5432,
    }


async def listen_for_job_notification(job_id: str, timeout_seconds: float = 60.0) -> AsyncGenerator[str, None]:
    """Connects to Postgres and listens on channel 'job_updates'.

    Yields SSE formatted JSON messages when matching job_id is updated.
    """
    queue: asyncio.Queue[str] = asyncio.Queue()

    def notification_handler(connection, pid, channel, payload):
        try:
            data = json.loads(payload)
            if data.get("job_id") == job_id:
                queue.put_nowait(payload)
        except Exception as e:
            logger.error(f"Error handling NOTIFY payload: {e}")

    conn = None
    try:
        kwargs = get_asyncpg_connection_kwargs()
        conn = await asyncpg.connect(**kwargs)
        await conn.add_listener("job_updates", notification_handler)

        elapsed = 0.0
        interval = 0.5
        while elapsed < timeout_seconds:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=interval)
                yield f"data: {payload}\n\n"
                data = json.loads(payload)
                if data.get("status") in ("COMPLETED", "FAILED"):
                    break
            except asyncio.TimeoutError:
                elapsed += interval
                # Yield ping/keepalive comment
                yield ": keepalive\n\n"

    except Exception as e:
        logger.warning(f"Postgres NOTIFY listener failed ({e}). Yielding fallback SSE.")
        yield f"data: {json.dumps({'job_id': job_id, 'status': 'PROCESSING', 'info': 'polling_fallback'})}\n\n"
    finally:
        if conn:
            try:
                await conn.remove_listener("job_updates", notification_handler)
                await conn.close()
            except Exception:
                pass
