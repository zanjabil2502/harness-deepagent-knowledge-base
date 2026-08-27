# Cost control

## Problem

An unbounded agent loop burns money overnight with nobody noticing until
the bill arrives - that isn't speculation, it follows directly from a fact
`guardrails.md` already records: `deepagents` raises LangGraph's
`recursion_limit` to **9999** as a safety net for legitimately long tasks,
not as a cost ceiling. An application that doesn't explicitly install its
own Loop guardrail effectively has no cost ceiling until 9999 steps are
reached - a number large enough to burn significant money before it stops
on its own.

Second problem: a "budget" with no clear level is useless against two
failures of different shape. One run turning pathological (a single turn
spending hundreds of dollars in a loop) needs a **per-run** limit so one
bad turn doesn't consume a month's budget. One user calling the agent
repeatedly with runs that each look reasonable but add up (distributed
abuse, not one extreme turn) needs a **per-user** limit aggregated across
runs and time, which a per-run limit alone cannot catch. Collapsing both
into one number makes that limit either too tight for legitimate large
tasks, or too loose for distributed abuse.

Third problem: without attributing cost to a specific step, a budget alert
only says "something is expensive", not "what to fix" - the cost-specific
version of the "the agent fails silently" problem in `observability.md`.

## Pattern

### Two budget levels: run and user

- **Per run/thread** - two distinct limits that are often confused:
  `thread_limit` (cumulative across one conversation thread, spanning many
  turns) and `run_limit` (a single execution/turn). Both matter for
  different reasons: `run_limit` catches one turn spiralling;
  `thread_limit` catches a conversation continuing without bound across
  many turns that each look reasonable in isolation. The concrete
  mechanism is in `guardrails.md` point 5
  (`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`) and isn't
  re-proposed here.
- **Per user** - aggregated across runs/threads/time windows (e.g. a
  daily or monthly dollar cap per `user_id`), and this **cannot** be
  enforced by any `deepagents`/`langchain` middleware, because middleware
  only ever sees one graph execution at a time and has no memory across
  runs. It must be enforced at the application layer: accumulated cost per
  `user_id` stored (Postgres/Redis) and checked **before** a new turn is
  allowed to start (a preflight check, not post-hoc after the cost has
  already been incurred) - using exactly the `user_id` scope already
  established in `isolation-and-scoping.md`, with no new model proposed.
- **Kill switch** - two layers: automatic (from the run/user limits above,
  `exit_behavior="error"`/`"end"` in `guardrails.md`, plus
  `cancel_async_task` for background tasks) and **manual/operator**,
  independent of any automatic detection - for a new failure mode no
  detector has caught yet, an operator needs a way to stop a specific
  user's run or the whole system **now**, not when a numeric limit
  happens to be touched.

### Runaway loop detection

Oscillation/no-progress detection (the guardrail point 5 line in
`guardrails.md`; its mechanism isn't re-proposed here) has a cost angle of
its own: a loop can be **"on-budget" by step count** and still be pure
waste - repeating a failing tool call with near-identical arguments, each
one consuming real tokens, making no progress. A numeric limit
(`thread_limit`/`run_limit`) only fires once the Nth step is reached;
oscillation detection can cut in earlier as soon as the pattern is visible
(e.g. N consecutive tool calls with identical arguments/results) - cheaper
than waiting for the numeric ceiling, because every extra step allowed to
run before the limit is reached is real money already burnt.

### Per-step cost attribution

Cost isn't a pipeline separate from tracing - it is an attribute attached
to the same span `observability.md` §Span per step already describes.
`Langfuse` extracts token usage per generation span (`_parse_usage(response)`,
written to the span's `usage`/`usage_details`) and has a per-span
`cost_details` field (defaulting to `cost_details={"total": 0}` before
being recomputed from usage × a model price table). `[code]` -
`langfuse/langchain/CallbackHandler.py` (the lines defining `_parse_usage`,
`usage_details`, and several `cost_details={"total": 0}` defaults). The
practical consequence: a span per **step** (an individual model call, not
a turn aggregate) means cost is also attributed to a specific step - which
subagent, which tool, which model call number - not just "this turn was
expensive", which is exactly what's needed to answer "what should be
fixed" rather than "something is expensive".

## Trade-offs

- **A tight vs loose per-run limit** - tight prevents one turn burning a
  large budget but cuts off legitimately large tasks (long research, a
  refactor across many files); loose accommodates legitimate work but
  slows detection of a pathological loop. A safe default: a `run_limit`
  loose enough for the longest legitimate task, **paired mandatorily**
  with oscillation detection (not just a numeric limit) so a pure-waste
  loop is still cut before the numeric limit is touched.
- **A preflight user budget check (before the turn starts) vs post-hoc
  (after the turn finishes, checked for the next one)** - preflight stops
  an already-over-budget user from starting a new run at all (a kill
  switch that genuinely prevents rather than merely detects after the
  fact), at the cost of one extra query (reading the user's accumulated
  cost) on the critical path before every turn; post-hoc is cheaper
  per-turn but the user can still start one last expensive run before the
  system realises the budget is gone - fine for a soft limit (a warning),
  wrong for a hard cap.
- **An automatic-only kill switch vs one plus a manual operator switch** -
  automatic-only is cheaper to build (no operator panel) but blind to
  failure modes nobody has seen or defined yet; a manual kill switch adds
  work (an operator panel/endpoint, authorisation over who may press it)
  but closes the "the detector doesn't know this failure shape yet" gap
  that automatic-only can never close on its own.

## In deepagents

`deepagents` has no built-in token/cost accounting - no such module was
found in the Task 3 source (`deepagents/graph.py` and the related
middleware never mention usage or cost). `[inferred]` - concluded from the
absence of a cost accounting module in the `deepagents` source dissected in
Task 3. The consequence is identical to `guardrails.md` §In deepagents
point 5: run/thread limits are enforced through
`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`
(`langchain.agents.middleware`, not `deepagents`', injected through
`create_deep_agent(middleware=[...])`) - this file proposes no new
mechanism for that, only explains its cost angle.

Two specifics that matter here:

- **A per-user limit cannot be a `deepagents`/`langchain` middleware at
  all** - not merely "doesn't exist yet", but structurally cannot,
  because middleware operates within a single graph execution (the same
  `create_deep_agent` is called again each turn, with no memory across
  calls except through the application-injected `checkpointer`/`store`).
  Accumulated per-`user_id` cost must live at the application/DB layer and
  be checked before `create_deep_agent(...).invoke(...)` is called - not
  inside any middleware attached to that agent.
- **`AnthropicPromptCachingMiddleware`** (always installed unconditionally,
  a no-op for non-Anthropic providers) directly affects real cost - a
  provider-specific prompt cache reduces the tokens billed at full rate
  for a prefix that doesn't change between calls. `[code]` - cited from
  `../systems/deepagents.md` §Built-in middleware. It is not a cost
  guardrail (no limit is enforced), but it matters for attribution: a span
  showing cache-hit vs cache-miss tokens (if the tracing backend records
  them) explains why one step's cost can be far below a naive
  token-count × full-price estimate.

## Sources

- `[code]` [`guardrails.md`](guardrails.md) - point 5 (Loop): the
  `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` mechanism,
  `exit_behavior`, `cancel_async_task`, oscillation detection, and the
  `recursion_limit=9999` warning - re-cited without proposing any new
  mechanism.
- `[code]` `langfuse/langchain/CallbackHandler.py` (Langfuse Python SDK
  4.14.4, `pip install langfuse` in a separate research venv) -
  `_parse_usage`, the per-span `usage`/`usage_details`/`cost_details`
  fields.
- `[code]` [`observability.md`](observability.md) - §Span per step, the
  basis for the claim that "cost attaches to the same span as tracing";
  not re-proposed.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) - the
  `user_id` scope model that per-user cost accumulation builds on.
- `[inferred]`/`[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §1 (`recursion_limit` 9999), §Built-in middleware
  (`AnthropicPromptCachingMiddleware`) - a tier-1 reference verified in
  Task 3; no cost accounting module was found in the source dissected
  there, cited without re-reading the `deepagents` source in this task.
