
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def validate_file(file_path, requirements):
    """
    Validate an image or PDF against structured requirements.
    Returns a report with individual checks and an overall result.
    """
    path = Path(file_path)
    checks = []

    def add_check(name, passed, actual, expected=None):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "actual": actual,
            "expected": expected,
        })

    if not path.is_file() or path.stat().st_size == 0:
        add_check("file_exists_and_nonempty", False, "Missing or empty")
        return {"valid": False, "checks": checks}

    size_bytes = path.stat().st_size
    max_size_kb = requirements.get("max_size_kb")

    if max_size_kb is not None:
        add_check(
            "file_size",
            size_bytes <= max_size_kb * 1024,
            size_bytes,
            f"At most {max_size_kb} KB",
        )

    file_type = requirements.get("file_type", "").lower()

    try:
        if file_type == "image":
            with Image.open(path) as image:
                image.verify()

            with Image.open(path) as image:
                image_format = image.format
                width, height = image.size

            allowed_formats = requirements.get("allowed_formats")
            if allowed_formats:
                add_check(
                    "image_format",
                    image_format in [f.upper() for f in allowed_formats],
                    image_format,
                    allowed_formats,
                )

            expected_width = requirements.get("width")
            expected_height = requirements.get("height")

            if expected_width is not None:
                add_check(
                    "image_width",
                    width == expected_width,
                    width,
                    expected_width,
                )

            if expected_height is not None:
                add_check(
                    "image_height",
                    height == expected_height,
                    height,
                    expected_height,
                )

        elif file_type == "pdf":
            reader = PdfReader(str(path), strict=True)

            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")

            page_count = len(reader.pages)
            add_check("pdf_integrity", page_count > 0, page_count, "At least 1 page")

            expected_pages = requirements.get("page_count")
            if expected_pages is not None:
                add_check(
                    "pdf_page_count",
                    page_count == expected_pages,
                    page_count,
                    expected_pages,
                )

        else:
            add_check(
                "file_type",
                False,
                file_type or "Not specified",
                "image or pdf",
            )

    except Exception as exc:
        add_check("content_integrity", False, str(exc))

    return {
        "valid": bool(checks) and all(c["passed"] for c in checks),
        "file_name": path.name,
        "size_bytes": size_bytes,
        "checks": checks,
    }
