---
name: mapcodebase
description: Map codebase architecture using parallel subagents. Generates high-level prose overview, low-level structured entry/exit/flow documentation, and an actionable concern rollup.
allowed-tools: Agent, Task, Read, Write, Glob, Grep, Bash, AskUserQuestion, TodoWrite, TaskCreate, TaskUpdate, TaskList, TaskGet
---

# Map Codebase Architecture

> **Skill version:** see `VERSION` (single line). This shared bundle omits the original changelog and test suite.

Dispatch parallel subagents to explore a codebase, then synthesize findings into two-tier architecture documentation: high-level prose for understanding, low-level structured notation for precision.

**Design principles:** `DESIGN-PRINCIPLES.md` (same directory) is normative — read it once per session before a full run. The short form: the corpus exists to answer agents' real questions cheaper than grep (the Question Test); contracts/invariants/absent-semantics are the payload, prose is a header; every load-bearing claim carries a `file:line` anchor; **unverified boundary claims are tracked debt, never carry-forward prose**; prefer verified boundary tables to generic summaries.

**Before running (Immediate Step 0):** Resolve `<skill-dir>` to this installed
`mapcodebase` folder and read its `VERSION`. Use the strongest available model for
orchestration and synthesis, **in a session whose model has a 1M-token context
window** (choose one with `/model`). Synthesis and diagnosis run in the main agent
from all discovery output (Phases 1-5) held in its own context; on a smaller window
the skill falls back to delegating the diagnosis or skipping the optional action
plan (see the context-pressure notes in Phase 6 and Phase 6e). Run the discovery prompts as parallel subagents when
available (Claude Code's Agent/Task tool, `subagent_type: "Explore"`); otherwise run
the same prompts sequentially. Record the actual synthesis and exploration models
in the manifest `model` field, and stamp SKILL_VERSION into generated output.
Commands run from the target repository root. Quote the resolved skill path if it
contains spaces; `<skill-dir>` is a placeholder, not a literal shell path.

**Terms used by the economic-authority checks:**
- *Economic authority*: the single calculation site whose semantics define what a
  public monetary label (APR, cost, P&L, fee, fill price, valuation) means. Every
  other site under that label is proven equivalent to it or is flagged.
- *Calculation site*: a place in source that computes or transforms a monetary
  quantity such that its price side, depth, fees, horizon, rounding, or formula
  could differ from another site's. A display copy is a consumer, not a site;
  rounding a finished number for display is not a site.
- *Executable economics*: the quantity a trader can actually realize after fees,
  depth at the target size, and the real horizon.

A codebase without monetary calculations records zero matrix rows and zero
economic counters after classifying the semantic sweep's non-monetary hits.

## Usage

```
/mapcodebase                    # Incremental update — re-explore changed files, merge into existing docs
/mapcodebase src/worker         # Map specific directory
/mapcodebase --focus flows      # Focus on data/control flows
/mapcodebase --focus api        # Focus on API surface
/mapcodebase --nuke-existing-docs             # DESTRUCTIVE: regenerate ALL docs from scratch (destroys manually-authored content)
```

## Argument Parsing

Parse the user's input after `/mapcodebase`:
- **No args**: TARGET_DIR = project root (cwd), UPDATE_MODE = true (incremental is default)
- **Path arg** (e.g. `src/worker`): TARGET_DIR = that path relative to cwd
- **`--focus <area>`**: Set FOCUS_MODE, still explore everything but emphasize that area in synthesis
- **`--nuke-existing-docs`**: Set NUKE_MODE — regenerate all docs from scratch. **This destroys manually-authored content** (migration notes, known bugs, feature flags, concurrency concerns, data flow diagrams). Use only for major version migrations or when existing docs are known to be fundamentally wrong. The Freshness Gate will confirm before proceeding.

## Freshness Gate (Required Preflight)

Before dispatching explorers, validate architecture freshness and migration state:

1. Resolve current git hash: `git rev-parse --short HEAD`
2. If `.architecture/manifest.json` exists, read:
   - `manifest.git_hash`
   - `manifest.schema_version`
   - `manifest.skill_version`
3. Check the required accessor layer:
   - `.architecture/primer.md`
   - `.architecture/access-guide.md`
   - `.architecture/INDEX.md`
   - the bounded `mapcodebase-accessor-contract` marker in all three files. It must
     match the manifest `skill_version`, `git_hash`, `freshness_status`, and
     `components[].doc_path` source declaration; file existence alone is not a
     freshness check.
4. Interpret the result:
   - **No manifest:** full scan required (no existing docs to update)
   - **Manifest schema < 2.0:** legacy output; full scan required
   - **Manifest present but required accessor artifacts missing:** legacy/incomplete output; full scan required
   - **Manifest schema = 2.0 but any accessor marker is absent, malformed, or disagrees
     with manifest metadata:** the accessor layer is stale; run an incremental whole-layer
     refresh even if the source git hash matches HEAD
   - **Manifest schema = 2.0, git hash matches HEAD, and all accessor markers match:** mapping is current for this commit
   - **Manifest schema = 2.0 and git hash differs from HEAD:** mapping is stale; run incremental update (default)
5. **Component inventory gate:** For an existing schema-2.0 manifest, run
   `validate-component-inventory` before dispatching explorers. If the direct component
   directory is not an exact mirror of the previous `components[].doc_path` set, STOP
   before source discovery. Report the exact missing/untracked paths and require an
   explicit reconciliation operation; do not spend a full map run merely to rediscover
   an already-known inventory mismatch.
6. **Full scan safety gate:** If `--nuke-existing-docs` was passed AND valid 3.x docs already exist, confirm with the user before proceeding:
   ```
   WARNING: --nuke-existing-docs will regenerate ALL architecture docs from scratch.
   This DESTROYS manually-authored content: migration notes, known bugs,
   feature flags, data flow diagrams, concurrency concerns.

   Existing docs: {N} component files, {lines} total lines

   Are you sure? Incremental update (default) preserves existing content.
   [Proceed with --nuke-existing-docs] [Switch to incremental update]
   ```
   If the user selects "Switch to incremental update", drop NUKE_MODE and proceed with UPDATE_MODE.
7. **Schema migration rule:** When upgrading from `v2.x` to `3.x`, incremental update creates new artifacts (primer.md, access-guide.md, manifest schema 2.0) while preserving existing component docs. This is safe — the v2.6 → 3.2 upgrade used incremental mode successfully. `--nuke-existing-docs` is never auto-triggered by schema version.

Always stamp output with: `Architecture verified at <HEAD>`.

## Model Selection & Run Resilience (Required Preflight)

### Check 1: Model Selection

Use the strongest model available for synthesis. Identify the available subagent
tool before dispatch. Select parallel discovery when supported; otherwise select
sequential discovery up front. Both modes must run all five prompts and persist
the same five outputs. Record whichever models actually ran in `manifest.model`.

### Check 2: Resume Existing Run

Check for an in-progress run file at `.architecture/.mapcodebase-progress.json`:

1. If the file exists AND `status` is `"in_progress"`:
   - Read the progress file
   - Show the user what phases are complete vs pending
   - Ask: "Resume from where the previous run left off, or start fresh?"
   - If resume: skip only phases with verified durable outputs, continue from the first incomplete phase
   - If fresh: delete the progress file and start from Phase 1
2. If the file doesn't exist or `status` is `"complete"`: proceed normally

### Progress File: `.architecture/.mapcodebase-progress.json`

**Write this file BEFORE Phase 1 starts. Update it AFTER each phase completes.** This is the crash-recovery mechanism.

```json
{
  "status": "in_progress",
  "started_at": "2026-03-22T19:00:00Z",
  "git_hash": "824613d",
  "mode": "full|update",
  "target_dir": "/path/to/repo",
  "skill_version": "{SKILL_VERSION}",
  "phases": {
    "phase_1_discovery":    { "status": "pending" },
    "phase_2_high_level":   { "status": "pending" },
    "phase_3_structured":   { "status": "pending" },
    "phase_4_verification": { "status": "pending" },
    "phase_5_patterns":     { "status": "pending" },
    "phase_6_findings":     { "status": "pending" },
    "phase_6f_verification": { "status": "pending" },
    "phase_7_manifest":     { "status": "pending" },
    "phase_8_visuals":      { "status": "pending" }
  },
  "phase_artifacts": {
    "phase_1_discovery": [
      ".architecture/.work/discovery/entry-points.md",
      ".architecture/.work/discovery/data-flow.md",
      ".architecture/.work/discovery/control-flow.md",
      ".architecture/.work/discovery/dependencies.md",
      ".architecture/.work/discovery/contracts.md"
    ]
  },
  "artifacts_written": []
}
```

**Phase lifecycle:**
1. Before starting a phase: set its status to `"in_progress"`, write the file
2. After completing a phase and writing its durable outputs: set status to `"complete"`, append user-facing artifact paths to `artifacts_written`, write the file
3. After ALL phases complete: set top-level `status` to `"complete"`

**On resume:** For each phase:
- `"complete"` → skip only if its durable outputs still exist on disk
- `"in_progress"` → phase was interrupted; re-run it from scratch (its artifacts may be partial)
- `"pending"` → not yet started; run normally

**Artifact verification on resume:** When resuming, stat-check all files in `artifacts_written` and `phase_artifacts` to confirm they actually exist. If any are missing, downgrade the owning phase back to `"pending"`.

**Cleanup:** When the full run completes successfully (manifest written, status `"complete"`), the progress file serves as a historical record. It is NOT deleted — it documents the last successful run for debugging.

## Output Structure

Two-tier architecture: **high-level** (prose, orientation) and **low-level** (structured, precise).

```
.architecture/
├── .mapcodebase-progress.json            # Session resilience: phase completion tracker
├── .work/                                # Internal durable workspace for resume/reload
│   └── discovery/
│       ├── entry-points.md               # Raw/slightly-normalized explorer output
│       ├── data-flow.md
│       ├── control-flow.md
│       ├── dependencies.md
│       └── contracts.md
├── manifest.json                         # Machine-compatibility record and co-owned state
├── manifest.md                           # Generated compact view: JSON metadata + Markdown tables
├── INDEX.md                              # Navigation hub: what to read for what
├── primer.md                             # ACCESSOR: small-context default entrypoint
├── access-guide.md                       # ACCESSOR: human-readable reading paths
├── overview.md                           # HIGH-LEVEL: prose system description
├── filesystem-map.md                     # HIGH-LEVEL: directory purposes
├── concerns.md                           # ANALYTICAL: actionable fix-first concern rollup
├── patterns.md                           # ANALYTICAL: cross-cutting pattern findings
├── findings.md                           # ANALYTICAL: opinionated architectural suggestions
│
├── structured/                           # LOW-LEVEL: machine-friendly precision
│   ├── entry-points.md                   # All entrances with types and destinations
│   ├── flows.md                          # Searchable current-flow index + detailed records
│   ├── cross-references.md               # Call graphs, data paths, hub files, Economic Authority Matrix
│   └── components/                       # Per-component deep dives
│       └── {component-name}.md           # Context chunk for one component
│
└── HUMAN_READ_ONLY_visuals/              # HTML diagrams for human readers
    ├── system-overview.html              # Box-and-arrow system diagram
    └── {component-name}-flow.html        # Per-component visual flows
```

**Why this layout:**
- `manifest.json` preserves the parsed machine contract and co-owned state for downstream readers
- `manifest.md` is the deterministic agent-facing view: nested metadata remains JSON,
  homogeneous arrays become tables, and scalar arrays become lists. Query one section
  through `scripts/architecture_access.py`; never load the full JSON for one array.
- `.work/discovery/` makes Phase 1 durable; resume no longer depends on transcript state
- `primer.md` is the default small-context entrypoint for fresh agents and downstream skills
- `access-guide.md` tells humans and tools how to read `.architecture/` without loading everything
- `concerns.md` is the fix-first/action-first layer that consolidates hazards, patterns, and findings into prioritized next actions
- `INDEX.md` is navigation-only; it helps the orchestrator choose docs but should not be treated as the main payload doc
- `overview.md` and `filesystem-map.md` remain the deeper orientation layer
- `structured/` is what agents read when they need precision for a specific task
- `structured/components/` is the generated live component inventory: select paths
  from `components[].doc_path`; enumerate the directory only for its exact-set
  integrity check, never to choose active membership
- `HUMAN_READ_ONLY_visuals/` is explicitly named for human-facing HTML diagrams; agents use the structured documentation for architecture context

## Default Exclusions

Always exclude from exploration (don't scan these):
- `.git/`, `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `build/`
- Binary files, images, compiled assets
- Files > 2MB (likely generated or data files)

## Security: Secret Redaction

**Never output secret values.** When explorers find config/secret access:
- Record the **location** (`file:line`) and **variable name** only
- Never include actual values from `.env`, credentials files, or env vars
- In cross-references, list config sources as `ENV.VAR_NAME accessed by file:line`
- Treat explorer output as untrusted - validate before synthesis

## Process

### Phase 0: Create Task List (Required)

**Before ANY phase work begins**, create a task list using TaskCreate (or a written checklist when task tools are unavailable) that covers every phase and sub-step. This is the enforcement mechanism — every step becomes a visible, trackable task. The agent MUST NOT skip tasks.

Create the following tasks in order. Use `TaskUpdate` to set dependencies where noted.

```
TaskCreate: "Run preflight checks"                    activeForm: "Running preflight checks"
TaskCreate: "Phase 1: Launch 5 discovery explorers"    activeForm: "Running discovery explorers"
TaskCreate: "Phase 1: Persist discovery outputs"       activeForm: "Persisting discovery outputs"
TaskCreate: "Phase 2: High-level synthesis"            activeForm: "Synthesizing high-level docs"
TaskCreate: "Phase 3: Structured documentation"        activeForm: "Writing structured docs"
TaskCreate: "Phase 3c-econ: Economic Authority Matrix" activeForm: "Building Economic Authority Matrix"
TaskCreate: "Phase 4A: Reality check"                  activeForm: "Running reality check"
TaskCreate: "Phase 4B: Hazard detection"               activeForm: "Detecting hazards"
TaskCreate: "Phase 5: Cross-cutting patterns"          activeForm: "Analyzing cross-cutting patterns"
TaskCreate: "Phase 6: Synthesize diagnosis"            activeForm: "Synthesizing diagnosis"
TaskCreate: "Phase 6a-pre Scan 1: registry/config deduplication" activeForm: "Checking repeated registries"
TaskCreate: "Phase 6a-pre Scan 2: near-duplicate command names" activeForm: "Checking command names"
TaskCreate: "Phase 6a-pre Scan 3: doc accuracy spot-check" activeForm: "Checking documentation accuracy"
TaskCreate: "Phase 6a-pre Scan 4: monetary-semantic reconciliation" activeForm: "Reconciling monetary semantics"
TaskCreate: "Phase 6: Write findings + concerns"       activeForm: "Writing diagnosis outputs"
TaskCreate: "Phase 6e: Draft action plan"              activeForm: "Drafting action plan"
TaskCreate: "Phase 6f: Verification debt + answerability" activeForm: "Resolving verification debt + answerability tests"
TaskCreate: "Phase 7: Write manifest + compact view"   activeForm: "Writing manifest views"
TaskCreate: "Phase 8: Human visuals"                   activeForm: "Generating visual diagrams"
TaskCreate: "Quality checks"                           activeForm: "Running quality checks"
```

**Rules:**
- Set each task to `in_progress` BEFORE starting the step
- Set each task to `completed` AFTER the step finishes and outputs are verified
- If a step is skipped (e.g., patterns skipped for <5 files), set it to `completed` with a note
- The four Phase 6a-pre scan tasks are individual — each must be independently started, executed, and completed
- Check `TaskList` (or the written checklist) after completing each phase to confirm progress and pick up the next task

This task list is the user's primary visibility into mapcodebase progress. It replaces scrolling through output to figure out what phase the run is in.

### Phase 0b: Delegation Safety (Required, before any writer dispatch)

Keep delegated writers isolated and generated views deterministic. These rules
apply to every writer, including sequential runs.

1. **One generator per registry payload.** Any table that mirrors a manifest array
   (`economic_authority_matrix[]`, `components[]`, `hazards[]`, `verification_items[]`, and the
   provenance header derived from `components[].key_files`) is RENDERED from that array, never authored
   by a writer. Writers supply the narrative around these tables, not their contents or their column sets.
   Run `scripts/normalize_economic_views.py` and `scripts/normalize_component_provenance.py` after all
   writers exit and before validating the corpus.
2. **Stage-then-replace, never delete-then-write.** Every delegated writer writes to `<target>.staged`,
   self-checks it, then `os.replace`s it onto the target. Deleting a target before composing its
   replacement is forbidden: `.architecture/` is gitignored by convention, so a writer that dies mid-compose
   destroys the previous corpus with no recovery.
3. **Cap concurrent heavy writers at 5.** More thrashes the sandbox helpers and makes the long tail
   unattributeable. Component-doc batches count as heavy writers.
4. **Presence before trust.** Wait for every writer to exit before counting component
   docs, normalizing views, validating inventory, or finalizing the manifest. Track
   every launched and resumed writer through the harness's completion handles; a
   partial process-name check is not proof of completion. When checking filesystem
   timestamps as a final cross-check, no generated document may be newer than the
   final manifest. If writer completion cannot be proved, do not finalize.
5. **Foreign processes need a cwd read.** Before claiming another process is touching this corpus, resolve
   `/proc/<pid>/cwd`. Relative paths in a command line are relative to *that* process's cwd, not yours.
   A false "concurrent run" alarm costs the operator a decision and costs the run its credibility.
6. **Authorship discipline for the orchestrator's own tooling.** Registry-shaped payloads are built by a
   re-runnable local generation script, validated before writing, and never patched by hand edit —
   a find/replace in a generated structure silently drops required fields.

### Phase 1: Discovery (Parallel Exploration)

**Discovery execution (choose before starting).** In Claude Code, dispatch the
five prompts through the Agent/Task tool with `subagent_type: "Explore"`, in
parallel when capacity allows. If subagents are unavailable, run the same five
prompts sequentially in the main agent. The source scope, output formats, and
durable recovery paths are identical in both modes.

Before committing to parallel mode, attempt one trivial Explore dispatch. If
unavailable, choose sequential execution before starting the five prompts.

- Read each prompt before running it and substitute `{TARGET_DIR}`.
- Keep runner stdout/log paths separate from deliverable paths; a completion log
  must never overwrite a discovery document.
- Each explorer owns its own output. Never overwrite another writer's output or
  terminate sibling explorers to recover one failed deliverable.
- If any prompt fails or times out, stop before Phase 2. Do not synthesize from
  partial discovery or overwrite the previous corpus. Preserve only `.work/`
  scratch and the progress record, report the failure, and restart discovery as
  a complete set when the cause has been resolved. Sequential mode is an initial
  execution choice, not a mid-run excuse to omit a failed prompt.

**Progress:** Set `phase_1_discovery` to `"in_progress"` before launching. Set it to `"complete"` only after ALL 5 prompts complete AND their outputs are written to `.architecture/.work/discovery/`.

Launch 5 Explore subagents in parallel when available, or execute these five prompts sequentially. Each gets the full prompt from `prompts/` with TARGET_DIR substituted.

```
# Parallel example; use the available Agent or Task tool:
Task(subagent_type="Explore", prompt=read("prompts/explore-entry-points.md").replace("{TARGET_DIR}", TARGET_DIR), description="Map entry points")
Task(subagent_type="Explore", prompt=read("prompts/explore-data-flow.md").replace("{TARGET_DIR}", TARGET_DIR), description="Map data flow")
Task(subagent_type="Explore", prompt=read("prompts/explore-control-flow.md").replace("{TARGET_DIR}", TARGET_DIR), description="Map control flow")
Task(subagent_type="Explore", prompt=read("prompts/explore-dependencies.md").replace("{TARGET_DIR}", TARGET_DIR), description="Map dependencies")
Task(subagent_type="Explore", prompt=read("prompts/explore-contracts.md").replace("{TARGET_DIR}", TARGET_DIR), description="Map contracts")
```

**Important:** Read each prompt file from `<skill-dir>/prompts/` before dispatching. The prompts contain output format instructions that agents need.

Wait for ALL 5 prompts to complete, then persist their outputs as durable recovery artifacts:

- `.architecture/.work/discovery/entry-points.md`
- `.architecture/.work/discovery/data-flow.md`
- `.architecture/.work/discovery/control-flow.md`
- `.architecture/.work/discovery/dependencies.md`
- `.architecture/.work/discovery/contracts.md`

These files may contain lightly normalized explorer output, but they must preserve the structured facts the later phases depend on. They are internal working files, not human-facing architecture docs.

Only after those 5 files exist on disk may `phase_1_discovery` be marked `"complete"`.

### Phase 2: High-Level Synthesis

**Progress:** Set `phase_2_high_level` to `"in_progress"` before starting. After writing primer.md, access-guide.md, overview.md, filesystem-map.md, and INDEX.md, add them to `artifacts_written` and set to `"complete"`.

#### Accessor Refresh Contract

Every run writes the complete accessor layer: `primer.md`, `access-guide.md`, and
`INDEX.md`. Render their body and marker from current run metadata; Phase 7 performs
a final whole-layer refresh from the completed manifest before validation. Never retain
an accessor merely because it already exists, including on a source-only incremental
update.

Using the combined outputs from all 5 prompts, write the high-level and accessor documents. On resume in a fresh session, reload the Phase 1 discovery files from `.architecture/.work/discovery/` before synthesizing.

#### 2a. primer.md

Write the small-context architecture entrypoint. Requirements:
- Keep it materially smaller than `overview.md`
- Include a one-paragraph system summary
- Surface `freshness_status` and a short trust note
- Highlight the 5-10 most important components
- Highlight the most important shared contracts and access boundaries
- Call out 3-7 non-obvious gotchas
- Reserve a short "Top Actionable Concerns" section. In a fresh full run this may be a temporary placeholder until Phase 6 concern synthesis finalizes it.
- Tell readers when to escalate to `overview.md`, the `flows.md` index, or component docs

Use template: `templates/primer.md`

#### 2b. access-guide.md

Write the human-readable reading recipe layer. Requirements:
- Define four reading paths: General Primer, Actionable Concerns, Plan Evaluation, Component Deep Dive
- Include the verbatim bounded-access commands from the template for one manifest
  section, tracked component paths, the flow index, and one detailed flow
- Keep it procedural and compact
- Make it consistent with `manifest.access_paths`
- Treat `INDEX.md` as navigation-only
- Treat `components[].doc_path` as authoritative; never tell readers to glob the
  component directory to determine the tracked set
- Carry the accessor-contract marker from the template with current manifest metadata.

Use template: `templates/access-guide.md`

#### 2c. overview.md

Write a prose document that explains the system to both humans and LLMs. Requirements:
- Open with a 2-3 sentence summary of what the system does and why it exists
- Describe the major components and how they relate to each other, in narrative form
- Explain the primary data flows in plain language ("Market data arrives via WebSocket, gets validated, then stored in Convex")
- Call out architectural patterns and decisions ("Uses a producer-consumer pattern for order processing because...")
- Note any non-obvious aspects that would trip up a newcomer
- Keep it under 200 lines - this is a map, not a book
- Use `file:line` references sparingly, only for key entry points

Use template: `templates/overview.md`

#### 2d. filesystem-map.md

Write a directory-purpose map. Requirements:
- Every top-level directory gets a row with its purpose
- Key subdirectories get expanded where architecturally significant
- List configuration files and what they configure
- Identify entry points (main files, CLI scripts)
- Note any unconventional locations ("tests live alongside source files, not in a separate test/ dir")

Use template: `templates/filesystem-map.md`

#### 2e. INDEX.md

Write the navigation hub. Requirements:
- System summary (one paragraph, same as primer.md/overview.md opening)
- Quick-start guidance that points to `primer.md` first
- Add fix-first guidance that points to `concerns.md`
- Component table (name, purpose, runtime status, architecture status, key files)
- Navigation by intent ("If you're working on X, read Y")
- Architecture decisions (key patterns, 1 line each)
- Generation metadata (timestamp, target dir, git hash, freshness/trust)
- Carry the accessor-contract marker from the template with current manifest metadata.
- Explicit note that this file is for navigation, not full architecture payloads

Use template: `templates/INDEX.md`

### Phase 3: Low-Level Structured Documents

**Progress:** Set `phase_3_structured` to `"in_progress"` before starting. After writing ALL structured docs (entry-points.md, flows.md, cross-references.md, and all component docs), add them to `artifacts_written` and set to `"complete"`.

#### 3a. entry-points.md

Consolidate from Agent 1 (Entry Points) output. One table with every entry point, its type, trigger, and what it calls. Use the structured format from `templates/entry-points.md`.

#### 3b. flows.md

Synthesize from Agents 1-3 (Entry Points, Data Flow, Control Flow) as two layers:

1. **Current Flow Index:** one compact Markdown-table row per significant flow, with
   stable ID, domain, category, status, trigger, entry anchor, component IDs, boundary
   IDs, and a link to its detailed record. Keep cells short; the index routes reads.
2. **Detailed records:** retain the full eight-field notation for ordered steps,
   branches, input/output data, exits, and boundaries:

```
### FLOW: stable-kebab-case-id
TRIGGER: what initiates this flow
ENTRY: function_name() (file:line)
STATUS: implemented | partial | disabled
STEPS:
  1. action -> next_action
  2. action [condition] -> branch_a | branch_b
  3. external_call() -> wait for response
DATA_IN:
  - param_name: type (description)
DATA_OUT:
  - return_value: type (description)
EXITS_TO: destination_flow(s)
BOUNDARIES: boundary-slug(s) crossed, or none
```

Group detailed records under stable domain/component-family headings; record category
(Lifecycle, Data Processing, Background, Error Recovery) in the index. **Never append
dated, commit-labelled, treatment-wave, or "incremental delta" sections.** Incremental
runs update the current row and record in place, preserve stable IDs, and remove
superseded descriptions when no active path uses them. Source control is the history.

`BOUNDARIES` links each runtime/process crossing in the flow to its Boundary Field
Contract table; a flow that crosses a boundary with no contract table is a coverage
gap — either write the table this run or register a verification item. The index and
details must be bijective: unique ID, one row, one record.
Use template: `templates/flows.md`

After writing or updating flows, run:

```bash
python3 <skill-dir>/scripts/architecture_access.py validate-flows
```

Do not mark Phase 3 complete until it passes.

#### 3c. cross-references.md

Synthesize from all 5 agents. Build lookup tables:
- Entry point table (function, file:line, type, calls, called_by)
- Call graph per component (tree format)
- Data path summary (source -> transforms -> sink)
- **Boundary Field Contracts (REQUIRED)** — one table per runtime/process boundary
  (HTTP→RPC/mutation, queue, webhook, socket, hook stdio, cross-language call), one row
  per field: emitted condition, adapter forwards?, consumer accepts?, persistence
  behavior, **absent semantics**, authority side, evidence anchors, verification status.
  Source: the contracts explorer's `BOUNDARY_FIELD_CONTRACTS` output. Any cell you
  cannot anchor to source THIS RUN is `unverified` and MUST get a manifest
  `verification_items[]` entry. Adapter-dropped or never-accepted fields are defect
  candidates — cross-post them into Phase 6 findings.
- **Economic Authority Matrix (REQUIRED)** — one row per calculation site (row schema:
  `templates/manifest.json` → `economic_authority_matrix[]`; enums are enforced by
  `validate-economic-authority`), built from the contracts explorer's `MONETARY_CALCULATION_SITES` output and
  grouped by public label. Record the exact UI/API label and aliases; producer and
  consumers; price source/side; size/depth basis; fees/rebates; time basis;
  formula/version; authority disposition; and reconciliation proof. The matrix must
  name a canonical executable-economics owner/contract per label group or state that
  none exists; it may not paper over a split by relabeling the raw value.

  Rules:

  1. Differing semantics under a public monetary label emit an **error finding** and Concern—no
     documentation exemption.
  2. “Display” is not an exemption if a value drives selection, thresholds, or operator judgement.
  3. A raw signal may remain only with a distinct name; it may not populate a public/executable
     label (e.g. "APR").
  4. A formula/version field must be accepted, rejected, or explicitly retired at every boundary.
  5. The output must name a canonical executable-economics owner/contract per label group (a
     single canonical calculation contract per label), or state that none exists. It must not paper over
     the split by relabeling the raw upstream value.
- Type contracts crossing component boundaries
- Data model / RPC surfaces and their access boundaries
- Hub files (imported by 5+ others)
- External dependency usage

Use template: `templates/cross-references.md`

#### 3d. components/{name}.md

Build the component records that will be serialized into `manifest.components[]`, then
select every generated component-doc path from those records' `doc_path` fields.
`structured/components/` is a live generated inventory, not a discovery source: never
promote a file merely because directory enumeration finds it.

One file per major component identified during discovery. A "component" is a cohesive group of files serving a single purpose (e.g., "WebSocket Client", "Order Engine", "Auth System").

Each component file includes (contract-first ordering — a planning agent should be able
to stop after the Contracts section):
- Provenance header: `Derived from: <files>` + `Verified at: <git hash>` + the explicit
  precedence rule ("if a derived-from file changed since <hash>, trust source over this doc")
- Quick reference table (entry, purpose, key files, depends on, used by)
- Contracts section, opening with **Boundary Field Contracts** (REQUIRED when any payload
  this component produces/consumes crosses a runtime/process boundary — same row schema as
  cross-references.md), then **Economic Authority** (REQUIRED when the component owns any
  matrix row; include this component's rows plus each label group's disposition), type
  contracts, data model/RPC surfaces, reusable UI interfaces
- Invariants: cross-file truths an agent must not break, each with an evidence anchor
  (e.g. "set once at construction, never flips"; "writes to X require lock Y")
- Data flow summary (IN -> PROCESS -> OUT)
- Key functions table
- Common patterns in this component
- Error handling approach
- Concurrency concerns (if applicable — shared state, multi-caller hazards; populated during Phase 4B)
- Configuration with precedence order when layered (env vs file vs default)
- Integration points (calls out to / called by)
- Active-vs-target architecture note when target boundaries and live callers diverge
- Notes for LLMs (non-inferable knowledge ONLY — hidden couplings, why-this-shape,
  "looks like the entry point but isn't"; never restate what reading the file shows)

Keep filenames and headings descriptive, stable, and keyword-rich so downstream
tools can match task text to component docs. Keep each component doc comfortably
under ~25K tokens to support bounded, on-demand reads.

Use template: `templates/component.md`

### Phase 4: Verification

**Progress:** Set `phase_4_verification` to `"in_progress"` before starting. Set to `"complete"` after both Part A and Part B finish.

Two passes — implementation status (Part A) and design-level hazards (Part B). Both must complete before manifest generation.

#### Part A: Reality Check

Run a drift/reality pass against source:

1. Detect implementation markers:
   - `TODO`, `not yet implemented`, `stub`, `placeholder`
   - Disabled behavior markers (`DISABLED`, commented registrations, feature flags set to false)
2. Validate runtime claims in docs against code:
   - Any claim of "automatic" behavior must have an active entry point
   - Scheduled/cron-based flows must verify whether the schedule is enabled or commented out
3. Reconcile contradictions:
   - If docs claim behavior is active but code is disabled/partial, mark flow `STATUS: partial|disabled`
   - Record contradiction in `manifest.warnings[]`

Do not publish "fully implemented" language without verifying the code path is active.

4. Validate numeric claims before writing them to docs:
   - Before writing "N+ models", "N endpoints", "N providers", etc., count the actual entries in the source file
   - Never extrapolate counts from file size or description — always count
   - If you cannot count precisely, use language like "multiple" or "several" instead of a specific number

#### Part B: Hazard Detection

Scan for architectural hazards that the explorer agents identified (especially from `explore-control-flow`'s concurrency section) and any that emerge from cross-referencing the synthesized docs.

**Concurrency hazards** — for each function callable from 2+ independent triggers:
1. List all callsites (grep the function name across the codebase)
2. Check if callers can run concurrently (e.g., independent timers, error handlers, startup paths)
3. Check for synchronization (mutex, guard flag like `isRefreshing`, lock file)
4. If no synchronization exists and callers can race: record as a hazard

**Shared state hazards** — for each component that writes to shared state (tokens, credentials, config files, connection objects):
1. Identify all write paths
2. Check if writes are atomic or guarded
3. If multiple uncoordinated writers exist: record as a hazard

**Output:** Add a `hazards[]` array to `manifest.json`:
```json
{
  "hazards": [
    {
      "id": "HAZ-001",
      "type": "concurrency_race",
      "resource": "access token",
      "component": "gateway",
      "callers": ["maybeRefreshAccessToken (heartbeat)", "refreshAccessToken (watch error)", "maybeRefreshAccessToken (startup)"],
      "synchronization": "none",
      "severity": "high",
      "description": "3 independent code paths can trigger token refresh concurrently with no mutex"
    }
  ]
}
```

**Severity levels:**
- **high**: Data corruption, resource storms, or security impact (e.g., token refresh race, credential overwrite)
- **medium**: Potential for inconsistent state but self-recovering (e.g., duplicate writes that are idempotent)
- **low**: Theoretical race with minimal practical impact (e.g., stale counter reads)

Also surface hazards in the relevant `components/{name}.md` under the "Concurrency Concerns" section.

If no hazards are found, record `"hazards": []` in the manifest (explicit empty, not omitted).

### Phase 5: Cross-Cutting Pattern Analysis

**Progress:** Set `phase_5_patterns` to `"in_progress"` before starting. After writing patterns.md, add to `artifacts_written` and set to `"complete"`.

Detect repeated code patterns across files of the same role. This is the generalization of per-component warnings (Phase 4B catches "feature flags not cached" in one file) to cross-file detection ("12 pages all repeat independent auth calls").

**Skip condition:** If the codebase has <5 source files, skip this phase (too small for cross-cutting analysis). Record `"patterns": []` in the manifest.

#### 5a. Launch Pattern Explorer

Launch an Explore subagent with the prompt from `<skill-dir>/prompts/explore-patterns.md`,
substituting `{TARGET_DIR}`. If subagents are unavailable, execute the same prompt
sequentially in the main agent, preserving its scope and output format as in Phase 1.

```
Agent(subagent_type="Explore", prompt=read("<skill-dir>/prompts/explore-patterns.md").replace("{TARGET_DIR}", TARGET_DIR), description="Detect cross-cutting patterns")
```

This runs after Phase 4 (not in the Phase 2 parallel batch) because it needs the component analysis from Phase 3 to know what roles files play.

#### 5b. Group Files by Role

Using Phase 3 component data + the explorer's findings, group files by structural role:
- Page entry points (e.g., `app/**/page.tsx`, `pages/**/*.py`, `routes/**/*.go`)
- API route handlers
- Components/widgets of the same type
- Configuration files
- Test files (check for pattern consistency with source)

Only analyze groups with 3+ files.

#### 5c. Extract Repeated Patterns

For each group:
1. Identify the common "setup block" — imports, client creation, auth checks, data fetching
2. Note what varies between files (business logic) vs. what is identical boilerplate
3. Assess whether the repeated code could be centralized per the framework's documented patterns
4. Consult the framework's official documentation when a recommendation depends on its supported behavior

#### 5d. Produce Outputs

**Manifest `patterns[]` array:**
```json
{
  "patterns": [
    {
      "pattern_id": "per-page-auth",
      "files": ["app/orders/page.tsx", "app/shipments/page.tsx"],
      "description": "Each page independently calls auth.getUser()",
      "concern": "Redundant network call per navigation (~200ms each)",
      "best_practice": "React cache() wrapper or middleware-based auth",
      "severity": "warning",
      "category": "auth"
    }
  ]
}
```

Field definitions:
- **pattern_id**: `kebab-case` descriptive name
- **files**: list of file paths exhibiting the pattern
- **description**: what the code does (neutral, factual)
- **concern**: why this might be problematic (null if acceptable pattern)
- **best_practice**: what the framework/stack recommends instead (null if current approach is correct)
- **severity**: `info` (observed, no concern) | `warning` (suboptimal, should fix) | `error` (will cause user-facing issues)
- **category**: `data-fetching` | `auth` | `state-management` | `loading` | `error-handling` | `configuration`

Empty `patterns[]` is valid — codebases with good abstractions may produce none.

**Human-readable `patterns.md`:**

Write `.architecture/patterns.md` using the template from `templates/patterns.md`:

```markdown
# Cross-Cutting Pattern Analysis

> Generated by mapcodebase Phase 5 — compares repeated code patterns against
> framework best practices.

## Patterns Detected

### [pattern_id]
- **Files:** [N files]
  - `path/to/file1.ext`
  - `path/to/file2.ext`
- **Description:** [what the code does]
- **Severity:** [info|warning|error]
- **Category:** [category]
- **Concern:** [why problematic, or "None — pattern is appropriate"]
- **Recommended:** [best practice, or "Current approach is correct"]

---

## Summary
- **Total patterns detected:** N
- **Info:** N | **Warning:** N | **Error:** N
- **Top pattern:** [most impactful pattern to address]
```

**Downstream consumers:** Readers can validate flagged patterns against the cited
source and use `patterns[]` for review or implementation planning.

### Phase 6: Diagnosis

**Progress:** Set `phase_6_findings` to `"in_progress"` before starting. After writing `findings.md`, `concerns.md`, and refreshing `primer.md` / `INDEX.md` with the concern rollup, add `findings.md` and `concerns.md` to `artifacts_written` and set the phase to `"complete"`.

**Default: synthesize directly in the main agent.** After Phases 1-5, the main agent's context already contains the full discovery data — explorer outputs, hazards, patterns, and the just-written architecture docs. Spawning a "fresh context" subagent to diagnose throws that context away and forces re-exploration (re-reading docs, re-grepping source), which is wasteful and duplicates work the main agent already did.

Work directly from Phase 1-5 data in context. Apply the 6a-pre scans and 6a category analysis as self-directed reasoning, not as delegated subagent work. Grep source files only for *targeted verification* of a specific finding — never as open-ended exploration.

**Skip condition:** If the codebase has <5 source files, skip this phase. Record `"findings": []` in the manifest.

**Subagent fallback (rare):** Only delegate to a general-purpose subagent if the main agent's context is genuinely pressured (e.g., you're past 70% of the effective window after Phases 1-5 and further reasoning risks auto-compact). If you do delegate, inject the Phase 1-5 discovery content directly into the subagent prompt — do NOT tell the subagent to re-read architecture docs from disk or re-grep source, since those steps duplicate work already reflected in the discovery artifacts.

**Error handling:** If diagnosis fails, log `"FINDINGS_PHASE_FAILED: <reason>"` to `manifest.warnings[]`, write empty `findings: []`, skip `findings.md`, and continue to Phase 7. Do NOT halt mapcodebase.

#### 6-synthesize. Produce Findings and Concerns in the Main Agent

1. **Verify Phase 1-5 outputs on disk:**
   ```bash
   ls .architecture/primer.md .architecture/overview.md .architecture/filesystem-map.md \
      .architecture/structured/entry-points.md .architecture/structured/flows.md \
      .architecture/structured/cross-references.md .architecture/patterns.md \
      .architecture/.work/discovery/*.md 2>/dev/null | wc -l
   ```

2. **Work from context, not from disk.** The data you need is already in your conversation from the Phase 1 explorer outputs and the Phase 2-5 synthesis you just wrote. Do NOT re-Read the architecture docs. Do NOT launch a general-purpose agent to re-explore the codebase.

3. **Apply the 6a-pre scans as self-directed checks.** For each of the four mandatory scans (Registry/Config Deduplication, Near-Duplicate Command Names, Doc Accuracy Spot-Check, Monetary-Semantic Authority Reconciliation), run the check against the data you already have. If a specific numeric claim or file identity is in doubt, you may Grep or Read short sections for targeted verification — but do not re-explore broadly.

4. **Apply the 6a category analysis.** Walk through the 12 finding categories (dead-code, layer-violation, missing-abstraction, security, performance, error-handling, idiomatic, duplication, complexity, test-integrity, doc-accuracy, economic-authority) against the Phase 1-5 discovery data. Produce up to 20 findings.

5. **Synthesize the concern rollup (6c)** from hazards + patterns + findings.

6. **Write output files** directly:
   - `findings.md` from the findings array (using template)
   - `concerns.md` from the concerns array (using template)
   - Update `primer.md` top concerns section
   - Update `INDEX.md` fix-first link

The full diagnosis instructions below (6a-pre scans + 6a categories + 6b output format + 6c concern rollup) are written to be executable directly by the main agent. They were previously framed as "subagent prompt instructions" but are identical regardless of who runs them.

---

**BEGIN DIAGNOSIS INSTRUCTIONS (executed by main agent; subagent fallback only when context is pressured)**

#### 6a-pre. Mandatory Cross-File Scans

**Each scan must be completed sequentially. Log results before proceeding to the next scan.**

Before the general findings analysis, run these targeted scans. These exist because general-purpose LLM reasoning consistently misses cross-file relationships — the agent examines each file individually and never compares them. These scans force explicit comparison.

**Scan 1: Registry / Config / Mapping Deduplication**

**1a. Code & config registries:**
1. Search the codebase for files containing registry, config, or mapping patterns:
   - Grep for: `registry`, `REGISTRY`, `_registry`, `config`, `CONFIG`, `mapping`, `MAPPING`, `catalog`
   - Also check: `.toml`, `.yaml`, `.json` files that define key→value maps of domain entities

**1b. Filesystem data layers:**
2. Search for code that enumerates directories as data sources:
   - Grep for: `listdir`, `iterdir`, `scandir`, `os.walk`, `glob(`, `Path(`, `os.path.isdir`
   - For each hit, check: does the code treat directory names or filenames as entity keys? (e.g., each subdirectory = one model, each file = one task)
   - List the actual directory contents (`ls`) to count entries and extract the naming pattern
   - A directory with 5+ entries of the same type that maps to the same entity as a code/config registry IS a registry — include it in pair comparison

**1c. Pair comparison:**
3. For each pair of hits (code, config, OR filesystem), check:
   - Do both map the same entity type? (e.g., both map model IDs → API configs, or user roles → permissions)
   - What is the key overlap? (full overlap = ok, partial = warning, zero = error)
   - Do both serve consuming code that does the same thing? (e.g., both feed LLM API calls)
   - Do the naming schemes match? (e.g., registry key `catalog-standard` vs directory name `catalog-standard-detailed`)
4. If a pair serves the same semantic purpose with <50% key overlap, emit a `duplication` finding with severity `error`
5. If three or more registries exist for the same entity type, emit findings for ALL of them — not just the first two found

**Scan 2: Near-Duplicate Command / Endpoint Names**

1. From the entry-points doc, list all CLI commands, API routes, and task/job names
2. For each pair, compute edit distance. Flag pairs with edit distance ≤ 2 (e.g., `generate-orders` vs `generate-order`)
3. For flagged pairs, check: do they share purpose? Do they use different data sources?
4. If they share purpose but diverge on source data, emit a `duplication` finding

**Scan 3: Doc Accuracy Spot-Check**

1. For any numeric claim in the architecture docs above (e.g., "40+ models", "12 endpoints", "3 providers"):
   - Count the actual entries in the source file
   - If the claim differs from reality by >20%, emit an `error`-severity finding in the `doc-accuracy` category
2. This catches cardinality fabrication — the LLM writes plausible-sounding numbers that don't match the code

**Scan 4: Monetary-Semantic Authority Reconciliation**

1. Run:
   ```bash
   python3 <skill-dir>/scripts/architecture_access.py validate-economic-authority
   ```
2. Every `ECON-CONFLICT` / `ECON-RAW-LABEL` / `ECON-VERSION-DROPPED` /
   `ECON-NO-CANONICAL` line becomes a finding with category `economic-authority`,
   severity `error`, and confidence per evidence.
3. “Documented by design”, “for display”, and “two independent freshness authorities”
   are NOT exemptions — a map declaration of authority is evidence to verify, never a
   reason to suppress.
4. If the matrix is empty but the semantic sweep in Phase 1
   (`prompts/explore-contracts.md` step 7) produced hits, that is itself an
   `economic-authority` error finding (matrix incomplete).
5. **An empty matrix is valid** when the sweep found no operator-facing or decision-driving
   monetary calculation site. That is the expected outcome for projects with no monetary
   surface (CLI tools, content pipelines, games). Empty is not "unfinished": it is a claim,
   and it must be recorded as one — add a `warnings[]` entry naming the sweep result,
   e.g. `MONETARY_SWEEP: no operator-facing monetary calculation sites found; matrix empty
   by design`, and set the three `metrics.economic_*` counters to `0`. Rule 4 then applies
   only to a matrix that is empty *despite* qualifying hits. Sweep vocabulary is intentionally
   broad (`cost`, `score`, `lock`, `expiry`, `horizon`, `*_VERSION`), so most hits in a
   non-monetary project will be non-monetary terms; classify them and say so rather than
   inventing rows or padding the matrix with noise.

Log results of all four scans before proceeding to the general analysis. If any scan produces findings, they are included in the findings[] array alongside general findings.

#### 6a. Analyze with Full Context

Using the architecture docs provided above **and the results of the 6a-pre scans**, identify architectural concerns across these categories:

| Category | What to look for | Example |
|----------|-----------------|---------|
| dead-code | Unreachable code, unused imports, orphan modules | Module imported nowhere, function never called |
| layer-violation | Components reaching across architectural boundaries | UI layer directly accessing database |
| missing-abstraction | Repeated logic with slight variations (semantic duplication, unlike patterns[] syntactic duplication) | 5 endpoints each manually validating auth differently |
| security | Unvalidated input, exposed secrets, missing auth checks at boundaries | User input passed to shell command unsanitized |
| performance | N+1 queries, unbounded loops, missing caching | Loading all records to count them |
| error-handling | Missing error handling at system boundaries, swallowed exceptions | Bare `except: pass` on network call |
| idiomatic | Deviations from the stack's recommended patterns | Using raw SQL in a Django project with ORM |
| duplication | Same logical purpose served by multiple independent implementations with divergent data or keys | Two model registries mapping model names to API configs, with disjoint key sets and different cardinalities. See detailed detection guidance below |
| complexity | Functions/modules too complex for their role | 300-line function with 8 levels of nesting |
| test-integrity | Test infrastructure leaked into production code, or mock targets that don't match real import paths | See detailed detection guidance below |
| doc-accuracy | Factual claims in generated architecture docs that don't match source code | Doc says "40+ models" but file has 10 entries |
| economic-authority | Same public monetary label produced by calculations with different price/fee/depth/time semantics, or a raw signal populating an executable label | Picker APR is gross one-level simple-365 while the order ladder is fee-aware depth-walked rounded-day |

#### Test-Integrity Detection (Detailed)

This category catches two classes of bugs that produce failures **indistinguishable from real application bugs**, wasting hours of debugging time.

**Class 1: Mock/test infrastructure in production source files**

Grep non-test source files for these patterns. Any hit is severity `error`:

| Signal | What it means |
|--------|--------------|
| `mockUser`, `mock_user`, `fakeFoo` in identifiers | Test doubles living in production code |
| `E2E_`, `TEST_`, `PLAYWRIGHT_` env var reads | Environment-gated test behavior |
| `isTestMode`, `isPlaywrightAuth`, `__testing__` | Conditional branches that only execute during testing |
| `playwright`, `jest`, `vitest`, `pytest`, `cypress` references | Test framework names in non-test files |
| `mintPlaywrightJwt`, `createMockToken` | Test-only credential minting in production code |

**Why severity `error`:** Test-only authentication or credential branches in
production can use a local signing secret against a remote service with a different
secret. The resulting authorization failures can look like missing application data.
Verify the exact boundary and mechanism rather than treating a test shortcut as a
production contract.

**The fix pattern is always the same:** delete mock infrastructure from production code, use real test users/fixtures instead. For auth: `supabase.auth.admin.createUser()` or equivalent.

**Class 2: Mock targets that don't match production import paths**

For Python `mock.patch()` / `unittest.mock.patch()` and JS `jest.mock()` / `vi.mock()`:

1. Extract the dotted path from each `mock.patch('a.b.c')` call
2. Find the test's target module (the code under test)
3. Check whether the target module imports the mocked symbol via that exact path
4. If the mock patches `a.b.c.thing` but production code imports `thing` via `from x.y import thing`, the mock is a silent no-op — it patches a path nobody uses

Flag as severity `error` with confidence `medium` (requires verifying import resolution, which static analysis can get wrong with re-exports).

**What to exclude from test-integrity checks:**
- Files in `tests/`, `test/`, `__tests__/`, `*.test.*`, `*.spec.*`, `e2e/`, `playwright/` directories
- Dedicated test utility files (`conftest.py`, `test-utils.ts`, `fixtures/`)
- `__mocks__/` directories (framework-mandated mock locations)

**What NOT to flag:**
- Issues already in hazards[] (don't duplicate concurrency findings)
- Issues already in patterns[] (don't duplicate boilerplate findings)
- Style/formatting preferences (not architectural)
- Framework-mandated patterns that look wrong but are correct
- Anything requiring runtime profiling (static analysis only)
- Deliberate decisions documented in `.architecture/overview.md`
- Deliberate decisions documented in overview.md — EXCEPT divergent monetary semantics under one operator label, which are never exempt.

**Large codebase prioritization (>100 source files):** Focus on:
1. Components with existing hazards[] from Phase 4B
2. Components with warning/error patterns[] from Phase 5
3. Files with high fan-in (hub files from cross-references)
4. Entry points and system boundaries

#### Duplication Detection (Detailed)

This category catches multiple independent implementations of the same logical purpose that diverge over time, creating "which one is right?" confusion and blocking automation that assumes a single source of truth.

**Class 1: Parallel registries / config sources**

During Phase 1 discovery and Phase 2-3 synthesis, watch for files that:

1. Serve the same semantic purpose (e.g., both are "model registries", "API config maps", "feature flag stores", "user role definitions")
2. Map similar key types to similar value types (e.g., both map model names → API provider configs)
3. Have disjoint or minimally-overlapping key sets (the registries don't share entries)
4. Are consumed by parallel but similar code paths (e.g., two CLI commands that both call LLMs)

**Signals to check:**
- Two files described with the same role noun ("registry", "config", "mapping", "catalog") in their docstrings, comments, or variable names
- Both files export or define a dict/map/object with semantically equivalent keys (model IDs, provider names, feature names)
- The consuming code paths do the same thing (e.g., both generate catalog descriptions via model calls) but read from different registries
- Different key counts between the two sources (e.g., 10 entries vs 50 entries) — especially when architecture docs claim the same count for both

**Why severity `error`:** Parallel registries are invisible to automation. A CLI command that reads registry A will silently skip all entries only in registry B. The divergence compounds: each registry evolves independently, entries are added to whichever one the developer happens to be working with, and reconciliation becomes harder over time.

**Class 2: Divergent naming schemes for the same entities**

When the same logical entities (models, users, features, environments) are referenced by different names across different subsystems:

1. Check whether filesystem paths, database keys, config keys, and code constants use the same names for the same entities
2. Flag when a mapping/alias layer is missing — if entity `catalog-standard` in the registry becomes `catalog-standard-detailed` on the filesystem with no alias table, any code that joins across both will silently produce empty results

**Signals to check:**
- Registry keys don't match filesystem directory names in the same data pipeline
- Two subsystems reference the same real-world entity with different string identifiers
- No alias/mapping table exists to bridge the naming gap

Flag as severity `error` with confidence `high` when both registries are confirmed to serve the same purpose. Flag as `warning` with confidence `medium` when the semantic overlap is probable but the consuming code paths differ enough that intentional separation is plausible.

**What NOT to flag:**
- Intentional multi-tier configs (e.g., a base config + environment overrides that layer on top)
- Framework-separated concerns (e.g., client-side config vs server-side config for the same feature, when they serve different runtimes)
- Test fixtures that mirror production config structure (these belong in test-integrity if problematic)
- Deliberate decisions documented in overview.md — EXCEPT divergent monetary semantics under one operator label, which are never exempt.

**The fix pattern:** Consolidate to one authoritative source. The secondary consumer either reads from the primary source or imports/re-exports a subset. If different transport models require different schemas (e.g., direct SDK calls vs an HTTP proxy), use one registry with per-entry transport config rather than two registries split by transport.

#### 6b. Produce Outputs

**Manifest `findings[]` array:**
```json
{
  "findings": [
    {
      "finding_id": "FIND-001",
      "category": "dead-code|layer-violation|missing-abstraction|security|performance|error-handling|idiomatic|duplication|complexity|test-integrity|doc-accuracy|economic-authority",
      "severity": "info|warning|error",
      "component": "component-slug",
      "files": ["path/to/file.py"],
      "title": "Short descriptive title",
      "description": "What was observed",
      "suggestion": "What to consider changing (or null if info-only)",
      "confidence": "high|medium|low",
      "evidence": "Specific code reference or measurement"
    }
  ]
}
```

Field definitions:
- **finding_id**: Sequential `FIND-NNN` within a run
- **category**: Classification from the table above
- **severity**: `info` (observation, no action) | `warning` (should address, maintenance pain) | `error` (user-facing issues or security problems)
- **component**: Links to the component doc where this was found
- **files**: Specific file paths involved
- **title**: One-line summary suitable for a task title
- **description**: Neutral observation of what exists
- **suggestion**: Opinionated recommendation (null for info severity)
- **confidence**: `high` (confirmed by code) | `medium` (likely from patterns) | `low` (heuristic, needs validation)
- **evidence**: File:line references or specific code patterns observed

**Max 20 findings per run.** If more are identified, prioritize by severity × confidence and note "N additional findings suppressed" in the summary.

Empty `findings[]` is valid — well-architected codebases may produce none.

**Human-readable `findings.md`:**

Write `.architecture/findings.md` using the template from `templates/findings.md`:

```markdown
# Architecture Findings

> Generated by mapcodebase Phase 6 — opinionated suggestions based on full
> codebase analysis. Validate these by reading the cited code.

## Findings

### FIND-001: [title]
- **Category:** [category]
- **Severity:** [severity]
- **Confidence:** [confidence]
- **Component:** [component]
- **Files:**
  - `path/to/file.py:42`
- **Observation:** [description]
- **Suggestion:** [suggestion]
- **Evidence:** [evidence]

---

## Summary
- **Total findings:** N
- **By severity:** info: N | warning: N | error: N
- **Top finding:** [most impactful finding to address first]
- **Confidence breakdown:** high: N | medium: N | low: N
```

**Relationship to other analytical outputs:**

| Output | Scope | Trigger |
|--------|-------|---------|
| hazards[] | Concurrency/shared state bugs | Multi-caller race detected |
| patterns[] | Syntactic duplication (identical boilerplate across 3+ files) | Same code block repeated |
| findings[] | Broad architectural quality (everything else) | Agent judgment after full context load |

**Downstream consumers:** Readers can validate or dispute each finding from its
evidence anchors; downstream tools can query `findings[]` for review and planning.

#### 6c. Synthesize Actionable Concerns

After hazards, patterns, and findings exist, produce a fix-first concern rollup.

Use these inputs:
- `hazards[]` from Phase 4B
- `patterns[]` from Phase 5
- `findings[]` from Phase 6b
- component/runtime/drift context from Phases 2-4

Goal: give humans and downstream skills the 3-10 most actionable concerns without making them inspect three different analytical layers.

Rules:
- A concern may reference one or more source items (e.g. `HAZ-001`, `FIND-003`, `jsonl-serialization-boilerplate`)
- Merge overlapping items when they point to the same underlying remediation
- Prefer concerns with a clear next action, large blast radius, boundary risk, or architectural drift
- Do not include low-signal informational items just to fill the list
- It is valid for `concerns[]` to be shorter than the union of hazards/patterns/findings
- An `economic-authority` error finding always produces its own concern with
  `severity: error`, `priority: now`, and `source_refs` that include the matrix row ids.
  Its `recommended_action` names the canonical owner/contract to create or adopt, or
  states that none exists and must be created. A header-only, display-only, or
  relabeling remediation is forbidden.

**Manifest `concerns[]` array:**
```json
{
  "concerns": [
    {
      "concern_id": "CON-001",
      "priority": "now|next|later",
      "severity": "warning|error",
      "component": "component-slug",
      "title": "Short descriptive title",
      "summary": "Why this matters in one or two sentences",
      "recommended_action": "Concrete next move",
      "files": ["path/to/file.py"],
      "source_refs": ["HAZ-001", "FIND-003"],
      "confidence": "high|medium|low"
    }
  ]
}
```

Field guidance:
- **priority**: `now` = fix-first / architecture-blocking, `next` = worthwhile near-term, `later` = useful but not urgent
- **severity**: normalize the contributing source items to `warning|error` at the concern layer
- **summary**: must explain impact, not just restate the title
- **recommended_action**: must be concrete enough to start implementation or debate
- **source_refs**: must point back to hazards, patterns, and/or findings so the rollup is traceable
- **confidence**: how strongly the rollup is supported by the underlying source items and code evidence

**Human-readable `concerns.md`:**

Write `.architecture/concerns.md` using `templates/concerns.md`.

This file should:
- open with the top 3 concerns
- include the underlying source refs for each concern
- tell the reader what to fix first and why
- stay compact enough to be a real "what next?" doc rather than another dump

#### 6d. Refresh the Accessor Layer

After `concerns.md` is written:
- update `primer.md` so its "Top Actionable Concerns" section points to the highest-priority items
- update `INDEX.md` so it explicitly answers "What should I fix first?" with `concerns.md`

This is a 3.1 accessor-layer update, not a full rewrite of those docs. Keep the changes compact.

**END DIAGNOSIS INSTRUCTIONS**

---

### Phase 6e: Action Plan (Main Agent)

**This step runs in the main agent after synthesizing diagnosis results.** The main agent still has Phases 1-5 codebase context — use it.

For each concern synthesized by the main agent during diagnosis:
1. Identify the files involved (the main agent already explored these)
2. Assess the fix approach: does this need design review, direct implementation, or is it a doc-only fix?
3. Estimate blast zone: what other files/components are affected?
4. Group related concerns that share a fix

Write `.architecture/action-plan.md`:
```markdown
# Architecture Action Plan

> Generated by mapcodebase Phase 6e — remediation plan based on diagnosis findings.
> Uses codebase context from Phases 1-5 to assess fix approaches.

## Priority: Now

### CON-001: [title]
- **Fix approach:** [design review | direct implementation | doc fix]
- **Files:** [list]
- **Blast zone:** [other affected files/components]
- **Grouped with:** [other CON-IDs if shared fix]
- **Estimated scope:** [small/medium/large]
- **Notes:** [any insight from codebase exploration]

## Priority: Next
...

## Priority: Later
...
```

This step is optional if context is too tight. The main agent should attempt it but may skip if only a few hundred tokens remain. The concerns and findings are already on disk — the action plan adds remediation context that would otherwise require a fresh codebase exploration.

### Phase 6f: Verification Debt & Answerability Gate (Main Agent)

**This phase is NOT optional.** An unverified boundary claim can conceal a dropped
field across multiple scans; track it as explicit verification debt until resolved.

**1. Collect verification debt.** Sweep everything written this run for unverified claims:
any boundary-contract cell marked `unverified`, any "not verified this wave" phrasing, any
runtime claim you could not anchor. Each becomes a `manifest.verification_items[]` entry
(id `VER-NNN`, kind, component, the exact claim, `owner_files`, `evidence_needed`, severity,
`next_action`). **Prose-only unverified notes are forbidden** — if it's worth flagging in a
doc, it's worth tracking in the manifest; the doc note must cite its `VER-NNN` id.
Any Economic Authority Matrix row whose semantic tuple contains `unknown` becomes a
`verification_items[]` entry with `kind: economic_semantics`.

**2. Attempt cheap resolution NOW.** Before registering an item, spend the 30 seconds:
most boundary verification is one targeted Read of the adapter/consumer file.
Compare the emitted, forwarded, and accepted fields directly before declaring debt. Register an item only when resolution
genuinely needs work beyond this run's scope (missing repo access, runtime-only behavior,
external service).

**3. Status effects (mandatory):**
- Any OPEN `verification_items[]` with `severity: high` on a boundary contract →
  manifest `status: "partial"` and `freshness_status` no better than `"caution"`.
- Open items must be surfaced: `concerns.md` gets a "Verification Debt" line-item list;
  `primer.md` trust note mentions the open count.

**4. Answerability tests (the Question Test, executed).** Compose 5-10 realistic agent
questions for THIS codebase — mandatory coverage: at least one "what does absence of field
X mean at boundary Y?", one "which file implements Z?", one "what breaks if I change W?",
plus questions derived from this project's actual recent work (recent changes/commits).
Answer each **from the generated docs alone** (no source reads), then spot-check the answers
against source. Record in `manifest.answerability_tests[]`. A failed question = a coverage
gap: fix the doc this run, or register a verification item explaining why not.
`metrics.answerability_pass_rate` = answered/total. Below 0.8 → `status: "partial"`.

**5. Resolution discipline for later runs:** an existing open item may only transition to
`resolved` (with evidence refs at current git) or `not_modeled` (with explicit rationale —
a deliberate decision that this is out of corpus scope). Re-emitting an open item unchanged
without re-checking is invalid when any of its `owner_files` changed.

### Phase 7: Manifest + Compact View

**Progress:** Set `phase_7_manifest` to `"in_progress"` before starting. After writing
and validating both `manifest.json` and `manifest.md`, verifying artifacts, and adding
both paths to `artifacts_written`, set it to `"complete"`.
Finish with a whole-layer refresh of `primer.md`, `access-guide.md`, and `INDEX.md`
from final manifest metadata before their accessor validation.

Write `.architecture/manifest.json` as the parsed machine-compatibility record. This
keeps the existing parsed contract, with additive fields on top of schema `2.0`. Then deterministically generate
`.architecture/manifest.md` as the compact agent-facing view. JSON remains necessary
for existing consumers and co-owned mutations; agents use the Markdown view or retrieve
one named section so repeated object keys do not consume task context.

Use template: `templates/manifest.json`

Populate:
- `schema_version: "2.0"`
- `skill_version`, `model`, `generated_at`, `target_dir`, `git_hash`, `head_git_hash` from run metadata
- `status`: `success` if all explorers returned and all required artifacts written; `partial` if any explorer failed or artifacts missing; `failed` if synthesis couldn't complete
- A component-inventory mismatch is never `success`; record it and set `status` to
  `partial` until explicitly reconciled in a future run.
- `discovery_outputs`: relative paths to the 5 persisted Phase 1 discovery files under `.work/discovery/`
- `commit_distance_from_scan`, `dirty_worktree`, `changed_files_since_scan`, `changed_components_since_scan`, `freshness_status`, and `trust_notes`

**Field semantics (STRICT — misfills here have misrouted downstream gates):**
- `commit_distance_from_scan` = commits between THIS run's `git_hash` and `head_git_hash`
  **at write time** — i.e. `0` at generation, by construction. It is NEVER the distance
  from the previous map (`freshness.previous_map_git_hash` may record lineage; compute
  nothing from it). Downstream freshness checks interpret this value as current drift.
- `freshness_status` measures **git/worktree drift relative to the mapped state only**
  (`fresh` = docs describe current state; `caution` = drift touches mapped areas;
  `stale` = regenerate). At generation time it is `fresh` unless the §"Status effects"
  rule (open high-severity boundary verification items) forces `caution`. Run HEALTH
  belongs in `status` and `warnings[]` and must NEVER leak into `freshness_status` —
  and per the Phase 1 gate, a run with any explorer failure never reaches this point
  anyway (it aborts before writing).
- `dirty_worktree` is a recorded fact about scan conditions; it does not by itself
  downgrade `freshness_status` (the map describes the dirty content it scanned).
- `access_paths`: machine-readable counterparts to `access-guide.md` for `general_primer`, `actionable_concerns`, `plan_evaluation`, and `component_deep_dive`
- `components[]`: one entry per component identified, with slug ID, name, entry file, key files, path to component doc, intent tags, runtime status, architecture status, active consumers, and legacy consumers. Select generated component-doc paths only from these entries' `doc_path` values.
- `metrics`: counts of files scanned, components/flows/entry points identified,
  explorer failures, hazards identified, patterns detected, findings produced,
  concerns identified, contracts identified, and access artifacts written. Preserve
  per-run counts, but also populate `patterns_total_tracked`,
  `findings_total_tracked`, `concerns_total_tracked`,
  `boundary_contracts_documented`, and `answerability_questions`; these total fields
  must equal their rendered table row counts. For backward compatibility,
  `components_identified` and `hazards_identified` are also current total row counts,
  not incremental-run deltas; record per-run component/hazard changes under distinct
  `*_refreshed`, `*_created`, `*_added_this_run`, or `*_resolved_this_run` keys.
- `metrics.economic_calculation_sites`: integer equal to
  `len(economic_authority_matrix)`; `metrics.economic_labels_tracked`: integer equal
  to the number of distinct normalized labels; and
  `metrics.economic_conflicts_open`: integer equal to the divergent label groups whose
  reconciliation is a `concern`.
- `artifacts[]`: list of all files actually written — **must be verified** (see artifact verification below)
- `warnings[]`: any issues (explorer timeouts, unresolved conflicts, skipped files, reality check contradictions, findings phase failures)
- `hazards[]`: architectural hazards from Phase 4 Part B (empty array if none)
- `patterns[]`: cross-cutting patterns from Phase 5 (empty array if skipped or none found)
- `findings[]`: architectural findings from Phase 6 (empty array if skipped or none found)
- `concerns[]`: actionable concern rollup from Phase 6c (empty array if no fix-first concerns emerge)
- `boundary_contracts[]`: one entry per boundary field-contract table written (Phase 3),
  with chain anchors, `doc_path`, field counts, `defect_candidates`, `verified_at_git`
- `economic_authority_matrix[]`: one row per monetary calculation site using the
  `economic_authority_matrix` schema in `templates/manifest.json`,
  with its public label, roles, semantic tuple, authority disposition,
  reconciliation, and verification hash. A divergent public-label group without an
  error Concern is non-success.
- `verification_items[]`: the verification debt ledger from Phase 6f (empty only if
  genuinely nothing is unverified)
- `answerability_tests[]`: the Question Test results from Phase 6f
- `freshness.map_git_hash`: set to this run's `git_hash` so downstream tools can
  compare the mapped commit without disturbing other freshness metadata
- `previous_run`: if updating, copy the old manifest's git_hash/timestamp/version here

**Compact view encoding (required):**

- Keep nested/type-sensitive non-array metadata in the `Run metadata` JSON block.
- Render homogeneous object arrays (`components`, `hazards`, `findings`, `concerns`,
  `patterns`, `boundary_contracts`, `economic_authority_matrix`,
  `verification_items`, `answerability_tests`) as
  Markdown tables so each key appears once in the header.
- Render scalar arrays (`artifacts`, `warnings`, `trust_notes`, changed-item lists,
  `exclusions`) as Markdown lists.
- Preserve every field, including foreign top-level metadata. Escape pipes and
  newlines deterministically. Never hand-edit `manifest.md`.
- Treat `components[].doc_path` as the exact generated and tracked component set.
  Enumerate the component directory only for the integrity check; never derive active
  membership from its glob.

**Manifest co-ownership (mandatory):** `.architecture/manifest.json` is co-owned.
Other tools may contribute an `audit` section and additional keys under the nested
`freshness` block (`audit_git_hash`, `diagnosis_for_map`, ...). mapcodebase must
**read-modify-write**: load the existing manifest, replace only the keys it owns, preserve
`audit` and any `freshness` sub-keys other than `map_git_hash`, and never emit the template
verbatim over a manifest that has foreign sections.

**Artifact verification (mandatory):** Before writing the final manifest, stat-check every file in `artifacts[]`. For each file that does not exist on disk:
1. Remove it from `artifacts[]`
2. Add an entry to `warnings[]`: `"MISSING_ARTIFACT: {path} listed but not written to disk"`
3. If the missing artifact is a component doc, set `status` to `partial`

This gate prevents the ghost-artifact bug where the manifest claims files exist that were never written.

**Component inventory integrity (mandatory):** Build the expected set by normalizing
the unique `components[].doc_path` values. Build the actual set from direct regular
Markdown children of `structured/components/`; reject symlinks and nested directories,
then require exact equality. Missing expected paths, duplicate expected paths, or
unknown actual extras are an inventory mismatch: add a warning, set `status` to
`partial`, and do not report success. Retain unknown extras unchanged for explicit
future reconciliation; this run does not delete, archive, or otherwise reconcile them.

**Normalize rendered views (mandatory, before validation):**

Once every delegated writer has exited, re-derive the doc-side views from the machine record rather than
trusting N writers to agree with it (Phase 0b rule 1):

```bash
python3 <skill-dir>/scripts/normalize_economic_views.py --write
python3 <skill-dir>/scripts/normalize_component_provenance.py --git-hash <SHORT_HEAD>
```

Both are idempotent and deterministic. The economic pass rewrites every Economic Authority table
(`cross-references.md` groups plus each owning component doc) from `manifest.economic_authority_matrix`;
the provenance pass stamps `Derived from: … | Verified at: …` from `components[].key_files`, refuses to
run against a manifest whose `git_hash` is not the expected one, and skips any doc whose header already
claims the current commit. Never hand-edit a table these scripts own.

**Validate and render (mandatory, after the JSON write):**

First refresh the entire accessor layer from the final manifest metadata, including the
marker in each template-derived file. Then run:

```bash
python3 <skill-dir>/scripts/architecture_access.py validate-manifest
python3 <skill-dir>/scripts/architecture_access.py validate-economic-authority
python3 <skill-dir>/scripts/architecture_access.py validate-flows
python3 <skill-dir>/scripts/architecture_access.py validate-component-inventory
python3 <skill-dir>/scripts/architecture_access.py render-manifest
python3 <skill-dir>/scripts/architecture_access.py validate-accessors
```

`validate-component-inventory` proves that normalized `components[].doc_path` values
and the component-directory files are the same exact set. `validate-accessors` proves
that all three accessor files carry the final manifest metadata marker and the required
bounded-read guidance; an old guide merely existing cannot pass.

The validator fails on missing required fields, duplicate stable IDs, or disagreement
between manifest metrics and table row counts. After rendering, stat-check all
`artifacts[]` again, including `manifest.json` and `manifest.md`. If the JSON changes
during artifact correction, re-run validation, rendering, the whole accessor refresh,
and `validate-accessors` so no generated view can drift.

**Bounded reads (the default agent contract):**

```bash
# One registry as a Markdown table
python3 <skill-dir>/scripts/architecture_access.py manifest-section components

# Only tracked component doc paths
python3 <skill-dir>/scripts/architecture_access.py manifest-section components --format lines --field doc_path

# Any filtered registry
python3 <skill-dir>/scripts/architecture_access.py manifest-section verification_items --where status=open
```

Do not read full `manifest.json` merely to obtain one array. `access-guide.md` must
carry these commands so downstream planning runs can recover narrow context after
compaction without reloading the full registry.

**The manifest enables:**
- `html-program-map` to load component membership, source provenance, and freshness
  while building the interactive architecture explorer
- downstream tools to check schema, current mapping status, and verification debt
- agents to load `manifest.md` or one named section without reading the full JSON
- planning workflows to follow `manifest.access_paths` and fix-first concerns
- incremental updates to reuse prior run metadata instead of parsing INDEX headers

### Phase 8: Human Visuals

**Progress:** Set `phase_8_visuals` to `"in_progress"` before starting. After writing visual files, add to `artifacts_written`, set to `"complete"`, then set top-level `status` to `"complete"`.

#### 8a. System Overview Visual

Create a diagram of the system in `HUMAN_READ_ONLY_visuals/`, named
`system-overview` with the `.html` extension. If it makes sense, any kind of highlighting that helps to make links clearer is recommended:
- data flows
- async/event flow
- `[condition]` branch point
- `(external)` external system

#### 8b. HUMAN_READ_ONLY_visuals/{component}-flow.html

Per-component visual flow diagrams. One file per component that benefits from visual representation. Not every component needs one - focus on complex flows. Use a kind of diagram that fits the underlying system. You should first think out loud "For this component, [data] flows or is displayed via [method] with [data structure]. Therefore the best visualization type to match this flow is [x]"


## Incremental Update (Default Mode)

This is the default when `/mapcodebase` is invoked without `--nuke-existing-docs`:

1. Read existing `.architecture/manifest.json` to get previous run metadata
   - If manifest missing, fall back to full scan (nothing to update)
   - If `schema_version < 2.0`, STOP and require `/mapcodebase --nuke-existing-docs`
   - If `primer.md` or `access-guide.md` are missing, STOP and require `/mapcodebase --nuke-existing-docs`
   - If `manifest.md` is missing, continue normally and generate it in Phase 7 (v4.0 → v4.1 additive upgrade)
   - If all three accessors exist but any bounded accessor marker is absent or mismatches
     manifest metadata, run the v4.3 whole-accessor refresh in this incremental update;
     existence alone does not pass an upgrade.
2. Resolve current HEAD and compare to manifest hash
   - If equal, no focus/path is requested, and all accessor markers match current
     manifest metadata, ask whether to skip regeneration; otherwise refresh accessors.
3. Run `git diff --name-only {previous_run.git_hash}..HEAD` to find changed files
4. Map changed files to affected components using manifest's `components[]` entries
5. If a changed file owns or defines a shared contract, also mark all listed consumer components as affected
5a. **Verification debt first:** intersect changed files with every open
   `verification_items[].owner_files`. Any intersecting item MUST be re-checked this run
   (resolve with evidence, or downgrade deliberately) — carrying it forward unchanged is
   invalid. This is the rule that prevents "unverified this wave" surviving across scans.
5b. **Contract-aware scoping:** if any changed file participates in a
   `boundary_contracts[]` chain (producer, adapter, consumer, or sink anchor) — or looks
   like a boundary surface (route/handler, RPC/mutation registry, queue/event model,
   webhook, schema validator, wrapper) — force a contracts-explorer rerun over that
   boundary and rebuild its field table. Record affected slugs in
   `manifest.changed_boundary_contracts_since_scan`. A diff-scoped run may NOT leave a
   touched boundary's contract table stale or `unverified`.
5c. **Economic-authority scoping:** if a changed file is a `producer` or `consumer` of
    any Economic Authority Matrix row, or matches the mandatory monetary semantic sweep,
    rebuild that label group's rows and re-run Scan 4. A diff-scoped run may not leave a
    touched label group stale.
6. Re-run only the relevant exploration agents, scoped to changed areas
7. Rebuild `.architecture/.work/discovery/*.md` for any rerun discovery slices before marking Phase 1 complete
8. Rebuild `primer.md`, `access-guide.md`, `INDEX.md`, and any docs for affected components/contracts. Reconcile affected flows into the stable Current Flow Index and domain sections in place; never append a dated/wave delta section. If `concerns.md` will change, do a second lightweight refresh of the concern sections in `primer.md` and `INDEX.md` after Phase 6
   Regardless of source scope, refresh the whole accessor layer from current manifest
   metadata; on a skill-version upgrade, this is mandatory even when no component changed.
9. Run Phase 4 Verification (Part A: Reality Check, Part B: Hazard Detection)
10. Run Phase 5 Pattern Analysis (re-analyze groups that include changed files)
11. Run Phase 6 Findings (re-evaluate findings whose files intersect with changed files, preserve IDs for unchanged findings)
12. Merge updated findings into existing documents without regenerating unchanged sections
13. Rebuild `concerns.md` if any hazards, patterns, findings, or component/runtime states change, then refresh the concern sections in `primer.md` and `INDEX.md`
14. Re-synthesize `concerns[]` and update manifest concern references
15. Run Phase 6f (verification debt + answerability) scoped to changed areas: re-check
    intersecting verification items, re-run answerability tests whose `expected_docs` changed
16. Write updated `manifest.json` with new git_hash, timestamp, and `previous_run`
    referencing the old manifest — preserving foreign sections per the manifest
    co-ownership rule — then validate it and regenerate `manifest.md`

After final manifest rendering, refresh all three accessors from final metadata and run
`validate-component-inventory` plus `validate-accessors` before completion.

## Quality Checks

Before finalizing, verify:
- [ ] `.mapcodebase-progress.json` shows all phases `"complete"` and top-level `status` is `"complete"`
- [ ] If `phase_1_discovery` is `"complete"`, all `.architecture/.work/discovery/*.md` files exist
- [ ] `manifest.json` exists with schema `2.0`, status, components, metrics, and artifacts list
- [ ] `manifest.md` exists, is listed in artifacts, and was regenerated from the final JSON with `architecture_access.py`
- [ ] `architecture_access.py validate-manifest`, `validate-economic-authority`, `validate-flows`, `validate-component-inventory`, and `validate-accessors` pass. The inventory validator proves manifest component paths equal actual docs; the accessor validator proves all three files carry current metadata and bounded-read guidance.
- [ ] Compact-manifest object tables preserve every source field and escape pipes/newlines; scalar arrays render as lists
- [ ] Every file listed in manifest.artifacts[] actually exists
- [ ] `primer.md` exists and is materially smaller than `overview.md`
- [ ] `access-guide.md` exists and matches `manifest.access_paths`
- [ ] `primer.md`, `access-guide.md`, and `INDEX.md` were refreshed from final manifest metadata; their bounded markers match it, so a stale existing guide cannot pass.
- [ ] `concerns.md` exists and matches `manifest.concerns[]` when any actionable concerns were synthesized
- [ ] overview.md is coherent prose, not just bullet points
- [ ] filesystem-map.md covers every top-level directory
- [ ] `flows.md` has a Current Flow Index with exactly one unique row per detailed flow record
- [ ] Flow records are grouped by stable domain/component family; no dated, commit-labelled, wave, or incremental-delta sections were appended
- [ ] Every flow has all 8 fields (TRIGGER, ENTRY, STATUS, STEPS, DATA_IN, DATA_OUT, EXITS_TO, BOUNDARIES)
- [ ] Every runtime/process boundary named in any flow's BOUNDARIES has a Boundary Field Contract table (cross-references.md and/or owning component doc)
- [ ] Every boundary field table has no blank `Absent means` cells — each is filled or `unverified` with a matching `verification_items[]` entry
- [ ] Every operator-facing monetary label has ≥1 Economic Authority Matrix row
- [ ] No generated doc calls any calculator the "sole" or "authoritative" public authority for a label unless the label group is either proven equivalent or carries an open error Concern
- [ ] Every `ECON-*` line maps to a finding + concern
- [ ] No prose "unverified"/"not verified this wave" note exists anywhere in `.architecture/` without a `VER-NNN` citation
- [ ] `boundary_contracts[]`, `verification_items[]`, `answerability_tests[]` present in manifest (empty arrays only if genuinely none)
- [ ] Open high-severity boundary verification items → `status: "partial"` and `freshness_status` ≤ `"caution"` (Phase 6f rule applied)
- [ ] `answerability_pass_rate` recorded; < 0.8 → `status: "partial"`
- [ ] Manifest co-ownership respected: existing `audit` section and foreign `freshness` sub-keys preserved; `freshness.map_git_hash` set to this run's hash
- [ ] Component docs carry the provenance header (Derived from + Verified at + precedence rule)
- [ ] Adapter-dropped / never-accepted boundary fields (defect candidates) appear in findings[] or concerns[]
- [ ] All file:line references are valid (spot-check at least 5)
- [ ] Cross-references are bidirectional (A calls B implies B called_by A)
- [ ] No orphan flows (every flow is reachable or is an entry point)
- [ ] HUMAN_READ_ONLY_visuals/ HTML diagrams render correctly in a browser
- [ ] INDEX.md navigation links all resolve to real files
- [ ] No secret values in any output (only locations and variable names)
- [ ] Runtime claims match code reality (enabled/disabled/partial per Phase 4A)
- [ ] Hazards array present in manifest (empty if none found, per Phase 4B)
- [ ] Components with concurrency hazards have "Concurrency Concerns" section populated
- [ ] Contradictions are recorded in manifest.warnings[]
- [ ] Every file in manifest.artifacts[] verified to exist on disk (Phase 7 artifact verification)
- [ ] `access_paths.general_primer`, `plan_evaluation`, and `component_deep_dive` resolve to real docs
- [ ] Each component has `intent_tags`, `runtime_status`, and `architecture_status`
- [ ] Normalized `components[].doc_path` values exactly equal component docs on disk; directory enumeration is integrity-only, and unknown extras leave the run non-success pending explicit future reconciliation (never silent deletion).
- [ ] Components with drift have `active_consumers` and/or `legacy_consumers` populated
- [ ] `patterns[]` array present in manifest (empty if Phase 5 skipped, per skip condition)
- [ ] Each pattern entry has all required fields (pattern_id, files, description, severity, category)
- [ ] Patterns with severity "warning" or "error" have non-null `concern` and `best_practice` fields
- [ ] No pattern references files not in the Phase 1 inventory
- [ ] If patterns were detected, `patterns.md` exists in `.architecture/`
- [ ] `findings[]` array present in manifest (empty if Phase 6 skipped or failed)
- [ ] Each finding entry has all required fields (finding_id, category, severity, component, files, title, description, confidence, evidence)
- [ ] Findings with severity "warning" or "error" have non-null `suggestion` field
- [ ] No finding duplicates an issue already in hazards[] or patterns[]
- [ ] No finding references files not in the Phase 1 inventory
- [ ] If findings were produced, `findings.md` exists in `.architecture/`
- [ ] Findings respect documented decisions in overview.md (no flagging deliberate choices)
- [ ] `concerns[]` array present in manifest (empty if no actionable concerns were synthesized)
- [ ] Each concern entry has all required fields (concern_id, priority, severity, component, title, summary, recommended_action, files, source_refs, confidence)
- [ ] Every `source_ref` in `concerns[]` resolves to an item in hazards[], patterns[], or findings[]
- [ ] `primer.md` and `INDEX.md` link readers to `concerns.md`

## Integration

After mapping, CLAUDE.md Progressive Disclosure points agents here:
```
| Codebase orientation | Read `.architecture/INDEX.md` for navigation, then `.architecture/primer.md` |
| Architecture/data flow | Read `.architecture/access-guide.md` for the right path |
```

Fresh agents working on specific components should read:
```
.architecture/INDEX.md                              # Navigation
.architecture/primer.md                             # Default initial context
.architecture/structured/components/{relevant}.md   # Deep context
```
