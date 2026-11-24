#!/usr/bin/env python3
"""Render every Economic Authority table in `.architecture/` from manifest.json.

The economic matrix is co-owned: `manifest.economic_authority_matrix` is the machine
record, and three generated views summarize it. Left alone, three writers produce three
different column sets and three different label vocabularies for the same rows — which is
exactly the failure the matrix exists to prevent.

This script makes the views deterministic:

  * `structured/cross-references.md` -> one `### <label>` group per normalized label,
    rendered as the template's full column set.
  * `structured/components/<id>.md`  -> a compact table of just that component's rows,
    plus the label-group disposition line.

Run after the manifest is written and after any component doc changes:

    python3 -B <skill-dir>/scripts/normalize_economic_views.py [--write]

Build the manifest first using mapcodebase/SKILL.md Phase 7.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO = Path.cwd()
ARCH = REPO / ".architecture"
MANIFEST = ARCH / "manifest.json"

GROUP_COLUMNS = (
    "ID", "Label", "Aliases", "Metric kind", "Roles", "Component", "Producer",
    "Consumers", "Price side", "Price source", "Depth basis", "Fees included",
    "Fee schedule", "Horizon source", "Annualization", "Day rounding", "Formula",
    "Formula version", "Version handling", "Authority disposition",
    "Reconciliation status", "Concern ID", "Reconciliation evidence", "Verified at git",
)

COMPONENT_COLUMNS = (
    "ID", "Label", "Roles", "Price side", "Depth basis", "Fees included",
    "Formula/version", "Authority disposition", "Reconciliation",
)


def cell(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return f"`{text}`" if text and " " not in text else text


def group_rows(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["label"].strip().casefold()].append(row)
    return dict(groups)


def render_group_table(rows: list[dict]) -> str:
    header = "| " + " | ".join(GROUP_COLUMNS) + " |"
    divider = "|" + "|".join(["----"] * len(GROUP_COLUMNS)) + "|"
    lines = [header, divider]
    for row in rows:
        recon = row["reconciliation"]
        lines.append("| " + " | ".join([
            cell(row["id"]), cell(row["label"]), cell(row["aliases"]),
            cell(row["metric_kind"]), cell(row["roles"]), cell(row["component"]),
            cell(row["producer"]), cell(row["consumers"]), cell(row["price_side"]),
            cell(row["price_source"]), cell(row["depth_basis"]), cell(row["fees_included"]),
            cell(row["fee_schedule"]), cell(row["horizon_source"]),
            cell(row["annualization"]), cell(row["day_rounding"]), cell(row["formula"]),
            cell(row["formula_version"]), cell(row["version_handling"]),
            cell(row["authority_disposition"]), cell(recon["status"]),
            cell(recon["concern_id"]), cell(recon["evidence"]), cell(row["verified_at_git"]),
        ]) + " |")
    return "\n".join(lines)


def disposition_line(rows: list[dict]) -> str:
    canonical = [row["id"] for row in rows
                 if row["authority_disposition"] == "canonical"]
    concerns = sorted({row["reconciliation"]["concern_id"] for row in rows
                       if row["reconciliation"]["status"] == "concern"
                       and row["reconciliation"]["concern_id"]})
    if canonical:
        return ("Disposition: canonical owner(s) " + ", ".join(f"`{cid}`" for cid in canonical)
                + (f"; open reconciliation concern(s) {', '.join(concerns)}" if concerns else ""))
    if concerns:
        return f"Disposition: none — {', '.join(concerns)}"
    return "Disposition: none registered (display-only or raw-signal rows)."


def render_component_table(rows: list[dict]) -> str:
    header = "| " + " | ".join(COMPONENT_COLUMNS) + " |"
    divider = "|" + "|".join(["----"] * len(COMPONENT_COLUMNS)) + "|"
    lines = [header, divider]
    for row in rows:
        recon = row["reconciliation"]
        lines.append("| " + " | ".join([
            cell(row["id"]), cell(row["label"]), cell(row["roles"]), cell(row["price_side"]),
            cell(row["depth_basis"]), cell(row["fees_included"]),
            cell(row["formula_version"] or row["formula"]),
            cell(row["authority_disposition"]),
            cell(f"{recon['status']} ({recon['concern_id']})"
                 if recon["concern_id"] else recon["status"]),
        ]) + " |")
    return "\n".join(lines)


def labels_touched(component: dict, rows: list[dict]) -> list[tuple[str, str, str]]:
    """(label, row id, owning component) for rows this component produces or consumes.

    Derived from `components[].key_files` intersecting each row's producer/consumer anchors —
    the manifest is the only source, so a component doc can never invent a label.
    """
    key_files = set(component.get("key_files", []))
    touched: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for row in rows:
        anchors = [row["producer"], *row["consumers"]]
        if any(anchor.rsplit(":", 1)[0] in key_files for anchor in anchors):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            touched.append((row["label"], row["id"], row["component"]))
    return touched


def no_rows_body(component: dict, rows: list[dict]) -> str:
    component_id = component["id"]
    touched = labels_touched(component, rows)
    lines = [
        f"`{component_id}` owns no rows in `manifest.economic_authority_matrix`.",
        "",
        "Monetary semantics are defined by the owning component for each label; this doc must "
        "not restate them. The authoritative tables are the label groups in "
        "[`structured/cross-references.md`](../cross-references.md#economic-authority-matrix).",
    ]
    if touched:
        lines += ["", "Labels this component produces or consumes:", ""]
        lines += ["| Label | Row | Owner |", "|-------|-----|-------|"]
        lines += [f"| {cell(label)} | {cell(row_id)} | {cell(owner)} |"
                  for label, row_id, owner in touched]
    return "\n".join(lines)


def replace_section(text: str, heading: str, body: str, stop_prefixes: tuple[str, ...]) -> str:
    """Replace `heading` .. next stop heading (exclusive) with heading + body."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return text
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if any(lines[i].startswith(prefix) for prefix in stop_prefixes):
            end = i
            break
    return "\n".join(lines[:start] + [heading, ""] + body.splitlines() + [""] + lines[end:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    rows = manifest["economic_authority_matrix"]
    groups = group_rows(rows)
    by_component: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_component[row["component"]].append(row)

    print(f"matrix rows: {len(rows)}  label groups: {len(groups)}  "
          f"components owning rows: {len(by_component)}")

    # 1. cross-references.md groups
    xref = ARCH / "structured/cross-references.md"
    if xref.exists():
        body = [
            "> One table per public monetary label group, rendered from "
            "`manifest.economic_authority_matrix`. Each row is a distinct calculation site.",
            "",
        ]
        for normalized, group in sorted(groups.items()):
            body.append(f"### {group[0]['label']}")
            body.append("")
            body.append(render_group_table(group))
            body.append("")
            body.append(disposition_line(group))
            body.append("")
        text = replace_section(xref.read_text(), "## Economic Authority Matrix",
                               "\n".join(body), ("## ",))
        if args.write:
            tmp = xref.with_suffix(".md.tmp")
            tmp.write_text(text)
            tmp.replace(xref)
        print(f"{'rewrote' if args.write else 'would rewrite'} {xref.name} "
              f"({len(groups)} label groups)")

    # 2. component docs — every doc that carries an Economic Authority section is rendered
    #    from the matrix, whether it owns rows or merely touches them. A component doc may
    #    never invent a label, and may not carry a table the machine record does not contain.
    changed = 0
    skipped_no_section = 0
    for component in manifest.get("components", []):
        slug = component.get("id")
        path = ARCH / "structured" / "components" / f"{slug}.md"
        if not path.exists():
            print(f"  SKIP (no doc): {slug}")
            continue
        text = path.read_text(encoding="utf-8")
        if "### Economic Authority" not in text:
            skipped_no_section += 1
            continue
        component_rows = by_component.get(slug, [])
        if component_rows:
            body = [render_component_table(component_rows), "",
                    disposition_line(component_rows)]
        else:
            body = [no_rows_body(component, rows)]
        updated = replace_section(text, "### Economic Authority", "\n".join(body),
                                  ("### ", "## "))
        if updated != text:
            changed += 1
            if args.write:
                tmp = path.with_suffix(".md.tmp")
                tmp.write_text(updated)
                tmp.replace(path)
    print(f"{'rewrote' if args.write else 'would rewrite'} {changed} component doc(s); "
          f"{skipped_no_section} carry no Economic Authority section")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
