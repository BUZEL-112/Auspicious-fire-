"""FastAPI package.

The ASGI app lives in ``fashion_pipeline.api.main:app``. It is not imported here:
an eager import created a circular import (services -> api -> routes -> services)
whenever a service module imported ``fashion_pipeline.api.kafka_producer``.
"""
