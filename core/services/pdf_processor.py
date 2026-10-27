from pathlib import Path

from pypdf import PdfReader, PdfWriter


def process_pdf(input_path, output_path, max_size_kb=None):
    """
    Validate a PDF and write a cleaned copy.
    Try page-content compression, then verify the output.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file() or input_path.stat().st_size == 0:
        raise ValueError("Input PDF is missing or empty.")

    try:
        reader = PdfReader(str(input_path), strict=True)

        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")

        if len(reader.pages) == 0:
            raise ValueError("PDF contains no pages.")

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)
            writer.pages[-1].compress_content_streams()

        with output_path.open("wb") as output:
            writer.write(output)

        # Reopen the output and check basic integrity.
        check = PdfReader(str(output_path), strict=True)

        if len(check.pages) != len(reader.pages):
            raise ValueError("PDF page count changed during processing.")

        if max_size_kb is not None:
            if max_size_kb <= 0:
                raise ValueError("Maximum size must be positive.")

            if output_path.stat().st_size > max_size_kb * 1024:
                raise ValueError(
                    "PDF exceeds the requested size limit. "
                    "Further compression may be required."
                )

        return {
            "output_path": str(output_path),
            "pages": len(check.pages),
            "size_bytes": output_path.stat().st_size,
            "valid": True,
        }

    except Exception:
        output_path.unlink(missing_ok=True)
        raise
