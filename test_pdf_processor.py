
from pathlib import Path

from pypdf import PdfWriter
from core.services.pdf_processor import process_pdf

input_path = Path("sample_input.pdf")
output_path = Path("sample_output.pdf")

# Create a small, valid PDF for testing.
writer = PdfWriter()
writer.add_blank_page(width=300, height=400)

with input_path.open("wb") as file:
    writer.write(file)

try:
    result = process_pdf(
        input_path=input_path,
        output_path=output_path,
        max_size_kb=100,
    )

    print("PDF processing successful!")
    print(result)

finally:
    input_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
