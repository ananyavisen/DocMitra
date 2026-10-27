from __future__ import annotations

import json
import logging
import uuid

from pathlib import Path
from typing import Any, Callable

from django.conf import settings

from functools import partial
from core.services.image_to_pdf import image_to_pdf
from core.services.image_processor import process_image
from core.services.pdf_processor import process_pdf
from core.services.validator import validate_file
from core.services.requirements_provider import RequirementsProvider


logger = logging.getLogger(__name__)

CORE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_REQUIREMENTS_PATH = (
    CORE_DIR / "config" / "document_requirements.json"
)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}


class OrchestratorError(Exception):
    """Raised when document orchestration cannot be completed."""


class DocumentOrchestrator:
    """
    Coordinates document processing, validation, retries, and output cleanup.

    Original uploads are never modified or deleted.

    Image processing requires an image-to-PDF converter because the existing
    image processor produces JPEG output rather than PDF output.
    """

    def __init__(
        self,
        requirements_path: str | Path = DEFAULT_REQUIREMENTS_PATH,
        image_to_pdf_converter: Callable | None = None,
        requirements_provider: RequirementsProvider | None = None,
    ):
        self.requirements_path = Path(requirements_path)
        self.requirements = self._load_requirements()

        self.max_size_kb = self.requirements.get(
            "global_document_rules", {}
        ).get("max_size_kb", 200)

        min_size_kb = self.requirements.get(
            "global_document_rules", {}
        ).get("min_size_kb", 50)

        self.image_to_pdf_converter = image_to_pdf_converter or partial(
            image_to_pdf,
            min_size_kb=min_size_kb,
            max_size_kb=self.max_size_kb,
        )

        self.requirements_provider = (
            requirements_provider or RequirementsProvider()
        )

        processing_config = self.requirements.get("processing", {})

        self.max_attempts = processing_config.get("max_attempts", 3)
        self.delete_invalid_output = processing_config.get(
            "delete_invalid_processed_output",
            True,
        )

        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or self.max_attempts < 1
        ):
            raise OrchestratorError(
                "max_attempts must be a positive integer."
            )

        self.max_size_kb = self.requirements.get(
            "global_document_rules", {}
        ).get("max_size_kb", 200)

        if (
            not isinstance(self.max_size_kb, (int, float))
            or isinstance(self.max_size_kb, bool)
            or self.max_size_kb <= 0
        ):
            raise OrchestratorError(
                "max_size_kb must be a positive number."
            )

    def _load_requirements(self) -> dict[str, Any]:
        """Load the application's deterministic document rules."""
        if not self.requirements_path.is_file():
            raise OrchestratorError(
                f"Requirements configuration not found: "
                f"{self.requirements_path}"
            )

        try:
            with self.requirements_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                requirements = json.load(file)

        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestratorError(
                f"Unable to load document requirements: {exc}"
            ) from exc

        if not isinstance(requirements, dict):
            raise OrchestratorError(
                "Document requirements must be a JSON object."
            )

        return requirements

    @staticmethod
    def _is_valid_report(report: Any) -> bool:
        """Accept only an explicit successful validation result."""
        return (
            isinstance(report, dict)
            and report.get("valid") is True
        )

    @staticmethod
    def _remove_file(path: Path) -> None:
        """Delete a generated file without affecting the original upload."""
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            logger.exception("Failed to remove generated file: %s", path)

    def _validate_output(self, output_path: Path) -> dict[str, Any]:
        """Run the existing validator against the final PDF."""
        report = validate_file(
            str(output_path),
            self.requirements,
        )

        if not isinstance(report, dict):
            raise OrchestratorError(
                "The validator returned an unexpected result."
            )

        return report

    def _convert_image_to_pdf(
        self,
        image_path: Path,
        pdf_path: Path,
    ) -> Path:
        """
        Convert a processed image into a PDF using the converter supplied
        by the image-processing integration.
        """
        if self.image_to_pdf_converter is None:
            raise OrchestratorError(
                "Image-to-PDF conversion is not configured. "
                "The image processor produces JPEG output, so a PDF "
                "converter must be supplied before image uploads can "
                "complete the PDF workflow."
            )

        result = self.image_to_pdf_converter(
            str(image_path),
            str(pdf_path),
        )

        # Accept either a path string or a result dictionary.
        if isinstance(result, dict):
            result_path = result.get("output_path")
        elif isinstance(result, (str, Path)):
            result_path = result
        else:
            result_path = None

        # If the converter writes to the requested destination and returns
        # None, the destination itself is still usable.
        if result_path is None and pdf_path.is_file():
            result_path = pdf_path

        if not result_path:
            raise OrchestratorError(
                "The image-to-PDF converter did not return an output path."
            )

        resolved_path = Path(result_path)

        if not resolved_path.is_file():
            raise OrchestratorError(
                "The image-to-PDF converter output does not exist."
            )

        if resolved_path.suffix.lower() != ".pdf":
            raise OrchestratorError(
                "The image-to-PDF converter did not produce a PDF."
            )

        return resolved_path

    def process_document(
        self,
        input_path: str | Path,
        *,
        job_id: str | None = None,
        student_type: str | None = None,
        width: int = 1200,
        height: int = 1600,
    ) -> dict[str, Any]:
        """
        Process an uploaded PDF or image and return a structured result.

        Image uploads require an image-to-PDF converter. The final PDF
        must pass the existing validator before success is reported.
        """
        original_path = Path(input_path).resolve()

        result: dict[str, Any] = {
            "success": False,
            "job_id": job_id or str(uuid.uuid4()),
            "input_path": str(original_path),
            "output_path": None,
            "attempts": 0,
            "validation": None,
            "requirements": None,
            "errors": [],
        }

        if not original_path.is_file():
            result["errors"].append("Input file does not exist.")
            return result

        if original_path.stat().st_size == 0:
            result["errors"].append("Input file is empty.")
            return result

        extension = original_path.suffix.lower()

        if extension not in (
            SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS
        ):
            result["errors"].append(
                f"Unsupported file extension: {extension or '(none)'}"
            )
            return result

        if extension in SUPPORTED_IMAGE_EXTENSIONS:
            if (
                not isinstance(width, int)
                or isinstance(width, bool)
                or width <= 0
                or not isinstance(height, int)
                or isinstance(height, bool)
                or height <= 0
            ):
                result["errors"].append(
                    "Image width and height must be positive integers."
                )
                return result

            if self.image_to_pdf_converter is None:
                result["errors"].append(
                    "Image-to-PDF conversion is not configured."
                )
                return result

        media_root = Path(settings.MEDIA_ROOT).resolve()

        job_directory = (
            media_root / "processing" / result["job_id"]
        ).resolve()

        # Prevent a caller-provided job ID from escaping the processing root.
        processing_root = (media_root / "processing").resolve()

        if not job_directory.is_relative_to(processing_root):
            result["errors"].append("Invalid job ID.")
            return result

        try:
            job_directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            result["errors"].append(
                f"Unable to create processing directory: {exc}"
            )
            return result

        # The knowledge base is advisory here. Its constraints are not
        # merged into or allowed to override the application's config.
        try:
            result["requirements"] = (
                self.requirements_provider.get_processing_constraints(
                    student_type
                )
            )
        except (ValueError, OSError, OrchestratorError) as exc:
            logger.exception("Unable to retrieve requirement metadata.")
            result["errors"].append(
                f"Unable to retrieve requirement metadata: {exc}"
            )
            return result

        generated_files: set[Path] = set()
        last_validation = None

        try:
            for attempt in range(1, self.max_attempts + 1):
                result["attempts"] = attempt

                try:
                    if extension == ".pdf":
                        output_path = (
                            job_directory / f"processed_{attempt}.pdf"
                        )

                        processor_result = process_pdf(
                            str(original_path),
                            str(output_path),
                            max_size_kb=self.max_size_kb,
                        )

                        if not isinstance(processor_result, dict):
                            raise OrchestratorError(
                                "PDF processor returned an unexpected result."
                            )

                        processed_path = processor_result.get("output_path")

                        if not processed_path:
                            raise OrchestratorError(
                                "PDF processor did not return output_path."
                            )

                        final_path = Path(processed_path).resolve()
                        generated_files.add(final_path)

                    else:
                        image_path = (
                            job_directory / f"processed_{attempt}.jpg"
                        )
                        pdf_path = (
                            job_directory / f"processed_{attempt}.pdf"
                        )

                        # Reduce dimensions on subsequent attempts.
                        # This does not replace a proper quality assessment.
                        attempt_width = max(
                            1,
                            int(width * (0.85 ** (attempt - 1))),
                        )
                        attempt_height = max(
                            1,
                            int(height * (0.85 ** (attempt - 1))),
                        )

                        processor_result = process_image(
                            str(original_path),
                            str(image_path),
                            width=attempt_width,
                            height=attempt_height,
                            max_size_kb=self.max_size_kb,
                        )

                        if not isinstance(processor_result, dict):
                            raise OrchestratorError(
                                "Image processor returned an unexpected result."
                            )

                        processed_image = processor_result.get("output_path")

                        if not processed_image:
                            raise OrchestratorError(
                                "Image processor did not return output_path."
                            )

                        processed_image = Path(processed_image).resolve()
                        generated_files.add(processed_image)

                        if not processed_image.is_file():
                            raise OrchestratorError(
                                "Processed image does not exist."
                            )

                        final_path = self._convert_image_to_pdf(
                            processed_image,
                            pdf_path,
                        )
                        generated_files.add(final_path)

                    if not final_path.is_file():
                        raise OrchestratorError(
                            "Processor output does not exist."
                        )

                    # Only PDF output is accepted as the final document.
                    if final_path.suffix.lower() != ".pdf":
                        raise OrchestratorError(
                            "Final output must be a PDF."
                        )

                    last_validation = self._validate_output(final_path)
                    result["validation"] = last_validation

                    if self._is_valid_report(last_validation):
                        result["success"] = True
                        result["output_path"] = str(final_path)

                        # Preserve the successful PDF and remove other
                        # generated intermediate files.
                        for generated_path in generated_files:
                            if generated_path != final_path:
                                self._remove_file(generated_path)

                        return result

                    result["errors"].append(
                        f"Attempt {attempt}: final PDF failed validation."
                    )

                    if self.delete_invalid_output:
                        self._remove_file(final_path)
                        generated_files.discard(final_path)

                    # The PDF processor has no documented adjustment
                    # parameters beyond max_size_kb. Repeating it unchanged
                    # is unlikely to fix a deterministic validation failure.
                    if extension == ".pdf":
                        break

                except (ValueError, OSError, OrchestratorError) as exc:
                    logger.warning(
                        "Processing attempt %s failed: %s",
                        attempt,
                        exc,
                    )

                    result["errors"].append(
                        f"Attempt {attempt}: {exc}"
                    )

                    # Avoid rerunning PDF processing with identical inputs
                    # and parameters when no adjustment mechanism exists.
                    if extension == ".pdf":
                        break

            if last_validation is not None:
                result["validation"] = last_validation

        finally:
            # Remove generated intermediates and failed outputs.
            # Never remove the original uploaded file.
            if not result["success"]:
                for generated_path in generated_files:
                    if self.delete_invalid_output:
                        self._remove_file(generated_path)

        return result