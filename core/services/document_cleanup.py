import time
from pathlib import Path

from django.conf import settings


RETENTION_SECONDS = 60 * 60


def cleanup_expired_documents():
    processing_dir = Path(settings.MEDIA_ROOT) / "processing"

    if not processing_dir.exists():
        return {"deleted": 0, "failed": 0}

    deleted = 0
    failed = 0
    now = time.time()

    for job_dir in processing_dir.iterdir():
        if not job_dir.is_dir():
            continue

        metadata_path = job_dir / "created_at.txt"

        if not metadata_path.is_file():
            continue

        try:
            created_at = float(
                metadata_path.read_text(encoding="utf-8")
            )

            if now - created_at <= RETENTION_SECONDS:
                continue

            for file_path in job_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()

            job_dir.rmdir()
            deleted += 1

        except (ValueError, OSError):
            failed += 1

    return {"deleted": deleted, "failed": failed}