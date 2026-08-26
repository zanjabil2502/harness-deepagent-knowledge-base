# Delta 05 — In-App Copilot

Base: [`../_base.md`](../_base.md). This file is **only** the difference. The
full rationale:
[`../../archetypes/05-in-app-copilot.md`](../../archetypes/05-in-app-copilot.md)
§Building this with deepagents.

## Replace

- **Tool surface**: a custom `tools=[...]`, each tool a thin wrapper around
  one host product API endpoint, mapped manually — deepagents' built-in
  filesystem is disabled entirely through
  `permissions=[FilesystemPermission(operations=["read", "write"],
  paths=["/**"], mode="deny")]` (`operations` accepts only
  `"read"`/`"write"`, and both must be given — it isn't an optional
  parameter. `[code]` sourced from `deepagents/middleware/filesystem.py`,
  read directly from `references/recipes/.venv`). `execute` needs no
  separate closing — as in delta 04, `_base`'s backend (`StoreBackend`)
  doesn't implement `SandboxBackendProtocol`, so that tool is never
  registered. `_base` installs no `tools=` and disables no filesystem at
  all. `[code]` sourced from the `create_deep_agent` signature (`tools`,
  `permissions`), archetype 05.
- **Backend**: `StoreBackend(namespace=...)` (`_base`, durable per user) →
  the default `StateBackend` (thread-scoped, not durable) — there are no
  file artifacts needing to survive across threads; the source of truth
  stays in the host product rather than the agent. `[code]` sourced from
  `ARCHITECTURE.md`.
- **Context**: not cross-session `memory=[...]` — context comes from the
  host application's state injected through `context_schema` per call.
  `[code]` the `context_schema` parameter exists in the `create_deep_agent`
  signature.

## Add

- **Safety gate**: an explicit `undo_<action>` tool paired with each product
  action tool, invoked from the host UI — not `interrupt_on`. `[ours]`
  archetype 05: vanilla `HumanInTheLoopMiddleware` is designed for
  approve/edit/reject **before** execution; we diverge to an "act first,
  undo available" pattern because this archetype's short horizon makes an
  approval pause feel like a UX regression against a host product that is
  already fast.

## Remove

- **`ScopeMiddleware` reading `x-user-id` from a raw header** (`_base`) —
  still used for request identity, but **not** for
  `StoreBackend.namespace` (the backend is now `StateBackend` and needs no
  namespace) — recorded explicitly so no leftover code assumes a per-user
  namespace that is in fact no longer used.
- **Cross-session `memory=[...]`** — explicitly declared NOT installed (not
  merely "happens to be absent" as in `_base`) because this archetype's
  short horizon has no cross-document memory the agent needs to preserve
  (archetype 05's `## Harness consequences`, point 4).
