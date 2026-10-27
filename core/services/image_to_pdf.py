
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader
from core.services.quality_validator import validate_image_quality

def image_to_pdf(
    input_path,
    output_path,
    min_size_kb=1,
    max_size_kb=200,
    min_ssim=0.83,
):
    """Convert an image to PDF, meeting both size and SSIM requirements."""
    import io

    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file() or input_path.stat().st_size == 0:
        raise ValueError("Input image is missing or empty.")

    if min_size_kb <= 0 or max_size_kb < min_size_kb:
        raise ValueError("Invalid PDF size limits.")

    if not 0 <= min_ssim <= 1:
        raise ValueError("min_ssim must be between 0 and 1.")

    min_bytes = min_size_kb * 1024
    max_bytes = max_size_kb * 1024

    try:
        with Image.open(input_path) as source:
            image = ImageOps.exif_transpose(source)
            image.load()

            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(
                    rgba,
                    mask=rgba.getchannel("A"),
                )
                image = background
            else:
                image = image.convert("RGB")

        # Try full resolution first, then progressively smaller versions.
        scales = (1.0, 0.85, 0.70, 0.55, 0.40)
        qualities = (95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40)

        best_size = None
        best_ssim = None

        for scale in scales:
            if scale == 1.0:
                candidate = image
            else:
                candidate_size = (
                    max(1, round(image.width * scale)),
                    max(1, round(image.height * scale)),
                )
                candidate = image.resize(
                    candidate_size,
                    Image.Resampling.LANCZOS,
                )

            for quality in qualities:
                buffer = io.BytesIO()

                candidate.save(
                    buffer,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )
                buffer.seek(0)

                with Image.open(buffer) as compressed:
                    compressed.load()
                    pdf_image = compressed.convert("RGB")

                buffer.close()

                output_path.unlink(missing_ok=True)
                pdf_image.save(
                    output_path,
                    format="PDF",
                    resolution=150.0,
                )

                size_bytes = output_path.stat().st_size

                # Do not spend time evaluating candidates outside the size limit.
                if size_bytes < min_bytes or size_bytes > max_bytes:
                    continue

                # Verify PDF integrity before measuring visual quality.
                reader = PdfReader(str(output_path), strict=True)

                if reader.is_encrypted or len(reader.pages) != 1:
                    raise ValueError(
                        "Generated PDF failed integrity validation."
                    )

                quality_result = validate_image_quality(
                    input_path,
                    output_path,
                    min_ssim=min_ssim,
                )

                score = quality_result["ssim"]

                
                if best_ssim is None or score > best_ssim:
                    best_ssim = score
                    best_size = size_bytes
                    

                # Accept only when BOTH size and visual-quality checks pass.
                if quality_result["quality_valid"]:
                    final_reader = PdfReader(
                        str(output_path),
                        strict=True,
                    )

                    if final_reader.is_encrypted or len(final_reader.pages) != 1:
                        raise ValueError(
                            "Final PDF integrity validation failed."
                        )

                    final_size = output_path.stat().st_size

                    if not min_bytes <= final_size <= max_bytes:
                        continue

                    return {
                        "output_path": str(output_path),
                        "pages": 1,
                        "size_bytes": final_size,
                        "size_kb": round(final_size / 1024, 2),
                        "valid": True,
                        "image_dimensions": list(candidate.size),
                        "jpeg_quality": quality,
                        "ssim": score,
                        "min_ssim": min_ssim,
                    }

        raise ValueError(
            f"No PDF candidate satisfied both the {min_size_kb}-"
            f"{max_size_kb} KB size range and minimum SSIM "
            f"{min_ssim}. Best observed SSIM: "
            f"{best_ssim if best_ssim is not None else 'unavailable'}; "
            f"best candidate size: "
            f"{round(best_size / 1024, 2) if best_size is not None else 'unavailable'} KB."
        )

    except Exception:
        output_path.unlink(missing_ok=True)
        raise
