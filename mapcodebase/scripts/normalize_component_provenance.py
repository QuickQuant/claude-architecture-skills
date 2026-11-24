#!/usr/bin/env python3
"""Normalize mapcodebase component-doc provenance headers (v4.3 contract).

Every component doc must open with the template's provenance header:

    # Component: <Name>

    > Derived from: <file1>, <file2>, ... | Verified at: <GIT_HASH>
    > If any derived-from file changed since <GIT_HASH>, trust source over this doc.

Older component docs may carry heterogeneous headers
("> Updated: ... | Git: ... | Skill version: ...", "> Generated: ...",
"> Created: ..."), and several use "Component 5:" / lowercase slugs as titles.

This script rewrites ONLY the leading title + provenance block. Everything from the
first "## " heading onward is preserved byte-for-byte. Idempotent: re-running after a
successful pass is a no-op.

Read-modify-write with atomic tmp+replace. Run from the repository being mapped.
Build its manifest first as described in mapcodebase/SKILL.md Phase 7.

Usage:
    python3 -B <skill-dir>/scripts/normalize_component_provenance.py --git-hash <SHORT_HEAD> [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ARCH = Path(".architecture")
COMPONENTS = ARCH / "structured" / "components"
MANIFEST = ARCH / "manifest.json"

HEADER_RE = re.compile(
    r"\A(?P<title>\#\s+[^\n]*\n)"          # leading H1
    r"(?P<block>(?:>[^\n]*\n|\n)*)"          # blank lines + blockquote lines
)


def load_component_index(manifest: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for comp in manifest.get("components", []):
        doc_path = comp.get("doc_path", "")
        if not doc_path.startswith("structured/components/"):
            continue
        index[Path(doc_path).name] = comp
    return index


def normalize(name: str, comp: dict, git_hash: str, changed: set[str],
              previous_hash: str | None, dry_run: bool) -> str:
    path = COMPONENTS / name
    text = path.read_text()
    m = HEADER_RE.match(text)
    if not m:
        return f"SKIP (no header match): {name}"

    derived_files = comp.get("key_files", [])
    derived = ", ".join(derived_files)
    title = comp.get("name") or name.removesuffix(".md")

    # Never overwrite a header another writer already produced for THIS run: their
    # derived-from list is the one they actually read, and it is at least as accurate
    # as the manifest's key_files proxy.
    existing_block = m.group("block")
    if f"Verified at: {git_hash}" in existing_block:
        return f"OK (verified at {git_hash} by this run's writer): {name}"

    # Honest provenance: a doc whose derived-from files did not change since the previous
    # map was NOT re-verified this run, so it must not claim the new commit. Claiming it
    # would be the same class of false-freshness the accessor contract exists to prevent.
    untouched = all(f not in changed for f in derived_files) and bool(derived_files)
    if untouched:
        if not previous_hash:
            return (f"SKIP (no previous_run.git_hash; unchanged source does not prove "
                    f"this body was verified): {name}. Follow mapcodebase/SKILL.md Phase 7 "
                    "to record provenance after reading source.")
        provenance_hash = previous_hash
        note = (f"> Body last verified at {previous_hash}; none of the derived-from files "
                f"appear in the {git_hash} changed set. Re-read source before relying on it "
                f"if any of them changes.\n")
    else:
        provenance_hash = git_hash
        note = ""

    new_head = (
        f"# Component: {title}\n\n"
        f"> Derived from: {derived} | Verified at: {provenance_hash}\n"
        f"{note}"
        f"> If any derived-from file changed since {provenance_hash}, "
        f"trust source over this doc.\n\n"
    )
    if text.startswith(new_head):
        return f"OK (already normalized): {name}"

    out = new_head + text[m.end():]
    if not dry_run:
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(out)
        os.replace(tmp, path)
    kind = "unchanged-body" if untouched else "refreshed"
    return f"REWRITTEN ({kind}): {name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--git-hash", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    index = load_component_index(manifest)
    if not index:
        print("no components in manifest", file=sys.stderr)
        return 1

    if manifest.get("git_hash") != args.git_hash:
        print(f"manifest git_hash is {manifest.get('git_hash')!r}, not {args.git_hash!r}: "
              "build the manifest using mapcodebase/SKILL.md Phase 7 first, otherwise the "
              "changed-file set is stale and every doc would be labelled unchanged",
              file=sys.stderr)
        return 2
    changed = set(manifest.get("changed_files_since_scan", []))
    previous_hash = (manifest.get("previous_run") or {}).get("git_hash")

    for name in sorted(index):
        if not (COMPONENTS / name).exists():
            print(f"MISSING ON DISK: {name}")
            continue
        print(normalize(name, index[name], args.git_hash, changed, previous_hash, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
