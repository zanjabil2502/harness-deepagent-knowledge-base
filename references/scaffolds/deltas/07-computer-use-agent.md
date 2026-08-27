# Delta 07 - Computer-Use Agent

Base: [`../_base.md`](../_base.md). This file is **only** the difference. The
full rationale:
[`../../archetypes/07-computer-use-agent.md`](../../archetypes/07-computer-use-agent.md)
§Building this with deepagents.

## Replace

- **Tool surface**: a custom `tools=[click_tool, type_tool,
  screenshot_tool, ...]`, mapped to an external browser automation backend
  (Playwright/CDP) - deepagents provides no built-in computer-use tools.
  `_base` installs no `tools=`. `[code]` sourced from the
  `create_deep_agent` signature (`tools`), archetype 07.
- **Backend**: `StoreBackend(namespace=...)` (`_base`) → a sandbox-family
  backend at the same level as delta 02's (e.g. `DaytonaSandbox` or an
  equivalent) wrapping the browser process - a crashed or abused browser
  session must not touch other compute. `[code]` sourced from
  `libs/partners/daytona/README.md`.

## Add

- **Safety gate**: `interrupt_on={"submit_form": True, "click":
  {"allowed_decisions": ["approve", "reject"]}}` - `_base` installs no
  `interrupt_on`. `[code]` the per-tool `allowed_decisions` pattern cited
  from `test_hitl.py`.
- **A verification loop**: a `verify_state` tool that must be called after
  every UI action tool, enforced through `system_prompt` instruction
  convention (not middleware - deepagents has no middleware enforcing tool
  call ordering). `[ours]` archetype 07: vanilla `create_deep_agent` assumes
  a tool call itself already carries its result (`ToolMessage`) with no
  separate verification phase; we diverge because computer-use has no
  guarantee that an action's result equals what is visible on screen.
  `PatchToolCallsMiddleware` (already in `_base`'s default stack) isn't
  relevant to this - its role is only patching dangling `ToolMessage`s in
  history, not enforcing tool execution order.

## Remove

- **Isolation through "a separate process/container per user"** (the delta
  01 pattern) - unnecessary; the sandbox backend already provides per
  browser session isolation by default (the same reason as delta 02, the
  microVM row of `sandboxing.md`).
