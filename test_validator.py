
from pathlib import Path

from PIL import Image
from pypdf import PdfWriter

from core.services.validator import validate_file

image_path = Path("validator_test.jpg")
pdf_path = Path("validator_test.pdf")

try:
    Image.new("RGB", (200, 230), "white").save(image_path)

    image_result = validate_file(
        image_path,
        {
            "file_type": "image",
            "width": 200,
            "height": 230,
            "max_size_kb": 50,
            "allowed_formats": ["JPEG"],
        },
    )

    print("IMAGE RESULT:", image_result)

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)

    with pdf_path.open("wb") as file:
        writer.write(file)

    pdf_result = validate_file(
        pdf_path,
        {
            "file_type": "pdf",
            "page_count": 1,
            "max_size_kb": 100,
        },
    )

    print("PDF RESULT:", pdf_result)

finally:
    image_path.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)
