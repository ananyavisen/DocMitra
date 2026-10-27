
import os
import django
from pathlib import Path
from PIL import Image, ImageDraw

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.services.document_processor import process_image_document

test_dir = Path("test_temp")
test_dir.mkdir(exist_ok=True)

input_path = test_dir / "test_document.png"
output_path = test_dir / "test_document.pdf"

image = Image.new("RGB", (800, 1100), "white")
draw = ImageDraw.Draw(image)
draw.text((60, 60), "DOCMITRA TEST DOCUMENT", fill="black")
draw.text((60, 120), "Name: Test User", fill="black")
draw.text((60, 180), "Document processing test.", fill="black")
image.save(input_path)

try:
    # Test 1: Normal document should convert successfully
    result = process_image_document(
        input_path,
        output_path,
        doc_id="income_certificate",
        min_size_kb=1,
        max_size_kb=200,
        min_ssim=0.95,
    )
    print("DOCUMENT TEST:", result)

    assert result["valid"] is True
    assert result["doc_id"] == "income_certificate"

    # Test 2: Passport photo should be rejected by this workflow
    try:
        process_image_document(
            input_path,
            output_path,
            doc_id="passport_photo",
            min_size_kb=1,
            max_size_kb=200,
        )
    except ValueError as error:
        print("PHOTO REJECTION TEST PASSED:", error)
    else:
        raise AssertionError(
            "Passport photo should not use the document PDF workflow."
        )

finally:
    input_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)

    if test_dir.exists():
        test_dir.rmdir()
