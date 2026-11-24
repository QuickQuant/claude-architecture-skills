# Program map contract

Examples use an invented order-processing service. Replace illustrative names and
source anchors with evidence from the target repository.

## Evidence model

Store five independent kinds of evidence:

1. Architecture source evidence: path, hash, freshness, classification.
2. Source declaration evidence: file, line, class, variable, static category.
3. Composition evidence: class/component and component/subsystem membership,
   including role (`declares`, `uses`, `tests`, `generates`, `supports`).
4. Relationship evidence: direction, mechanism, payload, trigger, cadence,
   guarantees/hazards, source references, and freshness.
5. Workflow evidence: touched architecture IDs plus ordered source-backed steps
   naming the callable, inputs, passing condition, effect, outputs/data objects,
   and source reference.

Never convert a relationship label into evidence. “Uses” is insufficient by
itself; say what crosses the boundary and how.

## Abstraction model

Use these levels even when the project has only one primary application system:

| Level | Answers | Typical selection result |
|---|---|---|
| System | What does the project do and what external systems touch it? | purpose, boundary, external actors, high-level arrows |
| Subsystem | What cohesive responsibility moves data through the system? | responsibility, components, aggregated inputs/outputs |
| Component | Which implementation capability participates? | key files/modules, classes declared/used, contracts, component edges |
| Class | Which source declaration carries behavior/state? | bases, properties, variables, memberships, source |
| Callable | Which behavior moves or transforms the data? | signature, parameters, guards, calls, visible mutations, returns, source |
| Variable | What state/schema field is visible statically? | type, kind, assignment context, source line |

A class may belong to several components. A component may support several
subsystems. Use primary containment for layout and explicit cross-links for the
rest.

## Callable relationship model

Containment normally ends at the callable. Unless source declares a nested
callable/class, render the callable as a behavior boundary with distinct
relationship groups:

| Group | Meaning | Never imply |
|---|---|---|
| Inputs | Parameter bindings with name, annotation, default, passing mode, and observed body-use expressions | ownership, retention, a copied value, or runtime frequency |
| Invokes / constructs | Outgoing statically resolved project targets | child membership or runtime certainty |
| Guards / branches | Conditions controlling observed source paths | complete runtime branch coverage |
| State effects | Visible assignments and mutations | persistence beyond the call without evidence |
| Outputs | Return annotation and observed return expressions | every runtime value shape |
| Called by | Statically identified inbound callers | runtime frequency |

Use **outgoing call expressions** for AST `Call` nodes inside the callable,
**resolved project targets** for unique statically linked destinations, and
**inbound callers** for `called_by`. Do not label outgoing expressions “call
sites” without direction because readers reasonably interpret that as callers.

Python parameter binding passes references to objects; it does not by itself
copy a list, configuration object, or record. A slice may create a new container
while retaining references to its elements. Show copy/ownership/storage only
when the body contains direct evidence such as a constructor, `.copy()`,
`dict(...)`, slicing, serialization, or assignment into retained state.
Parameter-use records are syntactic reads such as `params.shipping_fee`,
`order.received_at`, `orders=orders`, or `item_index=order_index`, each with a source
line and context. They explain why an input participates without pretending to
measure runtime frequency or establish a higher-level semantic role not present
in source.

## Standalone orientation record

The HTML page must not depend on a separate overview report for meaning. Its
model carries a short narrative guide with:

- a two- or three-paragraph project explanation;
- a numbered end-to-end operating loop whose stages link to exact subsystems;
- external/system boundaries with concise roles;
- durable inputs, outputs, and evidence products;
- question-led “start here” links to exact systems, subsystems, components, or
  workflow steps;
- architecture evidence paths used to derive the explanation.

The guide is prose and process, not a metric-card dashboard. Every link target
must validate against the same canonical IDs used by the explorer.

## Renderer input and model schema

`scripts/render_program_explorer.py` combines the authored `--model` JSON with
two independent ledgers: `--class-ledger` from `inventory_program_map.py`
(architecture corpus and class declarations), and `--symbol-ledger` from
`inventory_program_symbols.py` (Python callables, parameter uses, calls, and
modules). It fills `assets/program-explorer.html` with `#explorer-data`; do not
hand-author a different embedded format for `validate_program_explorer.py`.

```bash
python3 -B <skill-dir>/scripts/render_program_explorer.py \
  --model <project-root>/.reports/architecture-model.json \
  --class-ledger <project-root>/.reports/architecture-map-ledger.json \
  --symbol-ledger <project-root>/.reports/architecture-symbol-ledger.json \
  --output <project-root>/.reports/architecture.html \
  --architecture-read-count <actual-files-read> --strict
```

The five value-taking options above are required. All paths identify files;
`--architecture-read-count` is an integer from the protocol's actual read
checklist. `--strict` is a flag: detected guide/workflow reference errors cause
exit 1 before output is written. Without it, errors are embedded in
`coverage.validation_errors`. `--help` prints usage. Strict rendering is not a
complete schema/coverage validator: edge endpoints, membership, coverage, and
interaction integrity still require the contract checks and browser validator.

Use [model.example.json](model.example.json) as a minimal complete authored model.
It describes an invented four-module layout (`src/orders/__init__.py`,
`models.py`, `pricing.py`, and `service.py`), with `Order` declared at models
line 1, `calculate_total` at pricing line 4, and `accept_order` at service line 5.
Those are illustrative anchors, not discovery results. Replace them with exact
ledger IDs for the repository being mapped. Generate both ledgers from the
same source state before rendering.

The following schema comes from the renderer, template reads, and interaction
validator. Types are JSON types; supply the named arrays even when empty.

| Object | Fields and behavior |
|---|---|
| Model root | `project: object`, `systems: array`, `subsystems: array`, `components: array`, `system_edges: array`, `subsystem_edges: array`, `component_edges: array`, `workflows: array`; `guide: object` provides the required standalone orientation. |
| `project` | `name: string` for the visible brand; `title: string` for the document title. |
| `systems[]` | `id`, `name`, `kind`, `summary`: strings. The first `kind: "primary"` system (otherwise the first system) supplies the project breadcrumb root and contains the internal subsystems in this template. External systems use another descriptive `kind`, such as `external`. `x`, `y`: finite numbers positioning the node in the system diagram of the simpler atlas (`render_program_map.py`); that renderer draws `NaN` coordinates and `validate_browser.py` fails without them. The explorer does not use them, so supply them whenever the atlas may be rendered. |
| `subsystems[]` | `id`, `name`, `summary`: strings; `x`, `y`: finite numbers positioning a 190×80 node in the 1280×660 map. |
| `components[]` | `id`, `name`, `kind`, `summary`, `subsystem`, `architecture_source`: strings; `subsystem` references an existing subsystem; `key_files: string[]`; `class_rules: object[]`. Do not author generated `classes`, `symbols`, or `modules` lists: rendering replaces them with ledger matches. |
| `class_rules[]` | Optional `file` and `name` strings are Python `re.search` patterns; both must match when supplied. Missing patterns impose no restriction. `role: string` defaults to `member`. The same rules classify **classes, callables, and modules**, despite the field name. `name` matches `qualified_name` when present, otherwise `name` (a module's file stem). Match modules with file rules when a class-name pattern would exclude them. All matching roles/components are retained; no match stays visibly unclassified. |
| `guide` | `title: string`; `overview: string[]` for prose paragraphs; `evidence: string[]`; `operating_loop`, `boundaries`, `start_here`: arrays of the records below. |
| `guide.operating_loop[]` | `number: string or number`, `title: string`, `summary: string`, `target: object`. |
| `guide.boundaries[]`, `guide.start_here[]` | `label: string`, `note: string`, `target: object`. |
| Guide `target` | `type: "system"`, `"subsystem"`, `"component"`, `"class"`, or `"symbol"`, plus that record's `id: string`; or `type: "workflow"`, workflow `id: string`, optional zero-based `step: integer` (defaults to 0). Every target must exist. |
| `*_edges[]` | Relationship records defined below; `level` must match the containing array (`system`, `subsystem`, or `component`). IDs must be globally unique across all edge arrays; endpoints reference records at that level. Optional `via: number[][]` supplies `[x,y]` routing points and `label_position: number[]` supplies `[x,y]` for a subsystem arrow label. |
| `workflows[]` | `id`, `name`, `summary`, `status`: strings; `touched: object`; `steps: object[]`. The current template requires at least one workflow with at least one step: playback and the default overlay read the selected workflow directly. Empty workflow support in some validator branches does not make the template support an empty player. |
| Workflow `touched` | `systems`, `subsystems`, `components`, `classes`, `symbols`: arrays of canonical IDs, representing the full footprint, independent of containment. |
| Workflow `steps[]` | `id`, `title`, `kind`, `summary`, `symbol`, `condition`, `effect`, `source`: strings; optional `source_guard: string`; `subsystems`, `components`: arrays of existing IDs; `input`, `output`, `objects`: string arrays. `symbol` references the exact callable ID. `objects` names workflow data, not containment IDs. |

Authored IDs are stable, unique strings within each record kind. Source class
IDs are `file:line:qualified_name` from the class ledger; callable IDs are the
symbol ledger's `id` verbatim; module IDs are repository-relative file paths.
Do not invent source IDs from display names. The renderer reconciles the two
ledgers' spelling of function-local class references by file and line.

The renderer supplies `classes`, `symbols`, `modules`, memberships, component
indexes, and `coverage`, including architecture read/total counts and ledger
hashes. Preserve all recovered declarations; the authored model adds meaning
rather than replacing ledger facts. Check `errors: []` in renderer stdout,
then run the full contract and browser gates.

`scripts/render_program_map.py` produces the simpler class/variable atlas with
`#map-data`, using `--model`, `--ledger` (the class/architecture ledger),
`--architecture-read-count`, and `--output`. It also accepts `--strict`, and
`--validate-only` checks without requiring `--output`. Use that renderer when
class/variable navigation alone is requested. It does not provide the callable
relationships or workflow player required for the full explorer. Its browser
gate is `validate_browser.py --port <port>` after loading the rendered map in
the launched Chrome tab; the explorer gate is
`validate_program_explorer.py --port <port> --url <file-url>`.

## Relationship record

Every clickable arrow must resolve to a record equivalent to:

```json
{
  "id": "stable-edge-id",
  "level": "system|subsystem|component",
  "from": "source-id",
  "to": "destination-id",
  "label": "short human label",
  "trigger": "event or caller",
  "mechanism": "HTTP, direct call, file handoff, event stream, import, etc.",
  "payload": ["named contracts or data"],
  "guarantees": ["ordering, atomicity, validation, concurrency behavior"],
  "hazards": ["known failure modes or drift"],
  "evidence": ["path:line or architecture source"],
  "freshness": "current|stale|mixed|unverified"
}
```

Aggregate subsystem edges from component edges where possible. Keep a manual
top-down explanation only when it is explicitly labeled as interpretation.

## Workflow record

Every selectable workflow must carry a stable footprint and ordered successful
trace equivalent to:

```json
{
  "id": "fill-received-event",
  "name": "Order processing · fill received",
  "summary": "Resolve a received fill and construct its event record.",
  "status": "source-backed happy path",
  "touched": {
    "systems": ["order-service"],
    "subsystems": ["intake", "pricing", "fulfillment"],
    "components": ["order-intake", "pricing-engine", "event-store"],
    "classes": ["app/orders/events.py:99:FillReceivedEvent"],
    "symbols": ["app/orders/router.py:171:OrderRouter.route"]
  },
  "steps": [{
    "id": "event-01",
    "title": "Resolve the event shape",
    "kind": "method",
    "summary": "Inspect the received event and choose its successful branch.",
    "symbol": "app/orders/router.py:171:OrderRouter.route",
    "subsystems": ["pricing"],
    "components": ["pricing-engine"],
    "input": ["OrderEventType.FILL_RECEIVED", "order_id"],
    "condition": "The router has received a successful fill with an order identifier.",
    "source_guard": "event_type == OrderEventType.FILL_RECEIVED and order_id is not None",
    "effect": "Construct FillReceivedEvent with normalized order metadata",
    "output": ["FillReceivedEvent"],
    "objects": ["FillReceivedEvent"],
    "source": "app/orders/router.py:197"
  }]
}
```

Workflow membership is orthogonal to containment: it is an overlay, never a
replacement architecture tree. Every touched ID and step symbol must resolve.
Trace the successful branch first; display excluded failure branches as an
explicit limit rather than silently implying they do not exist.
Write `condition` for the reader (“why this step runs”), not as unexplained
source jargon such as “x is truthy.” When the literal guard is useful, preserve
it separately as optional `source_guard` evidence.

## Visual grammar

- Use a left-to-right or top-to-bottom high-level flow.
- Keep the default system view under nine visible nodes.
- Use subsystem blocks as the main expansion unit and let a selection split in
  place into constituents rather than replacing the architecture context.
- Use consistent node colors by subsystem, not by arbitrary status.
- Use line style for semantics: solid runtime data/control, dashed optional or
  asynchronous, dotted evidence/provenance.
- Place arrow labels on opaque backing plates; make the label or a wider
  invisible hit target clickable.
- Avoid crossing edges. If an edge must cross, route it orthogonally and keep
  its label close to the source or destination.
- Use semantic HTML drawers/cards for dense class and variable details.
- Keep workflow emphasis to the touched set plus one current-step focal signal;
  dim the rest without erasing the full architecture.

## Interaction state

Represent selection in the URL hash:

```text
#level=system
#level=subsystem&id=pricing
#level=component&id=pricing-engine
#level=class&id=app/orders/router.py:127:OrderRouter
#mode=workflow&workflow=fill-received-event&step=5&type=symbol&id=app/orders/router.py:171:OrderRouter.route
```

Changing a level keeps the closest valid ancestor selected. Browser navigation
must restore the selection. Provide a visible “copy link” action when practical.

## Coverage invariants

The rendered page must expose machine-checkable counters or embedded metadata:

- `architecture_files_total == architecture_files_read == architecture_files_rendered`
- `classes_scanned == classes_rendered`
- `variables_scanned == variables_rendered`
- `python_symbols_scanned == python_symbols_searchable`
- `call_sites_scanned == declared_call_site_count`
- `unmapped_classes == 0`
- `components_without_subsystem == 0` or visibly listed as unresolved
- `edges_without_details == 0`
- referenced IDs all exist at their declared level
- workflow touched IDs and every step symbol resolve

Keep stale architecture and current source counts separate. Never present a
mapped-commit metric as current HEAD truth.

## Static-analysis limits

The inventory script recovers explicit class fields, `self.x`/`cls.x`
assignments, literal `setattr(self, "x", ...)`, and properties. It cannot prove:

- nonliteral `setattr` names;
- fields injected by metaclasses/decorators/framework plugins;
- monkey-patched runtime state;
- dynamically generated classes;
- function-local data not represented by a class.

Display this limitation in the page. A runtime-instrumented map is a different
scope.

The callable ledger uses Python AST evidence. It cannot prove dynamic dispatch,
reflection, monkey patching, dependency-injection targets, or runtime path
frequency, and it does not cover TypeScript/JavaScript callables unless a
separate language ledger is added. Resolved and unresolved call expressions must stay
visually distinct.

## Acceptance checklist

- Source ledger hash re-check passes.
- Protocol contains all mistakes and method changes from the run.
- Architecture read checklist is complete.
- Every class appears once in the canonical class index.
- Cross-memberships do not duplicate the canonical class record.
- All variables are accessible from the canonical class detail.
- Every component lists key function-only modules as well as classes.
- The standalone page begins with a cohesive project orientation: purpose,
  operating loop, external boundaries, durable data products, and curated
  question-led links into exact architecture/workflow records.
- System and subsystem maps are understandable before any expansion.
- Selecting a system, subsystem, or component opens a contextual narrative that
  explains its place in the whole plus linked inbound/outbound relationships;
  a one-sentence summary and composition count alone do not pass.
- Clicking an arrow opens the exact relationship record.
- Clicking a component opens member classes and files.
- Clicking a class opens variables and source evidence.
- Clicking a callable opens its signature, parameters, conditions, resolved
  project targets, visible state changes, returns, and uncertainty statement.
- A callable view labels parameters as typed inputs and callees as outgoing
  relationships, never as constituent objects; it distinguishes outgoing call
  expressions, resolved targets, and inbound callers.
- Clicking an input exposes bounded source expressions showing how the callable
  reads or forwards it; type and passing mode alone are not sufficient.
- Parameter binding never appears as proof that an argument was copied, stored,
  or owned; explicit copy/retention evidence is shown separately when present.
- Selecting a workflow lights its entire footprint without hiding the complete
  architecture; changing steps moves the focal highlight and inspector.
- The player never autoplays; previous/play/pause/next work, and every step
  exposes input, passing condition, action, output, and source evidence.
- Search can reach an item at every level.
- Keyboard and pointer behavior agree.
- Narrow viewport has no page-level horizontal scroll.
- Print view includes the source/freshness ledger.
- A fresh browser target reports no console errors through the normal drill-down
  path; SVG connector paths contain no `NaN`/invalid geometry.
- The interaction-polish post-pass (using optional `make-interfaces-feel-better`
  guidance when installed) is recorded in the
  protocol, including reduced-motion and exact-property transition checks.
