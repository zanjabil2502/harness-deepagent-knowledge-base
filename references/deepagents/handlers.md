# `deepagents` - handlers & hooks

The available intercept points, what each one may change, what it
**cannot**, and the official error-handling patterns.

Every hook here comes from `langchain.agents.middleware.AgentMiddleware`;
`deepagents` adds no new hook types - it only assembles middleware that
uses them. `[code]` - `langchain/agents/middleware/types.py` lines
385-740.

## Hook table

| Hook | When | Receives | May change | **Cannot** |
|---|---|---|---|---|
| `before_agent` / `abefore_agent` | once per run, before the loop | `state`, `runtime` | a state update (`dict`), including rewriting `messages` wholesale | doesn't see `ModelRequest`; cannot change the tool list |
| `before_model` / `abefore_model` | every iteration, before the `model` node | `state`, `runtime` | a state update; `jump_to` when declared via `@hook_config(can_jump_to=[...])` | doesn't see or change `request.tools` or the system message |
| `wrap_model_call` / `awrap_model_call` | wraps the LLM call | `ModelRequest`, `handler` | `model`, `tools`, `system_message`, `messages`, `response_format`, `tool_choice` through `request.override(...)`; may call `handler` 0..N times; may return an `AIMessage` directly | ⚠️ a `Command` with `goto`, `resume`, or `graph` is **rejected** (`factory.py` lines 245-256). State updates only through `ExtendedModelResponse(command=...)` |
| `after_model` / `aafter_model` | every iteration, after the `model` node, in **reverse order** | `state`, `runtime` | a state update; `jump_to`; `interrupt()` | cannot cancel an LLM call that already happened (its cost is already incurred) |
| `wrap_tool_call` / `awrap_tool_call` | wraps each tool execution | `ToolCallRequest`, `handler` | tool arguments before execution; the result after; may skip calling `handler` (short-circuit); may return a `ToolMessage` or `Command` | doesn't see the other tool calls in the same `AIMessage` |
| `after_agent` / `aafter_agent` | once per run, before END, in **reverse order** | `state`, `runtime` | a state update; `jump_to` back to the model | cannot change the graph's structure |

On async variants: if a middleware implements only the sync version and
the graph runs through `ainvoke`, `create_agent` still installs it via
`RunnableCallable`, but for `wrap_*` a `NotImplementedError` can surface -
`factory.py` deliberately collects middleware having **either** sync or
async so that taking the wrong path fails visibly rather than silently.
`[code]` - `langchain/agents/factory.py` lines 1040-1060.

## Human-in-the-loop

Two paths, both ending at `HumanInTheLoopMiddleware`:

1. `create_deep_agent(interrupt_on={...})` - explicit, per tool name.
2. `create_deep_agent(permissions=[FilesystemPermission(..., mode="interrupt")])`
   - `_build_interrupt_on_from_permissions` synthesises `interrupt_on`
   entries with a `when` predicate that evaluates the path per call.

The two are merged by `_merge_fs_interrupt_on`; user entries win per tool
name. If the merged result is empty, the middleware is **not installed at
all**. `[code]` - `deepagents/graph.py` lines 182-198, 871-876;
`deepagents/middleware/_fs_interrupt.py`.

### The shape of `InterruptOnConfig`

`[code]` - `langchain/agents/middleware/human_in_the_loop.py` lines 51,
146-215.

| Field | Type | Notes |
|---|---|---|
| `allowed_decisions` | `list[Literal["approve","edit","reject","respond"]]` | Required. `respond` = the human answers **instead of** the tool; the tool is not executed and a synthetic `ToolMessage` with status `success` goes to the model. |
| `description` | `str` or a callable `(tool_call, state, runtime) -> str` | The text the approver sees. |
| `args_schema` | `dict` | JSON schema for the `edit` decision. |
| `when` | `(ToolCallRequest) -> bool` | An auto-approve predicate. This is the only official way to express "interrupt only when condition X". |

`interrupt_on={"execute": True}` is sugar for
`allowed_decisions=["approve","edit","reject"]`.

### Resume

A LangGraph interrupt means the run **stops** and the checkpointer records
its position. Continuing means
`invoke(Command(resume=HITLResponse(...)), config)` with the same
`thread_id`. Without a `checkpointer`, `interrupt_on` is useless - there
is nowhere to store the pause point.

⚠️ Inheritance: a declarative `SubAgent` inherits top-level
`interrupt_on`; `CompiledSubAgent` and `AsyncSubAgent` **do not**. A
subagent that supplies its own `interrupt_on` **replaces** the inherited
one rather than adding to it.

## Error-handling patterns

### A tool fails (exception)

`FilesystemMiddleware.wrap_tool_call` **deliberately lets tool exceptions
through**, including `ToolException` (docstring: "propagate through this
wrapper unhandled by design"). What officially handles them:

| Need | Middleware | Key configuration |
|---|---|---|
| Turn the exception into an error `ToolMessage` | `ToolErrorMiddleware` | `on_error=<callable>`, `aon_error=`, `tools=` (a subset). A handler returning `None` **re-raises the exception** |
| Retry with backoff | `ToolRetryMiddleware` | `max_retries=2`, `retry_on=`, `on_failure="continue"\|"error"\|callable`, `backoff_factor=2.0`, `initial_delay=1.0`, `max_delay=60.0`, `jitter=True` |
| Refuse before execution | your own `wrap_tool_call`, returning `ToolMessage(status="error")` | the maintainer's `ShellAllowListMiddleware` pattern |

`[code]` - `langchain/agents/middleware/tool_error.py` lines 75-105,
`tool_retry.py` lines 133-175.

### The model fails / times out

| Need | Middleware | Key configuration |
|---|---|---|
| Retry the model call | `ModelRetryMiddleware` | `max_retries=2`, `retry_on=`, `on_failure="continue"\|"error"\|callable`, same backoff as tools |
| Fall back to another model | `ModelFallbackMiddleware` | `ModelFallbackMiddleware(first_model, *additional_models)` - tried in order |
| Context overflow | already handled by deepagents' `SummarizationMiddleware`: `ContextOverflowError` is caught, history is compacted, and the request is retried | `create_summarization_middleware(...)` |

Pure network timeouts are not a middleware concern - configure them on the
model constructor (`ChatAnthropic(default_request_timeout=...,
max_retries=...)` - the alias `timeout` is also accepted).

### Budget exhausted

| Limit | Mechanism | Behaviour when exceeded |
|---|---|---|
| Graph steps | LangGraph's `recursion_limit`, default `9_999` from `create_deep_agent` | `GraphRecursionError` |
| Model calls | `ModelCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior="end"\|"error")` | `"end"` = jump to END plus an explanatory `AIMessage`; `"error"` = `ModelCallLimitExceededError` |
| Tool calls | `ToolCallLimitMiddleware(tool_name=, thread_limit=, run_limit=, exit_behavior="continue"\|"error"\|"end")` | `"continue"` = the over-limit tool is blocked with an error message while other tools keep running; `"end"` = stop now |

`recursion_limit` is overridden through
`agent.with_config({"recursion_limit": N})` or
`agent.invoke(..., config={"recursion_limit": N})` - which is what the
maintainers use in `examples/better-harness/better_harness/agent.py` and
in `libs/code/deepagents_code/agent.py` (`.with_config({**config,
"recursion_limit": effective_recursion_limit})`). `[code]` - repo
`langchain-ai/deepagents` commit `23b83ad`.

⚠️ The `9_999` default is not a safeguard; in practice it means
"unlimited". Every deployment must lower it explicitly.

`ToolCallLimitMiddleware` counts the **number** of calls, not identical
repetitions. There is no built-in "spinning in place" detection - see the
example in [`middleware.md`](middleware.md).

### Human interruption (cancel/kill)

There is no "stop all runs" API in `deepagents`. What exists:

- `interrupt()` (HITL) - a cooperative pause awaiting
  `Command(resume=...)`.
- Cancelling the asyncio task or killing the process - leaves dangling
  tool calls in the checkpoint. `PatchToolCallsMiddleware.before_agent`
  cleans them up on the next run with a synthetic `ToolMessage` reading
  "was cancelled - another message came in before it could be completed".
  This is the only official safety net for abrupt cancellation.
- A fleet-level kill switch is the responsibility of the orchestrator/
  queue above `deepagents`.

`[code]` - `deepagents/middleware/patch_tool_calls.py` lines 30-45.

### A subagent fails

If `subagent_type` is unknown, the `task` tool returns an ordinary error
**string** ("we cannot invoke subagent X ... the only allowed types are
...") rather than an exception - the model can try another name.
If a `CompiledSubAgent` returns state without a `messages` key,
`_return_command_with_state_update` **raises `ValueError`** and the run
fails. `[code]` - `deepagents/middleware/subagents.py` lines 474-482, 549
(sync path) and 577 (async path).

## What cannot be intercepted

- **The contents of the HTTP request to the provider** - that belongs to
  the `BaseChatModel` object.
- **Tool call ordering.** There is no "tool B must follow tool A" hook.
  `PatchToolCallsMiddleware` is often mistaken for an ordering enforcer;
  it only patches missing `ToolMessage`s. Ordering can only be enforced
  through prompt instructions, or a `wrap_tool_call` that refuses calls
  violating the order - neither of which is a structural guarantee.
- **Removing `FilesystemMiddleware`/`SubAgentMiddleware`** -
  `HarnessProfile.excluded_middleware` refuses with a `ValueError`.
- **Making `after_model` run after HITL** - HITL is always first in that
  phase (see [`middleware.md`](middleware.md) §5).

## Sources

**Versions read**: `deepagents==0.7.8`, `langchain==1.3.16`.

`[code]` from `references/recipes/.venv/lib/python3.13/site-packages/`:

- `langchain/agents/middleware/types.py` (the `AgentMiddleware` contract,
  decorators)
- `langchain/agents/middleware/human_in_the_loop.py` (`DecisionType`,
  `InterruptOnConfig`, `HITLRequest`/`HITLResponse`)
- `langchain/agents/middleware/tool_error.py`, `tool_retry.py`,
  `model_retry.py`, `model_fallback.py`, `model_call_limit.py`,
  `tool_call_limit.py` (`__init__` signatures plus docstrings)
- `langchain/agents/factory.py` (rejection of `Command` in
  `wrap_model_call`, per-hook middleware collection)
- `deepagents/graph.py`, `deepagents/middleware/_fs_interrupt.py`,
  `patch_tool_calls.py`, `filesystem.py`, `subagents.py`,
  `summarization.py`

`[code]` from `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21): `examples/better-harness/better_harness/agent.py`
lines 206-226 and `libs/code/deepagents_code/agent.py` lines 3093-3110
(the `recursion_limit` pattern).
