
from pathlib import Path
from PIL import Image, ImageOps


def process_image(
    input_path,
    output_path,
    width,
    height,
    max_size_kb,
):
    """
    Center-crop, resize and compress an image to JPEG.
    Verify the final dimensions and file-size limit.
    """
    if width <= 0 or height <= 0 or max_size_kb <= 0:
        raise ValueError("Dimensions and size limit must be positive.")

    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = max_size_kb * 1024

    with Image.open(input_path) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        image = image.convert("RGB")

    # Center-crop to the required aspect ratio, then resize.
    target_ratio = width / height
    source_ratio = image.width / image.height

    if source_ratio > target_ratio:
        crop_width = int(image.height * target_ratio)
        left = (image.width - crop_width) // 2
        image = image.crop(
            (left, 0, left + crop_width, image.height)
        )
    elif source_ratio < target_ratio:
        crop_height = int(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        image = image.crop(
            (0, top, image.width, top + crop_height)
        )

    image = image.resize(
        (width, height),
        Image.Resampling.LANCZOS,
    )

    # Reduce JPEG quality until the size limit is met.
    for quality in range(90, 19, -5):
        image.save(
            output_path,
            format="JPEG",
            quality=quality,
            optimize=True,
        )

        if output_path.stat().st_size <= max_bytes:
            break
    else:
        output_path.unlink(missing_ok=True)
        raise ValueError(
            "Could not meet the requested file-size limit "
            "at the supported JPEG quality settings."
        )

    # Independently verify the saved output.
    with Image.open(output_path) as result:
        result.verify()

    with Image.open(output_path) as result:
        actual_dimensions = result.size

    actual_size = output_path.stat().st_size

    if actual_dimensions != (width, height):
        output_path.unlink(missing_ok=True)
        raise ValueError("Output dimensions do not match requirements.")

    if actual_size > max_bytes:
        output_path.unlink(missing_ok=True)
        raise ValueError("Output exceeds the file-size limit.")

    return {
        "output_path": str(output_path),
        "format": "JPEG",
        "width": actual_dimensions[0],
        "height": actual_dimensions[1],
        "size_bytes": actual_size,
        "size_kb": round(actual_size / 1024, 2),
        "valid": True,
    }
