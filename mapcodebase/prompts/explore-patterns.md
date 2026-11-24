# Explore: Cross-Cutting Patterns

Find repeated code patterns across files of the same structural role. The goal is to detect missing shared abstractions — places where N files repeat boilerplate that the framework provides a centralized solution for.

**Target directory:** `{TARGET_DIR}`

## What to Find

### 1. Group Files by Role

Identify groups of 3+ files that serve the same structural role:
- **Page entry points**: `app/**/page.tsx`, `pages/**/*.py`, `routes/**/*.go`, etc.
- **API route handlers**: route/endpoint definitions
- **Components/widgets**: files in `components/`, `widgets/`, etc. of the same type
- **Test files**: check for pattern consistency with their source modules
- **Configuration files**: repeated config patterns across modules

### 2. For Each Group, Extract the Setup Pattern

Read the first ~50-80 lines of each file in the group. Identify:
- **Common imports** across all files (identical import blocks)
- **Setup boilerplate** — client creation, auth checks, data fetching preamble
- **Repeated inline logic** — same 5-20 line block copy-pasted across files
- **What varies** between files (the actual business logic) vs. what is identical

### 3. Assess Against Best Practices

For each repeated pattern, evaluate whether:
- The framework provides a centralized alternative (middleware, shared hooks, caching wrappers, layout components)
- A shared utility/module already exists in the codebase but isn't being used
- The repetition is necessary/appropriate (some duplication is fine)

Focus areas by category:

**Authentication:**
- How many files independently fetch auth state?
- Is there middleware, a shared hook, or a cached wrapper?
- What does the framework recommend?

**Data fetching:**
- How many files create their own database/API clients?
- Are queries deduplicated across components in the same request?
- Are loading states handled consistently?

**Error handling:**
- Is there a shared error boundary/handler pattern?
- Do files handle the same error types in different ways?

**State management:**
- Is interactive state persisted consistently?
- Do client components follow the same patterns for state initialization?

**Loading/streaming:**
- Do async pages/routes have consistent loading indicators?
- Are there missing loading states that cause UI freezes?

## Output Format

For EACH detected pattern, report in this exact format:

```
PATTERN: pattern-id-in-kebab-case
CATEGORY: data-fetching | auth | state-management | loading | error-handling | configuration
SEVERITY: info | warning | error
FILES:
  - path/to/file1.ext
  - path/to/file2.ext
  - path/to/file3.ext
DESCRIPTION: [Neutral, factual description of what the code does]
CONCERN: [Why this might be problematic — null if the pattern is appropriate]
BEST_PRACTICE: [What the framework/stack recommends instead — null if current approach is correct]
EVIDENCE: [Quote the repeated code block or summarize the 3-5 line pattern]
```

### Severity Guide

- **info**: Pattern observed, no concern. The repetition is appropriate or intentional.
- **warning**: Suboptimal pattern. The framework provides a better centralized solution. Should be refactored but isn't breaking anything.
- **error**: Pattern will cause user-facing issues (e.g., 3-second page loads from redundant auth calls, state loss on navigation, missing loading indicators causing UI freezes).

### What NOT to Flag

- Single-file issues (those belong in Phase 4B hazard detection)
- Style differences (formatting, naming conventions) — only structural patterns
- Patterns in <3 files (too few to be "cross-cutting")
- Framework-mandated boilerplate that cannot be reduced

## Summary

After listing all patterns, provide:
```
SUMMARY:
  Total patterns: N
  Info: N | Warning: N | Error: N
  Top pattern: [the single most impactful pattern to address first, with rationale]
  Groups analyzed: N (of M total groups found)
```
