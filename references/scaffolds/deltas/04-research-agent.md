# Delta 04 — Research/Analyst

Base: [`../_base.md`](../_base.md). This file is **only** the difference. The
full rationale:
[`../../archetypes/04-research-agent.md`](../../archetypes/04-research-agent.md)
§Building this with deepagents.

## Replace

- **Tool surface**: `_base` installs no `tools=` (only the built-in
  filesystem tools). Here the tool surface is narrowed to
  `tools=[web_search_tool, think_tool]` **plus**
  `permissions=[FilesystemPermission(operations=["write"], paths=["/**"],
  mode="deny")]` — `operations` accepts only `"read"`/`"write"` (a category
  classification, not literal tool names; `write_file`/`edit_file`/`delete`
  fall under the `"write"` category). `[code]` sourced from
  `deepagents/middleware/filesystem.py` (`FilesystemOperation =
  Literal["read", "write"]`, `_DEFAULT_FS_TOOL_OPS`), read directly from
  `references/recipes/.venv`. `execute` **needs no** closing through
  `permissions` at all — `_base`'s backend (`StoreBackend`) doesn't
  implement `SandboxBackendProtocol`, so the `execute` tool is never
  registered for this archetype (unlike deltas 01/02/07, which swap the
  backend for a `LocalShellBackend`/sandbox). `FilesystemMiddleware` itself
  can't be removed from the stack (`../../systems/deepagents.md` §7: core
  middleware can't be excluded through `excluded_middleware`), so file
  writing is closed through `permissions` rather than deleted — this
  archetype's blast radius is read-only towards the outside world
  (archetype 04's `## Position on the 6 axes`).
- **Delegation**: `subagents=[{"name": "research-agent", ..., "tools":
  [web_search_tool, think_tool]}]`, invoked through the `task` tool built
  into `SubAgentMiddleware` — `_base` installs no subagents. `[code]`
  sourced from `examples/deep_research/research_agent.ipynb`.
- **Provenance/output**: `response_format=<a schema of claims+citations>` on
  `create_deep_agent(...)` — `_base` installs no `response_format`. `[code]`
  the parameter exists in the `create_deep_agent` signature, sourced from
  `graph.py`.

## Add

- **Budget/loop limits**: `max_concurrent_research_units`,
  `max_researcher_iterations` as constants in the code calling the subagent
  (the application orchestrator level, not built-in `create_deep_agent`
  parameters). `[code]` the same source as delegation above.
- **An extra guardrail at point 4 (Output)**: post-hoc validation matching
  every citation in `response_format` against real `web_search` tool call
  results in the transcript. `[ours]` archetype 04: vanilla
  `response_format` validates only the schema's shape, not that its content
  genuinely came from a real tool call — that gap is what lets hallucinated
  citations (archetype 04's pitfall #1) through unless patched. The
  installation point: an extra `after_model` hook in `middleware=[...]`,
  following the point 4 pattern in `../../concepts/guardrails.md`.

## Remove

- **`StoreBackend` as the primary durable file route** — still present
  (persistence-schema.md still stores the final report as an artifact), but
  this archetype writes no working files through `write_file`/`edit_file` at
  all (closed through `permissions` above) — so `_base`'s backend is used
  purely for reading (where relevant), not as an active write target.
