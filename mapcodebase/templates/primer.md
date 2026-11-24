# Architecture Primer: {PROJECT_NAME}

> Generated: {TIMESTAMP} | Git: {GIT_HASH}
> Freshness: {FRESHNESS_STATUS} | Trust: {TRUST_NOTE}
<!-- mapcodebase-accessor-contract: {"skill_version":"{SKILL_VERSION}","git_hash":"{GIT_HASH}","freshness_status":"{freshness_status}","component_doc_paths_source":"components[].doc_path"} -->

## System Summary

{One paragraph: what the system does, who uses it, and the primary shape of the architecture. Keep this compact.}

## Most Important Components

| Component | Role | Runtime | Architecture |
|-----------|------|---------|--------------|
| {name} | {why it matters} | {implemented/partial/disabled} | {active_primary/target_only/etc.} |

## Shared Contracts and Boundaries

- **{Contract or boundary}:** {why it matters, where it lives, who depends on it}
- **{Contract or boundary}:** {why it matters, where it lives, who depends on it}

## Non-Obvious Gotchas

- {Gotcha}: {why it surprises fresh readers}
- {Gotcha}: {why it matters during implementation or review}

## Top Actionable Concerns

- {Concern title}: {why it matters now, where it lives, what to do next}
- {Concern title}: {why it matters now, where it lives, what to do next}

## Escalation Guidance

- Read [concerns.md](concerns.md) when you need the fix-first architecture debt and next actions.
- Read [overview.md](overview.md) when you need the full system narrative.
- Query the [Current Flow Index](structured/flows.md#current-flow-index) when the task crosses component boundaries, then load only matching detailed records.
- Read component paths returned by the manifest accessor when the task touches a specific blast zone; do not infer the tracked set by globbing [structured/components/](structured/components/).
- Read [access-guide.md](access-guide.md) for guided reading paths by task type.
