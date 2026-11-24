#!/usr/bin/env python3
"""Build deterministic architecture-source and class-declaration ledgers.

This script inventories evidence. It does not claim that a person or model has
read the files, and it does not infer component membership.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCANNED_SUFFIXES = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx"}
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
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "venv",
}
JS_CLASS_RE = re.compile(
    r"(?m)^[ \t]*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?"
    r"class\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([^\s{]+))?[^\n{]*\{"
)
JS_FIELD_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|readonly|static|declare|abstract)\s+)*"
    r"([A-Za-z_$][\w$]*)\s*(?:[!?])?\s*(?::\s*([^=;\n]+))?\s*(?:=|;)"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def logical_line_count(payload: bytes) -> int:
    if not payload:
        return 0
    return payload.count(b"\n") + (0 if payload.endswith(b"\n") else 1)


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


def iter_source_files(root: Path) -> Iterable[Path]:
    git_result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=False,
        capture_output=True,
    )
    if git_result.returncode == 0:
        paths = []
        for raw_path in git_result.stdout.split(b"\0"):
            if not raw_path:
                continue
            relative = Path(raw_path.decode("utf-8"))
            path = root / relative
            if (
                path.is_file()
                and path.suffix.lower() in SCANNED_SUFFIXES
                and not any(
                    part in EXCLUDED_PARTS or part.startswith(".venv")
                    for part in relative.parts
                )
            ):
                paths.append(path)
        yield from sorted(paths)
        return

    paths: list[Path] = []
    for directory, child_directories, filenames in os.walk(root):
        child_directories[:] = sorted(
            name
            for name in child_directories
            if name not in EXCLUDED_PARTS and not name.startswith(".venv")
        )
        base = Path(directory)
        for filename in sorted(filenames):
            path = base / filename
            if path.suffix.lower() in SCANNED_SUFFIXES:
                paths.append(path)
    yield from sorted(paths)


def expression_text(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):
        return None


def target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in target_names(item)]
    return []


class InstanceVariableVisitor(ast.NodeVisitor):
    """Collect statically visible self/cls fields without entering child classes."""

    def __init__(self) -> None:
        self.variables: dict[tuple[str, str], dict[str, Any]] = {}
        self.function_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _record(self, target: ast.AST, annotation: ast.AST | None = None) -> None:
        if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name):
            return
        owner = target.value.id
        if owner not in {"self", "cls"}:
            return
        kind = "instance" if owner == "self" else "class-runtime"
        key = (kind, target.attr)
        self.variables.setdefault(
            key,
            {
                "name": target.attr,
                "kind": kind,
                "line": target.lineno,
                "annotation": expression_text(annotation),
                "assigned_in": self.function_stack[-1] if self.function_stack else None,
            },
        )

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            self._record(target)
        self.generic_visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        self._record(node.target, node.annotation)
        if node.value is not None:
            self.generic_visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        self._record(node.target)
        self.generic_visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in {"self", "cls"}
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            owner = node.args[0].id
            kind = "instance-dynamic" if owner == "self" else "class-runtime-dynamic"
            key = (kind, node.args[1].value)
            self.variables.setdefault(
                key,
                {
                    "name": node.args[1].value,
                    "kind": kind,
                    "line": node.lineno,
                    "annotation": None,
                    "assigned_in": self.function_stack[-1] if self.function_stack else None,
                },
            )
        self.generic_visit(node)


def python_classes(path: Path, root: Path) -> list[dict[str, Any]]:
    relative = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative, type_comments=True)
    records: list[dict[str, Any]] = []

    def walk(body: list[ast.stmt], parents: tuple[str, ...] = ()) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(node.body, (*parents, f"{node.name}()"))
                continue
            if not isinstance(node, ast.ClassDef):
                nested_statements = [
                    child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt)
                ]
                if nested_statements:
                    walk(nested_statements, parents)
                continue
            qualified_name = ".".join((*parents, node.name))
            variables: dict[tuple[str, str], dict[str, Any]] = {}
            properties: list[dict[str, Any]] = []
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    variables[("class-field", statement.target.id)] = {
                        "name": statement.target.id,
                        "kind": "class-field",
                        "line": statement.lineno,
                        "annotation": expression_text(statement.annotation),
                        "assigned_in": None,
                    }
                elif isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        for name in target_names(target):
                            variables.setdefault(
                                ("class-variable", name),
                                {
                                    "name": name,
                                    "kind": "class-variable",
                                    "line": statement.lineno,
                                    "annotation": None,
                                    "assigned_in": None,
                                },
                            )
                elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decorator_names = {expression_text(item) for item in statement.decorator_list}
                    if "property" in decorator_names:
                        properties.append({"name": statement.name, "line": statement.lineno})

            instance_visitor = InstanceVariableVisitor()
            for statement in node.body:
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    instance_visitor.visit(statement)
            variables.update(instance_visitor.variables)
            records.append(
                {
                    "language": "python",
                    "name": node.name,
                    "qualified_name": qualified_name,
                    "file": relative,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "category": source_category(relative, root),
                    "bases": [expression_text(base) for base in node.bases],
                    "decorators": [expression_text(item) for item in node.decorator_list],
                    "variables": sorted(
                        variables.values(), key=lambda item: (item["name"], item["kind"], item["line"])
                    ),
                    "properties": sorted(properties, key=lambda item: (item["name"], item["line"])),
                }
            )
            walk(node.body, (*parents, node.name))

    walk(tree.body)
    return records


def find_balanced_block(source: str, opening_brace: int) -> tuple[int, int]:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening_brace, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return opening_brace, index
    return opening_brace, len(source) - 1


def javascript_classes(path: Path, root: Path) -> list[dict[str, Any]]:
    relative = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    for match in JS_CLASS_RE.finditer(source):
        opening_brace = source.find("{", match.start())
        _, closing_brace = find_balanced_block(source, opening_brace)
        body = source[opening_brace + 1 : closing_brace]
        line = source.count("\n", 0, match.start()) + 1
        end_line = source.count("\n", 0, closing_brace) + 1
        variables = []
        for field in JS_FIELD_RE.finditer(body):
            field_line = line + body.count("\n", 0, field.start())
            variables.append(
                {
                    "name": field.group(1),
                    "kind": "class-field",
                    "line": field_line,
                    "annotation": field.group(2).strip() if field.group(2) else None,
                    "assigned_in": None,
                }
            )
        records.append(
            {
                "language": "typescript" if path.suffix in {".ts", ".tsx"} else "javascript",
                "name": match.group(1),
                "qualified_name": match.group(1),
                "file": relative,
                "line": line,
                "end_line": end_line,
                "category": source_category(relative, root),
                "bases": [match.group(2)] if match.group(2) else [],
                "decorators": [],
                "variables": sorted(variables, key=lambda item: (item["name"], item["line"])),
                "properties": [],
            }
        )
    return records


def architecture_inventory(root: Path) -> dict[str, Any]:
    architecture_root = root / ".architecture"
    files: list[dict[str, Any]] = []
    if architecture_root.is_dir():
        for path in sorted(item for item in architecture_root.rglob("*") if item.is_file()):
            payload = path.read_bytes()
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": len(payload),
                    "lines": logical_line_count(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
    digest_payload = "\n".join(f"{item['path']}\0{item['sha256']}" for item in files).encode()
    return {
        "root": ".architecture",
        "file_count": len(files),
        "line_count": sum(item["lines"] for item in files),
        "byte_count": sum(item["bytes"] for item in files),
        "corpus_sha256": sha256_bytes(digest_payload),
        "files": files,
    }


def build_inventory(root: Path) -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    scanned_files: list[str] = []
    parse_failures: list[dict[str, str]] = []
    for path in iter_source_files(root):
        relative = path.relative_to(root).as_posix()
        scanned_files.append(relative)
        try:
            if path.suffix.lower() in {".py", ".pyi"}:
                classes.extend(python_classes(path, root))
            else:
                classes.extend(javascript_classes(path, root))
        except (SyntaxError, UnicodeDecodeError) as error:
            parse_failures.append({"file": relative, "error": str(error)})
    classes.sort(key=lambda item: (item["file"], item["line"], item["qualified_name"]))
    class_digest_payload = json.dumps(classes, sort_keys=True, separators=(",", ":")).encode()
    architecture = architecture_inventory(root)
    stable_payload = json.dumps(
        {
            "architecture_corpus_sha256": architecture["corpus_sha256"],
            "class_records_sha256": sha256_bytes(class_digest_payload),
            "scanned_files": scanned_files,
            "parse_failures": parse_failures,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "inventory_sha256": sha256_bytes(stable_payload),
        "architecture": architecture,
        "source_scan": {
            "suffixes": sorted(SCANNED_SUFFIXES),
            "excluded_parts": sorted(EXCLUDED_PARTS),
            "files_scanned": len(scanned_files),
            "class_count": len(classes),
            "classes_by_category": dict(sorted(Counter(item["category"] for item in classes).items())),
            "classes_by_language": dict(sorted(Counter(item["language"] for item in classes).items())),
            "parse_failures": parse_failures,
            "classes": classes,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path, help="Project containing .architecture and source")
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout")
    parser.add_argument("--check", type=Path, help="Compare stable inventory hash with an existing ledger")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    inventory = build_inventory(root)
    if args.check:
        previous = json.loads(args.check.read_text(encoding="utf-8"))
        if previous.get("inventory_sha256") != inventory["inventory_sha256"]:
            print("inventory drift detected", file=sys.stderr)
            return 1
        print(f"inventory matches {inventory['inventory_sha256']}")
        return 0
    serialized = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
