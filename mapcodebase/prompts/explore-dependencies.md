# Explore: Dependencies

Map the dependency graph: what imports what, shared code, external packages, and configuration.

## What to Find

1. **Internal Dependencies**
   - Which files import which (build the import graph)
   - Circular dependency risks
   - Hub files (imported by 5+ others - these are high-impact change targets)
   - Leaf files (import nothing internal - these are safe to modify)
   - Layer violations (if any architectural layering exists)

2. **Shared Code**
   - Utility functions used across multiple modules
   - Base classes / abstract classes / mixins
   - Common constants and enums
   - Shared helpers that are NOT already first-class contracts in `explore-contracts.md`

3. **External Packages**
   - Key npm/pip/cargo packages and their role in the architecture
   - Framework dependencies (what framework, which features used)
   - SDK/client libraries for external services
   - Dev dependencies that affect build/test

4. **Configuration**
   - Config file loading (where, how, what format)
   - Environment variable access (which vars, where accessed)
   - Feature flags (how implemented, where checked)
   - Secrets management (how secrets are loaded, NOT the secrets themselves)

## Output Format

```
DEPENDENCY_GRAPH:

file_a.ts
  imports: file_b.ts, file_c.ts, lodash
  imported_by: main.ts, handler.ts

file_b.ts
  imports: utils.ts
  imported_by: file_a.ts, file_d.ts

HUBS: (files imported by 5+ others)
  - utils.ts (imported by 12 files)
  - types.ts (imported by 8 files)

SHARED_UTILITIES:
  - formatDate() in utils.ts - used by: file_a, file_b, file_c
  - parseConfig() in config.ts - used by: main, worker

EXTERNAL_PACKAGES:
  - lodash: used for _.debounce (file_a:20), _.merge (file_b:45)
  - ws: WebSocket client (websocket-base.ts)
  - convex: backend functions (convex/*.ts)

CONFIG_SOURCES:
  - .env.local loaded by: config.ts:10
  - ENV.DATABASE_URL accessed by: db.ts:5, migrate.ts:12

ARCHITECTURAL_LAYERS: (if identifiable)
  - Layer 1 (presentation): files in src/components/
  - Layer 2 (business logic): files in src/services/
  - Layer 3 (data access): files in src/db/
  - Violations: src/components/Dashboard.tsx directly imports from src/db/
```

## Search Strategy

1. Parse import statements:
   - `import ... from` / `from ... import`
   - `require(...)` / `importlib.import_module()`
   - Dynamic imports (`import()`, `__import__()`)
   - Re-exports (`export { ... } from`)

2. Find hub files:
   - Count how many files import each file
   - Identify utility/common/shared directories
   - Look for barrel files (index.ts that re-exports)

3. Trace external package usage:
   - Read package.json / pyproject.toml / Cargo.toml dependencies
   - For key packages, search for import and note specific functions/classes used
   - Distinguish runtime vs dev dependencies

4. Map config access:
   - `process.env` / `os.environ` / `std::env` access
   - Config file reads (JSON, YAML, TOML, .env)
   - dotenv / python-dotenv usage
   - Config validation (schemas, defaults)

## Scope

Target directory: {TARGET_DIR}

Generate a dependency summary, not an exhaustive import list. Focus on architecturally significant dependencies. The output will be used to build cross-references.md, hub files analysis, and the dependency sections of component docs.
