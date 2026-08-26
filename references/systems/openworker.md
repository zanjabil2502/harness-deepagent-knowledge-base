# OpenWorker

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. Source read from a `git clone --depth 1` of the
`andrewyng/openworker` repo at commit `141d02a` (2026-08-22), 257 Python files /
75,493 lines. The repo is in **open beta** according to its own README. `[code]`

## Archetype

**General Task Agent (03)** at its core, but a **four-way** hybrid — the most of
any system in this index. Its artifacts are documents/spreadsheets/reports as
finished files (**Generative Builder 02**), it acts on SaaS objects through 25+
connectors (**In-App Copilot 05**), it touches the terminal and local files
(**Workspace Agent 01**), and it has scheduled automation running unattended
(**Workflow Agent 06**).

Blast radius: the operator's machine **plus** the SaaS data it connects to. Human
control: approval per consequential action. Interface: a desktop GUI, Slack
mentions, and a scheduler. **Single-operator** — the README states it explicitly:
*"designed for a single operator"*. `[docs]` README

## 1. Loop shape

`TurnEngine` (`coworker/engine.py:65`) runs a `while True` (`:356`) with an
iteration bound at the top of the loop (`:357`); when exceeded it emits the status
`max_iterations_exceeded` (`:360`). The model decides to stop normally; the bound
is only a safety net. `[code]`

Its effective default is **150**, from `config.max_iterations`
(`coworker/config.py:34`) passed at `coworker/agent.py:508-510`. The `12` in the
`TurnEngine.__init__` signature (`engine.py:75`) is only a constructor fallback
and doesn't apply on the normal path. `[code]`

## 2. Context

Auto-compaction with an explicit boundary. `CompactionState`
(`coworker/compaction.py:86-94`) stores a `boundary_index` pointing into the
**canonical message list**: messages before the boundary are represented by a
compacted block in the *outbound view*, messages from the boundary onwards are
sent verbatim. That state is persisted with the session
(`coworker/sessions.py:37-39`) so a reloaded session keeps its compacted view.
`[code]`

This canonical/outbound separation is equivalent to the transcript vs model
context separation in
[`../concepts/session-state.md`](../concepts/session-state.md) — arrived at
independently, and here the boundary is one explicit index.

## 3. Tool surface

A few broad tools plus many narrow connectors. The terminal (`run_shell`) and
local file operations (`write_file`, `replace_in_file`, `apply_patch`,
`apply_unified_diff`) are built-in tools whose risk is set by name
(`coworker/risk.py:26-33`). `[code]` On top of them sit 25+ integrations (GitHub,
Slack, Jira, Notion, Linear, HubSpot, Outlook, monday.com, Gmail, Google Calendar)
plus anything reachable through MCP. `[docs]` README

External binaries are managed in-house: `coworker/toolchain.py` downloads them,
verifies hashes (`_verify`, `:227`), and resolves paths (`resolve`, `:171`), with
`missing()`/`installable()` to state requirements before use. `[code]`

## 4. Delegation

One form of delegation: a read-only **explorer subagent**
(`coworker/tools/subagent.py:79`, `build_explorer_engine` at `:42`). Its tool
docstring states its own contract — broad read-only research with *"its own fresh
context window"*, returning **only the final report**, and *"the intermediate file
reads never touch your context"*. Independent `explore` calls run in parallel when
requested together. `[code]`

This result contract is exactly the pattern recommended in
[`../concepts/delegation.md`](../concepts/delegation.md): a subagent returns a
clean summary, not a transcript.

## 5. State & resume

Sessions are persisted along with their compaction state (`sessions.py:37-39`).
More interesting is **durable resume for approvals**: an inbox item stores its
`tool_call_id` (`coworker/inbox.py:77`, `coworker/engine.py:55`) and `add_approval`
is **idempotent over `(session_id, tool_call_id)`** (`inbox.py:142`) — its comment
states *"a durable resume re-raises the same prompt"*. So if the process dies
while awaiting approval, its coroutine is lost but its request survives, and a
re-run raises the same prompt rather than a duplicate. `[code]`

The `(session_id, tool_call_id)` idempotency key has the same shape as
`turns.idempotency_key` + `UNIQUE(user_id, idempotency_key)` in
[`../concepts/persistence-schema.md`](../concepts/persistence-schema.md).
Independent convergence on the same shape.

## 6. Safety gate

Four risk classes as an enum (`coworker/risk.py:18-23`): `READ` (no side effects,
always allowed), `WRITE_LOCAL` (path-scoped + mode-gated), `EXEC` (mode-gated),
and `EXTERNAL` — whose comment calls itself *"the unattended Inbox hook"*.
`is_consequential()` (`:56-58`) states the rule: anything other than `READ` enters
the permission engine. `[code]`

The approver is a **strategy swapped per session mode**, not a branch inside the
engine. An unattended session uses `inbox_approver` (`coworker/inbox.py:387`)
whose docstring states: *"routes a permission request to the Inbox and suspends
until resolved"* — an `await store.wait(item.id)` (`:362-371`) **with no
timeout**. `ApprovalOutcome` (`engine.py:31-37`) has five values: `ONCE`,
`ALWAYS_TOOL`, `ALWAYS_COMMAND`, `READONLY_SESSION`, `DENY`. `[code]`

When the operator returns to attended control, `reconcile_on_resume`
(`inbox.py:374-380`) surfaces still-pending items inline **plus a recap of what
was answered while they were away**, on the principle *"Single source of truth:
every item already has one authoritative resolution."* `[code]`

See [`../concepts/guardrails.md`](../concepts/guardrails.md) §The third failure
mode for the pattern's implications, and
[`../concepts/human-in-the-loop.md`](../concepts/human-in-the-loop.md) for the
attended/unattended transition.

## 7. Capability routing & policy

Risk is determined **as data, not prose**, with explicit precedence in
`classify()` (`risk.py:39-54`): a user-local override wins, then the by-name
`_BASE` table (`:29-33`), then aisuite's `requires_approval` metadata →
`EXTERNAL`, and a `READ` default. Its source comment calls that table *"the old
WRITE_TOOLS / SHELL_TOOL, **as data**"*. `[code]`

This is the same shape recommended in
[`../concepts/policy-as-data.md`](../concepts/policy-as-data.md): a code-verifiable
rule lives as a table rather than a sentence in a prompt — with enforcement at the
permission engine boundary. Which tool gets called remains model judgement; what
is data-driven is its **risk class**, not the routing. `[inferred]`

## Sources

- `[code]` `andrewyng/openworker` @ `141d02a` (2026-08-22), read via
  `git clone --depth 1`. Files read: `coworker/risk.py` (in full),
  `coworker/inbox.py:77,142,362-380,387-406`,
  `coworker/engine.py:31-37,55,65,356-360,75`, `coworker/config.py:34`,
  `coworker/agent.py:505-515`, `coworker/compaction.py:86-94`,
  `coworker/sessions.py:37-39`, `coworker/tools/subagent.py:42,79-100`,
  `coworker/toolchain.py:171,227`, `tests/test_unattended.py:22-60`.
- `[docs]` The repo README — its open beta status, the single-operator claim, the
  list of 25+ connectors, and the desktop app + local agent server architecture
  (on top of `aisuite`).
- `[docs]` The GitHub API: 14,948 stars, Python, MIT, created 2026-07-20.
