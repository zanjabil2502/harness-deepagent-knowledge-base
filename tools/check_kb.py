#!/usr/bin/env python3
"""The KB structure validator. Run: python3 tools/check_kb.py"""
import hashlib
import json
import subprocess
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "references"

# One heading per slot. The bilingual shim used during the translation to
# English is gone now that every group is translated -- add an alternative
# back only for another migration in progress.
FRAMES = {
    "archetypes": [
        ("## Definition",),
        ("## Position on the 6 axes",),
        ("## Harness consequences",),
        ("## Example systems",),
        ("## Common pitfalls",),
        ("## Building this with deepagents",),
        ("## Sources",),
    ],
    "concepts": [
        ("## Problem",),
        ("## Pattern",),
        ("## Trade-offs",),
        ("## In deepagents",),
        ("## Sources",),
    ],
    "systems": [
        ("## Archetype",),
        ("## 1. Loop shape",),
        ("## 2. Context",),
        ("## 3. Tool surface",),
        ("## 4. Delegation",),
        ("## 5. State & resume",),
        ("## 6. Safety gate",),
        ("## 7. Capability routing & policy",),
        ("## Sources",),
    ],
}
EXEMPT = {"README.md", "_template.md", "INDEX.md"}
LABEL = re.compile(r"\[(code|docs|inferred|ours)\]")
LINK = re.compile(r"\]\((?!https?:|mailto:)([^)#]+)")
SKILL_MAX_LINES = 150
# The skill assets scaffolded into a project. Their limits aren't our taste:
# the Agent Skills spec requires `name` to match the directory name and
# recommends SKILL.md stay under 500 lines; deepagents skips files above 10 MB
# during discovery without an error. All three fail silently when violated, so
# they are checked here. See references/deepagents/best-practices.md §5.
# references/deepagents/graph/ is a symbol->file:line index of the deepagents
# source. Its value depends entirely on staying in sync with the installed
# source: once the package changes, `file.py:NNN` citations across the KB can
# be off with no check failing. manifest.json stores each file's md5 at graph
# build time, so drift can be proven rather than assumed.
MANIFEST = REF / "deepagents" / "graph" / "manifest.json"
DA_SRC = next(
    iter(sorted(ROOT.glob("references/recipes/.venv/lib/python*/site-packages/deepagents"))),
    None,
)
GLOSSARY = REF / "GLOSSARY.md"
SKILL_ASSETS = REF / "scaffolds" / "skills"
ASSET_MAX_LINES = 500
ASSET_MAX_BYTES = 10 * 1024 * 1024
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

OURS = re.compile(r"\[ours\]")
# An [ours] roster row in conformance.md: | n | `path:l1,l2,...` | ... |
ROSTER_ROW = re.compile(r"^\|[^|]*\|\s*`([\w/\-.]+\.md):([\d,\s]+)`")
ROSTER = REF / "deepagents" / "conformance.md"
# references/deepagents/ holds pointers (per-archetype.md) and meta
# (conformance.md) about the label itself; the roster lists only substantive
# claims outside this folder.
ROSTER_EXEMPT_DIR = "deepagents"
# references/upstream/ = verbatim copies of vendor documentation. Not our
# writing, so not subject to the section frames, source labels, or the [ours]
# roster; its internal links also use the vendor site's absolute paths rather
# than repo paths.
UPSTREAM_DIR = "upstream"


def authored(f):
    """KB files we wrote ourselves (not upstream copies)."""
    return f.relative_to(REF).parts[0] != UPSTREAM_DIR


def check_frames(errs):
    for group, heads in FRAMES.items():
        folder = REF / group
        if not folder.is_dir():
            errs.append(f"references/{group}/: the folder does not exist")
            continue
        for f in sorted(folder.rglob("*.md")):
            if f.name in EXEMPT:
                continue
            txt = f.read_text(encoding="utf-8")
            rel = f.relative_to(ROOT)
            for alts in heads:
                if not any(h in txt for h in alts):
                    errs.append(f"{rel}: missing section '{alts[0]}'")
            if not LABEL.search(txt):
                errs.append(f"{rel}: no source label [code]/[docs]/[inferred]")


def tracked_files():
    """The files that genuinely come with a clone of the repo.

    check_links inspects the filesystem, so a link to a deliberately
    untracked file still looks alive on its author's machine and is dead for
    everyone else -- a failure invisible until somebody clones.
    """
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return set(out.stdout.split("\0")) - {""}


def check_links(errs):
    tracked = tracked_files()
    files = [ROOT / "SKILL.md", ROOT / "README.md"]
    if REF.is_dir():
        files += [f for f in sorted(REF.rglob("*.md")) if authored(f)]
    for f in files:
        if not f.exists() or ".venv" in f.parts:
            continue
        for m in LINK.finditer(f.read_text(encoding="utf-8")):
            target = (f.parent / m.group(1).strip()).resolve()
            if not target.exists():
                errs.append(f"{f.relative_to(ROOT)}: dead link -> {m.group(1)}")
            elif tracked is not None and target.is_file():
                try:
                    rel = target.relative_to(ROOT).as_posix()
                except ValueError:
                    continue
                if rel not in tracked:
                    errs.append(
                        f"{f.relative_to(ROOT)}: link to an untracked file "
                        f"-> {m.group(1)} (alive here, dead for anyone cloning)"
                    )


def check_skill_size(errs):
    skill = ROOT / "SKILL.md"
    if not skill.exists():
        errs.append("SKILL.md: does not exist")
        return
    n = len(skill.read_text(encoding="utf-8").splitlines())
    if n > SKILL_MAX_LINES:
        errs.append(f"SKILL.md: {n} lines, the maximum is {SKILL_MAX_LINES}")


def check_ours_roster(errs):
    """Every `[ours]` must be listed in conformance.md's roster, where the
    vanilla alternative and the reason for diverging are recorded. Checked in
    both directions: a location the roster lists must genuinely contain
    `[ours]`, and every `[ours]` must be listed."""
    if not ROSTER.exists():
        errs.append(f"{ROSTER.relative_to(ROOT)}: the [ours] roster does not exist")
        return

    rostered = set()
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        m = ROSTER_ROW.match(line)
        if not m:
            continue
        for n in m.group(2).split(","):
            n = n.strip()
            if n.isdigit():
                rostered.add((m.group(1), int(n)))

    actual = set()
    for f in sorted(REF.rglob("*.md")):
        if not authored(f):
            continue
        rel = f.relative_to(REF).as_posix()
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if OURS.search(line):
                actual.add((rel, i))

    for rel, n in sorted(rostered - actual):
        errs.append(f"[ours] roster points at {rel}:{n}, which contains no [ours] (stale?)")
    for rel, n in sorted(actual - rostered):
        if rel.split("/")[0] == ROSTER_EXEMPT_DIR:
            continue
        errs.append(f"{rel}:{n}: [ours] not listed in conformance.md's roster")


def check_skill_assets(errs):
    """Skill assets must follow the Agent Skills spec -- violations are silent."""
    if not SKILL_ASSETS.is_dir():
        return
    for d in sorted(p for p in SKILL_ASSETS.iterdir() if p.is_dir()):
        f = d / "SKILL.md"
        rel = f.relative_to(ROOT)
        if not f.exists():
            errs.append(f"{d.relative_to(ROOT)}/: no SKILL.md")
            continue
        txt = f.read_text(encoding="utf-8")
        m = FRONTMATTER.match(txt)
        if not m:
            errs.append(f"{rel}: no YAML frontmatter")
            continue
        fm = {}
        for ln in m.group(1).splitlines():
            if ln.startswith((" ", "\t")):
                continue  # a multi-line value continuation, not a new key
            k, sep, v = ln.partition(":")
            if sep:
                fm[k.strip()] = v.strip()
        if fm.get("name") != d.name:
            errs.append(f"{rel}: name={fm.get('name')!r} does not match the directory {d.name!r}")
        if not fm.get("description"):
            errs.append(f"{rel}: frontmatter without a description")
        n = len(txt.splitlines())
        if n > ASSET_MAX_LINES:
            errs.append(f"{rel}: {n} lines, the maximum is {ASSET_MAX_LINES}")
        if len(txt.encode()) > ASSET_MAX_BYTES:
            errs.append(f"{rel}: over 10 MB, it will be skipped during discovery")


def check_graph_sync(errs):
    """The AST graph must match the installed deepagents source."""
    if not MANIFEST.exists():
        errs.append("references/deepagents/graph/manifest.json: does not exist")
        return
    if DA_SRC is None or not DA_SRC.is_dir():
        print("SKIPPED: the references/recipes/ venv does not exist; graph sync unchecked")
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for rel, meta in sorted(manifest.items()):
        f = DA_SRC / rel
        if not f.exists():
            errs.append(f"graph: {rel} is in the graph but not in the installed source")
        elif hashlib.md5(f.read_bytes()).hexdigest() != meta.get("ast_hash"):
            errs.append(
                f"graph: {rel} changed since the graph was built -- "
                "rebuild the graph and review the line citations pointing at this file"
            )
    for f in sorted(DA_SRC.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(DA_SRC).as_posix()
        if rel not in manifest:
            errs.append(f"graph: {rel} is in the source but not yet in the graph")


def check_glossary(errs):
    """GLOSSARY.md is generated; it must be identical to a rebuild."""
    if not GLOSSARY.exists():
        errs.append("references/GLOSSARY.md: not generated yet "
                    "(python3 tools/build_glossary.py)")
        return
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_glossary
    except ImportError:
        errs.append("tools/build_glossary.py: cannot be imported")
        return
    for e in build_glossary.check_terms():
        errs.append(f"GLOSSARY: {e}")
    before = GLOSSARY.read_text(encoding="utf-8")
    if build_glossary.main() != 0:
        errs.append("GLOSSARY: build_glossary failed")
        return
    if GLOSSARY.read_text(encoding="utf-8") != before:
        errs.append("references/GLOSSARY.md: stale -- a rebuild differs; "
                    "commit the regenerated file")


def main():
    errs = []
    check_frames(errs)
    check_links(errs)
    check_skill_size(errs)
    check_ours_roster(errs)
    check_skill_assets(errs)
    check_graph_sync(errs)
    check_glossary(errs)
    for e in errs:
        print("FAIL:", e)
    print(f"\n{len(errs)} problems" if errs else "\nOK: all checks passed")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
