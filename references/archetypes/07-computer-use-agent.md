# 7. Computer-Use Agent

## Definition

An agent that drives interfaces **not designed for agents** — browsers,
desktops, third-party applications — through a loop of look
(screenshot/DOM) → decide → click/type → verify. Its tool surface is
narrow (click, type, scroll, screenshot) but deep, because one generic
tool must handle constantly changing UIs with no API contract. This is the
most brittle archetype: nothing structurally guarantees that the element
clicked today sits in the same place tomorrow.

Boundaries against neighbours: differs from **In-App Copilot** (05)
because it acts through the UI rather than the product's official API —
there is no contract the vendor maintains; differs from **Generative
Builder** (02) because it does not generate its own artifact, it operates
someone else's existing artifact/application.

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | The outside world — third-party apps/sites beyond the system's control |
| Artifact | Actions in other systems, executed through the UI (not an API) |
| Horizon | One task session (a sequence of clicks until the task is done) |
| Human control | Approval for risky actions (submit, pay); visual verification each step |
| Domain surface | General (any site) |
| Interface | Computer-use — screenshot/DOM as input, click/type as output |

## Harness consequences

1. **Loop shape: look → decide → act → verify**, with verification as a
   mandatory separate step — without explicit verification after each
   action, the agent has no idea whether the click actually changed UI
   state as expected or silently failed.
2. **A narrow but deep tool surface** (click-by-coordinate or
   click-by-selector, type, scroll, screenshot) — generalising to arbitrary
   UIs forces the tool set down to as few primitives as possible, unlike a
   Workspace Agent whose broad bash tool serves a more predictable domain
   (filesystem, shell).
3. **A safety gate for irreversible actions** (submit a form, pay, send) —
   because there is no API contract that can be dry-run, risky actions
   must pause for human approval before they are actually clicked.
4. **Retry/self-correction at the perception level**, not just the action
   level — a UI that failed to load, an unexpected popup, or an element
   that shifted position requires the agent to recognise "what I see
   doesn't match expectation" and re-observe, rather than blindly
   repeating the action at the same coordinates.

## Example systems

- **browser-use** `[code]` — `Agent.run()` drives a step loop bounded by
  `max_steps` (default 500) and tracks `consecutive_failures` against
  `max_failures` (default 5); when the consecutive-failure limit is
  reached the agent is forced to call the `done` tool as the only tool
  available, and when the step budget is nearly exhausted a "BUDGET
  WARNING" message is injected into context before the final step. These
  are real loop-level retry/self-correction mechanisms, not product
  description. Source: `browser_use/agent/service.py`
  (github.com/browser-use/browser-use).
- **OpenAI Operator** `[inferred]` — from product behaviour: a
  screenshot-then-click loop in an isolated browser, asking for explicit
  confirmation before risky actions such as submitting a payment.
- **Claude computer use** `[inferred]` — from product behaviour: accepts
  screenshots as input, emits click/type coordinates as actions, and runs
  inside a sandboxed virtual display.

## Common pitfalls

1. **Verification skipped for speed** — the agent moves to the next step as
   soon as an action is "sent" without checking that its result actually
   appears on screen, so errors accumulate and only surface several steps
   later when the cause is hard to trace.
2. **The UI changes between observation and action** (a visual race
   condition) — coordinates/selectors valid when the screenshot was taken
   are already invalid when the click executes, because the page
   re-rendered or a popup appeared in between.
3. **CAPTCHA/anti-bot stops the loop with no clear signal** — the agent
   doesn't know whether to ask a human for help or keep trying, and
   without explicit handling it can blindly retry the same page many
   times.
4. **An irreversible action executes without approval** — the safety gate
   for submit/pay is missed because it was treated like an ordinary action
   (clicking a navigation button), even though their blast radii are
   wildly different.

## Building this with deepagents

- **Tool surface**: custom `tools=[click_tool, type_tool, screenshot_tool,
  ...]` mapped onto an external browser automation backend (e.g.
  Playwright/CDP) — deepagents itself provides no built-in computer-use
  tools; these are supplied through `create_deep_agent`'s `tools`
  parameter like any other custom tool. `[code]` — source: the
  `create_deep_agent` signature (`tools`), `graph.py`.
- **Safety gate**: `interrupt_on={"submit_form": True, "click":
  {"allowed_decisions": ["approve", "reject"]}}` — the same per-tool
  configuration pattern with `allowed_decisions` used in the deepagents
  test suite to restrict which approval decisions are available per tool.
  `[code]` — source: `test_hitl.py`.
- **Verification loop**: `[ours]` deepagents has no built-in notion of
  "verify after acting" — we add a `verify_state` tool that must be called
  after every UI action tool, enforced purely through system-prompt
  convention (not through any middleware — deepagents has no middleware
  that enforces tool call ordering). Vanilla `create_deep_agent` assumes a
  tool call already carries its own result (a ToolMessage) with no
  separate verification phase; we diverge because computer-use has no
  guarantee that the action's result equals the visible result.
  `PatchToolCallsMiddleware` (used above for something else) is irrelevant
  here — its role is only to patch synthetic `ToolMessage`s for dangling/
  cancelled/malformed tool calls in message history, not to enforce
  execution order. `[code]` — source:
  `libs/deepagents/deepagents/middleware/patch_tool_calls.py`.
- **Sandbox**: the browser execution backend should ideally sit in an
  isolated sandbox at the same level as Generative Builder (02) — e.g.
  behind a sandbox-family backend (`DaytonaSandbox` or equivalent) — so a
  crashed or abused browser session cannot touch other compute. `[code]` —
  source: `libs/partners/daytona/README.md`.

## Sources

- browser-use `browser_use/agent/service.py` — `[code]` —
  https://github.com/browser-use/browser-use
- deepagents `graph.py`, `test_hitl.py`, `libs/partners/daytona/README.md`,
  `middleware/patch_tool_calls.py` — `[code]` — Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- OpenAI Operator, Claude computer use — `[inferred]` — closed-source
  product behaviour.
