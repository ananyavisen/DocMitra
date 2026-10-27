from django.urls import path

from core.views import (
    upload_document,
    process_image_api,
    process_pdf_api,
    document_checklist_api,
    process_document_api,
    download_processed_document,
)

urlpatterns = [
    path(
        "documents/upload/",
        upload_document,
        name="upload_document",
    ),
    path(
        "documents/process-image/",
        process_image_api,
        name="process_image",
    ),
    path(
        "documents/process-pdf/",
        process_pdf_api,
        name="process_pdf",
    ),
    path(
        "documents/checklist/",
        document_checklist_api,
        name="document_checklist",
    ),
    path(
        "documents/process-document/",
        process_document_api,
        name="process_document",
    ),
    path(
        "jobs/<str:job_id>/download/",
        download_processed_document,
        name="download_processed_document",
    ),
]