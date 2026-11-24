# Architecture Access Guide

> How to read `.architecture/` without loading everything.
<!-- mapcodebase-accessor-contract: {"skill_version":"{SKILL_VERSION}","git_hash":"{GIT_HASH}","freshness_status":"{freshness_status}","component_doc_paths_source":"components[].doc_path"} -->

## Targeted Manifest Access

`manifest.json` is the machine-compatibility record. `manifest.md` is its generated,
compact agent view. Do not load the full JSON to obtain one homogeneous array.

```bash
# Render or refresh the compact view after manifest.json changes.
python3 <skill-dir>/scripts/architecture_access.py render-manifest

# Read only components[] as a Markdown table.
python3 <skill-dir>/scripts/architecture_access.py manifest-section components

# Return only manifest-tracked component document paths (never glob the directory).
python3 <skill-dir>/scripts/architecture_access.py manifest-section components --format lines --field doc_path

# Read the bounded Current Flow Index.
python3 <skill-dir>/scripts/architecture_access.py flow-index

# Read one detailed flow record.
python3 <skill-dir>/scripts/architecture_access.py flow {flow-id}

# Filter when a task needs one architecture status.
python3 <skill-dir>/scripts/architecture_access.py manifest-section components --where architecture_status=active_primary
```

Replace `components` with `concerns`, `findings`, `patterns`, `hazards`,
`boundary_contracts`, `verification_items`, or `answerability_tests` to retrieve that
section alone. Treat `components[].doc_path` as the tracked component set; files merely
present under `structured/components/` may be legacy or otherwise untracked. **Never
derive active component membership from a glob.** Directory enumeration is an
exact-set integrity check only.

## General Primer

1. Read [primer.md](primer.md).
2. Use [INDEX.md](INDEX.md) only for navigation and component selection.
3. Escalate to [overview.md](overview.md) if the primer does not explain the system shape well enough.

## Actionable Concerns

1. Read [concerns.md](concerns.md).
2. Jump from each concern to its cited component docs, patterns, findings, or hazards.
3. Use this path when deciding what to fix first, what to debate, or what to validate against the cited source.

## Plan Evaluation

1. Start with [primer.md](primer.md).
2. Query the `components` manifest section and match the plan's paths, modules, and keywords to its `key_files`, `intent_tags`, and `doc_path` columns.
3. Read [concerns.md](concerns.md) if the plan touches areas with known architectural debt or drift.
4. Read only the matched `components[].doc_path` files; do not glob [structured/components/](structured/components/).
5. Read [structured/cross-references.md](structured/cross-references.md) if the plan changes contracts, routes, or boundaries.
6. Query the [flow index](structured/flows.md#current-flow-index) when the plan crosses component boundaries or introduces a new flow; then load only matching detailed flow records.

## Component Deep Dive

1. Start with [primer.md](primer.md).
2. Read [overview.md](overview.md) for full-system context.
3. Read [concerns.md](concerns.md) if the component appears in the fix-first rollup.
4. Read the selected manifest-tracked component doc.
5. Read the [flow index](structured/flows.md#current-flow-index) only if the component participates in a larger multi-step flow, then retrieve an individual record with the bounded commands above.
