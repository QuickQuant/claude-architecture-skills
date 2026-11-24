#!/usr/bin/env python3
"""Build a deterministic Python callable, parameter-use, mutation, and call ledger.

This is a static evidence boundary. It records syntax visible to Python's AST;
it does not claim runtime dispatch, reflection, monkey patches, or dynamic calls.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXCLUDED_PARTS = {
    ".architecture",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".reports",
    ".ruff_cache",
    ".tox",
    ".venv",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "venv",
}
MUTATING_METHODS = {
    "add",
    "append",
    "clear",
    "discard",
    "extend",
    "insert",
    "pop",
    "remove",
    "setdefault",
    "sort",
    "update",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def source_category(relative_path: str, root: Path) -> str:
    if relative_path.startswith("frontend/src/"):
        return "frontend"
    if relative_path.startswith("tests/"):
        return "test"
    if relative_path.startswith("scripts/"):
        return "tooling"
    if relative_path.startswith(("app/", "src/", "lib/")):
        return "runtime"
    parts = Path(relative_path).parts
    if len(parts) > 1 and (root / parts[0] / "__init__.py").is_file():
        return "runtime"
    return "root-support"


def iter_python_files(root: Path) -> Iterable[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Git source enumeration is required for the symbol ledger")
    paths: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(raw_path.decode("utf-8"))
        path = root / relative
        if (
            path.is_file()
            and path.suffix.lower() in {".py", ".pyi"}
            and not any(part in EXCLUDED_PARTS or part.startswith(".venv") for part in relative.parts)
        ):
            paths.append(path)
    yield from sorted(paths)


def expression_text(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):
        return None


def target_texts(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.Tuple, ast.List)):
        return [item for child in node.elts for item in target_texts(child)]
    text = expression_text(node)
    return [text] if text else []


def parameter_records(arguments: ast.arguments) -> list[dict[str, Any]]:
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(arguments.defaults)) + list(
        arguments.defaults
    )
    records: list[dict[str, Any]] = []
    for index, (argument, default) in enumerate(zip(positional, defaults)):
        records.append(
            {
                "name": argument.arg,
                "kind": "positional-only" if index < len(arguments.posonlyargs) else "positional",
                "annotation": expression_text(argument.annotation),
                "default": expression_text(default),
            }
        )
    if arguments.vararg:
        records.append(
            {
                "name": arguments.vararg.arg,
                "kind": "var-positional",
                "annotation": expression_text(arguments.vararg.annotation),
                "default": None,
            }
        )
    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        records.append(
            {
                "name": argument.arg,
                "kind": "keyword-only",
                "annotation": expression_text(argument.annotation),
                "default": expression_text(default),
            }
        )
    if arguments.kwarg:
        records.append(
            {
                "name": arguments.kwarg.arg,
                "kind": "var-keyword",
                "annotation": expression_text(arguments.kwarg.annotation),
                "default": None,
            }
        )
    return records


class ParameterUseFacts(ast.NodeVisitor):
    """Recover bounded, source-level evidence for how callable inputs are read."""

    def __init__(self, parameter_names: set[str]) -> None:
        self.parameter_names = parameter_names
        self.uses: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.parents: list[ast.AST] = []

    def visit(self, node: ast.AST) -> Any:
        self.parents.append(node)
        try:
            return super().visit(node)
        finally:
            self.parents.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        return

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if not isinstance(node.ctx, ast.Load) or node.id not in self.parameter_names:
            return
        parent = self.parents[-2] if len(self.parents) > 1 else node
        context = "read"
        expression = expression_text(parent) or node.id
        if isinstance(parent, ast.Attribute):
            context = "attribute-read"
        elif isinstance(parent, ast.Subscript):
            context = "index-or-key-read"
        elif isinstance(parent, ast.keyword):
            context = "argument"
        elif isinstance(parent, ast.Call):
            context = "call-argument"
        elif isinstance(parent, (ast.If, ast.While, ast.Compare, ast.IfExp, ast.Assert)):
            context = "condition"
        elif isinstance(parent, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
            context = "calculation"
        elif isinstance(parent, ast.Return):
            context = "return"
        elif isinstance(parent, ast.Dict):
            context = "record-field"
            for key, value in zip(parent.keys, parent.values):
                if value is node:
                    key_text = expression_text(key)
                    expression = f"{key_text}: {node.id}" if key_text else node.id
                    break
        expression = " ".join(expression.split())
        if len(expression) > 180:
            expression = expression[:177] + "..."
        record = {"line": node.lineno, "context": context, "expression": expression}
        if record not in self.uses[node.id] and len(self.uses[node.id]) < 40:
            self.uses[node.id].append(record)


class FunctionFacts(ast.NodeVisitor):
    """Inspect one callable without folding nested declarations into its facts."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.conditions: list[dict[str, Any]] = []
        self.mutations: list[dict[str, Any]] = []
        self.returns: list[dict[str, Any]] = []
        self.raises: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        return

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        expression = expression_text(node.func) or "<dynamic>"
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else expression
        )
        self.calls.append(
            {
                "expression": expression,
                "name": name,
                "line": node.lineno,
                "column": node.col_offset,
                "resolved": [],
            }
        )
        if isinstance(node.func, ast.Attribute) and node.func.attr in MUTATING_METHODS:
            target = expression_text(node.func.value)
            if target:
                self.mutations.append(
                    {"target": target, "operation": node.func.attr, "line": node.lineno}
                )
        self.generic_visit(node)

    def _condition(self, kind: str, node: ast.AST, line: int) -> None:
        self.conditions.append({"kind": kind, "expression": expression_text(node), "line": line})

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self._condition("if", node.test, node.lineno)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self._condition("while", node.test, node.lineno)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        self._condition("conditional-expression", node.test, node.lineno)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        self._condition("assert", node.test, node.lineno)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
        self._condition("match", node.subject, node.lineno)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            for text in target_texts(target):
                self.mutations.append({"target": text, "operation": "assign", "line": node.lineno})
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        for text in target_texts(node.target):
            self.mutations.append({"target": text, "operation": "assign", "line": node.lineno})
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        for text in target_texts(node.target):
            self.mutations.append(
                {"target": text, "operation": type(node.op).__name__.lower(), "line": node.lineno}
            )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
        self.returns.append({"expression": expression_text(node.value), "line": node.lineno})
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:  # noqa: N802
        self.raises.append({"expression": expression_text(node.exc), "line": node.lineno})
        self.generic_visit(node)


class DeclarationVisitor(ast.NodeVisitor):
    def __init__(self, relative: str, root: Path) -> None:
        self.relative = relative
        self.category = source_category(relative, root)
        self.stack: list[dict[str, Any]] = []
        self.symbols: list[dict[str, Any]] = []
        self.classes: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        qualified = ".".join([*(item["name"] for item in self.stack), node.name])
        class_record = {
            "name": node.name,
            "qualified_name": qualified,
            "line": node.lineno,
            "id": f"{self.relative}:{node.lineno}:{qualified}",
        }
        self.classes.append(class_record)
        self.stack.append({"kind": "class", **class_record})
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool) -> None:
        qualified = ".".join([*(item["name"] for item in self.stack), node.name])
        parent = self.stack[-1] if self.stack else None
        owner_class = next(
            (item for item in reversed(self.stack) if item["kind"] == "class"), None
        )
        if parent and parent["kind"] == "class":
            kind = "async-method" if is_async else "method"
        elif parent:
            kind = "async-local-function" if is_async else "local-function"
        else:
            kind = "async-function" if is_async else "function"
        parameters = parameter_records(node.args)
        facts = FunctionFacts()
        parameter_uses = ParameterUseFacts({item["name"] for item in parameters})
        for statement in node.body:
            facts.visit(statement)
            parameter_uses.visit(statement)
        for parameter in parameters:
            parameter["uses"] = sorted(
                parameter_uses.uses.get(parameter["name"], []),
                key=lambda item: (item["line"], item["context"], item["expression"]),
            )
        docstring = ast.get_docstring(node, clean=True)
        record = {
            "id": f"{self.relative}:{node.lineno}:{qualified}",
            "language": "python",
            "name": node.name,
            "qualified_name": qualified,
            "kind": kind,
            "file": self.relative,
            "line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "category": self.category,
            "owner_class": owner_class["id"] if owner_class else None,
            "owner_class_name": owner_class["qualified_name"] if owner_class else None,
            "parent_symbol": parent["id"] if parent and parent["kind"] == "function" else None,
            "decorators": [expression_text(item) for item in node.decorator_list],
            "parameters": parameters,
            "returns_annotation": expression_text(node.returns),
            "doc": docstring.splitlines()[0] if docstring else None,
            "calls": sorted(facts.calls, key=lambda item: (item["line"], item["column"], item["expression"])),
            "conditions": sorted(facts.conditions, key=lambda item: (item["line"], item["kind"])),
            "mutations": sorted(facts.mutations, key=lambda item: (item["line"], item["target"], item["operation"])),
            "returns": sorted(facts.returns, key=lambda item: item["line"]),
            "raises": sorted(facts.raises, key=lambda item: item["line"]),
            "called_by": [],
        }
        self.symbols.append(record)
        self.stack.append({"kind": "function", "name": node.name, "id": record["id"]})
        self.generic_visit(node)
        self.stack.pop()


def parse_python_file(path: Path, root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    relative = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative, type_comments=True)
    visitor = DeclarationVisitor(relative, root)
    visitor.visit(tree)
    return visitor.symbols, visitor.classes


def annotation_class_names(annotation: str | None) -> set[str]:
    if not annotation:
        return set()
    return set(__import__("re").findall(r"\b[A-Z][A-Za-z0-9_]*\b", annotation))


def resolve_calls(symbols: list[dict[str, Any]], classes: list[dict[str, Any]]) -> None:
    symbols_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    methods_by_owner_name: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    classes_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_name[symbol["name"]].append(symbol)
        if symbol["owner_class_name"]:
            methods_by_owner_name[(symbol["owner_class_name"], symbol["name"])].append(symbol)
    for class_record in classes:
        classes_by_name[class_record["name"]].append(class_record)

    callers_by_symbol: dict[str, set[str]] = defaultdict(set)
    for symbol in symbols:
        parameter_types = {
            parameter["name"]: annotation_class_names(parameter["annotation"])
            for parameter in symbol["parameters"]
        }
        for call in symbol["calls"]:
            expression = call["expression"]
            candidates: list[dict[str, Any]] = []
            if expression.startswith(("self.", "cls.")) and symbol["owner_class_name"]:
                candidates.extend(
                    methods_by_owner_name[(symbol["owner_class_name"], call["name"])]
                )
            elif "." in expression:
                receiver = expression.rsplit(".", 1)[0]
                receiver_leaf = receiver.split(".")[-1]
                for class_name in parameter_types.get(receiver_leaf, set()):
                    for owner_name in {
                        item["qualified_name"] for item in classes_by_name.get(class_name, [])
                    }:
                        candidates.extend(methods_by_owner_name[(owner_name, call["name"])])
                for class_record in classes_by_name.get(receiver_leaf, []):
                    candidates.extend(
                        methods_by_owner_name[(class_record["qualified_name"], call["name"])]
                    )
            else:
                named = symbols_by_name.get(call["name"], [])
                same_file = [item for item in named if item["file"] == symbol["file"]]
                candidates.extend(same_file or named)

            for class_record in classes_by_name.get(call["name"], []):
                candidates.append({"kind": "class", **class_record, "file": class_record.get("file")})

            unique: dict[tuple[str, str], dict[str, Any]] = {}
            for candidate in candidates:
                kind = candidate.get("kind", "symbol")
                candidate_id = candidate["id"]
                unique[(kind, candidate_id)] = {
                    "kind": "class" if kind == "class" else "symbol",
                    "id": candidate_id,
                    "qualified_name": candidate["qualified_name"],
                    "file": candidate.get("file", symbol["file"]),
                    "line": candidate["line"],
                }
            call["resolved"] = sorted(
                unique.values(), key=lambda item: (item["kind"], item["file"], item["line"])
            )[:12]
            for target in call["resolved"]:
                if target["kind"] == "symbol":
                    callers_by_symbol[target["id"]].add(symbol["id"])

    for symbol in symbols:
        symbol["called_by"] = sorted(callers_by_symbol.get(symbol["id"], set()))


def build_inventory(root: Path) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    scanned_files: list[str] = []
    failures: list[dict[str, str]] = []
    for path in iter_python_files(root):
        relative = path.relative_to(root).as_posix()
        scanned_files.append(relative)
        try:
            file_symbols, file_classes = parse_python_file(path, root)
            for class_record in file_classes:
                class_record["file"] = relative
            symbols.extend(file_symbols)
            classes.extend(file_classes)
        except (SyntaxError, UnicodeDecodeError) as error:
            failures.append({"file": relative, "error": str(error)})
    symbols.sort(key=lambda item: (item["file"], item["line"], item["qualified_name"]))
    classes.sort(key=lambda item: (item["file"], item["line"], item["qualified_name"]))
    resolve_calls(symbols, classes)
    modules: dict[str, dict[str, Any]] = {}
    for relative in scanned_files:
        modules[relative] = {
            "id": relative,
            "file": relative,
            "name": Path(relative).stem,
            "category": source_category(relative, root),
            "symbols": [],
            "classes": [],
        }
    for symbol in symbols:
        modules[symbol["file"]]["symbols"].append(symbol["id"])
    for class_record in classes:
        modules[class_record["file"]]["classes"].append(class_record["id"])

    stable = {
        "scanned_files": scanned_files,
        "parse_failures": failures,
        "symbols": symbols,
        "classes": classes,
    }
    stable_payload = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    call_count = sum(len(symbol["calls"]) for symbol in symbols)
    resolved_call_count = sum(
        bool(call["resolved"]) for symbol in symbols for call in symbol["calls"]
    )
    return {
        "schema_version": "2.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "inventory_sha256": sha256_bytes(stable_payload),
        "source_scan": {
            "boundary": "Git-tracked plus non-ignored untracked Python/Python-stub files",
            "files_scanned": len(scanned_files),
            "parse_failures": failures,
            "symbol_count": len(symbols),
            "symbol_count_by_kind": dict(sorted(Counter(item["kind"] for item in symbols).items())),
            "symbol_count_by_category": dict(
                sorted(Counter(item["category"] for item in symbols).items())
            ),
            "call_count": call_count,
            "resolved_call_sites": resolved_call_count,
            "classes": classes,
            "modules": list(modules.values()),
            "symbols": symbols,
        },
        "limits": [
            "Static call targets can be ambiguous or unresolved under dynamic dispatch.",
            "Parameter uses are syntactic reads; they do not prove ownership, copying, retention, or runtime frequency.",
            "Reflection, monkey patches, decorators, framework injection, and runtime-created callables are not proven.",
            "TypeScript/JavaScript callable coverage is not yet part of this exact AST boundary.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = build_inventory(args.project_root.resolve())
    if args.check:
        previous = json.loads(args.check.read_text(encoding="utf-8"))
        if previous.get("inventory_sha256") != inventory["inventory_sha256"]:
            print("symbol inventory drift detected", file=sys.stderr)
            return 1
        print(f"symbol inventory matches {inventory['inventory_sha256']}")
        return 0
    payload = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
