# `deepagents` — extension points

## The hard rule

> **Don't write custom code at a layer that already has an extension
> point.**

Custom code at the wrong layer usually **still runs**. That is the
problem: it passes tests, passes review, and only looks wrong once
built-in behaviour is silently bypassed — a tool you thought was
restricted is still installed, a permission you thought was enforced is
never consulted, a prompt cache you thought was active misses every
session. All of them fail with no error.

Before writing a new class or function, match the need against the table
below. If there is a row for it, use that.

## Inventory of official extension points

| # | Extension point | Shape | For | `[code]` |
|---|---|---|---|---|
| 1 | **Middleware** | subclass `AgentMiddleware` or the `@before_model`/`@wrap_tool_call`/etc. decorators, installed via `middleware=[...]` | changing the prompt, tools, request, tool results, state, or stopping the loop | `langchain/agents/middleware/types.py:385` |
| 2 | **Backend** | an implementation of `BackendProtocol` (or `SandboxBackendProtocol` for `execute`), installed via `backend=` | where files are read/written and where the shell runs | `deepagents/backends/protocol.py:378,840` |
| 3 | **Composite backend** | `CompositeBackend(default=..., routes={prefix: backend})` | some paths ephemeral, others durable/scoped | `deepagents/backends/composite.py:180` |
| 4 | **Subagent** | `SubAgent` / `CompiledSubAgent` / `AsyncSubAgent` via `subagents=` | per-subtask context isolation, a different tool surface, a different model | `deepagents/middleware/subagents.py:36,166` |
| 5 | **Tool** | a function or `BaseTool` via `tools=` | a new capability the model can call | `deepagents/graph.py:270` |
| 6 | **State schema** | a middleware's `state_schema` (recommended) or `create_deep_agent(state_schema=)` (global) | extra state fields across turns; `PrivateStateAttr` for fields that must not cross into a subagent | `deepagents/middleware/_state.py:14`, `graph.py:281` |
| 7 | **Handler / hook** | `interrupt_on`, `permissions`, `InterruptOnConfig.when` | human approval pauses and filesystem permission rules | `deepagents/middleware/_fs_interrupt.py`, `graph.py:277,279` |
| 8 | **Harness profile** | `register_harness_profile(key, HarnessProfile(...))` | drop built-in tools, override tool descriptions, add middleware to **every** stack (main + GP subagent + declarative subagents), set base/suffix prompts per model | `deepagents/profiles/harness/harness_profiles.py:483,977` |
| 9 | **Provider profile** | `register_provider_profile(key, ProviderProfile(...))` | changing how the model is constructed per provider | `deepagents/profiles/provider/provider_profiles.py:38` |
| 10 | **Graph config** | `.with_config({...})` / `invoke(config=...)` | `recursion_limit`, `thread_id`, metadata, callbacks | `deepagents/graph.py:935-944` |
| 11 | **Skill** | a `SKILL.md` directory via `skills=` | layered instructions (progressive disclosure) without bloating the system prompt | `deepagents/middleware/skills.py:764` |
| 12 | **Memory** | an `AGENTS.md` file via `memory=` | persistent context that always enters the system prompt | `deepagents/middleware/memory.py:178` |

What is **not** an extension point (and therefore may and must be written
yourself at the application layer): triggers (when the agent is called),
queues, a fleet kill switch, authentication/user identity resolution, and
the checkpointer/store storage itself. `deepagents` deliberately touches
none of those four.

## Anti-patterns

### 1. Subclassing built-in middleware to narrow its tools

**What people usually write**

```python
class RestrictedFilesystem(FilesystemMiddleware):
    def __init__(self):
        super().__init__(tools=["read_file", "ls"])

agent = create_deep_agent(model=m, middleware=[RestrictedFilesystem()])
```

**Why it's wrong**: `_apply_custom_middleware` replaces stack entries
**by `.name`**, and the default `.name` is the class name. The class
`RestrictedFilesystem` has a different name from `FilesystemMiddleware`,
so it is **added**, not substituted. The built-in `FilesystemMiddleware`
stays installed with all 8 of its tools.

Runtime verification `[code]`:

```
default                                    → delete, edit_file, execute, glob,
                                             grep, ls, read_file, task, write_file
middleware=[FilesystemMiddleware(          → ls, read_file, task
    tools=["read_file","ls"])]
middleware=[MyFS(tools=["read_file"])]     → delete, edit_file, execute, glob,
  (subclass, different class name)           grep, ls, read_file, task, write_file
```

The restriction on the third line **vanishes without a trace** — no
warning, no error.

**The official way**: pass an **instance of the original class** with
different configuration.

```python
agent = create_deep_agent(
    model=m,
    backend=backend,                      # the same backend, mandatory
    middleware=[FilesystemMiddleware(backend=backend, tools=["read_file", "ls"])],
)
```

For per-subagent, put the same instance in `spec["middleware"]` — the
`SubAgent` docstring says so explicitly: *"To restrict filesystem tools,
include a `FilesystemMiddleware(tools=...)` instance here."*
To hide a tool from **every** stack at once, use
`HarnessProfile(excluded_tools=frozenset({"execute", "delete"}))`.

`[code]` — `deepagents/graph.py` lines 201-235
(`_apply_custom_middleware`); `deepagents/middleware/subagents.py` lines
62-66; `deepagents/middleware/filesystem.py` lines 1714-1744.

### 2. Wrapping tool functions one by one for audit/guard/retry

**What people usually write**

```python
def audited(fn):
    def wrapper(*a, **kw):
        log.info("tool call: %s", fn.__name__)
        try:
            return fn(*a, **kw)
        except Exception as e:
            return f"error: {e}"
    return wrapper

tools = [audited(search), audited(fetch), audited(publish)]
```

**Why it's wrong**: three problems at once. (a) Middleware's built-in
tools (`read_file`, `write_file`, `execute`, `task`) never pass through
this wrapper — precisely the riskiest tools are missed. (b) The wrapper
loses `tool_call_id`, so it cannot return a correct `ToolMessage`. (c)
Every new tool must be remembered and wrapped; the ones forgotten fail
silently.

**The official way**: `wrap_tool_call` sees **every** tool call, including
middleware-injected ones, and receives a complete `ToolCallRequest`.

```python
class AuditMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        log.info("tool call: %s %s", request.tool_call["name"], request.tool_call["args"])
        return handler(request)
```

For errors and retries, don't write anything yourself —
`ToolErrorMiddleware(on_error=...)` and
`ToolRetryMiddleware(max_retries=..., backoff_factor=...)` already exist.
The maintainers themselves use the `wrap_tool_call` path for this
(`ShellAllowListMiddleware`, `libs/code/deepagents_code/agent.py:774`).

`[code]` — `deepagents/middleware/filesystem.py` line 3471;
`langchain/agents/middleware/tool_error.py:75`, `tool_retry.py:133`.

### 3. Writing your own `while` loop to bound step count

**What people usually write**

```python
for i in range(20):
    result = agent.invoke(state)
    if not result["messages"][-1].tool_calls:
        break
    state = result
```

**Why it's wrong**: `agent.invoke` **already** runs the loop to
completion; wrapping it again means running the agent 20 times from the
start, each with a growing history. The default `recursion_limit` of
`9_999` still applies inside each call, so the outer bound of 20
constrains nothing. It also breaks `run_limit` accounting in the limit
middleware, because each `invoke` is a new run.

**The official way**: one `invoke`, with the bound in config or
middleware.

```python
agent = create_deep_agent(model=m, tools=tools).with_config(
    {"recursion_limit": 60}
)
# or, with a message the model can read:
agent = create_deep_agent(
    model=m,
    tools=tools,
    middleware=[ModelCallLimitMiddleware(thread_limit=25, exit_behavior="end")],
)
```

Both are maintainer patterns, in two equivalent variants.
`libs/code/deepagents_code/agent.py:3110` uses
`.with_config({**config, "recursion_limit": effective_recursion_limit})`
on a freshly built agent;
`examples/better-harness/better_harness/agent.py:225` uses the per-call
variant
`agent.invoke(..., config={"recursion_limit": experiment.better_agent_max_turns})`.
Use `.with_config` when the bound belongs to the agent, `config=` when it
differs per invocation.

The exception that **is** a legitimate outer loop: the Ralph pattern
(`examples/ralph_mode/`) — each iteration deliberately starts from a
**fresh thread with empty context**, with the filesystem as memory between
iterations. That isn't a step bound, it's a context strategy. An outer
loop whose only purpose is "bound the step count" has no such reason.

`[code]` — `deepagents/graph.py` lines 935-944;
`langchain/agents/middleware/model_call_limit.py:126`; repo
`langchain-ai/deepagents` commit `23b83ad`.

### 4. Filtering paths/permissions inside a tool function

**What people usually write**

```python
@tool
def safe_write(path: str, content: str) -> str:
    if path.startswith("/secrets"):
        return "denied"
    return backend.write(path, content)
```

**Why it's wrong**: it only applies to tools you wrote. The built-in
`write_file`, `edit_file`, `delete`, `execute`, `glob`, and `grep` never
pass through here. And `grep(path=None)` can return the contents of the
very file being "protected".

**The official way**: `permissions=[FilesystemPermission(...)]`. Rules are
evaluated in order (first match wins), apply to every built-in filesystem
tool, and `mode="interrupt"` automatically wires into HITL — including for
bulk tools (`ls`/`glob`/`grep`) whose search subtree intersects the rule's
pattern.

```python
permissions = [
    FilesystemPermission(operations=["read", "write"], paths=["/secrets/**"], mode="deny"),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="interrupt"),
]
```

⚠️ Its limit is real and must be known: `permissions` does **not** apply
to the `execute` tool — `FilesystemMiddleware.__init__` in fact **raises
`NotImplementedError`** if `permissions` is combined with a
`SandboxBackendProtocol` backend whose paths aren't scoped to a route. For
shell-capable backends, permission enforcement must live at another layer
(a command allow-list through `wrap_tool_call`, or the sandbox itself).

`[code]` — `deepagents/middleware/filesystem.py` lines 384-417, 1691-1700;
`deepagents/middleware/_fs_interrupt.py` lines 20-46.

### 5. Copy-pasting `create_deep_agent` to change the stack

**What people usually write**: copying the contents of `graph.py` into
`my_agent.py`, then deleting or swapping a few middleware lines, because
"there's no parameter for removing X".

**Why it's wrong**: once copied, the agent stops following the library —
bug fixes, new middleware, and tail-stack ordering changes no longer
arrive. And `_REQUIRED_MIDDLEWARE` exists precisely to prevent agents that
"silently degrade"; a manual copy loses that protection.

**The official way**: `HarnessProfile`.

```python
register_harness_profile(
    "anthropic:claude-sonnet-4-6",
    HarnessProfile(
        system_prompt_suffix="Answer in Indonesian.",
        excluded_tools=frozenset({"execute"}),
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        extra_middleware=[AuditMiddleware()],
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)
```

A profile applies to the main agent **and** declarative subagents **and**
the GP subagent all at once — a reach `middleware=[...]` cannot achieve.
Registration merges, so several modules may layer onto it.

⚠️ `excluded_middleware` refuses `FilesystemMiddleware` and
`SubAgentMiddleware` with a `ValueError` (required scaffolding), and
refuses entries matching nothing in the stack (a sign of a typo or a stale
profile). To remove the `task` tool, use
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`
plus passing no synchronous subagents.

`[code]` — `deepagents/graph.py` lines 238-265;
`deepagents/profiles/harness/harness_profiles.py` lines 483-700 (the
`HarnessProfile` fields), 977-1026 (`register_harness_profile`).

### 6. Storing agent files through your own storage module

**What people usually write**: a `save_artifact(user_id, path, content)`
function writing to S3/Postgres, called from inside a custom tool, while
the agent still uses the default `StateBackend`.

**Why it's wrong**: the agent ends up with two filesystems unaware of each
other. `read_file`/`glob`/`grep` cannot see artifacts saved through the
second path; large tool result eviction writes to the first backend; and
skills and memory load from the first backend. The model will write a file
and then fail to find it.

**The official way**: one backend, routed.

```python
backend = CompositeBackend(
    default=StateBackend(),
    routes={"/memories/": StoreBackend(namespace=lambda rt: (user_id, "memories"))},
)
```

Genuinely new storage = a new `BackendProtocol` implementation, not a
module beside it. `StoreBackend`'s `namespace` is the only official
per-user scoping *hook*.

`[code]` — `deepagents/backends/composite.py` lines 180-240;
`deepagents/backends/store.py` lines 89-120;
`deepagents/middleware/filesystem.py` lines 1602-1614 (the docstring
example).

## A note: two meanings of the word "middleware"

The scaffold [`../scaffolds/_base.md`](../scaffolds/_base.md) has a
`ScopeMiddleware`, and that is **not** an `AgentMiddleware` — it is a
`starlette.middleware.base.BaseHTTPMiddleware`, an HTTP layer resolving
identity from the request before the agent is called at all. Two different
things with the same name. The hard rule above applies only to
`AgentMiddleware`.

## Sources

**Versions read**: `deepagents==0.7.8`, `langchain==1.3.16`, from
`references/recipes/.venv/lib/python3.13/site-packages/`.

`[code]`: `deepagents/graph.py`,
`deepagents/backends/{protocol,composite,store,state,filesystem,local_shell}.py`,
`deepagents/middleware/{filesystem,subagents,_state,_fs_interrupt,_tool_exclusion,skills,memory}.py`,
`deepagents/profiles/harness/harness_profiles.py`,
`langchain/agents/middleware/{types,tool_error,tool_retry,model_call_limit}.py`.

`[code]` from `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21): `libs/code/deepagents_code/agent.py`,
`examples/better-harness/better_harness/agent.py`,
`examples/ralph_mode/ralph_mode.py`.

Runtime verification `[code]` for anti-pattern #1: three agents were built
(`default`, `FilesystemMiddleware(tools=[...])`, and a subclass with a
different class name), then
`sorted(agent.nodes["tools"].bound.tools_by_name)` was compared — the
result is exactly the table in anti-pattern #1.
