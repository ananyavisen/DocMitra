
#Load and validate the DocMitra Pragati knowledge base JSON.

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Literal

DEFAULT_KB_FILENAME = "docmitra_nsp_pragati_2026_27_final.json"

REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "_meta",
        "important_dates",
        "authorities_and_links",
        "schemes",
        "document_catalogue",
        "application_process",
        "verification_workflow",
        "faqs",
        "docmitra_features",
        "sources",
        "rag_chunks",
        "eligibility_rules",
    }
)

CHECKLIST_SECTIONS: frozenset[str] = frozenset(
    {"core", "conditional", "confirm_with_institute_or_nsp"}
)

ALLOWED_OPERATORS: frozenset[str] = frozenset(
    {
        "equals",
        "equals_case_insensitive",
        "in",
        "less_than",
        "greater_than",
        "is_unknown",
        "is_true_or_unknown",
    }
)

KNOWN_RULE_TYPES: frozenset[str] = frozenset(
    {
        "hard_rule",
        "uncertainty_rule",
        "workflow_rule",
        "advisory",
        "input_required",
        "document_requirement",
    }
)

SOURCE_REF_KEYS: frozenset[str] = frozenset({"source_ids", "purpose_source_ids"})


class KnowledgeBaseLoadError(Exception):
    """Raised when the knowledge base file cannot be read or parsed."""


@dataclass(frozen=True)
class ValidationIssue:
    level: Literal["error", "warning"]
    code: str
    path: str
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, level: Literal["error", "warning"], code: str, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(level=level, code=code, path=path, message=message))


@dataclass
class LoadResult:
    kb: KnowledgeBase
    report: ValidationReport


def _default_kb_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / DEFAULT_KB_FILENAME


def _readonly(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _readonly(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_readonly(v) for v in value)
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeBaseLoadError(f"Cannot read knowledge base file: {path}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise KnowledgeBaseLoadError(f"Malformed JSON in knowledge base file: {path}") from exc
    if not isinstance(data, dict):
        raise KnowledgeBaseLoadError("Knowledge base root must be a JSON object.")
    return data


class KnowledgeBase:
    def __init__(
        self,
        data: dict[str, Any],
        *,
        source_path: Path | None = None,
        indexes: dict[str, Any] | None = None,
    ) -> None:
        self._data = data
        self._source_path = source_path
        if indexes is not None:
            self._sources_by_id = indexes["sources_by_id"]
            self._schemes_by_id = indexes["schemes_by_id"]
            self._chunks_by_id = indexes["chunks_by_id"]
            self._rules_by_id = indexes["rules_by_id"]
            self._documents_by_id = indexes["documents_by_id"]
            self._checklist_types = indexes["checklist_types"]
        else:
            self._build_indexes()

    @classmethod
    def load(cls, path: Path | None = None, *, validate: bool = True) -> LoadResult:
        kb_path = path if path is not None else _default_kb_path()
        data = _load_json(kb_path)
        report = cls.validate(data) if validate else ValidationReport()
        kb = cls.from_data(
            data,
            source_path=kb_path,
            skip_index_build=not report.ok,
        )
        return LoadResult(kb=kb, report=report)

    @classmethod
    def from_data(
        cls,
        data: dict[str, Any],
        *,
        source_path: Path | None = None,
        skip_index_build: bool = False,
    ) -> KnowledgeBase:
        data = deepcopy(data)
        if skip_index_build:
            return cls(
                data,
                source_path=source_path,
                indexes={
                    "sources_by_id": {},
                    "schemes_by_id": {},
                    "chunks_by_id": {},
                    "rules_by_id": {},
                    "documents_by_id": {},
                    "checklist_types": [],
                },
            )
        return cls(data, source_path=source_path)

    @staticmethod
    def validate(data: Mapping[str, Any]) -> ValidationReport:
        report = ValidationReport()
        if not isinstance(data, dict):
            report.add("error", "INVALID_ROOT", "$", "Knowledge base root must be a JSON object.")
            return report

        _validate_top_level(data, report)

        verification_legend = _legend_keys(data, "_meta", "verification_legend")
        requirement_legend = _legend_keys(data, "_meta", "requirement_level_legend")

        source_ids = _validate_sources(data.get("sources"), report)
        scheme_ids = _validate_schemes(data.get("schemes"), report)
        doc_ids = _validate_documents(
            data.get("document_catalogue"),
            scheme_ids,
            report,
            requirement_legend,
            verification_legend,
        )
        _validate_checklists(data.get("document_catalogue"), doc_ids, report)
        _validate_rag_chunks(data.get("rag_chunks"), report, verification_legend)
        allowed_rule_fields, input_by_field = _validate_docmitra_eligibility_inputs(
            data.get("docmitra_features"), report
        )
        _validate_eligibility_rules(
            data.get("eligibility_rules"),
            report,
            allowed_rule_fields,
            input_by_field,
            verification_legend,
        )
        _walk_source_references(data, source_ids, report)
        _validate_faqs_type(data.get("faqs"), report)

        return report

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    @property
    def schema_version(self) -> str:
        meta = self._data.get("_meta") or {}
        return str(meta.get("schema_version", ""))

    @property
    def knowledge_base_id(self) -> str:
        meta = self._data.get("_meta") or {}
        return str(meta.get("knowledge_base_id", ""))

    def as_mapping(self) -> Mapping[str, Any]:
        return _readonly(self._data)

    def meta(self) -> Mapping[str, Any]:
        value = self._data.get("_meta")
        if not isinstance(value, dict):
            return MappingProxyType({})
        return _readonly(value)

    def docmitra_features(self) -> Mapping[str, Any]:
        value = self._data.get("docmitra_features")
        if not isinstance(value, dict):
            return MappingProxyType({})
        return _readonly(value)

    def iter_sources(self) -> Iterator[Mapping[str, Any]]:
        sources = self._data.get("sources")
        if not isinstance(sources, list):
            return
        for item in sources:
            if isinstance(item, dict):
                yield _readonly(item)

    def get_source(self, source_id: str) -> Mapping[str, Any] | None:
        found = self._sources_by_id.get(source_id)
        return _readonly(found) if found is not None else None

    def iter_schemes(self) -> Iterator[Mapping[str, Any]]:
        schemes = self._data.get("schemes")
        if not isinstance(schemes, list):
            return
        for item in schemes:
            if isinstance(item, dict):
                yield _readonly(item)

    def get_scheme(self, scheme_id: str) -> Mapping[str, Any] | None:
        found = self._schemes_by_id.get(scheme_id)
        return _readonly(found) if found is not None else None

    def scheme_ids(self) -> frozenset[str]:
        return frozenset(self._schemes_by_id.keys())

    def iter_rag_chunks(self) -> Iterator[Mapping[str, Any]]:
        chunks = self._data.get("rag_chunks")
        if not isinstance(chunks, list):
            return
        for item in chunks:
            if isinstance(item, dict):
                yield _readonly(item)

    def get_rag_chunk(self, chunk_id: str) -> Mapping[str, Any] | None:
        found = self._chunks_by_id.get(chunk_id)
        return _readonly(found) if found is not None else None

    def iter_eligibility_rules(self) -> Iterator[Mapping[str, Any]]:
        rules = self._data.get("eligibility_rules")
        if not isinstance(rules, list):
            return
        for item in rules:
            if isinstance(item, dict):
                yield _readonly(item)

    def get_eligibility_rule(self, rule_id: str) -> Mapping[str, Any] | None:
        found = self._rules_by_id.get(rule_id)
        return _readonly(found) if found is not None else None

    def iter_documents(self) -> Iterator[Mapping[str, Any]]:
        catalogue = self._data.get("document_catalogue")
        if not isinstance(catalogue, dict):
            return
        documents = catalogue.get("documents")
        if not isinstance(documents, list):
            return
        for item in documents:
            if isinstance(item, dict):
                yield _readonly(item)

    def get_document(self, doc_id: str) -> Mapping[str, Any] | None:
        found = self._documents_by_id.get(doc_id)
        return _readonly(found) if found is not None else None

    def list_checklist_student_types(self) -> list[str]:
        return list(self._checklist_types)

    def get_checklist(self, student_type: str) -> Mapping[str, Any] | None:
        catalogue = self._data.get("document_catalogue")
        if not isinstance(catalogue, dict):
            return None
        checklists = catalogue.get("checklists_by_student_type")
        if not isinstance(checklists, dict):
            return None
        found = checklists.get(student_type)
        if not isinstance(found, dict):
            return None
        return _readonly(found)

    def _build_indexes(self) -> None:
        self._sources_by_id = {}
        sources = self._data.get("sources")
        if isinstance(sources, list):
            for item in sources:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    self._sources_by_id[item["id"]] = item

        self._schemes_by_id = {}
        schemes = self._data.get("schemes")
        if isinstance(schemes, list):
            for item in schemes:
                if isinstance(item, dict) and isinstance(item.get("scheme_id"), str):
                    self._schemes_by_id[item["scheme_id"]] = item

        self._chunks_by_id = {}
        chunks = self._data.get("rag_chunks")
        if isinstance(chunks, list):
            for item in chunks:
                if isinstance(item, dict) and isinstance(item.get("chunk_id"), str):
                    self._chunks_by_id[item["chunk_id"]] = item

        self._rules_by_id = {}
        rules = self._data.get("eligibility_rules")
        if isinstance(rules, list):
            for item in rules:
                if isinstance(item, dict) and isinstance(item.get("rule_id"), str):
                    self._rules_by_id[item["rule_id"]] = item

        self._documents_by_id = {}
        catalogue = self._data.get("document_catalogue")
        if isinstance(catalogue, dict):
            documents = catalogue.get("documents")
            if isinstance(documents, list):
                for item in documents:
                    if isinstance(item, dict) and isinstance(item.get("doc_id"), str):
                        self._documents_by_id[item["doc_id"]] = item

        self._checklist_types = []
        if isinstance(catalogue, dict):
            checklists = catalogue.get("checklists_by_student_type")
            if isinstance(checklists, dict):
                for key in checklists:
                    if not key.startswith("_"):
                        self._checklist_types.append(key)


def _legend_keys(data: Mapping[str, Any], *path: str) -> frozenset[str]:
    node: Any = data
    for part in path:
        if not isinstance(node, dict):
            return frozenset()
        node = node.get(part)
    if isinstance(node, dict):
        return frozenset(str(k) for k in node.keys())
    return frozenset()


def _validate_top_level(data: Mapping[str, Any], report: ValidationReport) -> None:
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in data:
            report.add(
                "error",
                "MISSING_TOP_LEVEL_KEY",
                "$",
                f"Missing required top-level key: {key!r}.",
            )

    meta = data.get("_meta")
    if meta is None and "_meta" in data:
        meta = data["_meta"]
    if "_meta" in data and not isinstance(meta, dict):
        report.add("error", "INVALID_TYPE", "_meta", "_meta must be an object.")
    elif isinstance(meta, dict):
        if not isinstance(meta.get("schema_version"), str) or not meta.get("schema_version"):
            report.add(
                "error",
                "MISSING_FIELD",
                "_meta.schema_version",
                "schema_version must be a non-empty string.",
            )
        if not isinstance(meta.get("knowledge_base_id"), str) or not meta.get("knowledge_base_id"):
            report.add(
                "error",
                "MISSING_FIELD",
                "_meta.knowledge_base_id",
                "knowledge_base_id must be a non-empty string.",
            )

    type_expectations: list[tuple[str, type | tuple[type, ...]]] = [
        ("important_dates", dict),
        ("authorities_and_links", dict),
        ("schemes", list),
        ("document_catalogue", dict),
        ("application_process", dict),
        ("verification_workflow", dict),
        ("faqs", list),
        ("docmitra_features", dict),
        ("sources", list),
        ("rag_chunks", list),
        ("eligibility_rules", list),
    ]
    for key, expected in type_expectations:
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, expected):
            report.add(
                "error",
                "INVALID_TYPE",
                key,
                f"{key} must be {expected!r}, got {type(value).__name__}.",
            )


def _validate_sources(sources: Any, report: ValidationReport) -> set[str]:
    ids: set[str] = set()
    if not isinstance(sources, list):
        report.add("error", "INVALID_TYPE", "sources", "sources must be a list.")
        return ids

    for index, item in enumerate(sources):
        path = f"sources[{index}]"
        if not isinstance(item, dict):
            report.add("error", "INVALID_TYPE", path, "Each source must be an object.")
            continue
        source_id = item.get("id")
        if not isinstance(source_id, str) or not source_id:
            report.add("error", "MISSING_FIELD", f"{path}.id", "Source id must be a non-empty string.")
            continue
        if source_id in ids:
            report.add("error", "DUPLICATE_ID", f"{path}.id", f"Duplicate source id: {source_id!r}.")
        ids.add(source_id)
    return ids


def _validate_schemes(schemes: Any, report: ValidationReport) -> set[str]:
    ids: set[str] = set()
    if not isinstance(schemes, list):
        report.add("error", "INVALID_TYPE", "schemes", "schemes must be a list.")
        return ids

    for index, item in enumerate(schemes):
        path = f"schemes[{index}]"
        if not isinstance(item, dict):
            report.add("error", "INVALID_TYPE", path, "Each scheme must be an object.")
            continue
        scheme_id = item.get("scheme_id")
        if not isinstance(scheme_id, str) or not scheme_id:
            report.add(
                "error",
                "MISSING_FIELD",
                f"{path}.scheme_id",
                "scheme_id must be a non-empty string.",
            )
            continue
        if scheme_id in ids:
            report.add(
                "error",
                "DUPLICATE_ID",
                f"{path}.scheme_id",
                f"Duplicate scheme_id: {scheme_id!r}.",
            )
        ids.add(scheme_id)
        if not isinstance(item.get("official_name"), str) or not item.get("official_name"):
            report.add(
                "error",
                "MISSING_FIELD",
                f"{path}.official_name",
                "official_name must be a non-empty string.",
            )
    return ids


def _validate_documents(
    catalogue: Any,
    scheme_ids: set[str],
    report: ValidationReport,
    requirement_legend: frozenset[str],
    verification_legend: frozenset[str],
) -> set[str]:
    doc_ids: set[str] = set()
    if not isinstance(catalogue, dict):
        report.add("error", "INVALID_TYPE", "document_catalogue", "document_catalogue must be an object.")
        return doc_ids

    documents = catalogue.get("documents")
    if not isinstance(documents, list):
        report.add(
            "error",
            "INVALID_TYPE",
            "document_catalogue.documents",
            "documents must be a list.",
        )
        return doc_ids

    checklists = catalogue.get("checklists_by_student_type")
    if not isinstance(checklists, dict):
        report.add(
            "error",
            "INVALID_TYPE",
            "document_catalogue.checklists_by_student_type",
            "checklists_by_student_type must be an object.",
        )

    for index, item in enumerate(documents):
        path = f"document_catalogue.documents[{index}]"
        if not isinstance(item, dict):
            report.add("error", "INVALID_TYPE", path, "Each document must be an object.")
            continue
        doc_id = item.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id:
            report.add("error", "MISSING_FIELD", f"{path}.doc_id", "doc_id must be a non-empty string.")
            continue
        if doc_id in doc_ids:
            report.add("error", "DUPLICATE_ID", f"{path}.doc_id", f"Duplicate doc_id: {doc_id!r}.")
        doc_ids.add(doc_id)

        level = item.get("requirement_level")
        if not isinstance(level, str) or not level:
            report.add(
                "error",
                "MISSING_FIELD",
                f"{path}.requirement_level",
                "requirement_level must be a non-empty string.",
            )
        elif requirement_legend and level not in requirement_legend:
            report.add(
                "warning",
                "UNKNOWN_REQUIREMENT_LEVEL",
                f"{path}.requirement_level",
                f"requirement_level {level!r} is not listed in _meta.requirement_level_legend.",
            )

        applies_to = item.get("applies_to")
        if applies_to is not None:
            if not isinstance(applies_to, list):
                report.add("error", "INVALID_TYPE", f"{path}.applies_to", "applies_to must be a list.")
            else:
                for ai, scheme_ref in enumerate(applies_to):
                    if not isinstance(scheme_ref, str):
                        report.add(
                            "error",
                            "INVALID_TYPE",
                            f"{path}.applies_to[{ai}]",
                            "applies_to entries must be strings.",
                        )
                    elif scheme_ref not in scheme_ids:
                        report.add(
                            "error",
                            "UNKNOWN_SCHEME_ID",
                            f"{path}.applies_to[{ai}]",
                            f"Unknown scheme_id reference: {scheme_ref!r}.",
                        )

        verification = item.get("verification_status")
        if isinstance(verification, str) and verification:
            _warn_unknown_verification(
                verification, f"{path}.verification_status", report, verification_legend
            )

    return doc_ids


def _validate_checklists(catalogue: Any, doc_ids: set[str], report: ValidationReport) -> None:
    if not isinstance(catalogue, dict):
        return
    checklists = catalogue.get("checklists_by_student_type")
    if not isinstance(checklists, dict):
        return

    for student_type, checklist in checklists.items():
        if student_type.startswith("_"):
            continue
        base = f"document_catalogue.checklists_by_student_type.{student_type}"
        if not isinstance(checklist, dict):
            report.add("error", "INVALID_TYPE", base, "Each checklist must be an object.")
            continue
        for section in CHECKLIST_SECTIONS:
            if section not in checklist:
                report.add(
                    "error",
                    "MISSING_FIELD",
                    f"{base}.{section}",
                    f"Checklist must include section {section!r}.",
                )
                continue
            entries = checklist[section]
            if not isinstance(entries, list):
                report.add(
                    "error",
                    "INVALID_TYPE",
                    f"{base}.{section}",
                    f"{section} must be a list.",
                )
                continue
            seen: set[str] = set()
            for ei, doc_ref in enumerate(entries):
                ref_path = f"{base}.{section}[{ei}]"
                if not isinstance(doc_ref, str):
                    report.add("error", "INVALID_TYPE", ref_path, "Checklist entries must be strings.")
                    continue
                if doc_ref not in doc_ids:
                    report.add(
                        "error",
                        "UNKNOWN_DOCUMENT_ID",
                        ref_path,
                        f"Unknown doc_id in checklist: {doc_ref!r}.",
                    )
                if doc_ref in seen:
                    report.add(
                        "warning",
                        "DUPLICATE_CHECKLIST_ENTRY",
                        ref_path,
                        f"Duplicate doc_id {doc_ref!r} in the same checklist section.",
                    )
                seen.add(doc_ref)


def _validate_rag_chunks(
    chunks: Any,
    report: ValidationReport,
    verification_legend: frozenset[str],
) -> None:
    if not isinstance(chunks, list):
        report.add("error", "INVALID_TYPE", "rag_chunks", "rag_chunks must be a list.")
        return

    seen: set[str] = set()
    for index, item in enumerate(chunks):
        path = f"rag_chunks[{index}]"
        if not isinstance(item, dict):
            report.add("error", "INVALID_TYPE", path, "Each RAG chunk must be an object.")
            continue
        chunk_id = item.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            report.add("error", "MISSING_FIELD", f"{path}.chunk_id", "chunk_id must be a non-empty string.")
            continue
        if chunk_id in seen:
            report.add("error", "DUPLICATE_ID", f"{path}.chunk_id", f"Duplicate chunk_id: {chunk_id!r}.")
        seen.add(chunk_id)

        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            report.add("error", "MISSING_FIELD", f"{path}.text", "text must be a non-empty string.")

        status = item.get("verification_status")
        if not isinstance(status, str) or not status:
            report.add(
                "error",
                "MISSING_FIELD",
                f"{path}.verification_status",
                "verification_status must be a non-empty string.",
            )
        else:
            _warn_unknown_verification(status, f"{path}.verification_status", report, verification_legend)

        source_ids = item.get("source_ids")
        if not isinstance(source_ids, list):
            report.add("error", "INVALID_TYPE", f"{path}.source_ids", "source_ids must be a list.")


def _validate_docmitra_eligibility_inputs(
    features: Any,
    report: ValidationReport,
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    allowed: set[str] = set()
    by_field: dict[str, dict[str, Any]] = {}
    if not isinstance(features, dict):
        report.add("error", "INVALID_TYPE", "docmitra_features", "docmitra_features must be an object.")
        return allowed, by_field

    eligibility = features.get("eligibility_check")
    if not isinstance(eligibility, dict):
        report.add(
            "error",
            "MISSING_FIELD",
            "docmitra_features.eligibility_check",
            "eligibility_check must be an object.",
        )
        return allowed, by_field

    inputs = eligibility.get("inputs")
    if not isinstance(inputs, list):
        report.add(
            "error",
            "INVALID_TYPE",
            "docmitra_features.eligibility_check.inputs",
            "inputs must be a list.",
        )
        return allowed, by_field

    for index, item in enumerate(inputs):
        path = f"docmitra_features.eligibility_check.inputs[{index}]"
        if not isinstance(item, dict):
            report.add("error", "INVALID_TYPE", path, "Each input must be an object.")
            continue
        field_name = item.get("field")
        if not isinstance(field_name, str) or not field_name:
            report.add("error", "MISSING_FIELD", f"{path}.field", "field must be a non-empty string.")
            continue
        allowed.add(field_name)
        by_field[field_name] = item

    return allowed, by_field


def _validate_eligibility_rules(
    rules: Any,
    report: ValidationReport,
    allowed_fields: set[str],
    input_by_field: dict[str, dict[str, Any]],
    verification_legend: frozenset[str],
) -> None:
    if not isinstance(rules, list):
        report.add("error", "INVALID_TYPE", "eligibility_rules", "eligibility_rules must be a list.")
        return

    seen: set[str] = set()
    for index, item in enumerate(rules):
        path = f"eligibility_rules[{index}]"
        if not isinstance(item, dict):
            report.add("error", "INVALID_TYPE", path, "Each eligibility rule must be an object.")
            continue

        rule_id = item.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            report.add("error", "MISSING_FIELD", f"{path}.rule_id", "rule_id must be a non-empty string.")
            continue
        if rule_id in seen:
            report.add("error", "DUPLICATE_ID", f"{path}.rule_id", f"Duplicate rule_id: {rule_id!r}.")
        seen.add(rule_id)

        field_name = item.get("field")
        if not isinstance(field_name, str) or not field_name:
            report.add("error", "MISSING_FIELD", f"{path}.field", "field must be a non-empty string.")
        elif field_name not in allowed_fields:
            report.add(
                "error",
                "UNKNOWN_RULE_FIELD",
                f"{path}.field",
                f"field {field_name!r} is not declared in docmitra_features.eligibility_check.inputs.",
            )

        effect = item.get("effect")
        if not isinstance(effect, str) or not effect:
            report.add("error", "MISSING_FIELD", f"{path}.effect", "effect must be a non-empty string.")

        rule_type = item.get("rule_type")
        if not isinstance(rule_type, str) or not rule_type:
            report.add("error", "MISSING_FIELD", f"{path}.rule_type", "rule_type must be a non-empty string.")
        elif rule_type not in KNOWN_RULE_TYPES:
            report.add(
                "warning",
                "UNKNOWN_RULE_TYPE",
                f"{path}.rule_type",
                f"rule_type {rule_type!r} is not in the known rule type set.",
            )

        status = item.get("verification_status")
        if isinstance(status, str) and status:
            _warn_unknown_verification(status, f"{path}.verification_status", report, verification_legend)

        condition = item.get("condition")
        if not isinstance(condition, dict):
            report.add("error", "INVALID_TYPE", f"{path}.condition", "condition must be an object.")
            continue

        operator = condition.get("operator")
        if not isinstance(operator, str) or not operator:
            report.add(
                "error",
                "MISSING_FIELD",
                f"{path}.condition.operator",
                "operator must be a non-empty string.",
            )
            continue
        if operator not in ALLOWED_OPERATORS:
            report.add(
                "error",
                "UNKNOWN_OPERATOR",
                f"{path}.condition.operator",
                f"Unsupported operator: {operator!r}.",
            )
            continue

        if "value" not in condition:
            report.add(
                "error",
                "MISSING_FIELD",
                f"{path}.condition.value",
                "condition must include value.",
            )
            continue

        value = condition["value"]
        if isinstance(field_name, str):
            _validate_condition_value(
                operator,
                value,
                input_by_field.get(field_name),
                f"{path}.condition.value",
                report,
            )


def _input_value_kind(input_def: dict[str, Any] | None) -> str:
    if not isinstance(input_def, dict):
        return "general"

    declared_type = input_def.get("type")

    if declared_type == "tri_state":
        return "tri_state"

    if "values" in input_def:
        return "enum"

    if declared_type in {"integer", "number", "float"}:
        return "numeric"

    return "general"


def _validate_condition_value(
    operator: str,
    value: Any,
    input_def: dict[str, Any] | None,
    path: str,
    report: ValidationReport,
) -> None:
    kind = _input_value_kind(input_def)

    if operator == "in":
        if not isinstance(value, list):
            report.add("error", "INVALID_CONDITION_VALUE", path, "Operator 'in' requires a list value.")
            return

        for index, entry in enumerate(value):
            entry_path = f"{path}[{index}]"
            if not isinstance(entry, str):
                report.add("error", "INVALID_CONDITION_VALUE", entry_path, "Operator 'in' requires list elements to be strings.")
            elif kind == "enum" and entry not in input_def["values"]:
             report.add("error", "INVALID_CONDITION_VALUE", entry_path, f"Value {entry!r} is not in the allowed values for this field.")

    return

    if operator in {"is_unknown", "is_true_or_unknown"}:
        if not isinstance(value, bool):
            report.add(
                "error",
                "INVALID_CONDITION_VALUE",
                path,
                f"Operator {operator!r} requires a boolean value.",
            )
        return

    if operator in {"less_than", "greater_than"}:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            report.add(
                "error",
                "INVALID_CONDITION_VALUE",
                path,
                f"Operator {operator!r} requires a numeric value.",
            )
        return

    if operator == "equals_case_insensitive":
        if not isinstance(value, str):
            report.add(
                "error",
                "INVALID_CONDITION_VALUE",
                path,
                "Operator 'equals_case_insensitive' requires a string value.",
            )
        return

    if operator == "equals":
        if kind == "tri_state":
            if not isinstance(value, bool):
                report.add(
                    "error",
                    "INVALID_CONDITION_VALUE",
                    path,
                    "Operator 'equals' on a tri_state field requires a boolean value.",
                )
        elif kind == "enum":
            if not isinstance(value, str):
                report.add(
            "error",
            "INVALID_CONDITION_VALUE",
            path,
            "Operator 'equals' on an enum field requires a string value.",
        )
            else:
                allowed_values = input_def.get("values", [])
                if value not in allowed_values:
                    report.add(
                        "error",
                        "INVALID_CONDITION_VALUE",
                        path,
                        f"Value {value!r} is not in the allowed values for this field.",
                    )
        elif kind == "numeric":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                report.add(
                    "error",
                    "INVALID_CONDITION_VALUE",
                    path,
                    "Operator 'equals' on a numeric field requires a number.",
                )
        return


def _walk_source_references(data: Any, source_ids: set[str], report: ValidationReport) -> None:
    if not source_ids:
        return

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}" if path else key
                if key in SOURCE_REF_KEYS:
                    _validate_source_id_list(value, child_path, source_ids, report)
                walk(value, child_path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(data, "")


def _validate_source_id_list(
    value: Any,
    path: str,
    source_ids: set[str],
    report: ValidationReport,
) -> None:
    if not isinstance(value, list):
        report.add("error", "INVALID_TYPE", path, f"{path.split('.')[-1]} must be a list.")
        return
    for index, ref in enumerate(value):
        ref_path = f"{path}[{index}]"
        if not isinstance(ref, str):
            report.add("error", "INVALID_TYPE", ref_path, "Source reference must be a string.")
            continue
        if ref not in source_ids:
            report.add(
                "error",
                "BROKEN_SOURCE_REF",
                ref_path,
                f"Unknown source id reference: {ref!r}.",
            )


def _validate_faqs_type(faqs: Any, report: ValidationReport) -> None:
    if faqs is None:
        return
    if not isinstance(faqs, list):
        report.add("error", "INVALID_TYPE", "faqs", "faqs must be a list.")


def _warn_unknown_verification(
    status: str,
    path: str,
    report: ValidationReport,
    legend: frozenset[str],
) -> None:
    if legend and status not in legend:
        report.add(
            "warning",
            "UNKNOWN_VERIFICATION_STATUS",
            path,
            f"verification_status {status!r} is not listed in _meta.verification_legend.",
        )
