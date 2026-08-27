# Agent loop

## Problem

The "agent loop" is often treated as a single shape - think, act, observe,
repeat (ReAct) - when that is only one of several valid shapes, and the more
important question usually goes unanswered: **who decides the loop stops,
and through what signal?** Without an explicit answer, stopping behaviour
becomes an accident of whatever library default happens to be in play - a
recursion limit installed as a safety net (not as a "when is the task
finished" decision) mistaken for a task-completion mechanism, or a magic
string convention nobody ever wrote down as a deliberate decision.

The concrete confusion: "the loop stopped because the task is finished" and
"the loop stopped because the budget ran out" are **entirely different**
events - one a model decision (implicit or explicit), one a harness
decision independent of what the model wanted - but if the two aren't
distinguished at the exit point, downstream callers (the code processing
the run's result) cannot tell which happened without manually re-inspecting
state. A budget-truncated run is treated exactly like a normally finished
one → a partial answer goes to the user as if it were final, or the retry
logic that should fire for a truncated run never triggers because the
signal wasn't distinguished.

## Pattern

### A taxonomy of who-decides-to-stop

- **Implicit: the model stops by doing nothing** - the standard ReAct loop:
  the model is called repeatedly, the loop continues while the last
  response still contains `tool_calls`, and stops as soon as the last
  response contains **none**. There is no positive act marking "I'm done" -
  the absence of an act is itself the signal. Consequence: the harness has
  no event to record ("the model decided it was done at step N") - the
  "finished" conclusion can only be drawn after the fact, from the absence
  of a next tool call.
- **Explicit: the model calls a completion tool** - the SWE-agent pattern:
  the `submit` tool (recording the final diff and printing the
  `<<SWE_AGENT_SUBMISSION>>` sentinel the harness scans for) and
  `exit_forfeit` (an explicit give-up) are two **different** ways for the
  model to declare it is done - stopping not because it ran out of things
  to do, but because it actively called a tool meaning "I'm finished" or "I
  give up". `[code]` `tools/submit/config.yaml`, `tools/submit/bin/submit`,
  `tools/forfeit/config.yaml`, repo `SWE-agent/SWE-agent`. The difference
  from the implicit form: there is a concrete event to log/audit ("the
  model called `submit` at step N", not inferred from an absence), and the
  completion payload can be structured (the patch content, not just free
  text).
- **Plan-execute: done = every plan step marked complete** - a two-phase
  loop: a planning phase produces the list of steps first, an execution
  phase runs/verifies each one; it stops when the plan is exhausted, not
  when the model "feels" done mid-execution. See
  [`planning.md`](planning.md) for when explicit planning like this pays
  off versus becoming overhead - this file only marks the shape as a
  distinct loop variant, without repeating that analysis.
- **Externally supervised loop-until-done** - a supervisor outside the
  model (a scheduler, cron, an event trigger) decides when the loop runs
  and when it stops entirely; the model is never consulted about "when to
  stop" for a given round, that is a system decision. Relevant to the
  Workflow Agent archetype (`archetypes/06-workflow-agent.md`), which is
  deliberately designed with no human or model in the loop for the stop
  decision.

### Stopped-because-finished vs stopped-because-of-budget - two mechanisms, not one signal

Guardrail point 5 (`guardrails.md` - max tool calls, max model calls, kill
switch) is a **third breaker** standing entirely outside the model:
`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` stop the loop because
the budget is exhausted, regardless of whether the model wanted to continue
or was about to stop. That middleware's `exit_behavior` **is** the explicit
declaration of what happens when the budget runs out: `"error"` (raise an
exception, a clearly failed run), `"end"` (force the turn closed with state
as-is), `"continue"` (the library default - the loop doesn't actually stop,
see the warning in `guardrails.md`). The crucial point: **a run stopped by
`exit_behavior="end"` is not a finished run** - it is a run cut off
mid-flight, and the code processing its result must treat those two states
(normally finished vs budget-truncated) as two separate signals, not one
"the run stopped = the run is done" boolean. Collapsing them means a
partial answer (possibly with tool calls never executed, state not yet
consistent) goes downstream as if it were the final answer the model itself
decided on.

## Trade-offs

- **Implicit stopping vs an explicit completion tool** - implicit adds no
  tool surface (the model needn't be taught or reminded to call anything to
  finish), but the harness has no positive signal separating "done,
  satisfied with the result" from "quietly stopped out of confusion or
  surrender" - both appear as "no more tool_calls". An explicit tool gives
  a clean signal plus a structured payload (a diff, a final answer, a
  confidence level), but the model sometimes forgets to call it - exiting
  with ordinary text and no `tool_calls`, which drops the harness back to
  exactly the implicit behaviour even though the explicit tool was built.
  The mitigation (reprompting "are you sure you're finished?" before
  actually closing the turn) adds complexity the implicit form never needs.
- **Plan-execute vs loop-until-the-model-decides** - planning first gives
  an externally inspectable progress signal ("N of M steps done"), useful
  for progress UI and duration estimates; but the plan can be wrong as soon
  as execution hits something unexpected, forcing a replanning mechanism
  that loop-until-done never needs (that loop is designed to be open-ended).
  Loop-until-the-model-decides is flexible for open-ended tasks but has no
  external checkpoint to gauge progress until it is fully finished.
- **Separating the finished-vs-budget signal into two flags vs one combined
  signal** - two separate flags preserve precision (a budget-truncated run
  is often worth retrying with a larger budget; a normally finished one is
  not), at a cost: downstream callers must handle two states, not one. One
  combined signal is simpler to consume but discards a distinction that
  matters for cost accounting and retry logic.

## In deepagents

The default shape is **implicit** - `create_deep_agent(...)` delegates the
loop to `langchain.agents.create_agent(...)`, documented as creating "an
agent graph that calls tools in a loop until a stopping condition is met":
the model ⇄ tool loop stops when the last `AIMessage` contains no
`tool_calls` - that stop decision is purely implicit in the absence of a
next tool call, not something `deepagents` decides itself. `[code]` cited
from `../systems/deepagents.md` §1 (`langchain/agents/factory.py` lines
859-860). The automatically installed `recursion_limit=9999` is **not** a
"when to stop" mechanism - it is a safety net so a legitimately long task
isn't cut off by a `GraphRecursionError` at LangGraph's much smaller
default limit (25). `[code]` cited from `../systems/deepagents.md` §1.
There is no built-in `submit`/`exit_forfeit` tool pattern - a project
needing a SWE-agent-style explicit completion signal has to write it as a
custom tool; `deepagents` doesn't provide one. `[inferred]` concluded from
the built-in tools listed in `../systems/deepagents.md` §3
(`ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep`/`execute`/`task`),
none of which serve as a task-completion signal.

`response_format` on `create_deep_agent`/`SubAgent` (a Pydantic schema or
dict forcing the final output into a given structure) provides a
program-inspectable completion payload - similar in effect to SWE-agent's
`submit` tool (a structured final result rather than free text) - but does
**not** change the stopping mechanism itself: the loop still stops
implicitly when there are no `tool_calls`; `response_format` only shapes
the content of the final message once that point is reached. `[code]`
`deepagents/graph.py` lines 280, 507, 927;
`deepagents/middleware/subagents.py` lines 127, 337, 388-430 (the
`response_format` parameter on `create_deep_agent` and on the
`SubAgent`/`CompiledSubAgent` spec), the same research venv as
`../systems/deepagents.md`.

The "finished vs out of budget" distinction from `## Pattern` above maps
directly onto `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`'s
`exit_behavior`, already documented in full in `guardrails.md` point 5 -
this file doesn't repeat that table, it only stresses that those two
middlewares are a **third** loop breaker (besides "the model stops
implicitly" and "an explicit signal, if built custom") operating
independently of the model's intent.

## Sources

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §1 Loop
  shape (`create_agent`, the implicit stop condition,
  `recursion_limit=9999`), §3 Tool surface (the built-in tool list, the
  basis for the claim that there is no built-in explicit completion tool) -
  a tier-1 reference verified in Task 3, cited without re-reading the core
  `deepagents/graph.py` in this task.
- `[code]` `deepagents/graph.py` lines 280, 507, 927 (package
  `deepagents==0.7.8`, read from
  `references/recipes/.venv/lib/python3.13/site-packages/`, the same venv
  as `../systems/deepagents.md`) - the `response_format` parameter on
  `create_deep_agent`.
- `[code]` `deepagents/middleware/subagents.py` lines 127, 337, 388-430
  (same venv) - `response_format` on the `SubAgent`/`CompiledSubAgent`
  spec.
- `[code]` `tools/submit/config.yaml`, `tools/submit/bin/submit`,
  `tools/forfeit/config.yaml`, repo `SWE-agent/SWE-agent`, read via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/tools/submit/config.yaml`,
  `.../tools/submit/bin/submit`, `.../tools/forfeit/config.yaml` - the
  `submit`/`exit_forfeit` tools as an explicit completion signal.
- `[code]` [`guardrails.md`](guardrails.md) point 5 (Loop) - the
  `exit_behavior`/`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`
  table, referenced for the budget-based loop breaker, not re-proposed
  here.
- `[code]` [`planning.md`](planning.md) - the plan-execute loop shape
  referenced as a taxonomy variant, with the analysis of when explicit
  planning pays off delegated to that file; written in the same task, not
  re-proposed here.
