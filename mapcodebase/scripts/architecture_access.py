#!/usr/bin/env python3
"""Render and query bounded views of mapcodebase architecture artifacts.

The JSON manifest remains the machine-compatibility record. This helper renders
its homogeneous arrays as Markdown tables and lets agents retrieve one manifest
section or one detailed flow without loading the complete artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

PREFERRED_SECTION_ORDER = (
    "artifacts",
    "warnings",
    "trust_notes",
    "changed_files_since_scan",
    "changed_components_since_scan",
    "changed_boundary_contracts_since_scan",
    "components",
    "hazards",
    "findings",
    "concerns",
    "patterns",
    "boundary_contracts",
    "economic_authority_matrix",
    "verification_items",
    "answerability_tests",
    "exclusions",
)

PREFERRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "components": (
        "id",
        "name",
        "runtime_status",
        "architecture_status",
        "purpose",
        "entry_file",
        "key_files",
        "doc_path",
        "intent_tags",
        "active_consumers",
        "legacy_consumers",
    ),
    "hazards": (
        "id",
        "type",
        "severity",
        "component",
        "resource",
        "callers",
        "synchronization",
        "description",
    ),
    "findings": (
        "finding_id",
        "severity",
        "confidence",
        "category",
        "component",
        "title",
        "description",
        "suggestion",
        "files",
        "evidence",
    ),
    "concerns": (
        "concern_id",
        "priority",
        "severity",
        "confidence",
        "component",
        "title",
        "summary",
        "source_refs",
        "recommended_action",
        "files",
    ),
    "patterns": (
        "pattern_id",
        "severity",
        "category",
        "files",
        "description",
        "concern",
        "best_practice",
        "evidence",
    ),
    "boundary_contracts": (
        "id",
        "boundary",
        "name",
        "component",
        "producer",
        "adapters",
        "consumer",
        "sink",
        "doc_path",
        "fields_total",
        "field_count",
        "fields_unverified",
        "defect_candidates",
        "verified_at_git",
    ),
    "economic_authority_matrix": (
        "id",
        "label",
        "aliases",
        "metric_kind",
        "roles",
        "component",
        "producer",
        "consumers",
        "price_side",
        "price_source",
        "depth_basis",
        "fees_included",
        "fee_schedule",
        "horizon_source",
        "annualization",
        "day_rounding",
        "formula",
        "formula_version",
        "version_handling",
        "authority_disposition",
        "reconciliation",
        "verified_at_git",
    ),
    "verification_items": (
        "id",
        "kind",
        "status",
        "severity",
        "component",
        "boundary",
        "claim",
        "source_doc",
        "owner_files",
        "evidence_needed",
        "resolution",
        "next_action",
        "created_at_git",
        "last_checked_git",
    ),
    "answerability_tests": (
        "q",
        "question",
        "answered_from_docs",
        "expected_docs",
        "answer",
        "answer_status",
        "evidence_refs",
        "spot_check",
        "unanswered_reason",
    ),
}

IDENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "components": ("id",),
    "hazards": ("id",),
    "findings": ("finding_id",),
    "concerns": ("concern_id",),
    "patterns": ("pattern_id",),
    "boundary_contracts": ("id", "boundary"),
    "economic_authority_matrix": ("id",),
    "verification_items": ("id",),
}

TOTAL_COUNT_METRICS: dict[str, tuple[str, ...]] = {
    "components": ("components_identified",),
    "hazards": ("hazards_identified",),
    "patterns": ("patterns_total_tracked",),
    "findings": ("findings_total_tracked",),
    "concerns": ("concerns_total_tracked",),
    "boundary_contracts": (
        "boundary_contracts_documented",
        "boundary_contracts_identified",
    ),
    "economic_authority_matrix": ("economic_calculation_sites",),
    "answerability_tests": ("answerability_questions",),
}

ECONOMIC_ROW_FIELDS = (
    "id",
    "label",
    "aliases",
    "metric_kind",
    "roles",
    "component",
    "producer",
    "consumers",
    "price_side",
    "price_source",
    "depth_basis",
    "fees_included",
    "fee_schedule",
    "horizon_source",
    "annualization",
    "day_rounding",
    "formula",
    "formula_version",
    "version_handling",
    "authority_disposition",
    "reconciliation",
    "verified_at_git",
)
ECONOMIC_METRIC_KINDS = frozenset(
    {
        "apr",
        "roi",
        "cost_per_pair",
        "lock_in",
        "pnl",
        "fee",
        "fill_price",
        "valuation",
        "spread",
        "other",
    }
)
ECONOMIC_ROLES = frozenset(
    {
        "display",
        "selection",
        "threshold",
        "planner",
        "admission",
        "execution",
        "persistence",
        "replay",
    }
)
ECONOMIC_PRICE_SIDES = frozenset({"bid", "ask", "mid", "last", "mixed", "unknown"})
ECONOMIC_DEPTH_BASES = frozenset(
    {"one_level", "book_walk", "target_size", "fill_weighted", "unknown"}
)
ECONOMIC_ANNUALIZATIONS = frozenset(
    {"simple_365", "simple_360", "compound", "none", "unknown"}
)
ECONOMIC_DAY_ROUNDINGS = frozenset(
    {"fractional", "ceil", "floor", "round", "clamp_min_1", "unknown"}
)
ECONOMIC_VERSION_HANDLING = frozenset(
    {"emitted", "accepted", "rejected", "retired", "dropped", "n/a"}
)
ECONOMIC_AUTHORITY_DISPOSITIONS = frozenset(
    {"canonical", "derived_equivalent", "raw_signal_only", "conflicting", "unknown"}
)
ECONOMIC_RECONCILIATION_STATUSES = frozenset(
    {"proven_equivalent", "concern", "none"}
)
ECONOMIC_TUPLE_FIELDS = (
    "price_side",
    "depth_basis",
    "fees_included",
    "annualization",
    "day_rounding",
    "formula_version_or_formula",
)
ECONOMIC_TUPLE_DISPLAY_NAMES = {
    "formula_version_or_formula": "formula_version or formula",
}
ECONOMIC_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CONCERN_ID_RE = re.compile(r"^CON-\d{3}$")
SHORT_GIT_HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")

REQUIRED_COMPONENT_FIELDS = (
    "id",
    "name",
    "purpose",
    "entry_file",
    "key_files",
    "doc_path",
    "intent_tags",
    "runtime_status",
    "architecture_status",
    "active_consumers",
    "legacy_consumers",
)
COMPONENT_LIST_FIELDS = (
    "key_files",
    "intent_tags",
    "active_consumers",
    "legacy_consumers",
)
COMPONENT_DOC_PATH_DIRECTORY = ("structured", "components")
COMPONENT_DOC_PATHS_SOURCE = "components[].doc_path"

ACCESSOR_CONTRACT_PREFIX = "<!-- mapcodebase-accessor-contract:"
ACCESSOR_CONTRACT_RE = re.compile(
    r"^<!-- mapcodebase-accessor-contract: (?P<payload>\{[^\r\n]*\}) -->$",
    re.MULTILINE,
)
COMPONENT_PATH_COMMAND_RE = re.compile(
    r"\bmanifest-section[ \t]+components[ \t]+--format[ \t]+lines"
    r"[ \t]+--field[ \t]+doc_path\b"
)
COMPONENT_DOC_PATH_AUTHORITY_RE = re.compile(
    r"(?:"
    r"(?:treat|use)\s+`?components\[\]\.doc_path`?\s+as\s+"
    r"(?:the\s+)?(?:authoritative(?:\s+(?:component\s+)?"
    r"(?:set|source(?:\s+of\s+truth)?))?|tracked(?:\s+component)?\s+set)"
    r"|"
    r"`?components\[\]\.doc_path`?\s+is\s+(?:the\s+)?"
    r"(?:authoritative(?:\s+(?:component\s+)?"
    r"(?:set|source(?:\s+of\s+truth)?))?|tracked(?:\s+component)?\s+set)"
    r")",
    re.IGNORECASE,
)


class ManifestValidationError(ValueError):
    """Raised when a manifest cannot safely produce a compact view."""


FLOW_HEADER_RE = re.compile(r"^### FLOW:\s+([^\s]+)(?:\s+.*)?$")
FLOW_REQUIRED_FIELDS = (
    "TRIGGER",
    "ENTRY",
    "STATUS",
    "STEPS",
    "DATA_IN",
    "DATA_OUT",
    "EXITS_TO",
    "BOUNDARIES",
)
CHRONOLOGY_HEADING_PATTERNS = (
    re.compile(r"\bincremental(?:\s+\w+){0,4}\s+delta\b", re.I),
    re.compile(r"\b(?:wave|treatment)\b.*(?:\bdelta\b|\b[0-9a-f]{7,40}\b)", re.I),
    re.compile(r"\b(?:git|commit)\s+[0-9a-f]{7,40}\b", re.I),
    re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"),
)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestValidationError("manifest root must be a JSON object")
    return payload


def _record_list(data: Mapping[str, Any], section: str) -> list[dict[str, Any]]:
    value = data.get(section)
    if not isinstance(value, list):
        raise ManifestValidationError(f"{section} must be an array")
    if not all(isinstance(item, dict) for item in value):
        raise ManifestValidationError(f"{section} must contain only objects")
    return value


def _component_doc_path_issue(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "must be a nonempty string"

    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).is_absolute():
        return "must be repo-relative, not an absolute path"
    if any(part in {".", ".."} for part in path.parts):
        return "must not contain traversal segments"
    if value != path.as_posix():
        return "must be normalized"
    if path.parts[:2] != COMPONENT_DOC_PATH_DIRECTORY:
        return "must be directly under structured/components/"
    if len(path.parts) != 3:
        return "must be a direct child of structured/components/"
    if not path.name or path.suffix != ".md":
        return "must end with .md"
    return None


def validate_manifest(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in (
        "schema_version",
        "skill_version",
        "git_hash",
        "status",
        "access_paths",
    ):
        if field not in data:
            errors.append(f"missing required field: {field}")

    seen_component_doc_paths: set[str] = set()
    for section, identity_fields in IDENTITY_FIELDS.items():
        value = data.get(section)
        if not isinstance(value, list):
            errors.append(f"{section} must be an array")
            continue
        object_rows = [record for record in value if isinstance(record, dict)]
        consistent_fields = [
            candidate
            for candidate in identity_fields
            if all(
                isinstance(record.get(candidate), str) and record[candidate].strip()
                for record in object_rows
            )
        ]
        identity_field = consistent_fields[0] if consistent_fields else None
        if object_rows and identity_field is None:
            alternatives = " or ".join(identity_fields)
            errors.append(
                f"{section} must use one identity field consistently: {alternatives}"
            )
        seen: set[str] = set()
        for index, record in enumerate(value):
            if not isinstance(record, dict):
                errors.append(f"{section}[{index}] must be an object")
                continue
            identity = record.get(identity_field) if identity_field else None
            if isinstance(identity, str):
                if identity in seen:
                    errors.append(f"duplicate {section}.{identity_field}: {identity}")
                seen.add(identity)

            if section == "components":
                component_label = (
                    identity if isinstance(identity, str) else f"row-{index}"
                )
                missing = [
                    field for field in REQUIRED_COMPONENT_FIELDS if field not in record
                ]
                if missing:
                    missing_fields = ", ".join(missing)
                    prefix = f"components[{component_label}] missing routing fields: "
                    errors.append(prefix + missing_fields)
                for field in COMPONENT_LIST_FIELDS:
                    if field in record and not isinstance(record[field], list):
                        errors.append(
                            f"components[{component_label}].{field} must be an array"
                        )
                doc_path = record.get("doc_path")
                issue = _component_doc_path_issue(doc_path)
                if issue:
                    errors.append(f"components[{component_label}].doc_path {issue}")
                if isinstance(doc_path, str) and doc_path.strip():
                    if doc_path in seen_component_doc_paths:
                        errors.append(f"duplicate components.doc_path: {doc_path}")
                    seen_component_doc_paths.add(doc_path)

    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        for section, metric_names in TOTAL_COUNT_METRICS.items():
            records = data.get(section)
            metric_name = next(
                (name for name in metric_names if isinstance(metrics.get(name), int)),
                None,
            )
            expected = metrics.get(metric_name) if metric_name else None
            if (
                isinstance(records, list)
                and isinstance(expected, int)
                and expected != len(records)
            ):
                actual = len(records)
                errors.append(
                    f"metrics.{metric_name}={expected} but {section} has {actual} rows"
                )
        verification_items = data.get("verification_items")
        expected_open = metrics.get("verification_items_open")
        if isinstance(verification_items, list) and isinstance(expected_open, int):
            actual_open = sum(
                1
                for item in verification_items
                if isinstance(item, dict) and item.get("status") == "open"
            )
            if expected_open != actual_open:
                errors.append(
                    "metrics.verification_items_open="
                    f"{expected_open} but verification_items has "
                    f"{actual_open} open rows"
                )
    return errors


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_file_line(value: Any) -> bool:
    if not _is_nonempty_string(value) or ":" not in value:
        return False
    file_part, line_part = value.rsplit(":", 1)
    return bool(file_part.strip() and line_part.strip())


def _economic_row_label(row: Mapping[str, Any], index: int) -> str:
    identifier = row.get("id")
    if _is_nonempty_string(identifier):
        return identifier
    return f"row-{index}"


def _economic_schema_errors(row: Mapping[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    row_label = _economic_row_label(row, index)

    def fail(field: str, detail: str) -> None:
        errors.append(f"ECON-SCHEMA: row {row_label} {field} {detail}")

    for field in ECONOMIC_ROW_FIELDS:
        if field not in row:
            fail(field, "is required")

    identifier = row.get("id")
    if "id" in row and (
        not _is_nonempty_string(identifier) or not ECONOMIC_ID_RE.fullmatch(identifier)
    ):
        fail("id", "must be a non-empty slug")

    label = row.get("label")
    if "label" in row and not _is_nonempty_string(label):
        fail("label", "must be a non-empty string")

    aliases = row.get("aliases")
    if "aliases" in row and (
        not isinstance(aliases, list)
        or not all(isinstance(alias, str) for alias in aliases)
    ):
        fail("aliases", "must be an array of strings")

    metric_kind = row.get("metric_kind")
    if "metric_kind" in row and (
        not isinstance(metric_kind, str) or metric_kind not in ECONOMIC_METRIC_KINDS
    ):
        fail("metric_kind", "has an invalid enum value")

    roles = row.get("roles")
    if "roles" in row and (
        not isinstance(roles, list)
        or not roles
        or any(
            not isinstance(role, str) or role not in ECONOMIC_ROLES for role in roles
        )
    ):
        fail("roles", "must be a non-empty array of allowed roles")

    component = row.get("component")
    if "component" in row and (
        not _is_nonempty_string(component) or not ECONOMIC_ID_RE.fullmatch(component)
    ):
        fail("component", "must be a non-empty slug")

    producer = row.get("producer")
    if "producer" in row and not _is_file_line(producer):
        fail("producer", "must be a file:line string")

    consumers = row.get("consumers")
    if "consumers" in row and (
        not isinstance(consumers, list)
        or not all(_is_file_line(consumer) for consumer in consumers)
    ):
        fail("consumers", "must be an array of file:line strings")

    for field, allowed in (
        ("price_side", ECONOMIC_PRICE_SIDES),
        ("depth_basis", ECONOMIC_DEPTH_BASES),
        ("annualization", ECONOMIC_ANNUALIZATIONS),
        ("day_rounding", ECONOMIC_DAY_ROUNDINGS),
        ("version_handling", ECONOMIC_VERSION_HANDLING),
        ("authority_disposition", ECONOMIC_AUTHORITY_DISPOSITIONS),
    ):
        value = row.get(field)
        if field in row and (not isinstance(value, str) or value not in allowed):
            fail(field, "has an invalid enum value")

    for field in ("price_source", "horizon_source", "formula"):
        if field in row and not isinstance(row.get(field), str):
            fail(field, "must be a string")

    fees_included = row.get("fees_included")
    if "fees_included" in row and not (
        isinstance(fees_included, bool) or fees_included == "unknown"
    ):
        fail("fees_included", "must be true, false, or 'unknown'")

    for field in ("fee_schedule", "formula_version"):
        value = row.get(field)
        if field in row and value is not None and not isinstance(value, str):
            fail(field, "must be a string or null")

    reconciliation = row.get("reconciliation")
    if "reconciliation" in row and not isinstance(reconciliation, Mapping):
        fail("reconciliation", "must be an object")
    elif isinstance(reconciliation, Mapping):
        status = reconciliation.get("status")
        if status not in ECONOMIC_RECONCILIATION_STATUSES:
            fail("reconciliation.status", "has an invalid enum value")

        concern_id = reconciliation.get("concern_id")
        if concern_id is not None and (
            not isinstance(concern_id, str) or not CONCERN_ID_RE.fullmatch(concern_id)
        ):
            fail("reconciliation.concern_id", "must be a CON-NNN string or null")
        if status == "concern" and (
            not isinstance(concern_id, str) or not CONCERN_ID_RE.fullmatch(concern_id)
        ):
            fail("reconciliation.concern_id", "is required when status is concern")

        evidence = reconciliation.get("evidence")
        if evidence is not None and (
            not isinstance(evidence, list)
            or not all(_is_file_line(item) for item in evidence)
        ):
            fail("reconciliation.evidence", "must be an array of file:line strings")
        if status == "proven_equivalent" and (
            not isinstance(evidence, list)
            or not evidence
            or not all(_is_file_line(item) for item in evidence)
        ):
            fail(
                "reconciliation.evidence",
                "must be non-empty when status is proven_equivalent",
            )

    verified_at_git = row.get("verified_at_git")
    if "verified_at_git" in row and (
        not isinstance(verified_at_git, str)
        or not SHORT_GIT_HASH_RE.fullmatch(verified_at_git)
    ):
        fail("verified_at_git", "must be a short git hash string")
    return errors


def _economic_tuple_value(row: Mapping[str, Any], field: str) -> Any:
    if field == "formula_version_or_formula":
        formula_version = row.get("formula_version")
        return formula_version if formula_version is not None else row.get("formula")
    return row.get(field)


def _economic_tuple_has_unknown(row: Mapping[str, Any], field: str) -> bool:
    if field == "fees_included":
        return row.get(field) == "unknown"
    return field in {
        "price_side",
        "depth_basis",
        "annualization",
        "day_rounding",
    } and row.get(field) == "unknown"


def _economic_divergent_elements(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if len(rows) < 2:
        return []
    divergent: list[str] = []
    for field in ECONOMIC_TUPLE_FIELDS:
        values = {_economic_tuple_value(row, field) for row in rows}
        if len(values) > 1 or any(
            _economic_tuple_has_unknown(row, field) for row in rows
        ):
            divergent.append(ECONOMIC_TUPLE_DISPLAY_NAMES.get(field, field))
    return divergent


def _error_concern_ids(data: Mapping[str, Any]) -> set[str]:
    concerns = data.get("concerns")
    if not isinstance(concerns, list):
        return set()
    return {
        concern_id
        for concern in concerns
        if isinstance(concern, Mapping)
        and concern.get("severity") == "error"
        and isinstance(concern_id := concern.get("concern_id"), str)
    }


def _valid_economic_reconciliation(
    row: Mapping[str, Any],
    error_concern_ids: set[str],
    *,
    proven_equivalence_allowed: bool,
) -> bool:
    reconciliation = row.get("reconciliation")
    if not isinstance(reconciliation, Mapping):
        return False
    status = reconciliation.get("status")
    if status == "concern":
        concern_id = reconciliation.get("concern_id")
        return isinstance(concern_id, str) and concern_id in error_concern_ids
    if status == "proven_equivalent" and proven_equivalence_allowed:
        evidence = reconciliation.get("evidence")
        return isinstance(evidence, list) and bool(evidence)
    return False


def _economic_reconciliation_status(row: Mapping[str, Any]) -> str | None:
    reconciliation = row.get("reconciliation")
    if isinstance(reconciliation, Mapping):
        status = reconciliation.get("status")
        if isinstance(status, str):
            return status
    return None


def validate_economic_authority(data: Mapping[str, Any]) -> list[str]:
    """Validate source-derived monetary calculation sites and authority
    reconciliation."""
    errors: list[str] = []
    matrix = data.get("economic_authority_matrix")
    if not isinstance(matrix, list):
        return ["ECON-SCHEMA: economic_authority_matrix must be an array"]

    valid_rows: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(matrix):
        if not isinstance(row, Mapping):
            errors.append(
                f"ECON-SCHEMA: economic_authority_matrix[{index}] must be an object"
            )
            continue
        row_errors = _economic_schema_errors(row, index)
        errors.extend(row_errors)
        identifier = row.get("id")
        if _is_nonempty_string(identifier):
            if identifier in seen_ids:
                errors.append(
                    "ECON-SCHEMA: duplicate economic_authority_matrix.id: "
                    f"{identifier}"
                )
            seen_ids.add(identifier)
        if not row_errors:
            valid_rows.append(row)

    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in valid_rows:
        label = row["label"]
        assert isinstance(label, str)
        groups.setdefault(label.strip().casefold(), []).append(row)

    error_concern_ids = _error_concern_ids(data)
    divergent_groups: dict[str, list[str]] = {}
    for normalized_label, rows in groups.items():
        divergent_elements = _economic_divergent_elements(rows)
        if not divergent_elements:
            continue
        divergent_groups[normalized_label] = divergent_elements
        label = rows[0]["label"]
        assert isinstance(label, str)
        row_ids = [row["id"] for row in rows]
        assert all(isinstance(identifier, str) for identifier in row_ids)
        proven_equivalence_allowed = not any(
            _economic_tuple_has_unknown(row, field)
            for row in rows
            for field in ECONOMIC_TUPLE_FIELDS
        )
        unreconciled_ids = [
            row["id"]
            for row in rows
            if not _valid_economic_reconciliation(
                row,
                error_concern_ids,
                proven_equivalence_allowed=proven_equivalence_allowed,
            )
        ]
        if unreconciled_ids:
            errors.append(
                "ECON-CONFLICT: label "
                f"{label.strip()} rows {', '.join(row_ids)} have divergent tuple "
                f"elements: {', '.join(divergent_elements)}; unreconciled rows: "
                f"{', '.join(unreconciled_ids)}"
            )

    for rows in groups.values():
        label = rows[0]["label"]
        assert isinstance(label, str)
        execution_rows = [
            row
            for row in rows
            if isinstance(row.get("roles"), list)
            and any(role in {"execution", "persistence"} for role in row["roles"])
        ]
        for row in rows:
            if row.get("authority_disposition") != "raw_signal_only":
                continue
            colliding_rows = [
                execution_row["id"]
                for execution_row in execution_rows
                if execution_row is not row
            ]
            if colliding_rows:
                errors.append(
                    "ECON-RAW-LABEL: label "
                    f"{label.strip()} raw-signal row {row['id']} shares its label "
                    "with execution/persistence rows "
                    f"{', '.join(colliding_rows)}"
                )

        # A dropped version field is a defect the map must surface, but the map
        # cannot fix source. Like ECON-CONFLICT, it is acknowledged (not cleared)
        # by a reconciliation pointing at an error-severity concern on the row.
        def _acknowledged(candidate: Mapping[str, Any]) -> bool:
            return _valid_economic_reconciliation(
                candidate, error_concern_ids, proven_equivalence_allowed=False
            )

        for row in rows:
            if row.get("version_handling") == "dropped" and not _acknowledged(row):
                errors.append(
                    "ECON-VERSION-DROPPED: label "
                    f"{label.strip()} row {row['id']} has version_handling=dropped "
                    "without an error-severity concern reconciliation"
                )
            if (
                row.get("formula_version") is not None
                and row.get("version_handling") == "emitted"
                and not _acknowledged(row)
            ):
                handled_downstream = any(
                    consumer_row.get("version_handling")
                    in {"accepted", "rejected", "retired"}
                    for consumer_row in rows
                    if consumer_row is not row
                )
                dropped_consumers = [
                    consumer_row["id"]
                    for consumer_row in rows
                    if consumer_row is not row
                    and consumer_row.get("version_handling")
                    not in {"accepted", "rejected", "retired"}
                    and not _acknowledged(consumer_row)
                ]
                if dropped_consumers and not handled_downstream:
                    errors.append(
                        "ECON-VERSION-DROPPED: label "
                        f"{label.strip()} emitter {row['id']} has consumers without "
                        "accepted/rejected/retired version handling: "
                        f"{', '.join(dropped_consumers)}"
                    )

        has_execution_or_persistence = bool(execution_rows)
        has_canonical = any(
            row.get("authority_disposition") == "canonical" for row in rows
        )
        has_concern = any(
            _economic_reconciliation_status(row) == "concern" for row in rows
        )
        if has_execution_or_persistence and not has_canonical and not has_concern:
            row_ids = ", ".join(row["id"] for row in rows)
            errors.append(
                "ECON-NO-CANONICAL: label "
                f"{label.strip()} execution/persistence rows {row_ids} have no "
                "canonical owner or concern reconciliation"
            )

    metrics = data.get("metrics")
    if not isinstance(metrics, Mapping):
        return errors + ["ECON-METRICS: metrics must be an object"]

    tracked_labels = {
        label.strip().casefold()
        for row in matrix
        if isinstance(row, Mapping)
        and _is_nonempty_string(label := row.get("label"))
        and isinstance(label, str)
    }
    expected_metrics = {
        "economic_calculation_sites": len(matrix),
        "economic_labels_tracked": len(tracked_labels),
        "economic_conflicts_open": sum(
            1
            for normalized_label in divergent_groups
            if any(
                _economic_reconciliation_status(row) == "concern"
                for row in groups[normalized_label]
            )
        ),
    }
    for metric_name, expected in expected_metrics.items():
        actual = metrics.get(metric_name)
        if not isinstance(actual, int) or isinstance(actual, bool):
            errors.append(f"ECON-METRICS: metrics.{metric_name} must be an integer")
        elif actual != expected:
            errors.append(
                f"ECON-METRICS: metrics.{metric_name}={actual} but expected {expected}"
            )
    return errors


def require_valid_manifest(data: Mapping[str, Any]) -> None:
    errors = validate_manifest(data)
    if errors:
        rendered = "\n".join(f"- {error}" for error in errors)
        raise ManifestValidationError(f"manifest validation failed:\n{rendered}")


def _scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def markdown_cell(value: Any) -> str:
    if isinstance(value, list):
        text = "; ".join(_scalar_text(item) for item in value)
    else:
        text = _scalar_text(value)
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
    )


def _columns_for(section: str, records: Sequence[Mapping[str, Any]]) -> list[str]:
    discovered: list[str] = []
    for record in records:
        for key in record:
            if key not in discovered:
                discovered.append(key)
    if section == "components":
        # These fields are a downstream routing contract. Keep missing columns visible
        # instead of silently producing an apparently complete but unusable registry.
        preferred = list(PREFERRED_COLUMNS[section])
    else:
        preferred = [
            key for key in PREFERRED_COLUMNS.get(section, ()) if key in discovered
        ]
    return preferred + [key for key in discovered if key not in preferred]


def render_section(section: str, value: Any) -> str:
    count = len(value) if isinstance(value, list) else 1
    lines = [f"## {section} ({count})", ""]
    if isinstance(value, list) and section in PREFERRED_COLUMNS:
        if not all(isinstance(item, dict) for item in value):
            raise ManifestValidationError(f"{section} mixes object and scalar rows")
        columns = _columns_for(section, value)
        if not columns:
            columns = list(PREFERRED_COLUMNS.get(section, ()))
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("|" + "|".join("---" for _ in columns) + "|")
        for record in value:
            lines.append(
                "| "
                + " | ".join(markdown_cell(record.get(column)) for column in columns)
                + " |"
            )
    elif (
        isinstance(value, list)
        and value
        and all(isinstance(item, dict) for item in value)
    ):
        columns = _columns_for(section, value)
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("|" + "|".join("---" for _ in columns) + "|")
        for record in value:
            lines.append(
                "| "
                + " | ".join(markdown_cell(record.get(column)) for column in columns)
                + " |"
            )
    elif isinstance(value, list) and any(isinstance(item, dict) for item in value):
        # Foreign co-owned arrays may have schemas mapcodebase cannot normalize. Keep
        # their exact JSON instead of making the compact-view render a hard failure.
        lines.extend(
            ("```json", json.dumps(value, ensure_ascii=False, indent=2), "```")
        )
    elif isinstance(value, list):
        if value:
            lines.extend(f"- {markdown_cell(item)}" for item in value)
        else:
            lines.append("_None._")
    elif isinstance(value, dict):
        lines.extend(
            ("```json", json.dumps(value, ensure_ascii=False, indent=2), "```")
        )
    else:
        lines.append(markdown_cell(value))
    return "\n".join(lines)


def render_manifest(data: Mapping[str, Any], source_name: str = "manifest.json") -> str:
    require_valid_manifest(data)
    section_names = [key for key, value in data.items() if isinstance(value, list)]
    ordered_sections = [
        name for name in PREFERRED_SECTION_ORDER if name in section_names
    ]
    ordered_sections.extend(
        name for name in section_names if name not in ordered_sections
    )
    metadata = {key: value for key, value in data.items() if key not in section_names}

    blocks = [
        "# Architecture Manifest",
        "",
        f"> Generated compact view of `{source_name}`. Do not edit this file directly.",
        "> Nested metadata stays JSON; homogeneous record arrays render as Markdown "
        "tables so keys are paid once per section.",
        "",
        "## Run metadata",
        "",
        "```json",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        "```",
    ]
    for section in ordered_sections:
        blocks.extend(("", render_section(section, data[section])))
    return "\n".join(blocks).rstrip() + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _parse_filters(raw_filters: Iterable[str]) -> list[tuple[str, str]]:
    filters: list[tuple[str, str]] = []
    for raw_filter in raw_filters:
        if "=" not in raw_filter:
            raise ManifestValidationError(f"filter must be FIELD=VALUE: {raw_filter}")
        field, value = raw_filter.split("=", 1)
        if not field:
            raise ManifestValidationError(f"filter field is empty: {raw_filter}")
        filters.append((field, value))
    return filters


def _filter_records(value: Any, filters: Sequence[tuple[str, str]]) -> Any:
    if not filters:
        return value
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ManifestValidationError("--where requires an array of objects")
    return [
        item
        for item in value
        if all(_scalar_text(item.get(field)) == expected for field, expected in filters)
    ]


def _manifest_section(args: argparse.Namespace) -> str:
    data = load_manifest(args.manifest)
    if args.section not in data:
        raise ManifestValidationError(f"manifest section not found: {args.section}")
    value = _filter_records(data[args.section], _parse_filters(args.where))
    if args.format == "markdown":
        return render_section(args.section, value) + "\n"
    if args.format == "json":
        indent = None if args.compact else 2
        separators = (",", ":") if args.compact else None
        return (
            json.dumps(value, ensure_ascii=False, indent=indent, separators=separators)
            + "\n"
        )
    if not args.field:
        raise ManifestValidationError("--field is required with --format lines")
    records = _record_list({args.section: value}, args.section)
    missing = [
        index for index, record in enumerate(records) if args.field not in record
    ]
    if missing:
        raise ManifestValidationError(
            f"{args.section} rows missing field {args.field}: {missing}"
        )
    return "".join(f"{_scalar_text(record[args.field])}\n" for record in records)


def _declared_component_doc_paths(data: Mapping[str, Any]) -> set[str]:
    require_valid_manifest(data)
    components = _record_list(data, "components")
    return {record["doc_path"] for record in components}


def validate_component_inventory(
    data: Mapping[str, Any], components_dir: Path
) -> list[str]:
    """Compare manifest-tracked component docs with direct regular Markdown files."""
    declared_paths = _declared_component_doc_paths(data)
    actual_paths: set[str] = set()
    errors: list[str] = []

    if components_dir.is_symlink():
        errors.append(
            f"component docs directory must not be a symlink: {components_dir}"
        )
    elif not components_dir.is_dir():
        errors.append(f"component docs directory is missing: {components_dir}")
    else:
        for entry in sorted(components_dir.iterdir(), key=lambda item: item.name):
            relative_path = f"structured/components/{entry.name}"
            if entry.is_symlink():
                if entry.suffix == ".md":
                    errors.append(
                        f"component doc symlink is not allowed: {relative_path}"
                    )
                continue
            if entry.is_dir():
                errors.append(
                    f"nested component-doc directory is not allowed: {relative_path}"
                )
                continue
            if entry.suffix == ".md" and entry.is_file():
                actual_paths.add(relative_path)

    for missing_path in sorted(declared_paths - actual_paths):
        errors.append(f"missing declared component doc: {missing_path}")
    for untracked_path in sorted(actual_paths - declared_paths):
        errors.append(f"untracked component doc: {untracked_path}")
    return errors


def _parse_accessor_contract(text: str, label: str) -> dict[str, Any]:
    matches = list(ACCESSOR_CONTRACT_RE.finditer(text))
    marker_count = text.count(ACCESSOR_CONTRACT_PREFIX)
    if marker_count != 1 or len(matches) != 1:
        if marker_count:
            raise ManifestValidationError(
                f"{label} must contain exactly one correctly formatted "
                "accessor contract comment"
            )
        raise ManifestValidationError(f"{label} missing accessor contract comment")

    try:
        contract = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(
            f"{label} has invalid accessor contract JSON: {exc.msg}"
        ) from exc
    if not isinstance(contract, dict):
        raise ManifestValidationError(
            f"{label} accessor contract must be a JSON object"
        )
    return contract


def parse_accessor_contract(path: Path) -> dict[str, Any]:
    """Load one accessor's exact machine-readable contract comment."""
    return _parse_accessor_contract(path.read_text(encoding="utf-8"), path.name)


def _accessor_contract_expectations(data: Mapping[str, Any]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for field in ("skill_version", "git_hash", "freshness_status"):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            raise ManifestValidationError(
                f"manifest {field} must be a nonempty string for accessor validation"
            )
        expected[field] = value
    expected["component_doc_paths_source"] = COMPONENT_DOC_PATHS_SOURCE
    return expected


def validate_accessors(
    data: Mapping[str, Any],
    access_guide_path: Path,
    index_path: Path,
    primer_path: Path,
) -> list[str]:
    """Verify accessor provenance contracts and access-guide routing instructions."""
    errors = validate_manifest(data)
    if errors:
        return errors
    try:
        expected = _accessor_contract_expectations(data)
    except ManifestValidationError as exc:
        return [str(exc)]

    access_guide_text: str | None = None
    for label, path in (
        ("access-guide.md", access_guide_path),
        ("INDEX.md", index_path),
        ("primer.md", primer_path),
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{label} cannot be read: {exc}")
            continue
        if label == "access-guide.md":
            access_guide_text = text
        try:
            contract = _parse_accessor_contract(text, label)
        except ManifestValidationError as exc:
            errors.append(str(exc))
            continue
        for field, expected_value in expected.items():
            actual_value = contract.get(field)
            if actual_value != expected_value:
                errors.append(
                    f"{label} accessor contract {field} does not match "
                    f"manifest: {actual_value!r} != {expected_value!r}"
                )

    if access_guide_text is not None:
        if not COMPONENT_PATH_COMMAND_RE.search(access_guide_text):
            errors.append(
                "access-guide.md missing bounded component-path command: "
                "manifest-section components --format lines --field doc_path"
            )
        if not COMPONENT_DOC_PATH_AUTHORITY_RE.search(access_guide_text):
            errors.append(
                "access-guide.md missing components[].doc_path authority phrase"
            )
    return errors


def extract_markdown_section(path: Path, heading: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((index for index, line in enumerate(lines) if line == heading), None)
    if start is None:
        raise ManifestValidationError(f"heading not found in {path}: {heading}")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end]).rstrip() + "\n"


def extract_flow(path: Path, flow_id: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        match = FLOW_HEADER_RE.match(line)
        if match and match.group(1) == flow_id:
            start = index
            break
    if start is None:
        raise ManifestValidationError(f"flow not found in {path}: {flow_id}")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("### FLOW:") or lines[index].startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end]).rstrip() + "\n"


def validate_flows(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    errors: list[str] = []
    try:
        index_text = extract_markdown_section(path, "## Current Flow Index")
    except ManifestValidationError as exc:
        return [str(exc)]

    index_ids: list[str] = []
    for line in index_text.splitlines():
        if not line.startswith("|"):
            continue
        first_cell = line.split("|", 2)[1].strip()
        if (
            first_cell.casefold() in {"id", "flow id"}
            or not first_cell
            or set(first_cell) <= {"-", ":"}
        ):
            continue
        index_ids.append(first_cell)

    detail_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = FLOW_HEADER_RE.match(line)
        if match:
            detail_starts.append((index, match.group(1)))

    for label, identifiers in (
        ("index", index_ids),
        ("detail", [item[1] for item in detail_starts]),
    ):
        seen: set[str] = set()
        for identifier in identifiers:
            if identifier in seen:
                errors.append(f"duplicate {label} flow ID: {identifier}")
            seen.add(identifier)

    index_set = set(index_ids)
    detail_set = {identifier for _, identifier in detail_starts}
    for identifier in sorted(index_set - detail_set):
        errors.append(f"flow indexed without detailed record: {identifier}")
    for identifier in sorted(detail_set - index_set):
        errors.append(f"detailed flow missing from index: {identifier}")

    for position, (start, identifier) in enumerate(detail_starts):
        end = (
            detail_starts[position + 1][0]
            if position + 1 < len(detail_starts)
            else len(lines)
        )
        record_lines = lines[start + 1 : end]
        fence_indexes = [
            index
            for index, line in enumerate(record_lines)
            if line.strip().startswith("```")
        ]
        if len(fence_indexes) < 2:
            errors.append(f"flow {identifier} missing fenced detail block")
            field_lines: list[str] = []
        else:
            field_lines = record_lines[fence_indexes[0] + 1 : fence_indexes[1]]
        present = {
            field
            for field in FLOW_REQUIRED_FIELDS
            if any(line.startswith(f"{field}:") for line in field_lines)
        }
        for field in FLOW_REQUIRED_FIELDS:
            if field not in present:
                errors.append(f"flow {identifier} missing field: {field}")

    for line in lines:
        if line.startswith("## ") and any(
            pattern.search(line) for pattern in CHRONOLOGY_HEADING_PATTERNS
        ):
            errors.append(f"chronological flow heading is forbidden: {line}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render and query bounded mapcodebase architecture views."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render-manifest", help="render compact manifest.md")
    render.add_argument(
        "--manifest", type=Path, default=Path(".architecture/manifest.json")
    )
    render.add_argument(
        "--output", type=Path, default=Path(".architecture/manifest.md")
    )

    validate = subparsers.add_parser(
        "validate-manifest", help="validate manifest IDs and counts"
    )
    validate.add_argument(
        "--manifest", type=Path, default=Path(".architecture/manifest.json")
    )

    economic_authority = subparsers.add_parser(
        "validate-economic-authority",
        help="validate monetary calculation-site semantics and authority",
    )
    economic_authority.add_argument(
        "--manifest", type=Path, default=Path(".architecture/manifest.json")
    )

    component_inventory = subparsers.add_parser(
        "validate-component-inventory",
        help="validate manifest-tracked component docs against the active directory",
    )
    component_inventory.add_argument(
        "--manifest", type=Path, default=Path(".architecture/manifest.json")
    )
    component_inventory.add_argument(
        "--components-dir",
        type=Path,
        default=Path(".architecture/structured/components"),
    )

    accessor_validation = subparsers.add_parser(
        "validate-accessors",
        help="validate accessor provenance contracts and routing instructions",
    )
    accessor_validation.add_argument(
        "--manifest", type=Path, default=Path(".architecture/manifest.json")
    )
    accessor_validation.add_argument(
        "--access-guide", type=Path, default=Path(".architecture/access-guide.md")
    )
    accessor_validation.add_argument(
        "--index", type=Path, default=Path(".architecture/INDEX.md")
    )
    accessor_validation.add_argument(
        "--primer", type=Path, default=Path(".architecture/primer.md")
    )

    validate_flow_records = subparsers.add_parser(
        "validate-flows", help="validate flow-index/detail bijection and record schema"
    )
    validate_flow_records.add_argument(
        "--flows", type=Path, default=Path(".architecture/structured/flows.md")
    )

    section = subparsers.add_parser(
        "manifest-section", help="emit one top-level manifest section"
    )
    section.add_argument("section")
    section.add_argument(
        "--manifest", type=Path, default=Path(".architecture/manifest.json")
    )
    section.add_argument(
        "--format", choices=("markdown", "json", "lines"), default="markdown"
    )
    section.add_argument("--field", help="field emitted by --format lines")
    section.add_argument("--where", action="append", default=[], metavar="FIELD=VALUE")
    section.add_argument("--compact", action="store_true", help="compact JSON output")

    flow_index = subparsers.add_parser(
        "flow-index", help="emit only the Current Flow Index"
    )
    flow_index.add_argument(
        "--flows", type=Path, default=Path(".architecture/structured/flows.md")
    )

    flow = subparsers.add_parser("flow", help="emit one detailed flow record")
    flow.add_argument("flow_id")
    flow.add_argument(
        "--flows", type=Path, default=Path(".architecture/structured/flows.md")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "render-manifest":
            data = load_manifest(args.manifest)
            atomic_write(args.output, render_manifest(data, args.manifest.name))
            return 0
        if args.command == "validate-manifest":
            data = load_manifest(args.manifest)
            errors = validate_manifest(data)
            if errors:
                raise ManifestValidationError("\n".join(errors))
            print("manifest valid")
            return 0
        if args.command == "validate-economic-authority":
            data = load_manifest(args.manifest)
            errors = validate_economic_authority(data)
            if errors:
                raise ManifestValidationError("\n".join(errors))
            print("economic authority valid")
            return 0
        if args.command == "validate-component-inventory":
            data = load_manifest(args.manifest)
            errors = validate_component_inventory(data, args.components_dir)
            if errors:
                raise ManifestValidationError("\n".join(errors))
            print("component inventory valid")
            return 0
        if args.command == "validate-accessors":
            data = load_manifest(args.manifest)
            errors = validate_accessors(
                data,
                args.access_guide,
                args.index,
                args.primer,
            )
            if errors:
                raise ManifestValidationError("\n".join(errors))
            print("accessors valid")
            return 0
        if args.command == "validate-flows":
            errors = validate_flows(args.flows)
            if errors:
                raise ManifestValidationError("\n".join(errors))
            print("flows valid")
            return 0
        if args.command == "manifest-section":
            sys.stdout.write(_manifest_section(args))
            return 0
        if args.command == "flow-index":
            sys.stdout.write(
                extract_markdown_section(args.flows, "## Current Flow Index")
            )
            return 0
        if args.command == "flow":
            sys.stdout.write(extract_flow(args.flows, args.flow_id))
            return 0
    except (ManifestValidationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
