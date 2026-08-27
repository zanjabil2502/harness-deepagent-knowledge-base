#!/usr/bin/env python3
"""Build references/GLOSSARY.md - the term lookup entrance.

Run: python3 tools/build_glossary.py

Two sections, two different sources of truth:

- **Terms** are declared in `TERMS` below. Their definitions are hand-written
  because this is prose vocabulary, not extractable symbols. What the machine
  checks: that the canonical file exists and genuinely contains the term. A
  concept moved or renamed fails the build.
- **deepagents symbols** are derived from
  `references/deepagents/graph/graph.json` intersected with backticked tokens
  in the KB. The graph decides what counts as a real symbol, so there is no
  noise from ordinary backticks, and the `file:line` locations come from the
  AST rather than from memory.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_DIR = REPO_ROOT / "references"
GRAPH_PATH = REFERENCES_DIR / "deepagents" / "graph" / "graph.json"
GLOSSARY_PATH = REFERENCES_DIR / "GLOSSARY.md"
BACKTICKED_RE = re.compile(r"`([A-Za-z_][\w.]*)`")

# (term, one-line definition, canonical file relative to references/)
TERMS = [
    ("archetype", "One of 7 kinds of AI assistant, produced by cutting the 6 discriminating axes; it fixes the harness constraints from the outset.", "archetypes/README.md"),
    ("blast radius", "How far an agent's actions can reach into the world: the user's machine, a sandbox, SaaS data, or external systems. One of the 6 axes, and half the worth-stopping-for criterion.", "concepts/human-in-the-loop.md"),
    ("blueprint", "The main output of building mode: six harness decisions stated explicitly before a line of code is written.", "blueprint-template.md"),
    ("by-reference", "The rule that a transcript stores `artifact_id` + a version rather than the artifact's content; its bytes live in storage.", "concepts/artifacts-and-canvas.md"),
    ("dynamic subagent", "A subagent dispatched from inside code rather than chosen by the model per turn; it bypasses the per-dispatch approval gate.", "concepts/code-orchestration.md"),
    ("fail-closed", "The failure mode where a guardrail that cannot run refuses the action. Safe, at the cost of availability.", "concepts/guardrails.md"),
    ("fail-deferred", "The third failure mode: the action is suspended awaiting an enforcement that isn't available yet. It must be paired with a timeout and an on-expiry policy, or it is a deferred fail-open.", "concepts/guardrails.md"),
    ("fail-open", "The failure mode where a guardrail that cannot run lets the action proceed. Cheap, and silently voids the gate.", "concepts/guardrails.md"),
    ("golden transcript", "A reference transcript used by eval to score the full trajectory rather than only the final answer.", "concepts/evaluation.md"),
    ("harness", "The layer around the model that determines the loop shape, context, tool surface, delegation, and guardrails - what this skill designs.", "concepts/agent-loop.md"),
    ("idempotency key", "The key that makes resubmitting the same turn produce no duplicate execution; unique per user.", "concepts/persistence-schema.md"),
    ("intent/expression", "The separation between language-neutral intent (a stable code) and human-visible text (following the locale). The basis of all multilingual handling.", "concepts/multilingual.md"),
    ("compaction", "Summarising conversation history into a structured summary as the context window limit approaches; distinct from eviction, which moves content to the filesystem.", "concepts/context-engineering.md"),
    ("result contract", "Exactly what flows back from a subagent to its caller - the full transcript or a filtered summary - plus what deliberately must not flow back.", "concepts/delegation.md"),
    ("eviction / offload", "Moving a large input or tool result into the backend and replacing it with a pointer in the active context. The KB says \"eviction\"; the upstream documentation calls it \"offloading\" - the same thing.", "concepts/context-engineering.md"),
    ("policy-as-data", "Policy expressed as data that can be read, audited, and changed without a deploy - not an `if` branch inside the engine.", "concepts/policy-as-data.md"),
    ("progressive disclosure", "A skill loads its frontmatter into the system prompt, its body on activation, and its reference files only when its instructions say so - each layer with its own budget.", "concepts/skill-composition.md"),
    ("PTC", "Programmatic tool calling: an agent's tools exposed as functions inside code an interpreter runs, so one tool call can call many tools.", "concepts/code-orchestration.md"),
    ("reattach", "A disconnected client reconnecting to a running turn without losing the events that already passed.", "concepts/streaming-protocol.md"),
    ("tail stack", "The middleware slots `create_deep_agent` assembles **after** the user's `middleware=[...]`; their position determines what can still be filtered and gated.", "deepagents/middleware.md"),
]

HEADER = """# Glossary - looking up terms and symbols

Generated by `tools/build_glossary.py`. **Don't edit by hand**; change
`TERMS` in that script and re-run it.

This is the entrance to this skill's third mode: not a flow for designing or
building, but looking up one term's meaning or one symbol's location.

```bash
python3 tools/build_glossary.py
```
"""


def load_graph():
    """Code symbols from the graph: label -> {(source_file, source_location)}."""
    g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    symbols = defaultdict(set)
    for n in g["nodes"]:
        # A module node (a label ending in .py) always points at its file's
        # L1 -- correct, but not a dictionary entry. What we want: classes
        # and functions.
        if (n.get("file_type") == "code" and n.get("source_file")
                and not n["label"].endswith(".py")):
            symbols[n["label"]].add((n["source_file"], n.get("source_location", "")))
    return symbols


def kb_files():
    """The KB files we genuinely wrote.

    `upstream/` is a vendor copy; `deepagents/graph/` is machine output
    listing symbols without discussing them - citing it as "discussed in"
    would mislead, and would pull in symbols never explained anywhere.
    """
    skip = {"upstream", "graph"}
    return [f for f in sorted(REFERENCES_DIR.rglob("*.md"))
            if not skip & set(f.parts) and f != GLOSSARY_PATH]


def check_terms() -> list[str]:
    """Terms whose canonical file is missing or no longer contains them."""
    errors = []
    for term, _, canonical in TERMS:
        f = REFERENCES_DIR / canonical
        probe = re.split(r" vs | / ", term)[0].lower()
        if not f.exists():
            errors.append(f"{term!r}: canonical file {canonical} does not exist")
        elif probe not in f.read_text(encoding="utf-8").lower():
            errors.append(f"{term!r}: {canonical} no longer contains {probe!r}")
    return errors


def main() -> int:
    if not GRAPH_PATH.exists():
        print(f"FAIL: {GRAPH_PATH.relative_to(REPO_ROOT)} does not exist")
        return 1

    errors = check_terms()
    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1

    symbols = load_graph()
    mentions = defaultdict(set)
    for f in kb_files():
        for m in BACKTICKED_RE.finditer(f.read_text(encoding="utf-8")):
            if m.group(1) in symbols:
                mentions[m.group(1)].add(f.relative_to(REFERENCES_DIR).as_posix())

    lines = [HEADER, "## Terms", "",
             "| Term | Meaning | Discussed in |", "|---|---|---|"]
    for term, gist, canonical in sorted(TERMS, key=lambda x: x[0].lower()):
        lines.append(f"| **{term}** | {gist} | [`{canonical}`]({canonical}) |")

    lines += [
        "",
        "## deepagents symbols",
        "",
        f"{len(mentions)} symbols the KB mentions that exist in the source AST "
        "graph. The location column comes from `deepagents/graph/graph.json`, "
        "relative to the `deepagents` package root in "
        "`references/recipes/.venv/`; `tools/check_kb.py` keeps it in sync "
        "with the installed source.",
        "",
        "| Symbol | Defined in | Discussed in |",
        "|---|---|---|",
    ]
    for name in sorted(mentions, key=str.lower):
        loc = ", ".join(f"`{a}:{b}`" if b else f"`{a}`"
                        for a, b in sorted(symbols[name]))
        refs = ", ".join(f"[`{r}`]({r})" for r in sorted(mentions[name]))
        lines.append(f"| `{name}` | {loc} | {refs} |")

    GLOSSARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {GLOSSARY_PATH.relative_to(REPO_ROOT)} - {len(TERMS)} terms, "
          f"{len(mentions)} symbols")
    return 0


if __name__ == "__main__":
    sys.exit(main())
