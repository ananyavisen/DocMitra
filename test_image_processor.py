
from pathlib import Path
from PIL import Image

from core.services.image_processor import process_image

input_path = Path("sample_input.png")
output_path = Path("sample_output.jpg")

# Generate a real test image.
Image.new("RGB", (800, 600), "white").save(input_path)

try:
    result = process_image(
        input_path=input_path,
        output_path=output_path,
        width=200,
        height=230,
        max_size_kb=50,
    )

    print(result)

finally:
    input_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
