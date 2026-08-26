# Human-in-the-loop

## Problem

"Ask for approval before a dangerous action" is easy to say and hard to
operationalise without two explicit decisions that often go missing:

1. **What is worth stopping for?** Stopping too much (approval for every
   tool call, including harmless read-only ones) trains users to click
   "approve" without reading — the gate becomes decorative rather than a
   control. Stopping too little (only actions that "look" dangerous rather
   than ones systematically assessed) lets destructive actions through
   because they happened not to be on the list the code's author thought
   of. The "when to stop" criterion must be explicit and measurable, not
   the author's intuition at one point in time.
2. **How is that decision recorded?** An approval that is only a UI click
   leaving no trace separate from its side effect (the action that went
   ahead) can't answer later questions: who approved, when, whether the
   arguments were edited before execution, or whether it was rejected then
   retried with different arguments. Without an explicit trail, "who
   approved this action" can only be answered with "the action happened, so
   someone must have" — weak inference for anything needing an audit.

This file does **not** own the approval enforcement point itself —
[`guardrails.md`](guardrails.md) point 3 (Tool/action) already maps it to
`interrupt_on`/`permissions` → `HumanInTheLoopMiddleware`, and
[`security.md`](security.md) covers why destructive actions need tighter
control than reads. This file goes deeper on two things unanswered there:
the criterion for choosing what enters the gate, and how that gate decision
is recorded as data.

## Pattern

### The "worth stopping for" criterion: reversibility × blast radius, not a list of tool names

The gate decision is most robust when derived from two axes rather than
listed ad hoc tool by tool:

| | Small blast radius | Large blast radius |
|---|---|---|
| **Reversible** (undoable/repeatable with no permanent effect) | No gate needed — `read_file`, `search`, read-only queries | Consider a gate if the per-execution cost is high (e.g. a paid third-party API call) even though the effect can be undone |
| **Irreversible** (permanent, cannot be undone) | An optional gate depending on context — editing one line in the agent's own scratch file | **Always gate** — `delete_file` outside the sandbox, dropping a database table, sending email/messages to external parties, financial transactions, anything touching a system outside the agent's control (see "Blast radius" among the 6 archetype axes, `SKILL.md`) |

Reversibility and blast radius are two axes this KB **already** uses
elsewhere — blast radius is exactly the first of the 6 archetype-discriminating
axes (`SKILL.md`), and reversibility is the implicit reason `guardrails.md`
point 3 gives approval a specific fail-closed mode ("an approval timeout
defaults to *deny*, not to continue" — a default that only makes sense for
actions expensive to undo if they turn out wrong). The point: the "worth
stopping for" criterion isn't a list of tool names guessed once at project
start, but a derivation from two properties assessable even for a **new**
tool before it has ever been called — a new tool automatically has an answer
to "does this need a gate" as soon as its reversibility and blast radius are
known, without waiting for an incident to notice.

Consistent with `tool-design.md` §Heuristics: this criterion applies **per
operation**, not per broad tool name — an `execute` tool listing a directory
(reversible, small blast radius) and an `execute` running a recursive force
delete (irreversible, large blast radius) have different gate answers despite
sharing a tool name; if the gate can only hang off a tool name (see `## In
deepagents`), the tool's granularity itself has to be adjusted so the
reversibility/blast-radius classification can be enforced without reading
argument content inside the gate.

### The approver as a swapped strategy, not a branch inside the engine

Approval gates have a problem rarely written down: **session mode changes**.
A session that started attended can be walked away from; scheduled
automation runs with nobody waiting. If "who to ask" logic lives as an `if`
inside the agent loop, every new mode adds a branch on the hottest path.

OpenWorker separates them: one permission engine, with the **approver**
swapped. An attended session uses an inline prompt; an unattended session
uses `inbox_approver(store, session_id)`. `[code]` `andrewyng/openworker` @
`141d02a`, `coworker/inbox.py:387`; its routing is tested explicitly in
`tests/test_unattended.py:22-60` with the comment *"an unattended session
uses the inbox approver, so consequential actions park in the Inbox instead
of prompting inline."*

The return shape stays one enum whatever the approver — `ApprovalOutcome`
with `ONCE`, `ALWAYS_TOOL`, `ALWAYS_COMMAND`, `READONLY_SESSION`, `DENY`
(`coworker/engine.py:31-37`). `[code]` That is what makes the swap safe: the
engine needn't know which surface the answer came from.

### The attended ↔ unattended transition needs reconciliation

An easily missed consequence: if approvals can be answered from another
surface while the operator is away, they return without knowing **what was
approved in their name**.

OpenWorker answers this with `reconcile_on_resume`
(`coworker/inbox.py:374-380`): when the operator returns to attended
control, still-pending items are surfaced inline **and** accompanied by a
recap of what was answered while they were away, with the principle stated
in its docstring — *"Single source of truth: every item already has one
authoritative resolution."* `[code]`

One authoritative resolution per item is the important part. Without it, a
second surface (Slack, an inbox, a TUI) becomes a parallel approval path
that can answer the same request differently.

### Recording decisions as data, not just their side effects

One approval decision has four possible shapes — **approve** (run as-is),
**edit** (run with arguments a human changed before execution), **reject**
(don't run), **respond** (the human provides an answer without running the
action at all, e.g. for an action that turns out to be unnecessary). Those
four possibilities are themselves a protocol property, not a free UI
convention — see `## In deepagents` for their concrete shape.

What **must** be recorded for each decision, whatever mechanism is used:
*who* (the approver's identity — possibly different from the conversation
owner's `user_id` if approval is delegated to a separate reviewer), *when*
(the decision's timestamp, separate from the action's execution timestamp —
the gap between them is a useful signal: an approval clicked one second
after appearing, repeatedly, is exactly the rubber-stamping signal as a gate
that fires too often in §Criterion), *what was decided* (one of the four
above), and *the final arguments* (for `edit` — both the original arguments
the model proposed **and** the human-edited ones, so "the model asked for X,
the human changed it to Y" can be distinguished from "the model asked for X
and it ran as-is").

**An honestly reported gap**:
[`persistence-schema.md`](persistence-schema.md) has a `tool_calls` table
(`status` `'pending'`/`'success'`/`'error'`, `arguments`, `result`) storing
execution **results**, but that schema has **no** column for the
approver/decision timestamp/decision type/pre-edit arguments — a `'success'`
after a HITL gate is indistinguishable from a `'success'` with no gate at
all from that table alone. This isn't a defect in `persistence-schema.md`
(approval wasn't in the scope of the task that wrote it) — it is an
additional requirement this file marks explicitly: a project installing HITL
must extend the schema (extra columns on `tool_calls`, or a separate
`tool_call_approvals` table linking `tool_call_id` →
approver/decision/original arguments) so "who approved what" can be answered
from data rather than inference. This is consistent with the similar gap
already recorded in [`guardrails.md`](guardrails.md) §6 System for gate
audit logs generally ("per-step state checkpoints... the closest trail
available for free") — this file narrows it to the concrete shape of one
extra table for the HITL case specifically.

## Trade-offs

- **The reversibility × blast radius criterion vs a static tool name list**
  — a property-based criterion needs the discipline of assessing every new
  tool/operation against those two axes (one extra step of indirection
  compared with "add the tool name to the list"), but generalises to tools
  that don't exist yet; a static name list is quick to write initially but
  silently fails for a new tool someone forgot to add — exactly the ailment
  §Criterion sets out to avoid.
- **Granular approval (per operation/arguments) vs granular per tool name
  only** — per operation is the most precise (stopping only what genuinely
  needs it) but needs either sufficiently narrow tools or a gate that reads
  argument content (both extra design cost, see `tool-design.md`); per tool
  name is cheaper to install (one flag per tool) but forces every call of
  that tool into the same policy, including calls that are actually safe.
- **An approval timeout defaulting to deny vs to continue** — default-deny
  (chosen by `guardrails.md` point 3) is safe for actions expensive to undo
  but can block a legitimate workflow if the approver is slow (e.g. offline);
  default-continue never blocks a workflow but means an irreversible action
  can run without real approval whenever the timeout happens to be reached —
  the same asymmetry of harm described in `guardrails.md` §Trade-offs (a
  silent leak/wrong action vs a visible UX disruption) makes default-deny
  the winner for the action class that warrants a gate at all.
- **Storing approvals as extra columns on `tool_calls` vs a separate
  `tool_call_approvals` table** — extra columns on `tool_calls` are simpler
  (one table, one fewer join) but most `tool_calls` rows (those never gated)
  will have those columns permanently `NULL` — a sparse schema for the
  majority case; a separate table keeps `tool_calls` clean and only has rows
  where a HITL decision genuinely occurred, at the cost of one extra join
  whenever approval history needs displaying.

## In deepagents

`interrupt_on={"tool_name": True | InterruptOnConfig}` installs
`HumanInTheLoopMiddleware` (from `langchain.agents.middleware`) — already
mapped in `guardrails.md` point 3 and `../systems/deepagents.md` §6; this
file adds the decision shape detail and the resume mechanism:

- The four decision types in §Pattern are **exactly** `DecisionType =
  Literal["approve", "edit", "reject", "respond"]` in the middleware's
  implementation — not a free convention this file proposes but a type that
  already exists in the library. `ReviewConfig.allowed_decisions` restricts
  the valid decision subset **per action** (e.g. a given action may only be
  `approve`/`reject`, not `edit`, when its arguments make no sense for a
  human to edit). `[code]` —
  `langchain/agents/middleware/human_in_the_loop.py`, the `DecisionType`,
  `ReviewConfig`, `ActionRequest` classes.
- The pause mechanism: `HumanInTheLoopMiddleware` calls
  `interrupt(hitl_request)` from `langgraph.types` — this **stops graph
  execution** at that point and persists its state through the same
  `checkpointer` as Run state (`../systems/deepagents.md` §5). Resuming
  happens through `Command(resume={"decisions": [...]})` sent by the
  application after a human decides. The direct consequence for §Reattach in
  [`streaming-protocol.md`](streaming-protocol.md): because the interrupt
  state is already checkpointed automatically, "a waiting approval isn't
  lost when the client disconnects" **comes free** from `langgraph`'s resume
  mechanism — all the application must build is a way to tell a reconnecting
  client that the interrupt exists (the `interrupt` event in
  `streaming-protocol.md` §The event schema). `[code]` —
  `langchain/agents/middleware/human_in_the_loop.py` (the `interrupt(...)`
  call, its result read as `decisions =
  interrupt(hitl_request)["decisions"]`).
- **The gate keys on the tool name, but argument content is usable through
  `when`** — `interrupt_on` is keyed per tool name (`{"execute": True}`),
  yet `InterruptOnConfig` accepts a `when: Callable[[ToolCallRequest], bool]`
  field returning `True` to pause and `False` to pass through
  automatically. Its docstring example is precisely an argument-based case:
  `when=lambda req: req.tool_call["args"].get("path", "").startswith("/etc")`.
  `[code]` — `langchain/agents/middleware/human_in_the_loop.py:194-213` (the
  field definition), `:374,397` (the predicate genuinely being called).

  One important limitation comes with it. The docstring names two modes,
  `"batch"` and `"per_call"`; in the installed version (`langchain` in
  `../recipes/.venv`) the class implements **only** `after_model`/`aafter_model`
  — there is no `wrap_tool_call` — so the batch path is what runs, and on
  that path `ToolCallRequest` is constructed with `tool=None` and a
  node-level `runtime`, so `request.runtime.tool_call_id` and
  `request.runtime.tools` are **unavailable**. A predicate depending on
  either will fail rather than pass through. What is safe to read:
  `req.tool_call["name"]` and `req.tool_call["args"]`. `[code]` —
  `human_in_the_loop.py:194-203` (the mode contract), `:399,488` (only
  `after_model`/`aafter_model` present).

- **A malformed interrupt configuration fails hard, not silently.** An
  `InterruptOnConfig` without a non-empty `allowed_decisions` — a mistyped
  key, or an empty list — raises `ValueError` at construction. The docstring
  states the reason explicitly: a config with no decisions "would otherwise
  be silently dropped, disabling the approval gate for that tool". This is
  the correct fail-closed choice and worth copying when writing your own
  gates: an unreadable guardrail configuration must refuse to boot rather
  than run without a gate. `[code]` — `human_in_the_loop.py:250-254` (the
  `Raises` contract), `:257-265` (config resolution).

- **`False` and "not listed" both mean automatic pass-through.** A tool with
  no `interrupt_on` entry auto-approves; `False` states the same thing
  explicitly. The difference is only readability — and that isn't trivial: a
  list writing `False` for low-risk tools proves the decision was taken,
  whereas an absent entry is indistinguishable from an oversight. `[code]` —
  `human_in_the_loop.py:228-237`.

- **`respond` is the official route for "ask the user" tools, not merely a
  reject variant.** A `respond` decision skips tool execution and returns a
  synthetic `ToolMessage` with `status="success"` holding the human's text —
  the docstring names it for "'ask user' style tools whose real
  implementation is the human's response". The consequence: an ask-the-user
  flow needn't (and preferably shouldn't) use a free-form `interrupt()`; it
  is modelled as a schema'd tool whose answer comes from a human. That is
  also the only shape an editor protocol client can render — see
  [`agent-protocols.md`](agent-protocols.md) §In deepagents. `[code]` —
  `human_in_the_loop.py:111-127`.

  `reject` behaves differently: with `message` omitted, the model is told the
  tool wasn't run **and that it must not repeat the same tool call unless the
  user asks**. `[code]` — `human_in_the_loop.py:104-108`. Omitting `message`
  is therefore a choice rather than an oversight: it produces a rejection
  that stops repetition, while a `message` explaining the reason invites the
  model to try another approach.

- **`args_schema` determines whether `edit` is worth offering.**
  `InterruptOnConfig.args_schema` carries the arguments' JSON schema "if
  edits are allowed" — without it, the approval UI has no basis for
  rendering a correct edit form. Pair them: an `allowed_decisions` including
  `"edit"` without an `args_schema` means humans edit arguments with no
  shape guidance. `[code]` — `human_in_the_loop.py:191-192`.

- **`description` may be a callable, and that is the right place to compose
  approval text.** Its factory receives `(tool_call, state, runtime)` so the
  request text can include formatted arguments and state context. If unset,
  the built-in `description_prefix` `"Tool execution requires approval"` is
  used — English text appearing verbatim in the UI, so a multilingual
  product must supply its own (see [`multilingual.md`](multilingual.md)
  §The table of language-locked points). `[code]` —
  `human_in_the_loop.py:156-190`, `:223,243-248`.
- **Decision records don't automatically become audit rows** — the
  `interrupt()` result (the `approve`/`edit`/`reject`/`respond` decision, who
  decided) lives as part of the **resume payload** the application sends
  (`Command(resume=...)`), not as a separate row `deepagents`/`langgraph`
  automatically writes somewhere queryable across time — only the binary
  checkpoint holding a graph state snapshot. That is what underpins the
  explicit gap in §Pattern: the application must write those decisions to its
  own table (an extension of `tool_calls`/a new table) if it needs a
  queryable audit; `deepagents`/`langgraph` don't provide it. `[inferred]` —
  concluded from the absence of any separate audit-writing mechanism in
  `human_in_the_loop.py` or `deepagents/middleware/`, only the checkpoint
  path cited above.
- `permissions=[FilesystemPermission(mode="interrupt")]` **automatically**
  generates the equivalent `interrupt_on` entries
  (`_build_interrupt_on_from_permissions`), merged with any explicit
  `interrupt_on` — already mapped in `../systems/deepagents.md` §6, details
  not repeated here.

## Sources

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5, §6 —
  a tier-1 reference verified against `deepagents==0.7.8`, cited directly
  without re-reading the `deepagents/graph.py` source in this task.
- `[code]` `langchain/agents/middleware/human_in_the_loop.py` — read
  directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langchain/agents/middleware/human_in_the_loop.py`;
  the `DecisionType`, `ReviewConfig`, `ActionRequest`, `HITLRequest`
  classes, the `interrupt(hitl_request)` call and the reading of
  `interrupt(...)["decisions"]`.
- `[code]` [`guardrails.md`](guardrails.md) point 3 (Tool/action), §6 System
  — the basis for the `interrupt_on`/`permissions` → middleware mapping, and
  the audit log gap this file narrows; its mechanism isn't repeated.
- `[code]` [`tool-design.md`](tool-design.md) §Pattern (the "Granular
  approval (HITL)" row), §Selection heuristics — the basis for the per-tool
  name vs per-operation gate claim.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — the
  `tool_calls` table, cited for the approval column gap; the schema is
  unchanged by this file.
- `[code]` [`streaming-protocol.md`](streaming-protocol.md) §Reattach — the
  basis for the claim that automatically checkpointed interrupt state
  supports reattach.
- `[code]` `SKILL.md` §the 6 discriminating axes — the basis for the "Blast
  radius" axis reused in §Criterion.
