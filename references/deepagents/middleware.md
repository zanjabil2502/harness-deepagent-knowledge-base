# `deepagents` - middleware

Middleware is `deepagents`' primary *extension point*. This file: what is
built in, which lifecycle stage each one hooks into, their ordering, and
the middleware interactions that turn dangerous when the order is wrong.

For the lifecycle stages themselves see [`lifecycle.md`](lifecycle.md).

## The stack order `create_deep_agent` assembles

Runtime verification (`[code]`, by intercepting the `create_agent` call at
`deepagents/graph.py` line 922):

```
minimal   : FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware,
            PatchToolCallsMiddleware, AnthropicPromptCachingMiddleware

skills+memory+interrupt_on:
            SkillsMiddleware, FilesystemMiddleware, SubAgentMiddleware,
            SummarizationMiddleware, PatchToolCallsMiddleware,
            AnthropicPromptCachingMiddleware, MemoryMiddleware,
            HumanInTheLoopMiddleware

+ middleware=[TodoListMiddleware(), ModelCallLimitMiddleware(...)]:
            FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware,
            PatchToolCallsMiddleware,
            ▲ TodoListMiddleware, ModelCallLimitMiddleware ▲   ← inserted here
            AnthropicPromptCachingMiddleware, MemoryMiddleware
```

The formal structure: **base stack** → *user middleware* → **tail stack**.
`[code]` - `deepagents/graph.py` lines 817-876 (assembly), 361-406 (the
docstring's official ordering).

| Slot | Contents | Condition |
|---|---|---|
| base | `SkillsMiddleware` | `skills=` is set |
| base | `FilesystemMiddleware` | always (required scaffolding) |
| base | `SubAgentMiddleware` | any inline subagent exists (including the default `general-purpose`) |
| base | `SummarizationMiddleware` | always |
| base | `PatchToolCallsMiddleware` | always |
| base | `AsyncSubAgentMiddleware` | any `AsyncSubAgent` exists |
| - | **user middleware** | `middleware=[...]` |
| tail | `HarnessProfile.extra_middleware` | the profile has entries |
| tail | `_ToolExclusionMiddleware` | the profile has `excluded_tools` |
| tail | `AnthropicPromptCachingMiddleware` (+Bedrock/Fireworks when installed) | always |
| tail | `MemoryMiddleware` | `memory=` is set |
| tail | `HumanInTheLoopMiddleware` | the merged `interrupt_on` is non-empty |

Note: `_ToolExclusionMiddleware` is `append`ed **after** the user
middleware merge (`graph.py` lines 892-893), so its effective position is
dead last - further back than the table above suggests. The source comment
is explicit: "so excluded tool names are stripped last and cannot be
restored by a custom `wrap_model_call`".

## Built-in middleware table

| Middleware | Hooks used | What it does | `[code]` |
|---|---|---|---|
| `SkillsMiddleware` | `before_agent`, `wrap_model_call` | Loads the skill index from the backend into state and injects it into the system prompt | `middleware/skills.py:928,1018` |
| `FilesystemMiddleware` | `wrap_model_call`, `wrap_tool_call` | Registers 8 file tools, filters out tools the backend can't support, enforces `permissions`, evicts large tool results and `HumanMessage`s to the backend, scrubs multimodal blocks | `middleware/filesystem.py:3018,3066,3471` |
| `SubAgentMiddleware` | `wrap_model_call` | Provides the `task` tool plus the subagent list in its description | `middleware/subagents.py:722` |
| `SummarizationMiddleware` (from `create_summarization_middleware`) | `wrap_model_call` | Truncates old tool args, compacts history past a threshold, offloads evicted messages to `/conversation_history/...`, falls back on `ContextOverflowError` | `middleware/summarization.py:1335,1626` |
| `PatchToolCallsMiddleware` | `before_agent` | Patches synthetic `ToolMessage`s for dangling/invalid tool calls, then rewrites all `messages` | `middleware/patch_tool_calls.py:14` |
| `AsyncSubAgentMiddleware` | `wrap_model_call` | 5 background tools: `start/check/update/cancel/list_async_task(s)` | `middleware/async_subagents.py:908` |
| `MemoryMiddleware` | `before_agent`, `wrap_model_call` | Loads `AGENTS.md` into state and injects it into the system prompt with `cache_control` on Anthropic models | `middleware/memory.py:274,380` |
| `AnthropicPromptCachingMiddleware` | (langchain-anthropic) | Installs cache breakpoints; `unsupported_model_behavior="ignore"` makes it a no-op on other providers | `middleware/_prompt_caching.py:42` |
| `_ToolExclusionMiddleware` (private) | `wrap_model_call` | Removes tool names in `HarnessProfile.excluded_tools` from `request.tools` | `middleware/_tool_exclusion.py:32` |
| `HumanInTheLoopMiddleware` (langchain) | `after_model` | `interrupt()` before the tool runs | `langchain/agents/middleware/human_in_the_loop.py:219` |
| `RubricMiddleware` | `before_agent`, `after_agent` | Grades the transcript against a rubric, forcing another iteration on failure - **not** in the default stack | `middleware/rubric.py:522,573` |
| `SummarizationToolMiddleware` | `wrap_model_call` | A `compact_conversation` tool the model calls itself - **not** in the default stack | `middleware/summarization.py:1793,2110` |
| `TodoListMiddleware` (langchain, **not** `deepagents`) | `after_model` | The `write_todos` tool plus `PlanningState.todos` state - **not** in the default stack | `langchain/agents/middleware/todo.py` |

## Dangerous interactions

Three different composition rules coexist. Conflating them is the source
of ordering bugs:

| Hook | Composition | Consequence |
|---|---|---|
| `before_agent`, `before_model` | **Sequential, in list order** | `m[0]` runs first |
| `after_model`, `after_agent` | **Sequential, REVERSED order** | `m[-1]` runs first |
| `wrap_model_call`, `wrap_tool_call` | **Onion, `m[0]` = outermost** | `m[-1]`, closest to the model/tool, gets the last word on `request` |

`[code]` - `langchain/agents/factory.py` line 1793 (`add_edge("model",
m[-1].after_model)`), line 349 (`for h in reversed(handlers[:-2])`, with
the comment "first in list becomes outermost layer"), lines 1758-1790 (the
`before_*` chain).

### 1. Tool-filtering middleware vs tool-adding middleware

The filter must be **deeper** (further back in the list) than the adder.
Otherwise the filter sees `request.tools` before the new tools arrive and
filters nothing. This is exactly why `_ToolExclusionMiddleware` is
`append`ed after every merge. If you write your own filtering middleware
and install it through `middleware=[...]`, it lands **before** the tail
stack - deep enough to filter base stack tools, but **not** the tools a
profile's `extra_middleware` adds.

### 2. `MemoryMiddleware` vs the prompt-caching middleware

The installed order is `AnthropicPromptCachingMiddleware` **then**
`MemoryMiddleware`. This is deliberate - the source comment (`graph.py`
lines 856-858): profiles and caching are placed before memory "so that
memory updates (which change the system prompt) don't invalidate the
Anthropic prompt cache prefix". Reversing the order (e.g. by installing
your own `MemoryMiddleware()` through `middleware=[...]`, which lands
**before** the tail stack) moves content that changes every session into
the cached prefix → a cache miss every time `AGENTS.md` changes. The cost
is a token bill, not a crash - so no test will ever detect it.

### 3. `SummarizationMiddleware` vs middleware that reads `state["messages"]`

The `deepagents` version **deliberately does not mutate**
`state["messages"]`; compaction applies only to `request.messages` inside
`wrap_model_call` and is tracked in the private `_summarization_event`
field. `after_model`/`after_agent` middleware reading `state["messages"]`
therefore still sees the **full** transcript, not the compacted version -
good for replay/eval, misleading if used to estimate how many tokens were
actually sent.
By contrast, plain `langchain.agents.middleware.SummarizationMiddleware`
rewrites state through `before_model` plus
`RemoveMessage(REMOVE_ALL_MESSAGES)`. Mixing the two = history rewritten
twice.
`[code]` - `middleware/summarization.py` lines 1636-1668 (the
"Non-mutating message state" docstring).

### 4. `PatchToolCallsMiddleware` vs other `before_agent` middleware

`PatchToolCallsMiddleware.before_agent` returns
`{"messages": [RemoveMessage(REMOVE_ALL_MESSAGES), *patched]}` - **all**
history is rewritten. `before_agent` middleware that ran **earlier** and
appended messages will see those messages rewritten too (they survive,
because `patched_messages` copies everything) - but middleware relying on
message object identity or IDs may be surprised. `SkillsMiddleware` runs
before `PatchToolCalls`; `MemoryMiddleware` runs after.

### 5. `HumanInTheLoopMiddleware` is always last → `after_model` first

Because `create_deep_agent` places it at the end of the tail stack, it is
the **earliest** executed `after_model`. Custom `after_model` middleware
wanting to see or edit tool calls *before* a human approves them would
have to sit **even further back** than HITL - and that is impossible
through `middleware=[...]` (which lands before the tail). What about
`HarnessProfile.extra_middleware`? Also no - that too comes before HITL.
The only official path is `interrupt_on` with `InterruptOnConfig.when` (a
per-tool-call predicate) or a callable `description`.

### 6. Duplicate names = `AssertionError`

`create_agent` refuses two middleware with the same `.name`
(`factory.py` lines 1108-1110). `_apply_custom_middleware` prevents this
by **replacing in place** any entry whose name matches. The side effect:
passing `FilesystemMiddleware(...)` through `middleware=[...]`
**replaces** the built-in one (which is what you want); passing a
**subclass** with a different class name does **not** replace it, leaving
two filesystem middlewares active. See
[`extension-points.md`](extension-points.md) anti-pattern #1.

### 7. Middleware that opens a second execution path

Third-party middleware giving the model a way to call tools **from inside
a single tool call** (e.g. `CodeInterpreterMiddleware` from
`langchain-quickjs`) violates the silent assumption behind the whole table
above: that every touch of the outside world is one tool call passing
through `ToolNode`. Two direct consequences of its position in the **user
middleware slot**:

- It is **outside** `_ToolExclusionMiddleware` (which is `append`ed last),
  so it reads `request.tools` **before** exclusion runs - a tool removed
  by `HarnessProfile.excluded_tools` can still enter its allowlist.
- It is **earlier** than `HumanInTheLoopMiddleware` in the tail, so
  `interrupt_on` still gates the code execution tool itself, but not a
  single call inside it.

The general rule: middleware that **adds a calling path**, rather than
merely adding or filtering tools, must be evaluated against the entire
tail stack - not just against its neighbours in `middleware=[...]`. The
details are in
[`../concepts/code-orchestration.md`](../concepts/code-orchestration.md)
§In deepagents.

## Exclusion: slot identity, two passes, and the verify phase

Three behaviours invisible from `create_deep_agent`'s signature that
determine whether `HarnessProfile.excluded_middleware` actually binds.

### The slot identity rule - one principle, two behaviours

`deepagents` matches middleware by **exact identity**, not inheritance.
Class entries match on exact type, string entries on
`AgentMiddleware.name`.

`[code]` - `_excluded_middleware.py:90` (`_apply_excluded_middleware`),
whose docstring states: *"Class entries match on exact type (not
`isinstance`), mirroring the slot-identity semantics of `_merge_middleware`
so a subclass introduced by the caller is preserved when the profile
excludes the base class."*

This is the **same** rule that governs replacing built-in middleware
through the `middleware=` parameter (`graph.py:201`,
`_apply_custom_middleware`) - and that is why anti-pattern #1 in
[`extension-points.md`](extension-points.md) happens: a renamed subclass
silently **fails** to replace the built-in middleware, because its name
differs.

Two seemingly unrelated behaviours - exclusion skipping subclasses, custom
middleware failing to replace - are consequences of one rule. If you rely
on inheritance for either, you are wrong about both.

### The filter runs twice per stack

Exclusion cannot be bypassed by inserting middleware through the
`middleware=` parameter. The filter runs **both before and after** custom
middleware is inserted:

```
_apply_excluded_middleware(...)    # graph.py:877
_apply_custom_middleware(...)      # graph.py:883 - the user inserts here
_apply_excluded_middleware(...)    # graph.py:884 - filtered again
```

`[code]` - `graph.py:877-889`. The same pattern applies to tools:
`_ToolExclusionMiddleware` is deliberately appended **dead last**, with
the reason written in source (`graph.py:890-893`): *"Tool exclusion runs
after custom middleware so excluded tool names are stripped last and
cannot be restored by a custom `wrap_model_call`."*

### The verify phase: a typo fails loudly, not silently

Exclusion is not one function but a **three-phase protocol**, run
repeatedly across four scopes (main, declarative subagents, GP subagent):

| Phase | Function | Its role |
|---|---|---|
| 1 | `_validate_excluded_middleware_config` (`_excluded_middleware.py:23`) | Reject entries targeting required scaffolding (`_REQUIRED_MIDDLEWARE`, `graph.py:238-265`) → `ValueError` |
| 2 | `_apply_excluded_middleware` (`:90`) | Filter one stack, **recording what it matched** into a shared accumulator set |
| 3 | `_verify_excluded_middleware_coverage` (`:168`) | After every stack is filtered, ensure each entry matched **somewhere** |

`[code]` - 15 call sites in `graph.py` (`:607` validate main;
`:688,693,704,710` subagents; `:769,779` GP subagent; `:877,884,903`
main).

Phase 3 exists because the `matched_classes`/`matched_names` sets are
**shared across all `_apply` calls** rather than checked per stack. Its
docstring gives both sides of the reason: *"An entry that matched nothing
is almost always a typo or stale profile"*, and *"Per-stack checking would
be too strict - a profile legitimately targets middleware only one stack
carries."*

The practical consequence:
`excluded_middleware=["FilesytemMiddleware"]` (a typo) raises `ValueError`
at construction. Without that third phase it would be a silent no-op
discovered only in production.

## `artifacts_root`: where middleware writes, and who decides

Two built-in middlewares write to the backend unbidden - and to **three**
prefixes, not one. None of this is visible from any `create_deep_agent`
signature.

```python
artifacts_root = backend.artifacts_root if isinstance(backend, CompositeBackend) else "/"
_root = artifacts_root.rstrip("/")
self._history_path_prefix       = f"{_root}/conversation_history"
self._large_tool_results_prefix = f"{_root}/large_tool_results"
self._media_prefix              = f"{self._history_path_prefix}/media"
```

`[code]` - `middleware/summarization.py:598-603`.

| Prefix | Contents | Written by |
|---|---|---|
| `<root>/conversation_history/` | Conversation summaries, one `.md` file per session | `_DeepAgentsSummarizationMiddleware` (`summarization.py:1179` `_offload_to_backend`) |
| `<root>/conversation_history/media/` | Inline images offloaded from messages | `summarization.py:1044` (`_offload_inline_media`) |
| `<root>/large_tool_results/` | Tool output too large for context | `summarization.py:601` |

`FilesystemMiddleware` writes to the **same** directories through its
message eviction path - `[code]` `middleware/filesystem.py:1705` (the
prefix), `:3324,3350` (the writes). So two different middlewares share one
artifact namespace.

### The rule that determines isolation

`artifacts_root` **behaves differently depending on backend type**, and
this determines whether the artifacts above are scoped per user:

| Backend | `artifacts_root` | Consequence |
|---|---|---|
| A plain backend (`StoreBackend`, `FilesystemBackend`, …) | `"/"` - the `else` branch at `:598` | Artifacts land at that backend's root. For `StoreBackend(namespace=...)` that means **inside the user's namespace** → automatically scoped |
| `CompositeBackend` | `self.artifacts_root`, default `"/"` (`backends/composite.py:212,235`) | Artifacts follow the `routes` rules. If `/conversation_history/` and `/large_tool_results/` are **not** routed explicitly, both fall to `default` |

The easily missed consequence: composing
`CompositeBackend(default=StateBackend(), routes={"/memories/": StoreBackend(namespace=...)})`
makes `/memories/` durable and scoped, but **conversation summaries still
fall to `StateBackend`** - ephemeral, lost every turn. A namespaced
backend does not mean every artifact is namespaced; what decides is
whether `routes` covers the prefixes above.

See [`conformance.md`](conformance.md) §D-08 for the multi-user isolation
implications.

## Writing your own middleware

The contract: subclass `langchain.agents.middleware.AgentMiddleware` and
override only the hooks you need. The relevant class attributes:
`state_schema`, `tools`, `name` (a property, defaulting to
`__class__.__name__`), `trace_policy`.

A minimal example that genuinely runs - limiting how many times one tool
name may be called consecutively with identical arguments (the "agent
spinning in place" case `ToolCallLimitMiddleware` doesn't catch, because
that one counts total calls rather than repetitions):

```python
import json

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage


class RepeatedToolCallGuard(AgentMiddleware):
    """Refuse a tool call identical to the previous N consecutive ones."""

    def __init__(self, *, max_repeats: int = 3) -> None:
        super().__init__()
        self._max_repeats = max_repeats
        self._last: tuple[str, str] | None = None
        self._streak = 0

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        call = request.tool_call
        key = (call["name"], json.dumps(call.get("args") or {}, sort_keys=True))
        self._streak = self._streak + 1 if key == self._last else 1
        self._last = key
        if self._streak > self._max_repeats:
            return ToolMessage(
                content=(
                    f"Tool `{call['name']}` has been called {self._streak} times "
                    "in a row with the same arguments. Change approach or report "
                    "the impasse to the user."
                ),
                tool_call_id=call["id"],
                status="error",
            )
        return handler(request)


agent = create_deep_agent(
    model=model,
    tools=[...],
    middleware=[RepeatedToolCallGuard(max_repeats=3)],
)
```

What makes this example idiomatic:

- It uses `wrap_tool_call` rather than wrapping tool functions one by one.
- It returns a `ToolMessage` with status `error` rather than raising - the
  model gets feedback and can change course, matching the
  `ShellAllowListMiddleware` pattern in
  `libs/code/deepagents_code/agent.py` (the maintainers' repo), which does
  exactly this for shell commands.
- It sets no custom `name`, so it cannot accidentally collide with or
  replace built-in middleware.
- Per-instance state lives in instance attributes because it needn't
  survive checkpoints; if it must survive, declare a `state_schema` with
  a `PrivateStateAttr`-marked field and return updates through a
  `Command`.

⚠️ Middleware with instance state like the above is **not** safe when one
agent object is shared across threads concurrently. For that, keep the
count in `state_schema` rather than on `self`.

For simple cases there are also decorators: `@before_agent`,
`@before_model`, `@after_model`, `@after_agent`, `@wrap_model_call`,
`@wrap_tool_call`, `@dynamic_prompt` - all from
`langchain.agents.middleware`. `[code]` -
`langchain/agents/middleware/types.py` lines 934-2175.

## Sources

**Versions read**: `deepagents==0.7.8`, `langchain==1.3.16`.

`[code]` from `references/recipes/.venv/lib/python3.13/site-packages/`:
`deepagents/graph.py`, `deepagents/middleware/*.py` (all),
`langchain/agents/factory.py`,
`langchain/agents/middleware/types.py`,
`langchain/agents/middleware/__init__.py` (the `__all__` list),
`langchain/agents/middleware/human_in_the_loop.py`,
`langchain/agents/middleware/todo.py`.

`[code]` from `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21): `libs/code/deepagents_code/agent.py` lines 774-845
(`ShellAllowListMiddleware`) as an example of custom middleware written by
the maintainers themselves.

Runtime verification `[code]`: the stack orders above were printed by
intercepting `deepagents.graph.create_agent` and reading
`[m.name for m in kw["middleware"]]`.
