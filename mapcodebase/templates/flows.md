# Structured Flows

> Current-state flow catalog and detailed records. Generated: {TIMESTAMP} | Git: {GIT_HASH}
> If a derived source changed after this hash, trust source over this document.

## Access

Read the index first. Load only a matching detailed record unless the task genuinely
requires the complete flow corpus.

```bash
python3 <skill-dir>/scripts/architecture_access.py flow-index
python3 <skill-dir>/scripts/architecture_access.py flow {flow-id}
```

## Current Flow Index

| ID | Domain | Category | Status | Trigger | Entry | Components | Boundaries | Detail |
|---|---|---|---|---|---|---|---|---|
| {stable-kebab-case-id} | {stable domain/component family} | {lifecycle/data-processing/background/error-recovery} | {implemented/partial/disabled} | {short trigger} | {symbol at file:line} | {component IDs; semicolon-separated} | {boundary IDs or none} | [record](#flow-{stable-kebab-case-id}) |

Index rules:

- One row per detailed flow record; IDs are unique and stable across incremental runs.
- Keep cells to one line. Do not copy steps, payloads, or narrative into the index.
- Group and filter by stable domain/component ownership, never by scan date, commit,
  treatment wave, or incremental-delta chronology.
- On incremental updates, revise the current row and detailed record in place. Remove
  superseded descriptions once no active path uses them; source control is history.

## Detailed Flow Record Schema

Every significant flow has all eight fields below. If a field does not apply, write
`none`. `BOUNDARIES` links each runtime/process crossing to its Boundary Field Contract
table in `cross-references.md` or the owning component doc. A crossing without a
contract table is a coverage gap.

```text
TRIGGER: what initiates this flow
ENTRY: function(file:line)
STATUS: implemented|partial|disabled
STEPS:
  1. action -> next_action
  2. action [condition] -> branch_a | branch_b
DATA_IN:
  - param_name: type (description)
DATA_OUT:
  - return_value: type (description)
EXITS_TO: destination flow ID(s)
BOUNDARIES: boundary ID(s) crossed, or none
```

## {Stable Domain or Component Family}

### FLOW: {stable-kebab-case-id}

```text
TRIGGER: {what starts it}
ENTRY: {function}() ({file}:{line})
STATUS: {implemented|partial|disabled}

STEPS:
  1. {step} -> {next}
  2. {step} [condition] -> {branch_a} | {branch_b}

DATA_IN:
  - {param}: {type} ({description})

DATA_OUT:
  - {result}: {type} ({description})

EXITS_TO: {destination flow ID(s) or none}
BOUNDARIES: {boundary ID(s) or none}
```

{Repeat stable domain headings and detailed records. Do not append dated delta sections.}
