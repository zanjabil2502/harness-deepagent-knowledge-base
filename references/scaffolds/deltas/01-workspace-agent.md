# Delta 01 — Workspace Agent

Base: [`../_base.md`](../_base.md). This file is **only** the difference —
read `_base.md` first. The full rationale for each decision lives in
[`../../archetypes/01-workspace-agent.md`](../../archetypes/01-workspace-agent.md)
§Building this with deepagents; it is not repeated here except as short
quotes that explain the diff.

## Replace

- **Backend**: `StoreBackend(namespace=...)` (from `_base`, durable
  per-user, no `execute`) → `LocalShellBackend(root_dir=<repo/session
  path>, virtual_mode=True)`. `root_dir` is rooted at that session's
  repo/workspace directory rather than a per-user namespace — this
  archetype genuinely touches one repo's real filesystem, not an abstract
  store. `[code]` source `deepagents/backends/local_shell.py`, cited in
  archetype 01.
- **The blast radius changes explicitly from "isolated" to "host
  machine"** — unlike `StoreBackend`, `LocalShellBackend` has no scoping
  *hook* (`isolation-and-scoping.md`); `virtual_mode=True` only confines
  file operations (`read_file`/`write_file`/etc.) to `root_dir` and does
  **not** restrict `execute()` (`../../systems/deepagents.md` §6, quoting
  `THREAT_MODEL.md`). If tighter isolation is needed, replace it again
  with a sandbox backend (see delta 02) — not an assumption baked into
  this archetype.

## Add

- **Safety gate**: `interrupt_on={"execute": True, "write_file": True,
  "edit_file": True}` on `create_deep_agent(...)` in
  `deepagents_orchestrator.py` — `_base` installs no `interrupt_on` at
  all. `[code]` the per-tool `interrupt_on` pattern is cited from
  `test_hitl.py`, archetype 01.
- **Multi-user isolation outside the backend**: because
  `LocalShellBackend` has no scoping *hook*, isolation between users must
  be built at the process/container layer (one process/container per user
  session) rather than through a backend parameter — unlike `_base`, where
  `StoreBackend`'s `namespace=` is isolation enough. Deployment
  consequence: this component is the first candidate to split out as a
  "Tool executor" (see `../serving.md`).

## Remove

- **`StoreBackend` as the primary backend** — removed entirely rather than
  combined through `CompositeBackend`. There is no separate "durable
  across threads" state to preserve outside the repo itself; the git repo
  *is* the durable state, outside the application's control.
- **Delegation/subagents** — `_base` doesn't install them either, so
  nothing is literally removed, but it is stated explicitly here: this
  archetype deliberately stays flat. This is **not** a divergence from
  vanilla — 5 of the 10 `create_deep_agent` calls in the maintainer repo's
  `examples/` also pass no synchronous subagents (`[code]` archetype 01,
  `../../deepagents/conformance.md` D-01). Subagents are added only when a
  long subtask needs isolated context (e.g. running a large test suite in
  the background) — never by default.
