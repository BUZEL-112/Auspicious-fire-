import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

JsonType = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    """User account record for wardrobe storage and personal preferences."""

    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True, index=True)
    display_name = Column(String(128), nullable=True)
    default_city = Column(String(128), nullable=True)
    default_style = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    wardrobe_items = relationship(
        "WardrobeItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Job(Base):
    """Vision processing job record."""

    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True, index=True)
    mode = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    bucket = Column(String(128), nullable=False)
    object_key = Column(String(256), nullable=False)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=True, index=True)
    item_id = Column(String(64), nullable=True)
    result = Column(JsonType, nullable=True)
    error_reason = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class WardrobeItem(Base):
    """Wardrobe item mapping table between user, image, and extracted tags."""

    __tablename__ = "wardrobe_items"

    item_id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False, index=True)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=True, unique=True, index=True)
    bucket = Column(String(128), nullable=False)
    object_key = Column(String(256), nullable=False)
    source_url = Column(String(512), nullable=True)
    status = Column(String(32), nullable=False, default="PENDING_TAGS", index=True)
    slot = Column(String(32), nullable=True, index=True)
    category = Column(String(64), nullable=True)
    color = Column(String(64), nullable=True)
    fabric = Column(String(64), nullable=True)
    pattern = Column(String(64), nullable=True)
    neckline = Column(String(64), nullable=True)
    sleeve = Column(String(64), nullable=True)
    fit = Column(String(64), nullable=True)
    tags_json = Column(JsonType, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user = relationship("User", back_populates="wardrobe_items")
