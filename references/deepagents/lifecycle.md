# `deepagents` — the lifecycle of one turn

What happens from `agent.invoke({"messages": [...]})` to the final state,
stage by stage, and where each stage can be intervened in officially.

`create_deep_agent` does not build its own graph: it assembles a
middleware stack and then calls `langchain.agents.create_agent(...)`. So
the lifecycle is `create_agent`'s lifecycle, with the middleware nodes
`deepagents` assembles. `[code]` — `deepagents/graph.py` lines 922-944;
`langchain/agents/factory.py` lines 1543-1830 (node and edge assembly).

## Flow diagram

```
                     invoke(state, config)
                              │
                              ▼
                        ┌───────────┐
                        │   START   │
                        └─────┬─────┘
                              │
      ┌───────────────────────▼────────────────────────┐
      │  before_agent  (node, once per RUN)            │   order = list order
      │  m[0].before_agent → m[1].before_agent → …     │   (PatchToolCalls, Skills,
      └───────────────────────┬────────────────────────┘    Memory, Rubric)
                              │
   ╔══════════════════════════▼═══════════════════════════════════════════╗
   ║  LOOP  (repeats until the model stops calling tools)                 ║
   ║                                                                      ║
   ║   ┌──────────────────────────────────────────────┐                   ║
   ║   │  before_model (node, every iteration)        │  list order       ║
   ║   │  m[0] → m[1] → …                             │  (ModelCallLimit) ║
   ║   └──────────────────┬───────────────────────────┘                   ║
   ║                      │                                               ║
   ║   ┌──────────────────▼───────────────────────────┐                   ║
   ║   │  node "model"                                │                   ║
   ║   │                                              │                   ║
   ║   │  ModelRequest assembled:                     │                   ║
   ║   │    model, tools=default_tools,               │                   ║
   ║   │    system_message, response_format,          │                   ║
   ║   │    messages=state["messages"], state, runtime│                   ║
   ║   │                     │                        │                   ║
   ║   │   wrap_model_call ONION (m[0] = OUTERMOST):  │                   ║
   ║   │     m0( … m1( … mN( _execute_model )))       │                   ║
   ║   │        Skills/FS/Memory add to system prompt │                   ║
   ║   │        FS filters tools backend can't do     │                   ║
   ║   │        Summarization compacts if needed      │                   ║
   ║   │        _ToolExclusion (innermost) drops tools│                   ║
   ║   │                     │                        │                   ║
   ║   │   messages = [system_message, *messages]     │                   ║
   ║   │   model_.invoke(messages)  ◄── the LLM call  │                   ║
   ║   │                     │                        │                   ║
   ║   │   _handle_model_output → ModelResponse       │                   ║
   ║   └──────────────────┬───────────────────────────┘                   ║
   ║                      │                                               ║
   ║   ┌──────────────────▼───────────────────────────┐                   ║
   ║   │  after_model (node)  REVERSE ORDER           │  m[n] → … → m[0]  ║
   ║   │  HumanInTheLoopMiddleware LIVES HERE         │  ← interrupt()    ║
   ║   └──────────────────┬───────────────────────────┘                   ║
   ║                      │                                               ║
   ║          ┌───────────▼────────────┐                                  ║
   ║          │ any tool_calls?        │                                  ║
   ║          └──┬──────────────────┬──┘                                  ║
   ║       yes   │                  │ no → exit the loop                  ║
   ║   ┌─────────▼──────────────────────────────────┐                     ║
   ║   │  node "tools"                              │                     ║
   ║   │   wrap_tool_call ONION (m[0] = OUTERMOST)  │                     ║
   ║   │     FS: evict large results to the backend │                     ║
   ║   │     ToolRetry/ToolError when installed     │                     ║
   ║   │   → ToolMessage / Command enters state     │                     ║
   ║   └─────────┬──────────────────────────────────┘                     ║
   ║             └──────────► back to before_model/model                  ║
   ╚══════════════════════════╤═══════════════════════════════════════════╝
                              │
      ┌───────────────────────▼────────────────────────┐
      │  after_agent (node, once per RUN)              │  REVERSE ORDER
      │  m[n].after_agent → … → m[0].after_agent       │  (RubricMiddleware)
      └───────────────────────┬────────────────────────┘
                              │
                        ┌─────▼─────┐
                        │    END    │
                        └───────────┘
```

`[code]` — `langchain/agents/factory.py`: `model_node` lines 1468-1489,
`_execute_model_sync` lines 1441-1466, onion composition
`_chain_model_call_handlers` lines 263-352 (with the explicit comment
"first in list becomes outermost layer"), edge wiring lines 1675-1830.
The reverse ordering of `after_model` is readable from
`graph.add_edge("model", f"{middleware_w_after_model[-1].name}.after_model")`
at line 1793, which chains down to index 0; `after_agent` is the same,
lines 1817-1830.

## Stage by stage

### 1. `before_agent` — once per run

A graph node. Executed in middleware list order. In the default stack only
`PatchToolCallsMiddleware` uses it — it patches synthetic `ToolMessage`s
for dangling/malformed tool calls in history, then **rewrites all
`messages`** with `RemoveMessage(id=REMOVE_ALL_MESSAGES)` followed by its
patched list. This is what stops a resume after a crash/cancel from being
rejected by the provider. `SkillsMiddleware`, `MemoryMiddleware`, and
`RubricMiddleware` also use this hook (loading the skill index /
`AGENTS.md` contents / the rubric into state). `[code]` —
`deepagents/middleware/patch_tool_calls.py` lines 14-45; `skills.py` line
928; `memory.py` line 274; `rubric.py` line 522.

**Intervention point**: your own `before_agent` middleware, or the
`@before_agent` decorator from `langchain.agents.middleware`. It can
`jump_to` END.

### 2. `before_model` — every loop iteration

A graph node, list order. No `deepagents` middleware uses it. What uses it
in `langchain`: `ModelCallLimitMiddleware` (with
`@hook_config(can_jump_to=["end"])` so it can break the loop).

**Intervention point**: the `before_model` hook, or `@before_model`.

### 3. Prompt assembly & tool selection — inside the `model` node

`ModelRequest` is created once with a statically assembled
`system_message` (`USER` → `BASE` → `SUFFIX`) and
`tools=default_tools` (all tools: caller plus middleware). Every dynamic
adjustment happens in the `wrap_model_call` chain:

- `SkillsMiddleware`, `MemoryMiddleware`, and `FilesystemMiddleware` add
  fragments to the system message via
  `request.override(system_message=...)`.
- `FilesystemMiddleware` filters out tools the backend doesn't support
  (`execute` disappears when the backend isn't a
  `SandboxBackendProtocol`), scrubs unsupported multimodal blocks, and
  evicts an enormous `HumanMessage` to the backend.
- `SummarizationMiddleware` counts tokens and, past the threshold,
  replaces history with a summary **for this request only** —
  `state["messages"]` is not mutated (it is tracked in the private
  `_summarization_event` field).
- `_ToolExclusionMiddleware` sits last in the list = **innermost** = the
  final word on the contents of `request.tools`.

Only then does `messages = [request.system_message, *request.messages]`
happen and `model_.invoke(messages)` get called.

**Intervention point**: `wrap_model_call` / `awrap_model_call`, or
`@wrap_model_call` / `@dynamic_prompt`. The handler may be called several
times (retry), or not at all (short-circuit).
⚠️ A `Command` with `goto`/`resume`/`graph` is **not supported** in
`wrap_model_call` — `factory.py` lines 247-255 raise explicitly.

### 4. `after_model` — reverse order

A graph node. The **last** middleware in the list runs **first**.
`HumanInTheLoopMiddleware` lives here: it reads `tool_calls` on the last
`AIMessage` and calls `interrupt()` before the `tools` node gets to run.
Because `create_deep_agent` always places `HumanInTheLoopMiddleware` at
the end of the stack, it becomes the **first** `after_model` executed —
approval happens before any other `after_model` middleware sees the
model's output.

**Intervention point**: `after_model` / `@after_model`, `interrupt_on`,
`permissions(mode="interrupt")`.

### 5. Tool execution

The `tools` node. The `wrap_tool_call` chain is also an onion (first =
outermost). `FilesystemMiddleware.wrap_tool_call` calls the handler first
and then checks the result's size; a result above
`tool_token_limit_before_evict` is written to the backend and replaced by
a preview plus a file reference.
⚠️ Exceptions from a tool (including `ToolException`) are **deliberately
allowed through** by `FilesystemMiddleware` — to catch them, install
`ToolErrorMiddleware`/`ToolRetryMiddleware`.
`[code]` — `deepagents/middleware/filesystem.py` lines 3471-3520.

**Intervention point**: `wrap_tool_call` / `awrap_tool_call`, or
`@wrap_tool_call`.

### 6. Writing state

State is written through a node's return value — a `dict` update or
`Command(update=...)` — and reduced by LangGraph channels. For `messages`,
`DeepAgentState` uses
`DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)` so
checkpoints grow O(N) rather than O(N²).
Middleware that needs to write state from inside `wrap_model_call` uses
`ExtendedModelResponse(model_response=..., command=...)` — not direct
mutation.

**Intervention point**: a middleware's `state_schema` (the recommended
way), `create_deep_agent(state_schema=...)` (the global way), and
`PrivateStateAttr` for fields that must not cross to or from a subagent.

### 7. Stopping conditions

The loop stops when the last `AIMessage` has no `tool_calls`
(`_make_model_to_tools_edge` routes to `exit_node`). Besides that:

- LangGraph's `recursion_limit` — default `9_999` from
  `.with_config(...)` in `create_deep_agent`; **override through**
  `.with_config({"recursion_limit": N})` or
  `invoke(..., config={"recursion_limit": N})`.
- `ModelCallLimitMiddleware` / `ToolCallLimitMiddleware` — `jump_to end`
  or raise, depending on `exit_behavior`.
- A tool with `return_direct=True` — straight to `exit_node`.
- `interrupt()` from HITL — the run stops and awaits
  `Command(resume=...)`.

### 8. `after_agent` — reverse order, once per run

`RubricMiddleware` uses it to grade the transcript against a rubric and,
on failure, force another iteration.

## Subagents: a nested lifecycle

The `task` tool runs a **complete** subagent graph (stages 1-8 above)
inside a single tool call of the parent agent. The state sent to the
subagent is the parent's state minus `_EXCLUDED_STATE_KEYS` (`messages`,
`todos`, `structured_response`) and minus `PrivateStateAttr` fields, with
`messages` replaced by a single `HumanMessage` containing the
`description`.

What comes back: one `ToolMessage` holding the JSON-serialised
`structured_response` (when present) or the text of the last non-empty
`AIMessage`, **plus** a merge of the other non-excluded state keys into
the parent's state.
`[code]` — `deepagents/middleware/subagents.py` lines 251-268, 474-512,
529-540.

## Sources

**Versions read**: `deepagents==0.7.8`, `langchain==1.3.16`, from
`references/recipes/.venv/lib/python3.13/site-packages/`.

`[code]` files:

- `langchain/agents/factory.py` — `create_agent`, `model_node`,
  `_execute_model_sync`, `_chain_model_call_handlers`,
  `_chain_tool_call_wrappers`, `_add_middleware_edge`, START/END wiring
- `langchain/agents/middleware/types.py` — the `AgentMiddleware` contract
- `deepagents/graph.py` — stack assembly and `.with_config`
- `deepagents/middleware/patch_tool_calls.py`, `filesystem.py`,
  `summarization.py`, `subagents.py`, `skills.py`, `memory.py`,
  `rubric.py`, `_tool_exclusion.py`

Runtime verification `[code]`: the graph nodes of a minimal agent
(`create_deep_agent(model=..., tools=[])`) are
`['PatchToolCallsMiddleware.before_agent', '__end__', '__start__',
'model', 'tools']`; adding `permissions` in `interrupt` mode adds
`'HumanInTheLoopMiddleware.after_model'`. Other middleware adds no nodes
because it only uses `wrap_model_call`/`wrap_tool_call`.

The full stack (`memory=`, `skills=`, `interrupt_on=`,
`middleware=[TodoListMiddleware(), ModelCallLimitMiddleware(thread_limit=5)]`)
produces these nodes:

```
HumanInTheLoopMiddleware.after_model
MemoryMiddleware.before_agent
ModelCallLimitMiddleware.after_model
ModelCallLimitMiddleware.before_model
PatchToolCallsMiddleware.before_agent
SkillsMiddleware.before_agent
TodoListMiddleware.after_model
__end__  __start__  model  tools
```

Its `before_agent` execution order follows the stack list order:
`SkillsMiddleware` → `PatchToolCallsMiddleware` → `MemoryMiddleware`.
Its `after_model` order is reversed: `HumanInTheLoopMiddleware` →
`ModelCallLimitMiddleware` → `TodoListMiddleware`.
