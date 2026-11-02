"""End-to-End Pipeline Verification Script for Google Colab (Docker-Free).

Tests:
1. API Health Check (/healthz)
2. Stage 1 Single-Garment Tagging (POST /api/v1/jobs?mode=stage_1)
3. Job Polling & Verification (GET /api/v1/jobs/{job_id})
4. Stage 2 Multi-Garment Outfit Parsing (POST /api/v1/jobs?mode=stage_2)
5. Crop Generation and Presigned URLs
"""

import io
import json
import sys
import time
from typing import Dict, Any, Optional
import httpx
from PIL import Image, ImageDraw

API_BASE_URL = "http://localhost:8000"


def create_synthetic_garment_image() -> bytes:
    """Creates a synthetic single-garment JPEG image (red dress on neutral background)."""
    img = Image.new("RGB", (400, 600), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    # Draw simple red garment shape
    draw.polygon([(150, 100), (250, 100), (320, 500), (80, 500)], fill=(200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def create_synthetic_outfit_image() -> bytes:
    """Creates a synthetic multi-garment outfit JPEG image (upper clothes + pants)."""
    img = Image.new("RGB", (400, 800), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    # Upper-clothes: blue top
    draw.rectangle([120, 150, 280, 420], fill=(30, 80, 200))
    # Pants: dark grey jeans
    draw.rectangle([110, 430, 290, 700], fill=(40, 40, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def wait_for_api_ready(client: httpx.Client, max_retries: int = 30) -> None:
    """Verifies API gateway responds to /healthz."""
    print("Waiting for API service at http://localhost:8000/healthz...")
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.get(f"{API_BASE_URL}/healthz", timeout=3.0)
            if resp.status_code == 200:
                print(f"API service is healthy: {resp.json()}")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Timed out waiting for API service to become ready.")


def poll_job_until_done(
    client: httpx.Client,
    job_id: str,
    timeout_seconds: int = 60,
    poll_interval: float = 1.0,
) -> Dict[str, Any]:
    """Polls GET /api/v1/jobs/{job_id} until terminal state."""
    start_time = time.time()
    url = f"{API_BASE_URL}/api/v1/jobs/{job_id}"

    while time.time() - start_time < timeout_seconds:
        resp = client.get(url, timeout=5.0)
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
        data = resp.json()
        status = data.get("status")

        if status in ("COMPLETED", "FAILED"):
            return data

        time.sleep(poll_interval)

    raise TimeoutError(f"Job {job_id} did not finish within {timeout_seconds} seconds.")


def test_stage_1_pipeline(client: httpx.Client) -> None:
    """Tests Stage 1 Single-Garment Tagging end-to-end."""
    print("\n--- Testing Stage 1: Single-Garment Tagging ---")
    image_bytes = create_synthetic_garment_image()

    resp = client.post(
        f"{API_BASE_URL}/api/v1/jobs?mode=stage_1",
        files={"file": ("garment.jpg", image_bytes, "image/jpeg")},
        timeout=10.0,
    )
    assert resp.status_code == 202, f"Failed job submit: {resp.status_code} - {resp.text}"
    job_info = resp.json()
    job_id = job_info["job_id"]
    print(f"Job submitted successfully. Job ID: {job_id}")

    # Poll for completion
    completed_job = poll_job_until_done(client, job_id, timeout_seconds=60)
    print(f"Job finished with status: {completed_job['status']}")
    assert completed_job["status"] == "COMPLETED", f"Stage 1 failed: {completed_job.get('error_reason')}"

    pieces = completed_job.get("pieces", [])
    assert len(pieces) >= 1, "Expected at least 1 garment piece in Stage 1 result."
    first_piece = pieces[0]
    print(f"Piece ID: {first_piece.get('piece_id')}")
    print(f"Detected Label: {first_piece.get('label')}")
    print(f"Tags: {json.dumps(first_piece.get('tags', {}), indent=2)}")
    print("Stage 1 test PASSED.")


def test_stage_2_pipeline(client: httpx.Client) -> None:
    """Tests Stage 2 Multi-Object Outfit Parsing end-to-end."""
    print("\n--- Testing Stage 2: Multi-Object Outfit Parsing ---")
    image_bytes = create_synthetic_outfit_image()

    resp = client.post(
        f"{API_BASE_URL}/api/v1/jobs?mode=stage_2",
        files={"file": ("outfit.jpg", image_bytes, "image/jpeg")},
        timeout=10.0,
    )
    assert resp.status_code == 202, f"Failed job submit: {resp.status_code} - {resp.text}"
    job_info = resp.json()
    job_id = job_info["job_id"]
    print(f"Stage 2 Job submitted successfully. Job ID: {job_id}")

    completed_job = poll_job_until_done(client, job_id, timeout_seconds=90)
    print(f"Stage 2 Job finished with status: {completed_job['status']}")
    assert completed_job["status"] == "COMPLETED", f"Stage 2 failed: {completed_job.get('error_reason')}"

    pieces = completed_job.get("pieces", [])
    print(f"Total outfit pieces parsed: {len(pieces)}")
    assert len(pieces) > 0, "Expected parsed pieces in Stage 2."

    for p in pieces:
        print(f" - [{p.get('piece_id')}] Label: {p.get('label')}, Pixel Count: {p.get('pixel_count')}")
        print(f"   BBox: {p.get('bbox')}")
        print(f"   Crop URL: {p.get('crop_url')}")

    print("Stage 2 test PASSED.")


def main():
    print("=================================================================")
    print("Fashion Vision Pipeline: End-to-End Test Suite")
    print("=================================================================")

    with httpx.Client() as client:
        try:
            wait_for_api_ready(client)
            test_stage_1_pipeline(client)
            test_stage_2_pipeline(client)
            print("\n=================================================================")
            print("ALL END-TO-END PIPELINE TESTS PASSED SUCCESSFULLY!")
            print("=================================================================")
        except Exception as e:
            print(f"\nTEST SUITE FAILED: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
