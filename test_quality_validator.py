
from pathlib import Path
from PIL import Image, ImageDraw

from core.services.image_to_pdf import image_to_pdf
from core.services.quality_validator import validate_image_quality

image_path = Path("quality_test.jpg")
pdf_path = Path("quality_test.pdf")

# Create a non-blank sample image.
image = Image.new("RGB", (800, 600), "white")
draw = ImageDraw.Draw(image)
draw.rectangle((30, 30, 770, 570), outline="black", width=4)
draw.text((80, 80), "DocMitra Quality Test", fill="black")
draw.text((80, 130), "Fictional sample document", fill="black")
image.save(image_path, quality=95)

try:
    # Use a relaxed size range for this quality-only test.
    result = image_to_pdf(
        image_path,
        pdf_path,
        min_size_kb=1,
        max_size_kb=200,
    )
    print("PDF RESULT:", result)

    quality = validate_image_quality(image_path, pdf_path)
    print("QUALITY RESULT:", quality)

except Exception as exc:
    print("TEST ERROR:", exc)

finally:
    image_path.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)
