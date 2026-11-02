import datetime
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True, index=True)
    mode = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    bucket = Column(String(128), nullable=False)
    object_key = Column(String(256), nullable=False)
    result = Column(JSONB, nullable=True)
    error_reason = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
