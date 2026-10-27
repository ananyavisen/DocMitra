import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader


# Resolve paths relative to the project, not the terminal's working directory.
CORE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS_PATH = (
    CORE_DIR / "config" / "document_requirement.json"
)

BYTES_PER_KB = 1024


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    file_name: str
    size_bytes: int | None = None
    size_kb: float | None = None

    def to_dict(self) -> dict:
        """Convert the result into a JSON-serializable dictionary."""
        return asdict(self)


def load_requirements(
    requirements_path: str | Path = DEFAULT_REQUIREMENTS_PATH,
) -> dict:
    """Load the global document validation rules from JSON."""
    path = Path(requirements_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Requirements configuration not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    rules = config.get("global_document_rules")

    if not isinstance(rules, dict):
        raise ValueError(
            "Configuration must contain a 'global_document_rules' object."
        )

    min_size_kb = rules.get("min_size_kb")
    max_size_kb = rules.get("max_size_kb")
    extensions = rules.get("allowed_extensions")

    if (
        not isinstance(min_size_kb, (int, float))
        or isinstance(min_size_kb, bool)
        or not isinstance(max_size_kb, (int, float))
        or isinstance(max_size_kb, bool)
        or min_size_kb <= 0
        or max_size_kb < min_size_kb
    ):
        raise ValueError("Invalid minimum or maximum file size in config.")

    if (
        not isinstance(extensions, list)
        or not extensions
        or not all(isinstance(ext, str) for ext in extensions)
    ):
        raise ValueError(
            "'allowed_extensions' must be a non-empty list of strings."
        )

    return rules


def validate_pdf(
    file_path: str | Path,
    requirements_path: str | Path = DEFAULT_REQUIREMENTS_PATH,
) -> ValidationResult:
    """
    Validate a PDF against DocMitra's global document requirements.

    Checks:
    - File exists and is not empty.
    - Extension is allowed.
    - PDF signature is present.
    - File size is within the configured inclusive range.
    - PDF can be parsed and is not encrypted.

    This function does not modify or delete the input file.
    """
    path = Path(file_path)
    errors: list[str] = []

    if not path.is_file():
        return ValidationResult(
            valid=False,
            errors=["File does not exist or is not a regular file."],
            file_name=path.name,
        )

    size_bytes = path.stat().st_size
    size_kb = round(size_bytes / BYTES_PER_KB, 2)

    result_details = {
        "file_name": path.name,
        "size_bytes": size_bytes,
        "size_kb": size_kb,
    }

    if size_bytes == 0:
        return ValidationResult(
            valid=False,
            errors=["File is empty."],
            **result_details,
        )

    try:
        rules = load_requirements(requirements_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        # Configuration errors should be surfaced, not treated as
        # ordinary document-validation failures.
        raise ValueError(
            f"Unable to load document validation rules: {exc}"
        ) from exc

    # 1. Check the extension.
    allowed_extensions = {
        ext.lower() for ext in rules["allowed_extensions"]
    }

    if path.suffix.lower() not in allowed_extensions:
        errors.append(
            f"Invalid file extension '{path.suffix}'. "
            f"Allowed extensions: {', '.join(sorted(allowed_extensions))}."
        )

    # 2. Check the PDF signature.
    try:
        with path.open("rb") as file:
            header = file.read(1024)

        if b"%PDF-" not in header:
            errors.append(
                "The file does not contain a PDF signature "
                "in its first 1024 bytes."
            )
    except OSError as exc:
        errors.append(f"Unable to read file: {exc}")
        return ValidationResult(
            valid=False,
            errors=errors,
            **result_details,
        )

    # 3. Check the inclusive file-size range.
    min_bytes = rules["min_size_kb"] * BYTES_PER_KB
    max_bytes = rules["max_size_kb"] * BYTES_PER_KB

    if size_bytes < min_bytes:
        errors.append(
            f"File is too small: {size_kb} KB. "
            f"Minimum allowed size is {rules['min_size_kb']} KB."
        )

    if size_bytes > max_bytes:
        errors.append(
            f"File is too large: {size_kb} KB. "
            f"Maximum allowed size is {rules['max_size_kb']} KB."
        )

    # 4. Check whether the PDF can be parsed.
    try:
        reader = PdfReader(str(path), strict=False)

        if reader.is_encrypted:
            errors.append(
                "The PDF is encrypted and cannot be read without a password."
            )
        else:
            # Accessing the page collection helps detect parsing problems.
            _ = len(reader.pages)

    except Exception as exc:
        errors.append(f"PDF is corrupted or unreadable: {exc}")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        **result_details,
    )