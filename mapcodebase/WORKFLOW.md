# Architecture Production and Consumption

Run `/mapcodebase` from a repository root to produce a source-backed
`.architecture/` corpus. It discovers entry points, data and control flows,
dependencies, and contracts; writes component docs; verifies claims; and records
hazards, patterns, findings, concerns, and verification debt.

`manifest.json` is the machine contract. Its schema, stable IDs, component paths,
provenance, metrics, freshness, and foreign metadata must survive updates.
`manifest.md` is a deterministic compact view, never a second hand-edited source.
Use `scripts/architecture_access.py` to retrieve one manifest section or flow.

Start reading at `primer.md`, use `INDEX.md` for navigation and `access-guide.md`
for task-specific paths, then open only the needed component and flow records.
Use `concerns.md` to decide what to fix first; verify its evidence before changing
source. A codebase without monetary calculations records an empty economic matrix.

Run `/html-program-map` after mapping to create the interactive HTML explorer in
`.reports/`. It combines the corpus with source class/callable inventories and
authored workflows. The page must preserve evidence and show stale or unresolved
claims explicitly. Other tools may consume the same manifest independently.

After source changes, run `/mapcodebase` incrementally, validate the updated
corpus, then refresh the HTML explorer. Keep internal discovery outputs durable
for recovery and keep writers isolated until final normalization and validation.
