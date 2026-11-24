# Explore: Data Flow

Trace how data flows through this codebase from sources to sinks.

## What to Find

1. **Data Sources (Inputs)**
   - External API calls (fetch, axios, http clients, SDK calls)
   - Database reads (queries, subscriptions)
   - File reads (config, data files)
   - WebSocket/streaming incoming messages
   - User input / request bodies
   - Environment variables / config loading

2. **Data Transformations**
   - Parsing (JSON, XML, protobuf, etc.)
   - Validation / sanitization
   - Mapping / type conversion functions
   - Aggregation / computation
   - Serialization for output

3. **Data Buffering/Batching**
   - Queues (in-memory or external)
   - Buffers with flush logic
   - Batch accumulators (collect N items, then process)
   - Caches (what's cached, TTL, invalidation)

4. **Data Sinks (Outputs)**
   - External API calls (POST, PUT, mutations)
   - Database writes (inserts, updates, mutations)
   - File writes (logs, exports)
   - WebSocket/streaming outgoing messages
   - Response bodies (HTTP responses)
   - Metrics / monitoring

## Output Format

For each significant data path:

```
PATH: descriptive_name
SOURCE: where data originates (file:line)
TRANSFORMS:
  1. function_name (file:line) - what it does to the data
  2. function_name (file:line) - what it does to the data
SINK: where data ends up (file:line)
DATA_SHAPE: describe the data structure at entry and exit
NOTES: buffering, async patterns, error handling, retry logic
```

## Search Strategy

1. Start from entry points and trace forward through function calls
2. Look for I/O patterns:
   - `fetch`, `axios`, `requests`, database clients
   - `.json()`, `.parse()`, `.stringify()`, `.serialize()`
   - `.map()`, `.filter()`, `.reduce()`, comprehensions
   - `.push()`, `.append()`, `.add()`, `buffer`, `queue`
   - `.send()`, `.write()`, `.emit()`, `.mutate()`
3. Follow callback chains, promise flows, and async/await patterns
4. Identify where data crosses component boundaries

## Scope

Target directory: {TARGET_DIR}

Focus on architecturally significant data paths. Skip trivial internal variable passing. The output will be used to build flows.md, cross-references.md, and the Data Flow sections of component docs.
