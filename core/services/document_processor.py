
from pathlib import Path

from core.services.image_to_pdf import image_to_pdf
from core.services.quality_validator import validate_image_quality
from core.services.validator import validate_file
from core.services.requirements_provider import get_document_by_id


def process_image_document(
    input_path,
    output_path,
    doc_id=None,
    min_size_kb=50,
    max_size_kb=200,
    min_ssim=0.95,
):
    """Convert eligible document images to PDF and validate the result."""

    input_path = Path(input_path)
    output_path = Path(output_path)

    if doc_id is not None:
        document = get_document_by_id(doc_id)

        if not document:
            raise ValueError(f"Unknown document ID: {doc_id}")

        if doc_id in {"passport_photo", "signature"}:
            raise ValueError(
                f"{document['name']} must not be processed as a document PDF."
            )

    if not input_path.is_file():
        raise ValueError("Input image does not exist.")

    try:
        processing = image_to_pdf(
            input_path,
            output_path,
            min_size_kb=min_size_kb,
            max_size_kb=max_size_kb,
        )

        file_validation = validate_file(
            output_path,
            {
                "file_type": "pdf",
                "max_size_kb": max_size_kb,
            },
        )

        quality_validation = validate_image_quality(
            input_path,
            output_path,
            min_ssim=min_ssim,
        )

        valid = (
            processing["valid"]
            and file_validation["valid"]
            and quality_validation["quality_valid"]
        )

        if not valid:
            output_path.unlink(missing_ok=True)

        return {
            "valid": valid,
            "doc_id": doc_id,
            "processing": processing,
            "file_validation": file_validation,
            "quality_validation": quality_validation,
        }

    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def get_document_processing_policy(doc_id):
    """Return document metadata and upload-limit verification status."""

    document = get_document_by_id(doc_id)

    if not document:
        raise ValueError(f"Unknown document ID: {doc_id}")

    is_photo_or_signature = doc_id in {"passport_photo", "signature"}
    file_limits = document.get("file_limits", {})

    return {
        "doc_id": document["doc_id"],
        "name": document["name"],
        "requirement_level": document.get("requirement_level"),
        "convert_image_to_pdf": not is_photo_or_signature,
        "file_limits": file_limits,
        "file_limits_verified": (
            file_limits.get("verification_status") == "verified"
        ),
        "upload_instruction": (
            file_limits.get("instruction")
            if file_limits
            else "Confirm the accepted format and size on the live NSP upload page."
        ),
    }
