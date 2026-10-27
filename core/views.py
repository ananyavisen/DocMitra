
import uuid
from uuid import UUID
import time
from core.serializers import DocumentUploadSerializer
from pathlib import Path
from django.http import FileResponse
from core.serializers import DocumentProcessSerializer
from core.services.document_processor import process_image_document
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from core.serializers import ImageProcessSerializer
from core.services.image_processor import process_image as process_image_file
from core.services.validator import validate_file
from core.serializers import PDFProcessSerializer
from core.services.pdf_processor import process_pdf
from core.services.requirements_provider import (
    get_checklist,
    get_document_catalogue,
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def upload_document(request):
    serializer = DocumentUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    uploaded_file = serializer.validated_data["file"]

    extension = Path(uploaded_file.name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return Response(
            {"error": "Only PDF, PNG, JPG and JPEG files are allowed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size == 0:
        return Response(
            {"error": "The uploaded file is empty."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size > MAX_FILE_SIZE:
        return Response(
            {"error": "File size must not exceed 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Create a unique name instead of trusting the supplied filename.
    upload_id = str(uuid.uuid4())
    safe_filename = f"{upload_id}{extension}"

    upload_dir = settings.MEDIA_ROOT / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    destination = upload_dir / safe_filename

    try:
        with destination.open("wb") as output:
            for chunk in uploaded_file.chunks():
                output.write(chunk)
    except OSError:
        destination.unlink(missing_ok=True)
        return Response(
            {"error": "Could not save the uploaded file."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "message": "File uploaded successfully.",
            "file_id": upload_id,
            "original_filename": uploaded_file.name,
            "stored_filename": safe_filename,
            "file_size_bytes": uploaded_file.size,
            "file_type": extension.lstrip("."),
        },
        status=status.HTTP_201_CREATED,
    )

@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def process_image_api(request):
    serializer = ImageProcessSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    uploaded = serializer.validated_data["file"]
    width = serializer.validated_data["width"]
    height = serializer.validated_data["height"]
    max_size_kb = serializer.validated_data["max_size_kb"]

    job_id = str(uuid.uuid4())
    input_dir = settings.MEDIA_ROOT / "processing" / job_id
    input_dir.mkdir(parents=True, exist_ok=True)

    input_path = input_dir / "original_upload"
    output_path = input_dir / "processed.jpg"

    try:
        with input_path.open("wb") as destination:
            for chunk in uploaded.chunks():
                destination.write(chunk)

        result = process_image_file(
            input_path,
            output_path,
            width,
            height,
            max_size_kb,
        )

        validation = validate_file(
            output_path,
            {
                "file_type": "image",
                "width": width,
                "height": height,
                "max_size_kb": max_size_kb,
                "allowed_formats": ["JPEG"],
            },
        )

        return Response(
            {
                "job_id": job_id,
                "processing": result,
                "validation": validation,
                "download_url": (
                    f"/api/jobs/{job_id}/download"
                    if validation["valid"] else None
                ),
            },
            status=status.HTTP_200_OK,
        )

    except (ValueError, OSError) as exc:
        return Response(
            {"job_id": job_id, "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    finally:
        input_path.unlink(missing_ok=True)


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def process_pdf_api(request):
    serializer = PDFProcessSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    uploaded = serializer.validated_data["file"]
    max_size_kb = serializer.validated_data.get("max_size_kb")

    job_id = str(uuid.uuid4())
    input_dir = settings.MEDIA_ROOT / "processing" / job_id
    input_dir.mkdir(parents=True, exist_ok=True)

    input_path = input_dir / "original.pdf"
    output_path = input_dir / "processed.pdf"

    try:
        with input_path.open("wb") as destination:
            for chunk in uploaded.chunks():
                destination.write(chunk)

        result = process_pdf(
            input_path,
            output_path,
            max_size_kb=max_size_kb,
        )

        validation = validate_file(
            output_path,
            {
                "file_type": "pdf",
                "max_size_kb": max_size_kb,
            },
        )

        return Response(
            {
                "job_id": job_id,
                "processing": result,
                "validation": validation,
            },
            status=status.HTTP_200_OK,
        )

    except (ValueError, OSError) as exc:
        return Response(
            {"job_id": job_id, "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    finally:
        input_path.unlink(missing_ok=True)


@api_view(["GET"])
def document_checklist_api(request):
    student_type = request.query_params.get("student_type")

    if not student_type:
        return Response(
            {"error": "student_type query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    checklist = get_checklist(student_type)

    if checklist is None:
        return Response(
            {"error": "Invalid student_type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    catalogue = get_document_catalogue()
    documents = catalogue.get("documents", [])

    documents_by_id = {
        document["doc_id"]: document
        for document in documents
        if "doc_id" in document
    }

    result = {}

    for section, document_ids in checklist.items():
        if not isinstance(document_ids, list):
            continue

        result[section] = [
            documents_by_id[doc_id]
            for doc_id in document_ids
            if doc_id in documents_by_id
        ]

    return Response({
        "student_type": student_type,
        "checklist": result,
    })


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def process_document_api(request):
    serializer = DocumentProcessSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    uploaded = serializer.validated_data["file"]
    doc_id = serializer.validated_data["doc_id"]
    min_size_kb = serializer.validated_data["min_size_kb"]
    max_size_kb = serializer.validated_data["max_size_kb"]
    job_id = str(uuid.uuid4())
    input_dir = settings.MEDIA_ROOT / "processing" / job_id
    input_dir.mkdir(parents=True, exist_ok=True)

    input_path = input_dir / "original_upload"
    output_path = input_dir / "processed.pdf"
    metadata_path = input_dir / "created_at.txt"

    try:
        with input_path.open("wb") as destination:
            for chunk in uploaded.chunks():
                destination.write(chunk)

        result = process_image_document(
            input_path,
            output_path,
            doc_id=doc_id,
            min_size_kb=min_size_kb,
            max_size_kb=max_size_kb,
            min_ssim=0.95,
        )

        if not result["valid"]:
            return Response(
                {"job_id": job_id, "error": "Document validation failed.", "details": result},
                status=status.HTTP_400_BAD_REQUEST,
            )
        metadata_path.write_text(str(time.time()), encoding="utf-8")
        return Response(
            {
                "job_id": job_id,
                "doc_id": doc_id,
                "processing": result,
                "download_url": f"/api/jobs/{job_id}/download",
            },
            status=status.HTTP_200_OK,
        )

    except (ValueError, OSError) as exc:
        return Response(
            {"job_id": job_id, "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    finally:
        input_path.unlink(missing_ok=True)
          # Remove partial output after a failed request.
        # Keep successful output until a download/retention flow is implemented.
        if not output_path.exists():
            input_dir.rmdir() if input_dir.exists() and not any(input_dir.iterdir()) else None
@api_view(["GET"])
def download_processed_document(request, job_id):
    try:
        UUID(job_id, version=4)
    except ValueError:
         return Response(
            {"error": "Invalid job ID."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    job_dir = settings.MEDIA_ROOT / "processing" / job_id
    pdf_path = job_dir / "processed.pdf"
    metadata_path = job_dir / "created_at.txt"

    if not pdf_path.is_file() or not metadata_path.is_file():
        return Response(
            {"error": "Document not found or expired."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        created_at = float(
            metadata_path.read_text(encoding="utf-8")
        )
    except (ValueError, OSError):
        return Response(
            {"error": "Document metadata is invalid."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if time.time() - created_at > 60 * 60:
        try:
            pdf_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)

            if job_dir.exists() and not any(job_dir.iterdir()):
                 job_dir.rmdir()

        except OSError:
             return Response(
            {"error": "Expired document cleanup failed."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

        return Response(
        {"error": "Download link expired."},
        status=status.HTTP_410_GONE,
        )
    return FileResponse(
        open(pdf_path, "rb"),
        as_attachment=True,
        filename="processed.pdf",
        content_type="application/pdf",)