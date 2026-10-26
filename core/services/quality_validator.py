
from pathlib import Path

import numpy as np
import pymupdf  # PyMuPDF
from PIL import Image, ImageOps
from skimage.metrics import structural_similarity


def validate_image_quality(
    original_image_path,
    generated_pdf_path,
    min_ssim=0.95,
):
    """Compare the original image with the image rendered from a PDF."""

    original_image_path = Path(original_image_path)
    generated_pdf_path = Path(generated_pdf_path)

    if not original_image_path.is_file():
        raise ValueError("Original image is missing.")

    if not generated_pdf_path.is_file():
        raise ValueError("Generated PDF is missing.")

    with Image.open(original_image_path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")

    with pymupdf.open(generated_pdf_path) as document:
        if document.page_count != 1:
            raise ValueError("Expected a one-page PDF for image quality check.")

        page = document[0]
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(2, 2),
            alpha=False,
        )
        rendered = Image.frombytes(
            "RGB",
            (pix.width, pix.height),
            pix.samples,
        )

    # Compare at matching dimensions.
    rendered = rendered.resize(original.size, Image.Resampling.LANCZOS)

    original_array = np.asarray(original)
    rendered_array = np.asarray(rendered)

    score = structural_similarity(
        original_array,
        rendered_array,
        channel_axis=2,
        data_range=255,
    )

    return {
        "ssim": round(float(score), 4),
        "min_ssim": min_ssim,
        "quality_valid": bool(score >= min_ssim),
        "note": (
            "SSIM is a visual similarity indicator, not a guarantee "
            "of document readability or authenticity."
        ),
    }
