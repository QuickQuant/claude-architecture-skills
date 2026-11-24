# System Overview: {PROJECT_NAME}

> Generated: {TIMESTAMP} | Git: {GIT_HASH} | Target: {TARGET_DIR}
> Skill version: {SKILL_VERSION} | Model: {MODEL_NAME}
> Freshness: {FRESHNESS_STATUS} | Trust: {TRUST_NOTE}

## What This System Does

{2-3 sentences: what the system is, what problem it solves, who/what uses it}

## Architecture at a Glance

{Narrative description of the major components and how they fit together. Write this as connected prose, not a list. A reader should understand the system's shape after this section.}

{Example tone: "The system is built around a central event bus that connects three subsystems. Market data arrives through a WebSocket connection managed by the feed handler, which normalizes different exchange formats into a common internal representation. The strategy engine subscribes to these normalized events, evaluates trading signals, and emits order requests. The execution layer picks up order requests, manages position state, and communicates with the exchange API."}

## Primary Data Flows

{Describe the 2-4 most important data paths through the system in plain language. For each: where data comes from, what happens to it, where it ends up.}

### {Flow 1 Name}

{Plain language description. Reference key files with file:line only for the most important entry points.}

### {Flow 2 Name}

{Same pattern.}

## Key Architectural Decisions

{List the major patterns and why they were chosen. Keep each to 1-2 sentences.}

- **{Pattern}**: {Why it's used here}
- **{Pattern}**: {Why it's used here}

## Non-Obvious Things

{Things that would trip up someone new to this codebase. Naming conventions that differ from the norm, historical decisions that seem wrong but have reasons, implicit dependencies, etc.}

- {Thing}: {Explanation}
- {Thing}: {Explanation}

## Component Map

| Component | Purpose | Key Entry |
|-----------|---------|-----------|
| {name} | {one-line} | `func()` at file:line |

For detailed component docs, see `structured/components/`.
