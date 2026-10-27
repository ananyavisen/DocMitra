
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader


def image_to_pdf(input_path, output_path, min_size_kb=1, max_size_kb=200):
    """Convert an image to PDF, preserve image quality, and validate size."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file() or input_path.stat().st_size == 0:
        raise ValueError("Input image is missing or empty.")

    if min_size_kb <= 0 or max_size_kb < min_size_kb:
        raise ValueError("Invalid PDF size limits.")

    min_bytes = min_size_kb * 1024
    max_bytes = max_size_kb * 1024

    try:
        with Image.open(input_path) as source:
            image = ImageOps.exif_transpose(source)
            image.load()

            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            # Save the image inside a PDF without JPEG re-encoding.
            image.save(output_path, format="PDF", resolution=150.0)

        reader = PdfReader(str(output_path), strict=True)

        if reader.is_encrypted or len(reader.pages) != 1:
            raise ValueError("Generated PDF failed integrity validation.")


        size_bytes = output_path.stat().st_size

        if size_bytes < min_bytes or size_bytes > max_bytes:
            raise ValueError(
                f"Generated PDF is {size_bytes / 1024:.2f} KB; "
                f"required range is {min_size_kb}-{max_size_kb} KB."
            )

        # Recheck PDF integrity and size.
        final_reader = PdfReader(str(output_path), strict=True)
        final_size = output_path.stat().st_size

        if final_reader.is_encrypted or len(final_reader.pages) != 1:
            raise ValueError("Final PDF integrity check failed.")

        if not min_bytes <= final_size <= max_bytes:
            raise ValueError(
                f"Final PDF size is {final_size / 1024:.2f} KB; "
                f"required range is {min_size_kb}-{max_size_kb} KB."
            )

        return {
            "output_path": str(output_path),
            "pages": len(final_reader.pages),
            "size_bytes": final_size,
            "size_kb": round(final_size / 1024, 2),
            "valid": True,
        }

    except Exception:
        output_path.unlink(missing_ok=True)
        raise
