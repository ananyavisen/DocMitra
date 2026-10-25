
import uuid
from core.serializers import DocumentUploadSerializer
from pathlib import Path

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

