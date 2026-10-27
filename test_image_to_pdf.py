
from pathlib import Path
from PIL import Image, ImageDraw

from core.services.image_to_pdf import image_to_pdf

image_path = Path("test_sample.jpg")
pdf_path = Path("test_sample.pdf")

# Create a non-blank sample image for testing.
image = Image.new("RGB", (800, 600), "white")
draw = ImageDraw.Draw(image)
draw.rectangle((40, 40, 760, 560), outline="black", width=4)
draw.text((100, 100), "DocMitra Test Document", fill="black")
draw.text((100, 150), "Sample certificate - fictional data", fill="black")
image.save(image_path, quality=95)

try:
    result = image_to_pdf(
        image_path,
        pdf_path,
        min_size_kb=1,
        max_size_kb=200,
    )
    print("SUCCESS:", result)
except Exception as exc:
    print("TEST RESULT:", exc)
finally:
    image_path.unlink(missing_ok=True)
