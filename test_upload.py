
import requests
from pathlib import Path

url = "http://127.0.0.1:8000/api/documents/upload"

# Create a tiny test file for uploading.
test_file = Path("test_upload.jpg")
test_file.write_bytes(b"test image content")

try:
    with test_file.open("rb") as file:
        response = requests.post(
            url,
            files={"file": ("test_upload.jpg", file, "image/jpeg")},
        )

    print("Status code:", response.status_code)
    print("Response:", response.text)

finally:
    test_file.unlink(missing_ok=True)
