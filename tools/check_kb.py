#!/usr/bin/env python3
"""The KB structure validator. Run: python3 tools/check_kb.py"""
import ast
import hashlib
import json
import subprocess
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_DIR = REPO_ROOT / "references"

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
FRAME_EXEMPT = {"README.md", "_template.md", "INDEX.md"}
LABEL_RE = re.compile(r"\[(code|docs|inferred|ours)\]")
LINK_RE = re.compile(r"\]\((?!https?:|mailto:)([^)#]+)")
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
MANIFEST_PATH = REFERENCES_DIR / "deepagents" / "graph" / "manifest.json"
DEEPAGENTS_SRC_DIR = next(
    iter(sorted(REPO_ROOT.glob("references/recipes/.venv/lib/python*/site-packages/deepagents"))),
    None,
)
GLOSSARY_PATH = REFERENCES_DIR / "GLOSSARY.md"
SKILL_ASSETS_DIR = REFERENCES_DIR / "scaffolds" / "skills"
ASSET_MAX_LINES = 500
ASSET_MAX_BYTES = 10 * 1024 * 1024
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)

OURS_RE = re.compile(r"\[ours\]")
# An [ours] roster row in conformance.md: | n | `path:l1,l2,...` | ... |
ROSTER_ROW_RE = re.compile(r"^\|[^|]*\|\s*`([\w/\-.]+\.md):([\d,\s]+)`")
ROSTER_PATH = REFERENCES_DIR / "deepagents" / "conformance.md"
# references/deepagents/ holds pointers (per-archetype.md) and meta
# (conformance.md) about the label itself; the roster lists only substantive
# claims outside this folder.
ROSTER_EXEMPT_DIR = "deepagents"
# references/upstream/ = verbatim copies of vendor documentation. Not our
# writing, so not subject to the section frames, source labels, or the [ours]
# roster; its internal links also use the vendor site's absolute paths rather
# than repo paths.
UPSTREAM_DIR = "upstream"
# PEP 8 shapes, checked over both real .py files and the ```python blocks the
# scaffolds tell a reader to copy. Only mechanical rules live here: a name
# being English or meaningful cannot be decided by a regex, and
# python-practice.md section 6 carries those rules for a human reviewer.
SNAKE_CASE_RE = re.compile(r"^_{0,2}[a-z][a-z0-9_]*_?$")
PASCAL_CASE_RE = re.compile(r"^_?[A-Z][A-Za-z0-9]*$")
UPPER_SNAKE_RE = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
PYTHON_BLOCK_RE = re.compile(r"```python\n(.*?)```", re.S)


def is_authored(f):
    """KB files we wrote ourselves (not upstream copies)."""
    return f.relative_to(REFERENCES_DIR).parts[0] != UPSTREAM_DIR


def check_frames(errors):
    for group, heads in FRAMES.items():
        folder = REFERENCES_DIR / group
        if not folder.is_dir():
            errors.append(f"references/{group}/: the folder does not exist")
            continue
        for f in sorted(folder.rglob("*.md")):
            if f.name in FRAME_EXEMPT:
                continue
            txt = f.read_text(encoding="utf-8")
            rel = f.relative_to(REPO_ROOT)
            for alts in heads:
                if not any(h in txt for h in alts):
                    errors.append(f"{rel}: missing section '{alts[0]}'")
            if not LABEL_RE.search(txt):
                errors.append(f"{rel}: no source label [code]/[docs]/[inferred]")


def tracked_files():
    """The files that genuinely come with a clone of the repo.

    check_links inspects the filesystem, so a link to a deliberately
    untracked file still looks alive on its author's machine and is dead for
    everyone else -- a failure invisible until somebody clones.
    """
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return set(out.stdout.split("\0")) - {""}


def check_links(errors):
    tracked = tracked_files()
    files = [REPO_ROOT / "SKILL.md", REPO_ROOT / "README.md"]
    if REFERENCES_DIR.is_dir():
        files += [f for f in sorted(REFERENCES_DIR.rglob("*.md")) if is_authored(f)]
    for f in files:
        if not f.exists() or ".venv" in f.parts:
            continue
        for m in LINK_RE.finditer(f.read_text(encoding="utf-8")):
            target = (f.parent / m.group(1).strip()).resolve()
            if not target.exists():
                errors.append(f"{f.relative_to(REPO_ROOT)}: dead link -> {m.group(1)}")
            elif tracked is not None and target.is_file():
                try:
                    rel = target.relative_to(REPO_ROOT).as_posix()
                except ValueError:
                    continue
                if rel not in tracked:
                    errors.append(
                        f"{f.relative_to(REPO_ROOT)}: link to an untracked file "
                        f"-> {m.group(1)} (alive here, dead for anyone cloning)"
                    )


def check_skill_size(errors):
    skill = REPO_ROOT / "SKILL.md"
    if not skill.exists():
        errors.append("SKILL.md: does not exist")
        return
    n = len(skill.read_text(encoding="utf-8").splitlines())
    if n > SKILL_MAX_LINES:
        errors.append(f"SKILL.md: {n} lines, the maximum is {SKILL_MAX_LINES}")


def check_ours_roster(errors):
    """Every `[ours]` must be listed in conformance.md's roster, where the
    vanilla alternative and the reason for diverging are recorded. Checked in
    both directions: a location the roster lists must genuinely contain
    `[ours]`, and every `[ours]` must be listed."""
    if not ROSTER_PATH.exists():
        errors.append(f"{ROSTER_PATH.relative_to(REPO_ROOT)}: the [ours] roster does not exist")
        return

    rostered = set()
    for line in ROSTER_PATH.read_text(encoding="utf-8").splitlines():
        m = ROSTER_ROW_RE.match(line)
        if not m:
            continue
        for n in m.group(2).split(","):
            n = n.strip()
            if n.isdigit():
                rostered.add((m.group(1), int(n)))

    actual = set()
    for f in sorted(REFERENCES_DIR.rglob("*.md")):
        if not is_authored(f):
            continue
        rel = f.relative_to(REFERENCES_DIR).as_posix()
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if OURS_RE.search(line):
                actual.add((rel, i))

    for rel, n in sorted(rostered - actual):
        errors.append(f"[ours] roster points at {rel}:{n}, which contains no [ours] (stale?)")
    for rel, n in sorted(actual - rostered):
        if rel.split("/")[0] == ROSTER_EXEMPT_DIR:
            continue
        errors.append(f"{rel}:{n}: [ours] not listed in conformance.md's roster")


def check_skill_assets(errors):
    """Skill assets must follow the Agent Skills spec -- violations are silent."""
    if not SKILL_ASSETS_DIR.is_dir():
        return
    for d in sorted(p for p in SKILL_ASSETS_DIR.iterdir() if p.is_dir()):
        f = d / "SKILL.md"
        rel = f.relative_to(REPO_ROOT)
        if not f.exists():
            errors.append(f"{d.relative_to(REPO_ROOT)}/: no SKILL.md")
            continue
        txt = f.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(txt)
        if not m:
            errors.append(f"{rel}: no YAML frontmatter")
            continue
        fm = {}
        for ln in m.group(1).splitlines():
            if ln.startswith((" ", "\t")):
                continue  # a multi-line value continuation, not a new key
            k, sep, v = ln.partition(":")
            if sep:
                fm[k.strip()] = v.strip()
        if fm.get("name") != d.name:
            errors.append(f"{rel}: name={fm.get('name')!r} does not match the directory {d.name!r}")
        if not fm.get("description"):
            errors.append(f"{rel}: frontmatter without a description")
        n = len(txt.splitlines())
        if n > ASSET_MAX_LINES:
            errors.append(f"{rel}: {n} lines, the maximum is {ASSET_MAX_LINES}")
        if len(txt.encode()) > ASSET_MAX_BYTES:
            errors.append(f"{rel}: over 10 MB, it will be skipped during discovery")


def check_graph_sync(errors):
    """The AST graph must match the installed deepagents source."""
    if not MANIFEST_PATH.exists():
        errors.append("references/deepagents/graph/manifest.json: does not exist")
        return
    if DEEPAGENTS_SRC_DIR is None or not DEEPAGENTS_SRC_DIR.is_dir():
        print("SKIPPED: the references/recipes/ venv does not exist; graph sync unchecked")
        return
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for rel, meta in sorted(manifest.items()):
        f = DEEPAGENTS_SRC_DIR / rel
        if not f.exists():
            errors.append(f"graph: {rel} is in the graph but not in the installed source")
        elif hashlib.md5(f.read_bytes()).hexdigest() != meta.get("ast_hash"):
            errors.append(
                f"graph: {rel} changed since the graph was built -- "
                "rebuild the graph and review the line citations pointing at this file"
            )
    for f in sorted(DEEPAGENTS_SRC_DIR.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(DEEPAGENTS_SRC_DIR).as_posix()
        if rel not in manifest:
            errors.append(f"graph: {rel} is in the source but not yet in the graph")


def check_glossary(errors):
    """GLOSSARY.md is generated; it must be identical to a rebuild."""
    if not GLOSSARY_PATH.exists():
        errors.append("references/GLOSSARY.md: not generated yet "
                    "(python3 tools/build_glossary.py)")
        return
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    try:
        import build_glossary
    except ImportError:
        errors.append("tools/build_glossary.py: cannot be imported")
        return
    for e in build_glossary.check_terms():
        errors.append(f"GLOSSARY.md: {e}")
    before = GLOSSARY_PATH.read_text(encoding="utf-8")
    if build_glossary.main() != 0:
        errors.append("GLOSSARY.md: build_glossary failed")
        return
    if GLOSSARY_PATH.read_text(encoding="utf-8") != before:
        errors.append("references/GLOSSARY.md: stale -- a rebuild differs; "
                    "commit the regenerated file")


def naming_errors(tree, origin, line_offset=0):
    """PEP 8 name-shape violations in one parsed module."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind, name, ok = "function", node.name, SNAKE_CASE_RE
        elif isinstance(node, ast.ClassDef):
            kind, name, ok = "class", node.name, PASCAL_CASE_RE
        elif isinstance(node, ast.arg) and node.arg not in ("self", "cls"):
            kind, name, ok = "argument", node.arg, SNAKE_CASE_RE
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if SNAKE_CASE_RE.match(node.id) or UPPER_SNAKE_RE.match(node.id):
                continue
            kind, name, ok = "variable", node.id, SNAKE_CASE_RE
        else:
            continue
        # `_` is the idiomatic throwaway, not a name.
        if name != "_" and not ok.match(name):
            found.append(f"{origin}:{line_offset + node.lineno}: "
                         f"{kind} {name!r} is not PEP 8 shaped")
    return found


def check_naming(errors):
    """Name shapes in tools/, recipes/, and every ```python block we wrote."""
    tracked = tracked_files()
    if tracked is None:
        return  # no git; check_links already reports the missing listing
    for rel in sorted(tracked):
        if UPSTREAM_DIR in rel.split("/"):
            continue
        path = REPO_ROOT / rel
        if rel.endswith(".py"):
            errors += naming_errors(ast.parse(path.read_text(encoding="utf-8")), rel)
        elif rel.endswith(".md"):
            text = path.read_text(encoding="utf-8")
            for m in PYTHON_BLOCK_RE.finditer(text):
                try:
                    tree = ast.parse(m.group(1))
                except SyntaxError:
                    continue  # a deliberate fragment, not a module
                errors += naming_errors(tree, rel, text[:m.start()].count("\n") + 1)


def main():
    errors = []
    check_frames(errors)
    check_links(errors)
    check_skill_size(errors)
    check_ours_roster(errors)
    check_skill_assets(errors)
    check_graph_sync(errors)
    check_glossary(errors)
    check_naming(errors)
    for e in errors:
        print("FAIL:", e)
    print(f"\n{len(errors)} problems" if errors else "\nOK: all checks passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
