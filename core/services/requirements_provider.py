import json
from pathlib import Path
from typing import Any


# backend/core/services/requirements_provider.py
CORE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_KB_PATH = (
    CORE_DIR / "data" / "docmitra_nsp_pragati_2026_27_final.json"
)

# Only these statuses qualify as verified for processing.
# "official_document_copy" is intentionally excluded because the
# current knowledge base says it was not verified against the live
# 2026-27 portal.
VERIFIED_STATUSES = {
    "verified",
    "officially_verified",
    "live_portal_verified",
    "confirmed",
}


class RequirementsProviderError(Exception):
    """Raised when requirements cannot be safely loaded."""


class RequirementsProvider:
    def __init__(
        self,
        kb_path: str | Path = DEFAULT_KB_PATH,
    ):
        self.kb_path = Path(kb_path)
        self.knowledge_base = self._load_knowledge_base()
        self.sources = self._build_source_index()

        self.document_catalogue = self.knowledge_base.get(
            "document_catalogue", {}
        )

        self.documents = self._build_document_index()

        self.checklists = self.document_catalogue.get(
            "checklists_by_student_type", {}
        )

        if not isinstance(self.checklists, dict):
            raise RequirementsProviderError(
                "Knowledge base must contain a valid "
                "'checklists_by_student_type' object."
            )

    def _load_knowledge_base(self) -> dict[str, Any]:
        """Load and validate the knowledge-base JSON."""

        if not self.kb_path.is_file():
            raise RequirementsProviderError(
                f"Knowledge base not found: {self.kb_path}"
            )

        try:
            with self.kb_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise RequirementsProviderError(
                f"Knowledge base contains invalid JSON: {exc}"
            ) from exc
        except OSError as exc:
            raise RequirementsProviderError(
                f"Unable to read knowledge base: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise RequirementsProviderError(
                "Knowledge base must contain a JSON object."
            )

        if not isinstance(data.get("document_catalogue"), dict):
            raise RequirementsProviderError(
                "Knowledge base is missing a valid document_catalogue."
            )

        return data

    def _build_document_index(self) -> dict[str, dict[str, Any]]:
        """Index document metadata by document ID."""

        documents = self.document_catalogue.get("documents", [])

        if not isinstance(documents, list):
            raise RequirementsProviderError(
                "'document_catalogue.documents' must be a list."
            )

        index = {}

        for document in documents:
            if not isinstance(document, dict):
                continue

            document_id = document.get("doc_id")

            if not isinstance(document_id, str) or not document_id:
                continue

            if document_id in index:
                raise RequirementsProviderError(
                    f"Duplicate document ID in knowledge base: "
                    f"{document_id}"
                )

            index[document_id] = document

        return index

    @staticmethod
    def _is_verified(document: dict[str, Any]) -> bool:
        """Check whether the document's requirement status is verified."""

        status = document.get("verification_status")

        return (
            isinstance(status, str)
            and status.strip().lower() in VERIFIED_STATUSES
        )

    def get_checklist(
        self,
        student_type: str,
    ) -> dict[str, Any]:
        """
        Return checklist guidance for a student category.

        Supported categories are defined by the knowledge base,
        for example:
        - degree_first_year
        - degree_lateral_entry
        - diploma_first_year
        - diploma_lateral_entry
        - renewal
        """

        if not isinstance(student_type, str) or not student_type.strip():
            raise ValueError("student_type must be a non-empty string.")

        student_type = student_type.strip().lower()

        checklist = self.checklists.get(student_type)

        if not isinstance(checklist, dict):
            raise ValueError(
                f"Unknown student type: {student_type}. "
                f"Supported types: {', '.join(sorted(self.checklists))}"
            )

        categories = (
            "core",
            "conditional",
            "confirm_with_institute_or_nsp",
        )

        result = {
            "student_type": student_type,
            "checklist": {},
            "notes": [],
            "warnings": [],
        }

        for category in categories:
            document_ids = checklist.get(category, [])

            if not isinstance(document_ids, list):
                result["warnings"].append(
                    f"Invalid checklist category: {category}"
                )
                continue

            result["checklist"][category] = []

            for document_id in document_ids:
                document = self.documents.get(document_id)

                if document is None:
                    result["warnings"].append(
                        f"Document ID '{document_id}' is missing "
                        "from the document catalogue."
                    )
                    continue

                source_ids = document.get("source_ids", [])

                if not isinstance(source_ids, list):
                    source_ids = []

                result["checklist"][category].append({
                    "doc_id": document_id,
                    "name": document.get("name", document_id),
                    "requirement_level": document.get(
                        "requirement_level",
                        "not_verified",
                    ),
                    "verification_status": document.get(
                        "verification_status",
                        "not_found",
                    ),
                    "verified_for_processing": self._is_verified(document),
                    "condition": document.get("condition"),
                    "evidence": document.get("evidence"),
                    "tips": document.get("tips", []),
                    "source_ids": source_ids,
                    "sources": self.get_source_details(source_ids),
                })

        note = checklist.get("note")

        if isinstance(note, str) and note.strip():
            result["notes"].append(note)

        result["warnings"].append(
            "Checklist guidance is not proof of the live 2026-27 "
            "portal's final document requirements."
        )

        return result

    def get_processing_constraints(
    self,
        student_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Return explicitly defined processing constraints only when the
        document status and supporting source metadata meet the policy.

        This method does not infer constraints from descriptions, checklists,
        or RAG responses.
        """
        verified_constraints = []
        excluded_documents = []

        documents_to_check = list(self.documents.values())

        if student_type is not None:
            checklist_result = self.get_checklist(student_type)

            document_ids = {
                item["doc_id"]
                for category in checklist_result["checklist"].values()
                for item in category
            }

            documents_to_check = [
                self.documents[doc_id]
                for doc_id in document_ids
                if doc_id in self.documents
            ]

        for document in documents_to_check:
            document_id = document.get("doc_id", "unknown")
            verification_status = document.get(
                "verification_status",
                "not_found",
            )

            # 1. Check the document's verification status.
            if not self._is_verified(document):
                excluded_documents.append({
                    "doc_id": document_id,
                    "verification_status": verification_status,
                    "reason": "Document verification status is not accepted.",
                })
                continue

            # 2. Require explicit processing constraints.
            constraints = document.get("processing_constraints")

            if not isinstance(constraints, dict) or not constraints:
                continue

            # 3. Validate the structure of source references.
            source_ids = document.get("source_ids")

            if (
                not isinstance(source_ids, list)
                or not source_ids
                or not all(
                    isinstance(source_id, str) and source_id.strip()
                    for source_id in source_ids
                )
            ):
                excluded_documents.append({
                    "doc_id": document_id,
                    "verification_status": verification_status,
                    "reason": (
                        "Explicit processing constraints have no valid "
                        "supporting source references."
                    ),
                })
                continue

            # 4. Resolve source metadata.
            missing_source_ids = [
                source_id
                for source_id in source_ids
                if source_id not in self.sources
            ]

            if missing_source_ids:
                excluded_documents.append({
                    "doc_id": document_id,
                    "verification_status": verification_status,
                    "reason": "One or more referenced sources are missing.",
                    "missing_source_ids": missing_source_ids,
                })
                continue

            # 5. Do not treat an unchecked source as live-portal evidence.
            unchecked_sources = [
                source_id
                for source_id in source_ids
                if self.sources[source_id].get("checked_live_2026_27")
                is not True
            ]

            if unchecked_sources:
                excluded_documents.append({
                    "doc_id": document_id,
                    "verification_status": verification_status,
                    "reason": (
                        "Supporting sources have not all been confirmed "
                        "against the live 2026-27 portal."
                    ),
                    "unchecked_source_ids": unchecked_sources,
                })
                continue

            verified_constraints.append({
                "doc_id": document_id,
                "name": document.get("name", document_id),
                "source_ids": source_ids,
                "constraints": constraints,
            })

        return {
            "processing_constraints": verified_constraints,
            "excluded_documents": excluded_documents,
            "count": len(verified_constraints),
            "note": (
                "Only explicitly defined processing constraints with an "
                "accepted document verification status, valid source "
                "references, and sources checked against the live 2026-27 "
                "portal are returned. This does not independently establish "
                "that each source supports each individual constraint."
            ),
        }
   
   
    def _build_source_index(self) -> dict[str, dict[str, Any]]:
        sources = self.knowledge_base.get("sources", [])

        if not isinstance(sources, list):
            raise RequirementsProviderError(
                "'sources' must be a list in the knowledge base."
            )

        index = {}

        for source in sources:
            if not isinstance(source, dict):
                continue

            source_id = source.get("id")

            if not isinstance(source_id, str) or not source_id:
                continue

            if source_id in index:
                raise RequirementsProviderError(
                    f"Duplicate source ID in knowledge base: {source_id}"
                )

            index[source_id] = source

        return index
    
    def get_source_details(
    self,
    source_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Resolve source IDs and expose their verification limitations."""
        resolved_sources = []

        for source_id in source_ids:
            source = self.sources.get(source_id)

            if source is None:
                resolved_sources.append({
                    "source_id": source_id,
                    "found": False,
                    "warning": "Source ID is missing from the knowledge base.",
                })
                continue

            resolved_sources.append({
                "source_id": source_id,
                "found": True,
                "title": source.get("title"),
                "source_type": source.get("source_type"),
                "checked_live_2026_27": source.get("checked_live_2026_27"),
                "caution": source.get("caution"),
            })

        return resolved_sources