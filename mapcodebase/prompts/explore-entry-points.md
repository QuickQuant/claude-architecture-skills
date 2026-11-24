# Explore: Entry Points

Find all entry points in this codebase. An entry point is where execution begins or where external input arrives.

## What to Find

1. **Main/Start Functions**
   - `main()`, `start()`, `run()` functions
   - Module-level execution (scripts that run on import)
   - CLI command handlers

2. **HTTP/API Endpoints**
   - Route definitions (Express, FastAPI, Flask, etc.)
   - Controller methods
   - GraphQL resolvers
   - Middleware chains

3. **Event Handlers**
   - WebSocket message handlers
   - Event emitter listeners
   - Pub/sub subscribers
   - Signal handlers (SIGTERM, SIGINT)

4. **Scheduled/Background**
   - Cron jobs
   - Interval timers (`setInterval`, `setTimeout`, recurring tasks)
   - Queue processors / workers

5. **Exported APIs**
   - Public module exports consumed by other systems
   - SDK entry points
   - Library main exports

## Output Format

For EACH entry point, report in this exact format:

```
ENTRY: function_name
FILE: path/to/file:line_number
TYPE: main | http | websocket | event | scheduled | cli | export
TRIGGER: what causes this to execute
CALLS: list of functions it directly calls
NOTES: any important context (auth required, rate limited, etc.)
```

## Search Strategy

1. Start with obvious patterns:
   - Files named `main.*`, `index.*`, `app.*`, `server.*`, `cli.*`
   - `if __name__ == "__main__"`, `module.exports`, `export default`
   - Framework-specific: `@app.route`, `router.get`, `export const api`

2. Trace from package.json/pyproject.toml scripts

3. Look for framework-specific patterns:
   - Express: `app.get()`, `router.post()`
   - FastAPI: `@app.get()`, `@router.post()`
   - Convex: `export const` in `convex/` directory
   - Click/Typer: `@click.command()`, `@app.command()`

4. Find background/scheduled patterns:
   - `setInterval`, `schedule`, `cron`
   - `while True`, `while running`
   - Queue consumers

## Scope

Target directory: {TARGET_DIR}

Be thorough. Include every entry point, not just the obvious main function. The output of this exploration will be used to build entry-points.md and flows.md.
