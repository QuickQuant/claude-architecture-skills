# Cross References

> Call graphs, data paths, and dependency lookups.
> Generated: {TIMESTAMP} | Git: {GIT_HASH}

## Function Call Graph

### {Component Name}

```
function_a() (file:line)
  ├── calls: function_b(), function_c()
  ├── called_by: main()
  └── async: yes/no

function_b() (file:line)
  ├── calls: helper_x()
  ├── called_by: function_a(), function_z()
  └── async: yes/no
```

## Data Path Summary

```
DATA_PATH               SOURCE              TRANSFORMS          SINK
──────────────────────────────────────────────────────────────────────────
{path_name}             {source}            {transform list}    {sink}
```

## Message Formats

### {Protocol/API Name}

```
MESSAGE_TYPE            DIRECTION   FORMAT                  USED_BY
──────────────────────────────────────────────────────────────────────────
{type}                  {in/out}    {shape}                 {function()}
```

## Boundary Field Contracts

> One table per runtime/process boundary (HTTP→mutation, queue, webhook, socket, hook stdio).
> `Absent means` is the highest-value column — never leave it blank; write `unverified` and
> register a verification item instead. Rows where an adapter drops a consumer-accepted field
> are defect candidates: flag them in concerns/findings, don't just record them.

### {boundary-slug}: {Producer} → {adapter(s)} → {Consumer}

Chain: `{producer file:line}` → `{adapter file:line}` → `{consumer file:line}` → sink `{table/file/store}`

| Field | Emitted | Adapter forwards | Consumer accepts | Persist | Absent means | Authority | Evidence | Verified |
|-------|---------|------------------|------------------|---------|--------------|-----------|----------|----------|
| `{field}` | always / only-if-{cond} | yes/no/n/a/unverified | yes/no/unverified | required / preserve-on-absent / clear-on-absent / derived / ignored | {meaning of a missing field} | producer/consumer/adapter | {file}:{line} | verified/unverified |

## Economic Authority Matrix

> One table per public monetary label group. Each row is a distinct calculation site;
> preserve the source-derived price, fee, depth, time, formula, and version semantics.
> The matrix must name a canonical executable-economics owner/contract for the group or
> state `none — CON-NNN`; never paper over a split by relabeling a raw value.

### {exact-public-label}

| ID | Label | Aliases | Metric kind | Roles | Component | Producer | Consumers | Price side | Price source | Depth basis | Fees included | Fee schedule | Horizon source | Annualization | Day rounding | Formula | Formula version | Version handling | Authority disposition | Reconciliation status | Concern ID | Reconciliation evidence | Verified at git |
|----|-------|---------|-------------|-------|-----------|----------|-----------|------------|--------------|-------------|---------------|--------------|----------------|---------------|--------------|---------|-----------------|------------------|-----------------------|-----------------------|------------|-------------------------|-----------------|
| `{id}` | `{label}` | `{aliases}` | `{metric_kind}` | `{roles}` | `{component}` | `{file}:{line}` | `{file}:{line}` | `{bid/ask/mid/last/mixed/unknown}` | {source/cache/timestamp} | `{one_level/book_walk/target_size/fill_weighted/unknown}` | `{true/false/unknown}` | `{schedule or null}` | {close source} | `{simple_365/simple_360/compound/none/unknown}` | `{fractional/ceil/floor/round/clamp_min_1/unknown}` | {expression or canonical implementation} | `{formula_version or null}` | `{emitted/accepted/rejected/retired/dropped/n/a}` | `{canonical/derived_equivalent/raw_signal_only/conflicting/unknown}` | `{proven_equivalent/concern/none}` | `{CON-NNN or null}` | `{file}:{line}` | `{short git hash}` |

Disposition: `{canonical executable-economics owner/contract, or none — CON-NNN}`

## Type Contracts

```
CONTRACT                OWNER                CONSUMED_BY              NOTES
────────────────────────────────────────────────────────────────────────────────
{TypeName}              {file}:{line}        {component, component}   {purpose / missing fields / caveat}
```

## Data Model / Access Boundaries

```
SURFACE                 KIND      OWNED_BY            READERS/WRITERS         ACCESS
────────────────────────────────────────────────────────────────────────────────────────
{table_or_rpc}          {table}   {component}         {component/component}   {public/auth/admin/RLS}
```

## Hub Files

Files imported by many others (high-impact change targets):

```
FILE                    IMPORTED_BY_COUNT   EXPORTS
──────────────────────────────────────────────────────────────────────────
{file}                  {count}             {what it exports}
```

## Shared Utilities

```
UTILITY                 FILE:LINE           USED_BY (count)
──────────────────────────────────────────────────────────────────────────
{function}()            {file}:{line}       {N} files
```

## External Dependencies

```
PACKAGE                 USED_FOR            KEY_USAGE_SITES
──────────────────────────────────────────────────────────────────────────
{package}               {purpose}           {function} ({file}:{line})
```

## Config Sources

```
CONFIG                  SOURCE              ACCESSED_BY
──────────────────────────────────────────────────────────────────────────
{name}                  {env/file/etc.}     {file}:{line}, {file}:{line}
```
