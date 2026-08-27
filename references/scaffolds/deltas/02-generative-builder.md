# Delta 02 - Generative Builder

Base: [`../_base.md`](../_base.md). This file is **only** the difference.
Full rationale:
[`../../archetypes/02-generative-builder.md`](../../archetypes/02-generative-builder.md)
§Building this with deepagents.

## Replace

- **Backend**: `StoreBackend(namespace=...)` (from `_base`) → a microVM
  sandbox-family backend, e.g. `DaytonaSandbox` from `langchain_daytona`
  (`backend = DaytonaSandbox(sandbox=..., timeout=300)`), or through the
  deepagents CLI's `agent.json` with
  `{"backend": {"type": "sandbox", ...}}`. `[code]` source
  `libs/partners/daytona/README.md`, `libs/cli/README.md`, archetype 02.
  Every `FilesystemMiddleware` operation (including `execute`) is
  automatically confined to that sandbox rather than local disk - unlike
  delta 01, whose backend touches the real host.
- **Checkpointer**: `_base` always injects an external (Postgres)
  checkpointer for every turn. For deliberately ephemeral build/iterate
  sessions the checkpointer **stays installed** (it is needed to resume if
  a graceful drain cuts the session midway, `../_base.md` §Graceful
  drain) - what changes is `StoreBackend`/cross-session artifacts: `_base`
  installs it as the primary backend, whereas here it is **absent** unless
  added explicitly (see Add). `[code]`+`[ours]` archetype 02: vanilla
  documentation examples sometimes use no checkpointer/store at all for
  short sessions; we keep `_base`'s checkpointer (unlike the archetype,
  which drops it entirely) because `_base.md` already makes graceful drain
  plus resumability a standing contract across archetypes - dropping the
  checkpointer here would mean a session cut off by the drain window is
  lost completely, not merely "a short session we meant to discard".

## Add

- **A minimal safety gate**: `interrupt_on={"publish": True, "deploy":
  True}` - only on the publish/deploy tools, not on every `write_file`/
  `execute` as in delta 01. `[ours]` archetype 02: vanilla deepagents uses
  `interrupt_on=None` (no HITL forced at all); we add the narrowest
  possible gate because this archetype's human control is "review at the
  end through the preview", not approving every step.
- **Cross-session persistence (optional)**: if the product needs users to
  return tomorrow and continue the same project, add `StoreBackend` via
  `CompositeBackend(default=<sandbox backend>, routes={"/exports/":
  StoreBackend(namespace=...)})` - an explicit per-product choice, not
  this archetype's default.

## Remove

- **`interrupt_on` as broad as delta 01's** - irrelevant here; approving
  every `write_file`/`execute` would kill the fast-rewrite loop that is
  the core of this archetype (archetype 02 §Harness consequences, the
  full-rewrite vs granular-patch loop shape point).
- **Isolation through "a separate process/container per user"** (the delta
  01 pattern) - not needed here, because a microVM sandbox backend already
  provides per-session isolation out of the box (`sandboxing.md` - the
  microVM row, not the "no isolation" row).
