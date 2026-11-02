import pytest
from unittest.mock import MagicMock, AsyncMock
from fashion_pipeline.worker.consumer import FashionGPUWorker
from fashion_pipeline.schemas.job import JobStatus, ErrorReason, ExecutionMode


@pytest.mark.asyncio
async def test_worker_parse_s3_event_payload():
    worker = FashionGPUWorker()
    s3_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "raw-images"},
                    "object": {"key": "stage1/job-abc12345.jpg"},
                }
            }
        ]
    }
    job_id, bucket, key, mode = worker._parse_event_payload(s3_event, "fashion.jobs.stage1")
    assert job_id == "job-abc12345"
    assert bucket == "raw-images"
    assert key == "stage1/job-abc12345.jpg"
    assert mode == ExecutionMode.STAGE_1


@pytest.mark.asyncio
async def test_worker_parse_stage2_event_payload():
    worker = FashionGPUWorker()
    s3_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "raw-images"},
                    "object": {"key": "stage2/outfit-999.jpg"},
                }
            }
        ]
    }
    job_id, bucket, key, mode = worker._parse_event_payload(s3_event, "fashion.jobs.stage2")
    assert job_id == "outfit-999"
    assert mode == ExecutionMode.STAGE_2


def test_classify_error():
    worker = FashionGPUWorker()
    err1 = ValueError("NO_GARMENTS_DETECTED")
    assert worker._classify_error(err1) == ErrorReason.NO_GARMENTS_DETECTED.value

    err2 = ValueError("Could not decode image bytes into valid image")
    assert worker._classify_error(err2) == ErrorReason.CORRUPTED_IMAGE.value

    err3 = RuntimeError("CUDA out of memory")
    assert worker._classify_error(err3) == ErrorReason.INFERENCE_ERROR.value
