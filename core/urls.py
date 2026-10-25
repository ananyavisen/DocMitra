
from django.urls import path
from core.views import upload_document, process_image_api, process_pdf_api

urlpatterns = [
    path("documents/upload", upload_document, name="upload_document"),
    path("documents/process-image", process_image_api, name="process_image"),
    path("documents/process-pdf", process_pdf_api, name="process_pdf"),
]
