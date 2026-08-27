# Planning

## Problem

Two symmetric failures, both real: a multi-step task worked without any
written plan loses the thread as soon as step 4 turns up something that
changes steps 6 and 7 - there is no artifact holding the plan, only
momentary reasoning living in the current call's context, gone as soon as
that context is compacted or the session is resumed. Conversely, a trivial
task forced through a formal planning process (write a todo list, mark
in-progress, do the work, mark completed) pays several tool round-trips
merely to confirm a structure that was obvious from the start - tokens and
turns spent on overhead that adds nothing to the result.

The mistake underlying both is the same: treating "always plan" or "never
plan" as a global policy rather than a per-task decision with a clear
threshold. Without an explicit threshold, the decision falls to whatever
default happens to apply - if a planning tool is always available, some
models use it for everything "to be safe"; if it is never offered, tasks
that genuinely need decomposition get done haphazardly.

## Pattern

### A concrete threshold: three steps, not a feeling

The `write_todos` tool description in `langchain` puts a number on a
decision usually left vague: **"if the user's request is trivial and takes
less than 3 steps, it is better to NOT use this tool and just do the task
directly."** `[code]` `langchain/agents/middleware/todo.py`
(`WRITE_TODOS_TOOL_DESCRIPTION`). This isn't vibes advice - it is a
heuristic with a number that can be reused: if decomposing a task yields
fewer than three distinct steps, the cost of writing and updating the list
(at minimum one tool call to create it, another to mark progress, another to
close it) exceeds the value gained - the list itself becomes an extra task
rather than an aid to one.

### Explicit (a surviving artifact) vs implicit (momentary reasoning)

The difference isn't how detailed the plan is, but **where the plan lives**:

- **Implicit** - the plan exists in the model's reasoning for the current
  turn and is never written as separate state. Cheap (zero extra tool
  calls), but it disappears as soon as the context holding it is compacted
  or the session resumes from a checkpoint - callers outside the model
  cannot see the plan at all, only its effects (the tool call sequence that
  happened), and if the session breaks mid-way the plan has to be inferred
  again from the transcript rather than read directly.
- **Explicit** - the plan is written as structured state that survives
  independently of conversation messages. `PlanningState.todos`
  (`langchain`) is a state field separate from `messages` - `write_todos`
  overwrites the `todos` field through `Command(update={"todos": todos,
  ...})`, rather than writing the plan as text mixed into message history.
  `[code]` `langchain/agents/middleware/todo.py` (the `_write_todos`
  function, the `TodoListMiddleware` class, `state_schema = PlanningState`).
  The consequence is concrete: `SummarizationMiddleware`/any compaction
  operates on `messages`, not on other state fields - an already-written
  todo list doesn't vanish when old message history is summarised, because
  it isn't part of the `messages` being summarised. That is the concrete
  difference from an implicit plan existing only as reasoning inside a
  message - once that message is folded into a compaction, the plan goes
  with it.

The explicit form also enforces a discipline implicit reasoning doesn't give
for free: the `write_todos` tool documentation lists the rules for when a
task **must not** be marked complete - an unresolved issue, partial work, a
blocker, quality standards not met `[code]`
`langchain/agents/middleware/todo.py` (`WRITE_TODOS_TOOL_DESCRIPTION`, the
"Never mark a task as completed if" section). An explicit list with
per-item status can be checked against these rules directly (which line is
marked complete, was it actually finished); implicit reasoning has no object
to check at all.

### A plan is not the answer - and not a stop signal

Two recurring traps with the explicit form, both documented directly in the
`write_todos` tool description `[code]`: (1) marking the last todo complete
is **not** the answer to the user - the substantive result requested (the
number, the summary, the comparison) must appear as message content
**after** the final `write_todos` call, not be treated as represented by a
"completed" status; (2) all todo items being finished is not by itself a
loop stop signal - the stopping mechanism remains as described in
[`agent-loop.md`](agent-loop.md) (implicit: no more `tool_calls`; or
explicit if the project builds its own completion tool). A todo list is a
memory/progress aid, **not** a loop shape - an ordinary ReAct loop can use a
todo list as an internal record without becoming plan-execute (which stops
because the plan is exhausted, see `agent-loop.md`); they are different axes
and can be combined or not independently.

### A plan not kept honest is worse than no plan

A todo list marking a step "completed" when the tool call trail shows that
step actually failed or was skipped gives false confidence to its reader
(the user, or another process reading the state) - worse than having no plan
at all, because no plan at least claims nothing. The "don't mark complete
unless it really is" rule above is the defence against this, but that rule
lives only in the prompt/tool description - compliance depends on the model,
exactly as argued in `guardrails.md` §Policy must not live only in the
prompt. Unlike the class of policy discussed in
[`policy-as-data.md`](policy-as-data.md), "is this step genuinely finished"
is generally **not** verifiable by pure code - verifying it needs a
per-task definition of "done" usually as complex as performing the task
itself (e.g. passing tests for a coding task is code-verifiable, but "this
research is deep enough" isn't). That limit deserves explicit
acknowledgement: part of planning discipline stays in the realm of model
judgement; not all of it can be moved into code enforcement.

## Trade-offs

- **An explicit todo list vs implicit reasoning** - explicit pays tokens
  plus an extra tool-call turn per update, and gets in return resumability
  (surviving message compaction), visibility to callers/observers, and an
  inspectable status discipline. Implicit costs nothing extra but the plan
  is gone as soon as the context holding it is compacted, and callers
  outside the model never see the plan, only its effects.
- **The ≥3-step threshold enforced by model judgement (the tool
  description) vs enforced by the harness (an application decision up
  front, per task type/archetype)** - model judgement is flexible per
  request (adapting to each request's actual complexity) but depends on the
  model genuinely following the tool description's instruction, and counting
  "how many steps" before the plan exists is a chicken-and-egg problem that
  fundamentally needs judgement rather than a pure code check. A
  harness-level decision (e.g. the Workflow Agent archetype always using
  plan-execute, the In-App Copilot archetype almost never needing a todo
  list because its horizon is short) removes the per-request decision but is
  less precise for tasks that don't fit their archetype's pattern.
- **A todo list as a memory aid (ReAct + a todos state field) vs full
  plan-execute (the loop stopping because the plan is exhausted)** - a pure
  memory aid stays flexible when surprises appear mid-way (todos are simply
  rewritten; the loop isn't bound to complete the plan exactly as first
  written), but gives no guarantee that "every plan step will be executed" -
  the model can stop (implicitly) before the plan is finished with nothing
  forcing it back. Full plan-execute guarantees plan coverage but needs a
  separate replanning engine as soon as the plan turns out to be wrong
  mid-way (see `agent-loop.md`).

## In deepagents

`TodoListMiddleware` is **not** part of the default `create_deep_agent`
stack - it must be injected explicitly through
`middleware=[TodoListMiddleware()]`, and it comes from
`langchain.agents.middleware`, not `deepagents`. `[code]` cited from
`../systems/deepagents.md` §5 (`deepagents/graph.py` lines 361-402; the base
stack list never mentions `TodoListMiddleware`). `DeepAgentState` itself
adds no `todos` field - once `TodoListMiddleware` is installed, the graph
state gains `PlanningState.todos` from `langchain`; see `## Pattern` above
for its properties (separate from `messages`, not folded into compaction).
`[code]` `langchain/agents/middleware/todo.py`, cited from
`../systems/deepagents.md` §5.

This middleware injects `WRITE_TODOS_SYSTEM_PROMPT` at the end of the system
message through `wrap_model_call` **every time** the model is called
(`request.override(system_message=new_system_message)`, rebuilding the
`SystemMessage` with the extra block) - not once at session start. `[code]`
`langchain/agents/middleware/todo.py` (the `wrap_model_call` method of
`TodoListMiddleware`). The injected text itself is static (identical on
every call), so it doesn't change the cache-friendliness argument in
[`context-engineering.md`](context-engineering.md) - what changes each turn
is the `todos` **state field**, not the instruction text about using it.

The `write_todos` tool itself may only be called once per model turn
(preventing two parallel calls overwriting each other's `todos` field, since
the tool replaces the whole list rather than appending one item), and its
description explicitly separates "marking a todo complete" from "giving the
user the answer" - two different acts requiring two different messages.
`[code]` the `TodoListMiddleware` class docstring,
`WRITE_TODOS_TOOL_DESCRIPTION`'s "When You Finish" section,
`langchain/agents/middleware/todo.py`.

## Sources

- `[code]` `langchain/agents/middleware/todo.py` (package
  `langchain==1.3.16`, read from
  `references/recipes/.venv/lib/python3.13/site-packages/`, the same
  research venv as `../systems/deepagents.md`) -
  `WRITE_TODOS_TOOL_DESCRIPTION` (the ≥3-step threshold, the "Never mark a
  task as completed if" rules, the "When You Finish" section),
  `WRITE_TODOS_SYSTEM_PROMPT`, the `Todo`/`PlanningState`/`TodoListMiddleware`
  classes, the `_write_todos` function, the `wrap_model_call` method.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 State
  & resume (`TodoListMiddleware` is not a default; no `todos` field in the
  built-in `DeepAgentState`) - a tier-1 reference verified in Task 3.
- `[code]` [`agent-loop.md`](agent-loop.md) - the loop shape taxonomy
  (implicit/explicit/plan-execute) referenced to distinguish a todo list as
  a memory aid from plan-execute as a loop shape; written in the same task,
  not re-proposed here.
- `[code]` [`policy-as-data.md`](policy-as-data.md) §The distinguishing
  test - referenced for the limit that "is this step genuinely finished" is
  generally not code-verifiable, in contrast with the policy class that can
  be moved into data.
- `[code]` [`context-engineering.md`](context-engineering.md) - referenced
  for the claim that the static `WRITE_TODOS_SYSTEM_PROMPT` text doesn't
  disturb system message cache-friendliness.
- `[code]` [`guardrails.md`](guardrails.md) §Policy must not live only in
  the prompt - the basis for the argument about compliance with the "don't
  mark complete before it really is" rule living only in a tool
  description, not re-proposed here.
