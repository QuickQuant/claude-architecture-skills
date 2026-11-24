# Component: {COMPONENT_NAME}

> Derived from: {file1}, {file2}, ... | Verified at: {GIT_HASH}
> If any derived-from file changed since {GIT_HASH}, trust source over this doc.

## Quick Reference

| Property | Value |
|----------|-------|
| Purpose | {one-line description} |
| Entry | `function()` at file:line |
| Key files | file1, file2 |
| Depends on | {Component A, Component B} |
| Used by | {Component X, Component Y} |
| Runtime status | {implemented/partial/disabled} |
| Architecture status | {active_primary/active_fallback/legacy_active/target_only/deprecated} |

## What This Component Does

{2-3 sentence prose explanation. What problem does it solve? How does it fit into the larger system? Keep this a header, not the payload — the contracts below are the payload.}

## Contracts

{Contracts come FIRST among substantive sections: a planning agent should be able to stop reading after this section. Include only the subsections that apply.}

### Boundary Field Contracts

{REQUIRED whenever a payload this component produces or consumes crosses a runtime/process boundary (HTTP→RPC/mutation, queue, webhook, socket, hook stdio, cross-language call). One table per boundary. `Absent means` is the highest-value column — `unverified` there must have a matching manifest verification item, never a bare prose note.}

Chain: `{producer file:line}` → `{adapter file:line}` → `{consumer file:line}` → sink `{store}`

| Field | Emitted | Adapter forwards | Consumer accepts | Persist | Absent means | Authority | Evidence | Verified |
|-------|---------|------------------|------------------|---------|--------------|-----------|----------|----------|
| `{field}` | always / only-if-{cond} | yes/no/n/a/unverified | yes/no/unverified | required / preserve-on-absent / clear-on-absent / derived / ignored | {meaning of missing field} | producer/consumer/adapter | {file}:{line} | verified/unverified |

### Economic Authority

{REQUIRED when this component owns a row in the Economic Authority Matrix. Copy this
component's source-derived matrix rows and state the disposition for each public label
group; the group must name a canonical executable-economics owner/contract or `none —
CON-NNN`. Do not treat a display-only role or a relabeled raw value as reconciliation.}

| ID | Label | Roles | Price side | Depth basis | Fees included | Annualization | Day rounding | Formula/version | Authority disposition | Reconciliation |
|----|-------|-------|------------|-------------|---------------|---------------|--------------|-----------------|-----------------------|----------------|
| `{economic-site-id}` | `{public label}` | `{roles}` | `{price_side}` | `{depth_basis}` | `{true/false/unknown}` | `{annualization}` | `{day_rounding}` | `{formula_version or formula}` | `{disposition}` | `{status, CON-NNN/evidence}` |

Label-group disposition: `{canonical executable-economics owner/contract, or none — CON-NNN}`

### Type Contracts

| Contract | Purpose | Owner | Consumed By |
|----------|---------|-------|-------------|
| `{TypeName}` | {what it represents} | {file}:{line} | {component/page/API} |

### Data Model / RPC Surface

| Surface | Kind | Key Fields / Operations | Access Boundary |
|---------|------|-------------------------|-----------------|
| `{table_or_rpc}` | table/rpc/query/mutation | `{field1}`, `{field2}` | public/auth/admin/RLS/security-definer |

### Reusable UI Components

| Export | Props / Input Shape | Primary Usage Sites |
|--------|---------------------|---------------------|
| `{Component}` | `{PropType}` | {page1}, {page2} |

## Invariants

{Cross-file truths an agent must not break, with the anchor that proves each. Omit only if the component genuinely has none — most have 2-5. Examples: "X is set once at construction and never flips" ; "writes to Y must hold the lock at Z" ; "config A overrides B overrides default".}

- {Invariant} — evidence: {file}:{line}

## Data Flow

```
IN:  {description of inputs}
     └─> {source} ({file}:{line})

PROCESS:
     ├─> {step 1}
     ├─> {step 2}
     └─> {step 3}

OUT: {description of outputs}
     └─> {destination} ({file}:{line})
```

## Key Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `func1()` | {does X} | {file}:{line} |
| `func2()` | {does Y} | {file}:{line} |

## Common Patterns

### {Pattern Name}

{How this pattern is implemented in this component. Include a brief code-level explanation. Never paste code bodies — reference signatures by anchor.}

## Error Handling

- **{Error type}**: {how handled} at {file}:{line}

## Concurrency Concerns

{Omit this section if no shared mutable state or multi-caller patterns exist in this component. Include it when any function can be triggered by 2+ independent code paths, or when shared state (tokens, credentials, config, connections) is read-written without synchronization.}

| Resource | Callers | Synchronization | Risk |
|----------|---------|-----------------|------|
| `{shared_resource}` | `caller1()`, `caller2()` | {none / mutex at file:line / guard flag} | {what goes wrong} |

## Configuration

| Config | Source | Default | Precedence |
|--------|--------|---------|------------|
| `{NAME}` | {env/file} | {value} | {what overrides what, if layered} |

## Integration Points

**Calls out to:**
- `{Other}.{method}()` - for {purpose}

**Called by:**
- `{Caller}.{method}()` - when {condition}

## Active vs Target

- **Active consumers:** {routes/pages/services currently using this path}
- **Legacy consumers:** {older callers still hitting a deprecated path}
- **Target architecture:** {where the system is trying to converge}
- **Drift note:** {Call out mismatches between live runtime usage and target boundary. Omit if no meaningful drift exists.}

## LLM Notes

{Non-inferable knowledge only — things an agent cannot get by reading the files it is about to open: hidden couplings, why-this-shape decisions, "looks like the entry point but isn't", historical traps. Do not restate signatures or summarize files here.}

- {Note}
- {Note}
