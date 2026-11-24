# mapcodebase Design Principles (v4)

*Normative principles for this skill. Changes must preserve the source-backed
contracts and reading paths below; document any intentional exception alongside
the change so reviewers can assess its effect.*

## What mapcodebase is FOR

`.architecture/` exists so that an agent (or human) with zero context can answer
questions about the system **cheaper and more reliably than by reading source** —
and knows exactly when it must fall back to source instead. It is a *pre-computed
index over agentic search*, not a book. Every design decision serves one test:

> **The Question Test**: for the questions agents actually ask mid-task, does the
> corpus produce a correct answer faster than grepping — and does it *refuse* to
> answer (pointing at source) rather than mislead when it can't?

A corpus that describes what a gateway *is* without explaining its boundary
fields, emission conditions, and absent-field semantics cannot answer a caller's
contract questions. Descriptions are inferable from source;
**contracts, invariants, and absence-semantics are the non-inferable payload** that
justifies the corpus existing at all.

## The evidence constraint

Prefer localization-oriented, contract-shaped, citation-anchored documentation
to generic summaries. Validate its usefulness with source-checked questions for
the target codebase rather than assuming that more prose improves the map.

## Principles

### P1 — Answer "ins and outs", not "about"
Every component doc must let a reader operate at the component's boundaries without
opening source: entry points, exit points, and for each cross-runtime/cross-process
edge a **field-level contract** (field, producer condition, transport forwarding,
consumer acceptance, persistence behavior, absent-semantics, evidence anchor).
Responsibilities prose is a header, not the payload.

### P2 — Every load-bearing claim carries an anchor
`file:line` (or file+symbol) on anything an agent would act on. An unanchored claim
is unauditable and un-drift-checkable. Anchors are pointers, not copies: **never
paste code bodies** into docs — bodies drift fastest; signatures by anchor are fine.

### P3 — Non-inferable content only
Do not write what an agent gets by reading the file it's already about to open
(one-file summaries, restated signatures, README duplication). Do write what no
single file shows: cross-file invariants, absence-semantics, config precedence,
hidden couplings, authoritative-side of a contract, "looks like the entry point
but isn't", why-this-shape decisions.

### P4 — Unverified is debt, not decoration
An "unverified" annotation on a **boundary contract or invariant** is a tracked,
machine-readable debt item (`manifest.verification_items[]` with owner files + concrete
verification TODO), never a carry-forward prose note. Debt on high-value boundaries
downgrades `status` to `partial`; an untracked note can conceal a dropped-field bug
across multiple scan generations.
Resolution rule: next scan must either verify (cheap — usually one file read) or
escalate; it may not re-emit the note unchanged.

### P5 — Deterministic freshness, declared trust
Each generated doc records the commit hash and the **source files it derives from**
(`derived_from[]`). Staleness is then exact and free:
`git diff --name-only <hash>` ∩ `derived_from`. No LLM judgment in the freshness
path. Every doc's header states the precedence rule explicitly: *"if files in
`derived_from` changed since `<hash>`, trust source over this doc."* Readers
allocate trust badly without explicit precedence. The three accessor docs are
regenerated from current manifest metadata on every run; a file's existence is not
evidence of freshness.

### P6 — Progressive disclosure; the router stays tiny
INDEX.md routes; it never carries payload. Question→doc navigation, component
table, freshness banner — nothing else. Payload docs are sized for on-demand
loading under reader context budgets: keep each component doc comfortably below
~25K tokens and select only the documents needed for the current question.
Large registries must expose bounded section access; "machine-readable" never means
an agent should load the whole machine record into context.

### P7 — Functional validation, not aesthetic review
A run isn't done when the docs are written; it's done when the docs pass **coverage
probes**: a fixed panel of realistic agent questions (per project + a standard set:
"what does absence of field X mean at boundary Y?", "which file implements Z?",
"what breaks if I change W?") answered from the corpus alone and spot-checked
against source. Failing probes are gaps → either fixed this run or recorded as
`verification_items[]` debt. Coverage probes form the functional QA gate.

### P8 — Serve the consumers' actual read paths
The corpus has machine consumers with parsed contracts, including
`html-program-map` and any reader of `manifest.json`. Preserve these contracts:
- `manifest.json` keeps `schema_version`, `git_hash` (short), `head_git_hash`,
  `freshness_status` ∈ {fresh, caution, stale}, `access_paths`, `components[]`
  with `key_files`/`intent_tags`/`doc_path`.
- `manifest.md` is a deterministic compact view of that JSON contract for agent
  consumption: nested metadata stays JSON, homogeneous arrays become Markdown
  tables, and the bundled accessor emits one named section at a time. Never ask an
  agent to read the full JSON merely to obtain `components[]` or another array.
- `components[].doc_path` is the sole live component-membership source. Directory
  enumeration is only an exact-set integrity check; a mismatch is non-success, and
  unknown extras remain pending explicit reconciliation rather than silent deletion.
- Regeneration **preserves foreign manifest sections** (`audit`, `freshness` nested
  block) — other tools may co-own the manifest. Use read-modify-write and populate
  `freshness.map_git_hash` without overwriting their metadata.
- Component docs keep **descriptive, stable filenames** and keyword-rich headings
  so downstream tools can match task text to relevant documentation.
- Regenerating docs changes their hashes. Record regeneration so downstream
  readers can refresh any pinned evidence references.
- Economic authority is independent of freshness authority: the same public monetary
  label must have the same price/fee/depth/time semantics or carry an error Concern.
  A display value that drives selection, thresholds, or operator judgement is
  decision-grade; raw signals keep distinct names and documentation never exempts a
  divergent metric from reconciliation.

### P9 — Structure-first, per-page grounding
The planner commits the page tree first; each parallel explorer fills its page from
its assigned files only. Bounds subagent context, parallelizes cleanly, and prevents
unfocused whole-repository summaries.

### P10 — The corpus admits what it doesn't know
Coverage has edges. The corpus states its exclusions, its unresolved debt, and the
classes of question it cannot answer (e.g., external data formats consumed by hooks
unless those formats were explicitly mapped). A reader who
can see the edge of the map doesn't fall off it.

### P11 — Encode for the shape of the data
Use JSON where nesting, types, or machine mutation matter. Use Markdown tables for
homogeneous record sets so column names are paid once, not once per row. Use lists
for scalar collections and structured blocks for ordered or branching behavior.
Flows therefore get a compact searchable index plus full per-flow records; flattening
steps and branches into giant table cells fails the Question Test. Generated views
must be field-complete, deterministic, validated for duplicate IDs/count drift, and
derived from the machine record rather than maintained as a second hand-edited source.
The JSON record remains authoritative for exact types and round-trip fidelity.

### P12 — Economic authority is not freshness authority
The same public monetary label implies the same price, fee, depth, time, and executable
quantity semantics—or an error Concern. A displayed value is decision-grade when it
drives selection, thresholds, or operator judgement. Documentation never exempts a
split authority, and a raw signal keeps a distinct public name rather than occupying an
executable label.

## Anti-goals

- Not a narrative book about the system. (Prose beyond orientation headers is suspect.)
- Not a substitute for source at the frontier of change — freshness rules must push
  readers to source when drift touches their question.
- Not a place for code bodies, secrets, or generated-artifact archaeology.
- Not append-only: docs that restate the inferable get deleted, not preserved.
