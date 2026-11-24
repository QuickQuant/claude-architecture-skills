# Entry Points

> All system entrances: where execution begins or external input arrives.
> Generated: {TIMESTAMP}

## Summary

{1-2 sentences: how many entry points, what types dominate}

## Entry Point Table

```
ENTRY_POINT             FILE:LINE           TYPE            TRIGGER                 CALLS
──────────────────────────────────────────────────────────────────────────────────────────────
{function}()            {file}:{line}       {type}          {what triggers it}      {direct calls}
```

Types: `main` | `http` | `websocket` | `event` | `scheduled` | `cli` | `export`

## By Type

### Main / Startup

```
ENTRY: {function_name}
FILE: {path}:{line}
TRIGGER: {process start / import / etc.}
CALLS: {list of functions it directly calls}
NOTES: {important context}
```

### HTTP / API Endpoints

```
ENTRY: {handler_name}
FILE: {path}:{line}
METHOD: {GET/POST/PUT/DELETE}
ROUTE: {/api/path}
CALLS: {list of functions}
NOTES: {auth, middleware, etc.}
```

### Event Handlers

```
ENTRY: {handler_name}
FILE: {path}:{line}
EVENT: {event name or type}
SOURCE: {what emits this event}
CALLS: {list of functions}
```

### Scheduled / Background

```
ENTRY: {function_name}
FILE: {path}:{line}
SCHEDULE: {interval / cron expression}
CALLS: {list of functions}
NOTES: {timing, guards}
```
