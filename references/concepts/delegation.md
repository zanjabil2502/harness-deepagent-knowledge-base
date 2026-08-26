# Delegation

## Problem

"Spawn a subagent, get its result back" looks simple until two things that
are rarely decided deliberately become real problems. First, the **result
contract** — what exactly flows back from subagent to caller — is usually
left implicit: if the subagent's entire working transcript (every tool call,
every trial and error) flows back, delegation loses its own purpose
(isolating and compressing work into one clean handoff) and the caller's
context balloons with precisely what delegation was meant to prevent. If, on
the other hand, private state leaks back, that is an isolation breach nobody
wanted.

Second, **delegation depth** — nothing stops a subagent from spawning
subagents of its own, and with no explicit limit the blast radius (cost, a
runaway loop) grows silently across levels. This is the same pattern as
`agent-loop.md` §Problem: if the "how deep may this branch" decision isn't
made deliberately, actual behaviour is determined by whatever accidental
limit the platform happens to provide — and that accidental limit is usually
one **global** step counter shared by the whole tree rather than a
per-branch depth guard, so it cannot distinguish "one agent running 9000
steps" from "30 subagents running 300 steps each" — both exhaust the same
budget, but only the second is the recursive fan-out pattern that usually
signals something has gone wrong.

## Pattern

### A taxonomy of delegation routes

- **Flat** — one agent, no subagents at all. The baseline; everything below
  is a departure from it for a specific reason (work isolation, parallelism,
  a different model/tool set per sub-task).
- **Synchronous inline** — the caller blocks until the subagent finishes and
  gets one clean result back. Suited to sub-tasks whose result is needed
  before the caller can continue.
- **A caller-owned precompiled runnable** — a subagent built and controlled
  entirely by the calling application (not through the harness constructor),
  used as-is. Suited when the subagent's frame already has its own graph
  shape outside the harness and needs to inherit nothing from the main
  agent.
- **Remote/async** — dispatched to a separate process/server, non-blocking;
  the caller can continue working while waiting. Needs a tracking mechanism
  of its own (a task ID, status polling) because the result isn't
  immediately available in the same turn.
- **Dispatched from code** — the subagent is called from inside code the
  model wrote and an interpreter runs within the loop, rather than being
  chosen by the model one turn at a time. It turns fan-out over N items,
  layered verification, and recursive flows into program structure rather
  than a chain of model decisions. The distinguishing axis isn't
  sync/async but **who orders the dispatches** — and because those
  dispatches happen inside one already-approved tool call, this route
  bypasses the per-dispatch approval gate. The result contract and depth
  limits below still apply in full; only the scheduler changes. See
  [`code-orchestration.md`](code-orchestration.md).

### The result contract is a design decision, not an accidental default

What flows back from subagent to caller must be decided explicitly as one of
two shapes (or a tiered combination), not left as "whatever happens to be in
the subagent's state when it finishes":

- **The full transcript** — everything the subagent did comes back. No
  information is lost, but it defeats the reason for delegating at all: the
  caller's context balloons with exactly the detail delegation was supposed
  to isolate (back to the cost/cache concerns of
  `context-engineering.md`), and internal detail irrelevant to the caller
  (failed attempts, raw tool results needed only by the subagent's
  reasoning) is exposed along with it.
- **A filtered summary** — the subagent returns one clean result already
  filtered to the caller's needs. Compact, leaking no internal working
  detail, but it shifts the design burden onto the subagent's
  `system_prompt`: if the subagent isn't told the answer shape the caller
  needs, that filtering can itself discard the information that was needed.

The contract must also state **what deliberately must not flow back** —
private state relevant only to the subagent's internal work (a history of
failed attempts, temporary credentials/scopes) must not leak into the
caller's state, not merely "happen not to be mentioned".

### Depth limits: deliberate or accidental

The same principle as "who decides to stop" in `agent-loop.md` applies here
along the depth axis: a delegation system needs an **explicit** depth limit,
or it inherits whatever platform limit happens to exist. Two limit shapes
catch different failures and are ideally installed together, not one alone:

- **A per-branch limit** — each subagent knows how deep it sits in the
  delegation tree and refuses to spawn further past N. This catches
  unbounded recursive fan-out (an agent spawning an agent spawning an agent)
  even when each level is cheap — a blast radius growing structurally, not
  just in cost.
- **A shared tree-wide budget** — one total step/cost limit for the whole
  tree (the root plus all its descendants), whatever its shape. This catches
  total cost overrun in any shape, but cannot distinguish "one very deep but
  cheap branch" from "many shallow but expensive branches" — both hit the
  same limit, even though they are different risks (deep but cheap nesting
  is still an audit/observability risk of its own that a budget alone
  doesn't catch).

## Trade-offs

- **Synchronous inline vs remote/async** — synchronous is easier to reason
  about (the caller blocks, gets the result in the same turn, in natural
  order), but consumes the caller's whole execution while the subagent runs
  (additive latency). Async lets the caller keep working, with better
  wall-clock time, but needs its own state tracking mechanism (task IDs,
  polling) — an entirely new correctness surface — and complicates the
  result contract (what if the caller finishes before its subagent, what if
  the user session ends mid-way).
- **Full transcript vs filtered summary** — covered in `## Pattern`; in
  essence the classic completeness-vs-compression trade-off, with real
  consequences in context cost (`context-engineering.md`) on one side and
  information loss on the other.
- **An explicit depth limit vs a shared budget alone** — a depth limit
  catches recursive fan-out cheaply and predictably (a fixed ceiling), but
  is a blunt instrument when a legitimate case occasionally needs deeper
  nesting (requiring manual tuning per archetype). A shared budget is more
  general (catching overrun in any shape) and needs no per-branch
  bookkeeping, but cannot answer "is this depth safe" independently of "is
  this expensive" — two questions that sometimes need different answers.

## In deepagents

Three delegation routes map directly onto the `## Pattern` taxonomy:
`SubAgent` (synchronous inline, through the `task` tool),
`CompiledSubAgent` (a caller-owned precompiled runnable, not inheriting
`state_schema` from `create_deep_agent`), `AsyncSubAgent` (remote/background,
with five tools `start_async_task`/`check_async_task`/`update_async_task`/
`cancel_async_task`/`list_async_tasks`, non-blocking). `[code]` cited from
`../systems/deepagents.md` §4.

**The result contract** for `SubAgent`/`CompiledSubAgent` is concrete and
matches the "filtered summary" pattern: the subagent's final state
`messages` become the content of the `ToolMessage` returned to the `task`
tool — not its entire working transcript. Fields marked `PrivateStateAttr`
in any middleware (collected through `private_state_field_names`) do not
flow back into the main agent's state — that is the concrete mechanism
behind "private state must not leak" in `## Pattern`. `[code]` cited from
`../systems/deepagents.md` §4 (`deepagents/middleware/subagents.py`,
`deepagents/graph.py` lines 894-898). `AsyncSubAgent` has an entirely
different contract shape — not a synchronous `ToolMessage`, but a status
cached in `AsyncSubAgentState.tasks` (`task_id -> AsyncTask`) and
re-checked against the server through the `check_async_task` tool, as its
non-blocking nature requires. `[code]` cited from
`../systems/deepagents.md` §5.

**Depth**: `deepagents` has **no** explicit maximum-depth guard — a
subagent does not automatically inherit the ability to spawn subagents of
its own. The default subagent middleware stack (`FilesystemMiddleware` +
`SummarizationMiddleware` + `PatchToolCallsMiddleware`, then its spec's own
custom `middleware`) does not include `SubAgentMiddleware` unless that
subagent's spec adds it explicitly in `middleware=[...]` — nesting is
possible but requires a conscious opt-in at each level, not a default.
`[code]` cited from `../systems/deepagents.md` §4,
`deepagents/middleware/subagents.py` (the `SubAgent` field list; there is no
built-in `subagents` field). The only backstop against runaway depth is the
`recursion_limit=9999` **shared** by the whole tree (parent plus all
descendants) — not a per-branch counter: a code comment states the parent's
config (including `recursion_limit`) is passed to each subagent through
LangGraph's `ensure_config`, which seeds each run from the parent's ambient
config. `[code]` `deepagents/middleware/subagents.py` lines 558-566,
586-594 (the comments on propagating `recursion_limit`/tags/metadata
through a per-key merge). That is exactly the "shared tree-wide budget"
pattern in `## Trade-offs` above, with no per-branch limit alongside it — a
project needing to distinguish "a deep but cheap branch" from "many
expensive branches" has to build its own depth counter (e.g. through custom
state decremented each time `task` is called); `deepagents` doesn't provide
one. `[inferred]` concluded from the absence of any depth-tracking
parameter/field in the `SubAgent`/`SubAgentMiddleware`/`create_deep_agent`
read in Task 3 and in this task.

## Sources

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §4
  Delegation, §5 State & resume (the three routes
  `SubAgent`/`CompiledSubAgent`/`AsyncSubAgent`, the
  `messages`→`ToolMessage` result contract, `PrivateStateAttr`,
  `AsyncSubAgentState.tasks`) — a tier-1 reference verified in Task 3,
  cited without re-reading the core of
  `deepagents/middleware/subagents.py` beyond the specific lines below.
- `[code]` `deepagents/middleware/subagents.py` lines 558-566, 586-594
  (package `deepagents==0.7.8`, read from
  `references/recipes/.venv/lib/python3.13/site-packages/`, the same venv
  as `../systems/deepagents.md`) — the comments on parent→subagent config
  propagation (`recursion_limit`) through `ensure_config`, the basis for
  the "a shared budget, not per-branch" claim in `## In deepagents`.
- `[code]` `deepagents/middleware/subagents.py` — the `class SubAgent`
  definition (available fields:
  `tools`/`model`/`middleware`/`interrupt_on`/`skills`/`permissions`/`response_format`,
  with no built-in `subagents` field), the basis for the "nesting requires
  an explicit opt-in" claim in `## In deepagents`.
- `[code]` [`agent-loop.md`](agent-loop.md) §Problem — the "who decides"
  pattern generalised to the delegation depth axis in this file; written in
  the same task, not re-proposed here.
- `[code]` [`context-engineering.md`](context-engineering.md) — referenced
  for the context cost consequences of a "full transcript" result contract.
