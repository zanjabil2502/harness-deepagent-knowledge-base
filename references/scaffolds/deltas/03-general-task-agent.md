# Delta 03 — General Task Agent

Base: [`../_base.md`](../_base.md). This file is **only** the difference. The
full rationale:
[`../../archetypes/03-general-task-agent.md`](../../archetypes/03-general-task-agent.md)
§Building this with deepagents.

## Add

- **Planning**: `middleware=[TodoListMiddleware()]` on
  `create_deep_agent(...)` — `_base` doesn't install it (this middleware is
  **not** in `create_deep_agent()`'s default stack at all, not merely absent
  from `_base`). `[code]` sourced from `graph.py`, archetype 03.
- **Delegation**: `subagents=[{"name": ..., "description": ..., "model":
  ..., "system_prompt": ..., "tools": [...]}, ...]` — `_base` installs no
  subagents. `[code]` sourced from `middleware/subagents.py`,
  `examples/content-builder-agent/README.md`.
- **Cross-session memory**: `memory=["./AGENTS.md"]` on
  `create_deep_agent(...)` — loading `AGENTS.md` into the system prompt each
  session through `MemoryMiddleware`, on top of the `StoreBackend` `_base`
  already installs for durable files. `[code]` sourced from
  `ARCHITECTURE.md`.
- **Loop budget & kill switch**: custom middleware detecting an identical
  tool call repeated N times consecutively → force a stop. `[ours]`
  archetype 03: `deepagents` has no built-in "no-progress detector" —
  vanilla is LangGraph's generic `recursion_limit` (9999, the point 5
  warning in `../../concepts/guardrails.md`), per-tool `interrupt_on`, and
  `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware`
  (`langchain.agents.middleware`, not `deepagents`') — all three prevent a
  syntactically endless loop (or a budget overrun) but none detects
  *repetition*, so none suffices for an agent semantically spinning in place
  before its budget runs out.

## Replace

- **Nothing** — the backend (`StoreBackend(namespace=...)`) from `_base`
  already matches this archetype's "filesystem-as-memory" need as-is;
  `memory=["./AGENTS.md"]` above adds a layer on top of it rather than
  replacing it.

## Remove

- **Nothing** — `_base` installs nothing conflicting with this archetype;
  this delta is purely additive on top of the baseline.
