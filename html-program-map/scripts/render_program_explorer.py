#!/usr/bin/env python3
"""Render the workflow-driven program explorer from architecture and source ledgers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def class_id(record: dict[str, Any]) -> str:
    return f"{record['file']}:{record['line']}:{record['qualified_name']}"


def matches_component(record: dict[str, Any], component: dict[str, Any]) -> list[str]:
    roles: set[str] = set()
    for rule in component.get("class_rules", []):
        file_matches = not rule.get("file") or re.search(rule["file"], record["file"])
        name = record.get("qualified_name") or record.get("name") or ""
        name_matches = not rule.get("name") or re.search(rule["name"], name)
        if file_matches and name_matches:
            roles.add(rule.get("role", "member"))
    return sorted(roles)


def prepare_classes(model: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    classes: list[dict[str, Any]] = []
    for source in ledger["source_scan"]["classes"]:
        record = dict(source)
        record["id"] = class_id(record)
        record["memberships"] = [
            {"component": component["id"], "roles": roles}
            for component in model["components"]
            if (roles := matches_component(record, component))
        ]
        classes.append(record)
    return classes


def class_ref_resolver(classes: list[dict[str, Any]]) -> Any:
    """Map a class reference from the symbol ledger onto the class ledger's id.

    The two ledgers spell function-local classes differently (`func().Cls` vs `func.Cls`),
    but both agree on file and line, so references are matched by location. A location
    shared by two classes is ambiguous and left unmapped.
    """
    by_location: dict[tuple[str, int], str | None] = {}
    for record in classes:
        key = (record["file"], int(record["line"]))
        by_location[key] = None if key in by_location else record["id"]

    def resolve(ref: str) -> str:
        file, _, rest = ref.partition(":")
        line, _, _ = rest.partition(":")
        if not line.isdigit():
            return ref
        return by_location.get((file, int(line))) or ref

    return resolve


def compact_call(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "expression": call["expression"],
        "name": call["name"],
        "line": call["line"],
        "resolved": call.get("resolved", []),
    }


def prepare_symbols(model: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for source in ledger["source_scan"]["symbols"]:
        resolved = [call for call in source["calls"] if call.get("resolved")]
        unresolved = [call for call in source["calls"] if not call.get("resolved")]
        display_calls = [*resolved, *unresolved[: max(0, 18 - len(resolved))]]
        memberships = [
            {"component": component["id"], "roles": roles}
            for component in model["components"]
            if (roles := matches_component(source, component))
        ]
        symbols.append(
            {
                "id": source["id"],
                "language": source["language"],
                "name": source["name"],
                "qualified_name": source["qualified_name"],
                "kind": source["kind"],
                "file": source["file"],
                "line": source["line"],
                "end_line": source["end_line"],
                "category": source["category"],
                "owner_class": source["owner_class"],
                "parent_symbol": source["parent_symbol"],
                "decorators": source["decorators"],
                "parameters": source["parameters"],
                "returns_annotation": source["returns_annotation"],
                "doc": source["doc"],
                "calls": [compact_call(call) for call in display_calls],
                "call_count": len(source["calls"]),
                "resolved_call_count": len(resolved),
                "conditions": source["conditions"][:30],
                "condition_count": len(source["conditions"]),
                "mutations": source["mutations"][:30],
                "mutation_count": len(source["mutations"]),
                "returns": source["returns"][:16],
                "raises": source["raises"][:16],
                "called_by": source["called_by"][:40],
                "called_by_count": len(source["called_by"]),
                "memberships": memberships,
            }
        )
    return symbols


def prepare_modules(
    model: dict[str, Any], symbol_ledger: dict[str, Any], symbols: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    symbols_by_file: dict[str, list[str]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_file[symbol["file"]].append(symbol["id"])
    modules: list[dict[str, Any]] = []
    for source in symbol_ledger["source_scan"]["modules"]:
        record = {
            "id": source["id"],
            "name": source["name"],
            "file": source["file"],
            "category": source["category"],
            "symbols": symbols_by_file.get(source["file"], []),
            "classes": source["classes"],
        }
        record["memberships"] = [
            {"component": component["id"], "roles": roles}
            for component in model["components"]
            if (roles := matches_component(record, component))
        ]
        modules.append(record)
    return modules


def enrich_model(
    model: dict[str, Any],
    classes: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    class_symbols: dict[str, list[str]] = defaultdict(list)
    for symbol in symbols:
        if symbol["owner_class"]:
            class_symbols[symbol["owner_class"]].append(symbol["id"])
    for record in classes:
        record["symbols"] = class_symbols.get(record["id"], [])

    for component in model["components"]:
        component["classes"] = [
            record["id"]
            for record in classes
            if any(item["component"] == component["id"] for item in record["memberships"])
        ]
        component["symbols"] = [
            record["id"]
            for record in symbols
            if any(item["component"] == component["id"] for item in record["memberships"])
        ]
        component["modules"] = [
            record["id"]
            for record in modules
            if any(item["component"] == component["id"] for item in record["memberships"])
        ]
    return model


def validate(
    model: dict[str, Any], classes: list[dict[str, Any]], symbols: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    ids = {
        "system": {item["id"] for item in model["systems"]},
        "subsystem": {item["id"] for item in model["subsystems"]},
        "component": {item["id"] for item in model["components"]},
        "class": {item["id"] for item in classes},
        "symbol": {item["id"] for item in symbols},
    }
    workflow_ids = {item["id"] for item in model.get("workflows", [])}
    guide = model.get("guide", {})
    for section in ("operating_loop", "boundaries", "start_here"):
        for entry in guide.get(section, []):
            target = entry.get("target", {})
            target_type = target.get("type")
            target_id = target.get("id")
            if target_type == "workflow":
                if target_id not in workflow_ids:
                    errors.append(f"guide {section} references missing workflow id: {target_id}")
                elif "step" in target:
                    workflow = next(item for item in model["workflows"] if item["id"] == target_id)
                    if not 0 <= target["step"] < len(workflow["steps"]):
                        errors.append(
                            f"guide {section} references invalid workflow step: "
                            f"{target_id}[{target['step']}]"
                        )
            elif target_type not in ids or target_id not in ids[target_type]:
                errors.append(
                    f"guide {section} references missing {target_type or 'unknown'} id: {target_id}"
                )
    for workflow in model.get("workflows", []):
        touched = workflow["touched"]
        for plural, level in (
            ("systems", "system"),
            ("subsystems", "subsystem"),
            ("components", "component"),
            ("classes", "class"),
            ("symbols", "symbol"),
        ):
            missing = set(touched.get(plural, [])) - ids[level]
            if missing:
                errors.append(f"workflow {workflow['id']} has missing {level} ids: {sorted(missing)}")
        for step in workflow["steps"]:
            if step["symbol"] not in ids["symbol"]:
                errors.append(f"workflow step {step['id']} references missing symbol")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--class-ledger", type=Path, required=True)
    parser.add_argument("--symbol-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--architecture-read-count", type=int, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    model = json.loads(args.model.read_text(encoding="utf-8"))
    class_ledger = json.loads(args.class_ledger.read_text(encoding="utf-8"))
    symbol_ledger = json.loads(args.symbol_ledger.read_text(encoding="utf-8"))
    classes = prepare_classes(model, class_ledger)
    symbols = prepare_symbols(model, symbol_ledger)
    resolve_class = class_ref_resolver(classes)
    for symbol in symbols:
        if symbol["owner_class"]:
            symbol["owner_class"] = resolve_class(symbol["owner_class"])
        for call in symbol["calls"]:
            for target in call["resolved"]:
                if target.get("kind") == "class":
                    target["id"] = resolve_class(target["id"])
    modules = prepare_modules(model, symbol_ledger, symbols)
    for module in modules:
        module["classes"] = [resolve_class(ref) for ref in module["classes"]]
    model = enrich_model(model, classes, symbols, modules)
    errors = validate(model, classes, symbols)
    if errors and args.strict:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    payload = {
        "model": model,
        "classes": classes,
        "symbols": symbols,
        "modules": modules,
        "coverage": {
            "architecture_files_read": args.architecture_read_count,
            "architecture_files_total": class_ledger["architecture"]["file_count"],
            "architecture_lines": class_ledger["architecture"]["line_count"],
            "architecture_hash": class_ledger["architecture"]["corpus_sha256"],
            "class_count": len(classes),
            "variable_count": sum(len(item["variables"]) for item in classes),
            "python_symbol_count": symbol_ledger["source_scan"]["symbol_count"],
            "runtime_symbol_count": sum(item["category"] == "runtime" for item in symbols),
            "call_site_count": symbol_ledger["source_scan"]["call_count"],
            "resolved_call_sites": symbol_ledger["source_scan"]["resolved_call_sites"],
            "component_count": len(model["components"]),
            "subsystem_count": len(model["subsystems"]),
            "workflow_count": len(model.get("workflows", [])),
            "class_inventory_hash": class_ledger["inventory_sha256"],
            "symbol_inventory_hash": symbol_ledger["inventory_sha256"],
            "symbol_limits": symbol_ledger["limits"],
            "validation_errors": errors,
        },
    }
    template = (Path(__file__).resolve().parent.parent / "assets" / "program-explorer.html").read_text(
        encoding="utf-8"
    )
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    rendered = template.replace("__TITLE__", model["project"]["title"]).replace("__DATA__", data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "architecture": f"{args.architecture_read_count}/{class_ledger['architecture']['file_count']}",
                "classes": len(classes),
                "variables": payload["coverage"]["variable_count"],
                "python_symbols": len(symbols),
                "runtime_symbols": payload["coverage"]["runtime_symbol_count"],
                "call_sites": payload["coverage"]["call_site_count"],
                "workflows": payload["coverage"]["workflow_count"],
                "errors": errors,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
