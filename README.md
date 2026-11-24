# Architecture skills for Claude Code

`mapcodebase` writes a source-backed `.architecture/` corpus: components,
entry points, flows, contracts, freshness, and actionable concerns.
`html-program-map` combines it with source inventories to build a standalone,
interactive architecture and workflow explorer in `.reports/`.

## Install

Copy both folders, `mapcodebase/` and `html-program-map/`, into either
`~/.claude/skills/` (all projects) or `<project>/.claude/skills/` (one project).
Keep this README and LICENSE with redistributed copies.

## Requirements and use

- Claude Code with the Agent/Task subagent tool for parallel discovery. If
  subagents are unavailable, run the same prompts sequentially.
- **Run `/mapcodebase` with a 1M-token-context model** (choose one with `/model`).
  The skill synthesizes and diagnoses in the main agent from everything the
  discovery step produced, so it needs the large window. On a smaller window it
  falls back to delegating the diagnosis or skipping the optional action plan.
- Python 3.9+ and Git. Helpers use standard-library `ast.unparse` and
  `str.removesuffix`; their input source must parse under the chosen Python.
- Browser validation requires local Chrome/Chromium and `websocket-client`:
  `pip install websocket-client`. Both browser validators use Chrome DevTools.
- Companion design skills are optional; follow the bundled guidance if absent.

From the repository root, run `/mapcodebase` first, then `/html-program-map`.
Mapping outputs land in `.architecture/`; the explorer, inventories, and protocol
normally land in `.reports/`. In commands below, replace `<skill-dir>` with the
installed `html-program-map` folder and `<project-root>` with the repository.

Launch an isolated browser with a fresh temporary profile:

```bash
PROFILE=$(mktemp -d)
google-chrome --headless=new --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check \
  "file://<project-root>/.reports/architecture.html"
```

Use `chromium` or `chromium-browser` if that is your installed binary. While that
browser runs, use another terminal:

```bash
python3 -B <skill-dir>/scripts/validate_program_explorer.py --port 9222 \
  --url file://<project-root>/.reports/architecture.html
```

For the simpler map rendered by `render_program_map.py`, replace the URL in the
Chrome launch command with that output's file URL so it is the open page tab.
Then run `python3 -B <skill-dir>/scripts/validate_browser.py --port 9222`.
That validator reads the already-open tab; it accepts only `--port`.
Stop only the browser process you launched; remove its temporary profile afterward.
If provenance normalization reports a mismatched manifest hash, regenerate the
manifest following `mapcodebase/SKILL.md` Phase 7 before retrying. Unchanged docs
without `previous_run.git_hash` are skipped until source is read and provenance
is recorded honestly.

The explorer renderer, both ledger inputs, and its authored model schema are
documented in `html-program-map/SKILL.md` Step 7 and
`html-program-map/references/map-contract.md`. Start from the neutral
`html-program-map/references/model.example.json`, replacing IDs with source evidence.

The bundle omits the original test suite and changelog.
License: MIT, see LICENSE
