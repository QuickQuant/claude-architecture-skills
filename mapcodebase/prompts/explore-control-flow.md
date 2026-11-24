# Explore: Control Flow

Map control flow patterns: how execution moves through the system over time.

## What to Find

1. **Lifecycle Sequences**
   - Startup sequence (what initializes in what order)
   - Shutdown sequence (cleanup order, graceful shutdown)
   - Connection lifecycle (connect, disconnect, reconnect logic)
   - Initialization dependencies (what must be ready before what)

2. **Background Loops**
   - Polling intervals (what, how often, what triggers changes)
   - Heartbeat timers
   - Flush/sync loops (buffer draining, periodic writes)
   - Health check loops
   - Reconnection loops with backoff

3. **State Machines**
   - Explicit state enums/types
   - State transition logic (what event causes what transition)
   - State persistence (how state survives restarts)
   - Guard conditions on transitions

4. **Error Handling & Recovery**
   - Try/catch boundaries (what's caught where)
   - Retry logic (what's retried, how many times, backoff strategy)
   - Fallback strategies (what happens when primary fails)
   - Circuit breakers (if any)
   - Fatal vs recoverable error distinction

5. **Branching Logic**
   - Feature flags
   - Environment-based branches (dev vs prod behavior)
   - Type-based dispatch (polymorphism, strategy pattern)

6. **Concurrency & Shared Resources**
   - Shared mutable state accessed from multiple code paths (e.g., tokens, credentials, connection objects)
   - Functions callable from multiple independent triggers (timers, error handlers, startup) without synchronization
   - Missing mutexes/locks/guards on resources that multiple flows read-write
   - Race conditions: identify where two flows can interleave on the same resource
   - Token/credential refresh called from multiple sites (proactive refresh, error-triggered refresh, startup refresh)
   - File or config writes from multiple callers without coordination

## Output Format

For each control flow pattern:

```
FLOW: descriptive_name
TYPE: lifecycle | loop | state_machine | error_recovery | branch

SEQUENCE: (for lifecycle/loops)
  1. step_one (file:line)
  2. step_two (file:line)
  3. [condition] -> step_a | step_b

STATES: (for state machines)
  - STATE_A -> [event] -> STATE_B
  - STATE_B -> [event] -> STATE_C

TRIGGERS:
  - what initiates this flow

EXITS:
  - how/where this flow ends

NOTES: timing, guards, edge cases, failure modes
```

For concurrency hazards specifically:

```
HAZARD: descriptive_name
RESOURCE: what shared state is at risk (e.g., access token, config file, connection)
CALLERS:
  - caller_1 (file:line) — triggered by {event}
  - caller_2 (file:line) — triggered by {event}
  - caller_3 (file:line) — triggered by {event}
SYNCHRONIZATION: none | mutex at (file:line) | guard flag at (file:line)
CONSEQUENCE: what goes wrong when callers race (e.g., token storm, corrupted state, double-write)
```

## Search Strategy

1. Look for lifecycle patterns:
   - `async function start()`, `init()`, `setup()`, `bootstrap()`
   - `shutdown()`, `cleanup()`, `close()`, `destroy()`, `dispose()`
   - Signal handlers (SIGTERM, SIGINT, `process.on('exit')`)
   - `atexit`, `finally` blocks in main functions

2. Find interval/loop patterns:
   - `setInterval`, `setTimeout`, `schedule`
   - `while True`, `while running`, `while self._running`
   - Recursive scheduling (`setTimeout` at end of handler)
   - `asyncio.create_task`, background task spawning

3. Identify state patterns:
   - Enums with states (`ConnectionState`, `OrderStatus`)
   - `switch`/`match` on state variables
   - `isConnected`, `isRunning`, `status` fields
   - State transition methods (`transition_to`, `set_state`)

4. Map error boundaries:
   - Top-level `try/catch` blocks
   - `.catch()` handlers on promises
   - Error event listeners (`on('error')`)
   - Custom error classes and where they're thrown/caught

5. Find concurrency hazards:
   - Functions called from 2+ independent triggers (grep for function name, count distinct callsites)
   - Shared state written by multiple flows: tokens, credentials, config objects, connection handles
   - Look for `refresh`, `rotate`, `reconnect`, `retry` functions — these are common multi-caller targets
   - Check if callers have guards (`if (isRefreshing) return`, mutex, lock) — absence = hazard
   - `setInterval` callbacks that can fire while a previous invocation is still running
   - File writes (config persistence) from multiple code paths without file locking

## Scope

Target directory: {TARGET_DIR}

Focus on architectural control flow, not every if/else branch. The output will be used to build flows.md and the control flow sections of component docs.
