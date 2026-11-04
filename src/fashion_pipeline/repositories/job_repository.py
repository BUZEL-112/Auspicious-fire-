from typing import Any, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.db.models import Job


class JobRepository:
    """Repository handling database operations for Job records."""

    async def get_by_id(self, session: AsyncSession, job_id: str) -> Optional[Job]:
        """Fetch a job record by primary key."""
        stmt = select(Job).where(Job.id == job_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, job: Job) -> Job:
        """Persist a new job record."""
        session.add(job)
        await session.flush()
        return job

    async def update_status(
        self,
        session: AsyncSession,
        job_id: str,
        status: str,
        result: Optional[Any] = None,
        error_reason: Optional[str] = None,
    ) -> Optional[Job]:
        """Update job execution status, result payload, and error details."""
        stmt = (
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=status,
                result=result,
                error_reason=error_reason,
            )
            .execution_options(synchronize_session="fetch")
        )
        await session.execute(stmt)
        return await self.get_by_id(session, job_id)
