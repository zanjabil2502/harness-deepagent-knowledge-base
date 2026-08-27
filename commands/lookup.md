---
description: Look up one harness term or deepagents symbol - its meaning, or where it is defined in source
argument-hint: [term or symbol, e.g. fail-deferred or CompositeBackend]
---

Invoke the `agent-harness-kb` skill, then run its **looking up** mode for:
$ARGUMENTS

1. Read `references/GLOSSARY.md` first. It has two sections: **Terms** (the
   KB's own vocabulary, hand-written definitions) and **deepagents symbols**
   (derived from the source AST graph, with `file:line` locations).
2. If it is a term, give the one-line meaning, then open the canonical file
   the glossary points to and summarise what that file adds.
3. If it is a `deepagents` symbol, give the `file:line` from the graph, then
   read that location in
   `references/recipes/.venv/lib/python*/site-packages/deepagents/` to state
   the real signature - the graph gives the address, the source gives the
   parameters. Never recite a signature from memory.
4. If it is in neither, say so plainly rather than inventing a definition.

This is a lookup, not a flow. Do not produce a blueprint, a scaffold, or a
review. Answer, cite the file, stop.
