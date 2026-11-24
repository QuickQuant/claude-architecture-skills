# Explore: Contracts

Map the contract surfaces that planning workflows and fresh agents need before reading source in depth.

## What to Find

1. **Type Contracts**
   - Exported/shared interfaces, types, dataclasses, schemas, enums
   - Key fields that other components depend on
   - Important absences or caveats ("has public_order_id but not customer_note")
   - Which files/components own the contract and which consume it

2. **API and Message Contracts**
   - Request/response payload shapes for routes, actions, mutations, RPCs, webhooks
   - Event/message shapes that cross component boundaries
   - Public vs authenticated vs internal-only surfaces

3. **Data Model / RPC Surface**
   - Tables, collections, ORM models, migrations, RPCs, queries, mutations
   - Key columns/fields, foreign-key-like links, indexes, and constraints when visible
   - Access boundaries: RLS, admin-only clients, service-role access, security-definer RPCs

4. **Reusable UI Component Contracts**
   - Reusable exported UI components and their prop types/interfaces
   - Primary usage sites
   - Whether the component is read-only, editable, or coupled to specific data shapes

5. **Boundary Field Contracts (REQUIRED — highest value)**
   - For every payload that crosses a runtime/process boundary (HTTP handler → RPC/mutation,
     queue/event bus, webhook, socket, CLI↔daemon, hook stdin/stdout, cross-language calls):
     enumerate the FIELD-LEVEL contract, one row per field.
   - Each row: emitted condition (always / conditional-on-what), whether each intermediate
     adapter/wrapper forwards it, whether the consumer validates/accepts it, persistence
     behavior (required / preserve-on-absent / clear-on-absent / derived / ignored),
     ABSENT SEMANTICS (what a missing field means — capability not present? old build?
     failure? — this is the highest-value cell), and which side is authoritative.
   - Read EVERY hop of the chain (producer, each adapter, consumer, sink). If you cannot
     read a hop this run, mark the affected cells `unverified` — these become tracked
     verification debt, not footnotes. Never guess a cell.
   - Fields accepted by the consumer but never forwarded by an adapter (or emitted but
     never accepted) are DEFECT CANDIDATES — flag them explicitly in `notes`.

6. **Monetary Metric Calculation Sites (REQUIRED)**
   - Find every distinct source calculation that produces a value shown or used under a
     public/operator-facing monetary label. One output row represents one calculation
     site, not one label.
   - Read every calculator you find, record the semantic tuple from SOURCE (never from
     a comment or an existing architecture doc), and follow each value forward through
     display → selection → planner/ladder → gateway start/arm → persisted/locked/replay
     state.
   - A version/formula field that is emitted but never read downstream is a defect
     candidate; flag it in notes.

## Output Format

Examples use an invented order-processing service. Replace names and evidence
anchors with facts from the target repository.

```
TYPE_CONTRACTS:
  - name: OrderSummaryEntry
    owner: frontend/src/lib/order-contract.ts:12
    consumed_by:
      - frontend/src/lib/order-service.ts
      - frontend/src/components/order-table.tsx
    key_fields:
      - entity_id
      - display_name
      - item_count
      - public_order_id
    caveats:
      - missing customer_note

API_CONTRACTS:
  - surface: GET /api/v1/orders/[orderId]
    location: frontend/src/app/api/v1/orders/[orderId]/route.ts:1
    request_shape: orderId path param
    response_shape: order viewer payload
    access: public|auth|internal

DATA_MODEL_SURFACES:
  - surface: orders
    kind: table|collection|model|rpc|query|mutation
    owner: db/migrations/20260101_orders.sql:1
    key_fields:
      - id
      - customer_id
      - label
      - user_id
    access_boundary: public|auth|admin|RLS|security-definer
    readers_writers:
      - frontend/src/app/customers/[customerId]/orders/[orderId]/page.tsx
      - frontend/src/app/api/v1/orders/[orderId]/route.ts

UI_COMPONENT_CONTRACTS:
  - export: OrderViewer
    location: frontend/src/components/order-viewer.tsx:1
    props: OrderViewerProps
    usage_sites:
      - frontend/src/app/orders/[orderId]/page.tsx
      - frontend/src/app/customers/[customerId]/orders/[orderId]/page.tsx
    notes:
      - read-only viewer

BOUNDARY_FIELD_CONTRACTS:
  - boundary: worker-heartbeat            # stable slug
    producer: worker/src/heartbeat.ts:80
    adapters:
      - app/api/heartbeat.ts:40            # HTTP wrapper; omit if direct
    consumer: app/workers/accept.ts:60    # validator/handler
    sink: workers table (store.patch at app/workers/accept.ts:90)
    fields:
      - field: inventoryReaderHealthy
        emitted: only if this.inventoryReader set (fixed at construction)
        adapter_forwards: yes              # yes|no|n/a|unverified
        consumer_accepts: yes (v.optional(v.boolean()))
        persistence: preserve-on-absent
        absent_means: process built without inventory reader (NOT "inventory reader failed")
        authority: producer
        evidence: [worker/src/heartbeat.ts:80, app/api/heartbeat.ts:48, app/workers/schema.ts:12]
        verification: verified            # verified|unverified
      - field: pending_counts
        emitted: always
        adapter_forwards: no               # DEFECT CANDIDATE: dropped by wrapper
        consumer_accepts: yes
        persistence: clear-on-absent
        absent_means: never arrives via HTTP path (defect)
        authority: producer
        evidence: [app/api/heartbeat.ts:40-54]
        verification: verified
    notes:
      - wrapper drops pending_counts/pending_units/replica_lag_ms

MONETARY_CALCULATION_SITES:
  - id: apr-pricing-simple365
    label: APR
    aliases: [annualizedRoiPercent, aprPct]
    metric_kind: apr
    roles: [display, selection]
    component: pricing-engine
    producer: app/pricing/apr.ts:80
    consumers: [app/orders/summary.ts:40]
    price_side: ask
    price_source: pricing top-of-book cache, snapshot timestamp
    depth_basis: one_level
    fees_included: false
    fee_schedule: null
    horizon_source: market close timestamp
    annualization: simple_365
    day_rounding: fractional
    formula: spreadPercent * 365 / fractionalDaysToClose
    formula_version: simple365GrossV1
    version_handling: emitted
    authority_disposition: conflicting
    reconciliation:
      status: concern
      concern_id: CON-001
      evidence: [app/orders/confirm.tsx:120-134]
    verified_at_git: abc1234
```

Notes:
- Record a version/formula field emitted but never read downstream as a defect candidate.

## Search Strategy

1. Search for exported type/interface/schema definitions:
   - `export interface`, `export type`, `z.object`, dataclasses, pydantic models, protobuf/message defs
   - SQL migrations, schema files, ORM model definitions, Supabase/Convex/Prisma schemas
2. Trace where those contracts are imported or referenced
3. Identify API boundaries:
   - route handlers, RPC definitions, webhook handlers, mutations/actions
4. Search reusable UI surfaces:
   - exported TSX components, props types, shared component directories
5. Record only contract-relevant fields and boundaries, not full implementation bodies
6. For boundary field contracts: find the runtime seams first (HTTP servers/clients,
   RPC/mutation registries, queue producers/consumers, webhook handlers, socket protocols,
   hook stdio), then trace ONE payload at a time through every hop. Prioritize boundaries
   where producer and consumer live in different languages/runtimes/processes — that is
   where silent field drops and absent-semantics bugs live.
7. Run a mandatory semantic sweep over identifiers and labels: `apr`, `roi`,
   `annualized`, `annualised`, `return`, `yield`, `spread`, `cost`, `fee`, `rebate`,
   `lock`, `locked`, `pnl`, `profit`, `edge`, `expiry`, `daysTo`, `horizon`,
   `*FormulaVersion`, `*_VERSION`. Read every calculator found by this sweep and trace
   each produced value through display, selection, planner/ladder, gateway start/arm,
   and persisted/locked/replay state.

## Scope

Target directory: {TARGET_DIR}

Focus on architecturally meaningful contracts that affect planning, modification, or access control. The output will feed component docs, cross-references.md, primer.md, and manifest access metadata.
