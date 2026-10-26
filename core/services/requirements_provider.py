import json
from pathlib import Path
from django.conf import settings


JSON_PATH = (
    settings.BASE_DIR
    / "core"
    / "data"
    / "docmitra_nsp_pragati_2026_27_final.json"
)


def load_requirements():
    """Load DocMitra requirements from the shared JSON source."""
    try:
        with JSON_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not load DocMitra requirements: {exc}"
        ) from exc


def get_document_catalogue():
    """Return the document catalogue from the JSON."""
    data = load_requirements()
    return data.get("document_catalogue", {})


def get_document_by_id(doc_id):
    """Find one document by its ID."""
    catalogue = get_document_catalogue()
    documents = catalogue.get("documents", [])

    for document in documents:
        if document.get("doc_id") == doc_id:
            return document

    return None


def get_checklist(student_type):
    """Return the checklist for a student type."""
    catalogue = get_document_catalogue()
    checklists = catalogue.get("checklists_by_student_type", {})

    return checklists.get(student_type)
