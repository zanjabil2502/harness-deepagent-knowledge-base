# `deepagents`

> Label every claim: [code] / [docs] / [inferred]

Tier **T1** - a deep dissection. Every `[code]` claim is read directly from the
installed `deepagents==0.7.8` package (`uv sync` from
`references/recipes/pyproject.toml`, verified through `deepagents.__version__`
and the `deepagents-0.7.8.dist-info` directory), plus the `langchain==1.3.16`
and `langgraph==1.2.11` it is built on. The full source details are in
`## Sources`.

## Archetype

`deepagents` is **not** one archetype - it is a harness SDK used to build any
archetype in this grid; its instantiation (the backend + middleware +
`interrupt_on`/`permissions` installed) determines the final archetype. The
official documentation describes it as the middle of three layers: `[docs]`

```
Deep Agents  -> an opinionated harness: middleware, backends, profiles, subagents
LangChain    -> the agent abstraction: model + tools + middleware
LangGraph    -> the execution runtime: state, checkpoints, streaming, interrupts
```

(`openwiki/architecture/overview.md`, langchain-ai/deepagents, cited through
Context7 `/langchain-ai/deepagents`). Its default stack (the filesystem as
memory, a `task` tool + an automatic general-purpose subagent, no explicit
todos) is closest to a **General Task Agent (03)**, but every axis below can be
shifted through `create_deep_agent(...)` parameters to form another archetype
(e.g. a `Workspace Agent` through `LocalShellBackend`, a `Generative Builder`
through a sandbox backend). `[code]` - `deepagents/graph.py`.

## 1. Loop shape

`create_deep_agent(...)` is a thin graph builder on top of
`langchain.agents.create_agent(...)`: all middleware is assembled into one
`list[AgentMiddleware]`, then passed to `create_agent()`, which returns a
LangGraph `CompiledStateGraph`. `[code]` - `deepagents/graph.py` lines 922-934.

`create_agent()` itself is documented as creating "an agent graph that calls
tools in a loop until a stopping condition is met" - a standard ReAct loop
(model node ⇄ tool node) that stops when the last `AIMessage` contains no
`tool_calls`, not something `deepagents` decides. `[code]` -
`langchain/agents/factory.py` lines 859-860 (the `create_agent` docstring).

`deepagents` raises LangGraph's `recursion_limit` from a default of 25 to
**9999** through the `.with_config({"recursion_limit": 9_999, ...})` installed
on every agent `create_deep_agent` builds - not a "when to stop" mechanism but
a safety net so a long deep-agent task isn't cut off by a
`GraphRecursionError` at LangGraph's much smaller default. `[code]` -
`deepagents/graph.py` lines 935-944.

## 2. Context

Three mechanisms run **by default**, with no explicit configuration:

- **`SummarizationMiddleware`** (through `create_summarization_middleware(model,
  backend)`) is always present in the main stack and in every subagent. Its
  trigger/keep/`truncate_args_settings` thresholds are computed automatically
  from the model profile (`compute_summarization_defaults`, based on
  `max_input_tokens`). When tokens are exceeded, old messages are compacted
  into a summary; this is *deepagents' own middleware* wrapping
  `langchain.agents.middleware.SummarizationMiddleware` to add backend/file
  awareness. `[code]` - `deepagents/middleware/summarization.py`.
- **`FilesystemMiddleware`** *evicts* large tool results to the filesystem
  backend once they exceed `tool_token_limit_before_evict` (20000 tokens by
  default) or `human_message_token_limit_before_evict` (50000) - the original
  result is written to a path, then the message is replaced by a head/tail
  preview + a path reference (`TOO_LARGE_TOOL_MSG`). This is the
  *filesystem-as-memory* pattern: not discarded but moved into storage
  re-readable through `read_file`. `[code]` -
  `deepagents/middleware/filesystem.py` lines 1556-1630,
  `deepagents/middleware/_message_eviction.py`.
- **`DeepAgentState.messages`** uses the LangGraph reducer
  `DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)`, reducing
  checkpoint size growth from O(N²) to O(N) - significant for long sessions
  with piles of messages. `[code]` - `deepagents/graph.py` lines 70-73.

The optional mechanisms:

- **`SummarizationToolMiddleware`** (through
  `create_summarization_tool_middleware`) adds a `compact_conversation` tool
  for manual compaction triggered by the model/user, using the same
  summarisation engine as `SummarizationMiddleware` but never compacting
  automatically on its own. `[code]` -
  `deepagents/middleware/summarization.py`.
- **`memory=["./AGENTS.md", ...]`** on `create_deep_agent` triggers
  `MemoryMiddleware`, which loads the `AGENTS.md` file's contents into the
  system prompt at startup (not dynamic filesystem-as-memory, but static
  context injected once at session start). `[code]` -
  `deepagents/middleware/memory.py`.
- **`AnthropicPromptCachingMiddleware`** is always added unconditionally (a
  no-op for non-Anthropic models) through `append_prompt_caching_middleware`;
  `BedrockPromptCachingMiddleware`/`FireworksPromptCachingMiddleware` are added
  automatically too when `langchain-aws`/`langchain-fireworks` are installed.
  This is an explicit compaction vs prompt-cache trade-off:
  `AnthropicPromptCachingMiddleware` is added to the stack **before**
  `MemoryMiddleware` (`deepagents/graph.py` line 860 vs lines 861-870, not the
  reverse order) - memory updates don't break the prefix cache not because of
  that middleware ordering but because `MemoryMiddleware` itself marks the
  system message's last block with `cache_control` through its
  `add_cache_control=True` parameter (set `True` for the main stack's
  instance), applied only when the target model is a `ChatAnthropic`. `[code]`
  - `deepagents/middleware/_prompt_caching.py`,
  `deepagents/middleware/memory.py` lines 193, 342-374, `deepagents/graph.py`
  lines 856-870.
- **`PatchToolCallsMiddleware`** is always present in the main stack and in
  subagents - patching in a synthetic `ToolMessage` for tool calls left
  dangling/cancelled in message history (e.g. by an interrupt or a summary),
  keeping the message history valid for the next model call. `[code]` -
  `deepagents/middleware/patch_tool_calls.py`.

## 3. Tool surface

Few broad tools rather than many narrow ones - by design. The built-in
`execute` tool keeps one name even though its implementation changes entirely
depending on the backend, `[code]` per the `create_deep_agent` docstring:

- `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep` -
  from `FilesystemMiddleware`, always present. `delete` is in `_FS_TOOL_ORDER`
  (`deepagents/middleware/filesystem.py` line 1348) and gated by
  `_supports_delete` (`deepagents/backends/protocol.py` lines 939-954,
  `type(backend).delete is not BackendProtocol.delete`) - but all three
  built-in backends (`FilesystemBackend`, `StateBackend`, `StoreBackend`)
  override `delete`, so in practice this tool is always present.
- `execute` - appears only if the installed `backend` implements
  `SandboxBackendProtocol`; for a non-sandbox backend, `FilesystemMiddleware`
  filters it out entirely (not a tool returning an error - the tool isn't
  exposed to the model at all). `[code]` -
  `deepagents/backends/protocol.py` lines 840-939, confirmed by
  `THREAT_MODEL.md` (langchain-ai/deepagents): *"the execute tool is filtered
  out by FilesystemMiddleware when the backend does not implement
  SandboxBackendProtocol"*.
- `task` - from `SubAgentMiddleware`, appearing only when inline subagents
  exist (by default: the `general-purpose` subagent is always added unless
  disabled through a profile).
- `tools=[...]` on `create_deep_agent` is **additive** - always merged with the
  built-in tools above, never replacing them. To remove a built-in tool, the
  only official route is `HarnessProfile.excluded_tools` (through
  `_ToolExclusionMiddleware`, run last in the stack so that tools injected by
  other middleware are filtered too). `[code]` - `deepagents/graph.py` lines
  331-339, 787-788, `deepagents/middleware/_tool_exclusion.py`.
- `FsToolName = Literal["ls", "read_file", "write_file", "edit_file",
  "delete", "glob", "grep", "execute"]` - the official enumeration of
  filesystem/execution tool names (`delete` is in the literal but installed
  only when the backend supports it). `[code]` -
  `deepagents/middleware/filesystem.py` line 1345.

## 4. Delegation

Three delegation routes; it isn't flat:

- **`SubAgent`** (a declarative dict: `name`, `description`, `system_prompt`,
  optionally `tools`/`model`/`middleware`/`interrupt_on`/`skills`/
  `permissions`/`response_format`) - invoked through the `task` tool built by
  `SubAgentMiddleware`. A subagent automatically gets its own base middleware
  stack (`FilesystemMiddleware` + `SummarizationMiddleware` +
  `PatchToolCallsMiddleware`, then its spec's `custom middleware`) before its
  spec's custom `middleware` runs. `[code]` - `deepagents/graph.py` lines
  645-743, `deepagents/middleware/subagents.py`.
- **`CompiledSubAgent`** - a runnable the caller compiled themselves, used
  as-is; it doesn't inherit `state_schema` from `create_deep_agent`. `[code]`
  - `deepagents/middleware/subagents.py`.
- **`AsyncSubAgent`** - a remote/background subagent through the LangGraph SDK
  to an Agent Protocol server (a managed LangGraph Platform/LangSmith
  Deployment, or self-hosted). Routed to `AsyncSubAgentMiddleware` rather than
  `SubAgentMiddleware`, and exposing five different tools:
  `start_async_task`, `check_async_task`, `update_async_task`,
  `cancel_async_task`, `list_async_tasks` - running non-blocking, so the main
  agent can keep working while the async subagent runs. `[code]` -
  `deepagents/middleware/async_subagents.py`.

The `general-purpose` subagent is added automatically unless the caller already
supplied a subagent of the same name, or the harness profile sets
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`.
`[code]` - `deepagents/graph.py` lines 745-814.

**The result returning to the caller**: the `ToolMessage` content from the
`task` tool is **not** the subagent's entire final `messages` state.
`_return_command_with_state_update` picks one of two: if the subagent's
`structured_response` isn't `None`, its value is serialised to JSON
(`model_dump_json()` for Pydantic, `json.dumps(dataclasses.asdict(...))` for a
dataclass, `json.dumps(...)` otherwise) and that is the `ToolMessage`'s
content; if `None`, the code walks backwards from the last message and uses
the first **non-empty** `AIMessage` text it finds (that walk-back exists
because Anthropic sometimes closes with an empty `end_turn` `AIMessage`). The
result is still what one would expect - a clean summary rather than the
subagent's working transcript - but the mechanism is selecting one message,
not copying message state.

Beyond `messages`, other state keys a subagent returns **are** merged into the
main agent's state, except `_EXCLUDED_STATE_KEYS` (`messages`, `todos`,
`structured_response`) and private fields. A subagent's private state (fields
marked `PrivateStateAttr` in any middleware, collected through
`private_state_field_names`) doesn't leak back into the main agent's state -
the same filter is also used when sending parent state **into** a subagent.
`[code]` - `deepagents/middleware/subagents.py` lines 251-268
(`_EXCLUDED_STATE_KEYS`), 474-512 (`_return_command_with_state_update`),
529-540 (`_validate_and_prepare_state`); `deepagents/graph.py` lines 894-898.

## 5. State & resume

The `checkpointer` and `store` in `create_deep_agent` are passed **unchanged**
to `langchain.agents.create_agent(...)` - `deepagents` never builds a
checkpointer/store of its own; the calling application injects them. `[code]`
- `deepagents/graph.py` lines 546-553, 922-931 (the `checkpointer` and `store`
parameters passed straight through).

The concrete state layer map:

| Layer | The deepagents mechanism |
|---|---|
| Per-thread transcript | `DeepAgentState.messages` (a `DeltaChannel`, resumable through the application-injected `checkpointer`) |
| Ephemeral files | `StateBackend` (the default) - living in LangGraph state, checkpointed automatically per step, not crossing threads |
| Durable cross-thread files | `StoreBackend(namespace=...)` on top of the application-injected `store` |
| Async subagent tasks | `AsyncSubAgentState.tasks` (a `task_id -> AsyncTask` dict, its status cached then re-checked against the server) |
| Self-eval iteration | `RubricState` (private: status, iteration count, evaluation history) - active only when the caller sends a `rubric` in the invoke state |

There is no built-in todo/scratchpad mechanism in the default stack -
`DeepAgentState` only adds a message reducer, with no `todos` field.
`TodoListMiddleware` (which comes from `langchain.agents.middleware`, not
`deepagents`) has to be added explicitly through
`middleware=[TodoListMiddleware()]`; it appears in no base stack list in
`create_deep_agent`. `[code]` - `deepagents/graph.py` lines 361-402 (the
complete base stack list never mentions `TodoListMiddleware`),
`langchain/agents/middleware/todo.py`.

## 6. Safety gate

Two independent gate routes, usable together:

1. **`interrupt_on={"tool_name": True | InterruptOnConfig}`** - installs
   `HumanInTheLoopMiddleware` (from `langchain.agents.middleware`) only if the
   merge result (`_merge_fs_interrupt_on`) is non-empty; if empty, that
   middleware isn't installed at all (no overhead). `[code]` -
   `deepagents/graph.py` lines 871-876. `InterruptOnConfig` supports
   `allowed_decisions` (a subset of `"approve"/"edit"/"reject"/"respond"`) per
   tool. `[code]` - `langchain/agents/middleware/human_in_the_loop.py`.
2. **`permissions=[FilesystemPermission(operations=[...], paths=[...],
   mode="allow"|"deny"|"interrupt")]`** - rules evaluated in order, first
   match winning, defaulting to `allow` when nothing matches. `mode="deny"`
   makes the tool return a permission-denied message (with no pause);
   `mode="interrupt"` **automatically** generates `interrupt_on` entries
   through `_build_interrupt_on_from_permissions`, then merges them with the
   explicit `interrupt_on` (the user's entry winning per tool name on a
   conflict). An `"interrupt"` rule requires a `langchain` version supporting
   the `when` predicate on `InterruptOnConfig`. `[code]` -
   `deepagents/middleware/filesystem.py` lines 384-419,
   `deepagents/middleware/_fs_interrupt.py`.

A subagent (`SubAgent`) inherits the main agent's `interrupt_on`/`permissions`
by default; declaring those fields in its own spec **replaces** them entirely
rather than merging. `CompiledSubAgent`/`AsyncSubAgent` inherit nothing - HITL
for both must be configured inside their own runnable/server. `[code]` - the
`interrupt_on` and `permissions` parameter docstrings in
`deepagents/graph.py`.

**Sandboxing**: `execute` runs only through a backend implementing
`SandboxBackendProtocol`. Per `THREAT_MODEL.md` (langchain-ai/deepagents,
cited via WebFetch): `LocalShellBackend` *"is not the default; it must be
explicitly provided by the user"*, and it runs commands through
`subprocess.run(shell=True)` with no validation of command content beyond a
non-empty check - *"passes the LLM-generated command string directly to
subprocess.run (shell=True)...Zero validation on command content"*.
Importantly: `virtual_mode` on `FilesystemBackend`/`LocalShellBackend`
**only** restricts file operations (`read_file`/`write_file`/etc.) to
`root_dir`; `execute()` is **not** restricted - *"Even when virtual_mode=True
restricts file operation paths to root_dir, the execute() method runs shell
commands without path restrictions."* `[code]`/`[docs]` (quoted directly from
THREAT_MODEL.md). A third-party sandbox backend (e.g. `LangSmithSandbox`, or
another custom backend implementing `SandboxBackendProtocol`) isn't
automatically safe - "sandbox" here is an interface contract, not a guarantee
of OS-level isolation; that responsibility belongs to the backend's
implementation. `[code]` - `deepagents/backends/local_shell.py`,
`deepagents/backends/langsmith.py`.

## 7. Capability routing & policy

Two declarative mechanisms side by side, **not** a classifier, and neither is
"prose as rules":

- **`HarnessProfile` / `ProviderProfile`** (`deepagents.profiles`, marked
  beta) - dataclasses selected automatically based on the **model/provider**
  at construction (`_harness_profile_for_model`), not on task intent. They
  govern `materialize_extra_middleware()`, `excluded_middleware`,
  `excluded_tools`, `tool_description_overrides`, `base_system_prompt` +
  `system_prompt_suffix`, and `general_purpose_subagent`. A caller can
  register their own profile through
  `register_harness_profile`/`register_provider_profile`. The core middleware
  (`FilesystemMiddleware`, `SubAgentMiddleware`) can't be removed through this
  mechanism - an `excluded_middleware` touching either raises `ValueError` at
  construction. `[code]` -
  `deepagents/profiles/harness/harness_profiles.py`, `deepagents/graph.py`
  lines 238-266, 605-611.
- **`SkillsMiddleware`** (`skills=["/skills/user/", ...]`) - implements
  Anthropic's Agent Skills pattern with *progressive disclosure*: metadata
  (`name`/`description` from `SKILL.md`'s YAML frontmatter) is loaded into the
  system prompt up front, with the skill's full content loaded only when the
  model selects it. This is pure **prose + model judgement** - no code
  classifier determines which skill is invoked; the decision is entirely the
  model's, from the visible descriptions. Sources are loaded in order, with
  later sources winning for same-named skills (base→user→project→team
  layering). `[code]` - `deepagents/middleware/skills.py`.

There is no built-in intent classifier in `deepagents` for choosing a
skill/mode: skill routing = model judgement over metadata; profile routing =
deterministic from the model/provider spec, decided once per agent
construction rather than per turn. `[inferred]` - concluded from the absence
of any classifier module in the source read (see the full file list in
`## Sources`).

## Surface API

| Entrypoint | Type | Function |
|---|---|---|
| `create_deep_agent(model, tools=None, *, system_prompt=None, middleware=(), subagents=None, skills=None, memory=None, permissions=None, backend=None, interrupt_on=None, response_format=None, state_schema=None, context_schema=None, checkpointer=None, store=None, debug=False, name=None, cache=None)` | function | The main entrypoint; assembles the middleware then delegates to `langchain.agents.create_agent` |
| `DeepAgentState` | `TypedDict` (`AgentState`) | The base graph state; `messages` uses a `DeltaChannel` reducer |
| `SubAgent` | `TypedDict` | The declarative synchronous subagent spec |
| `CompiledSubAgent` | `TypedDict` | A wrapper for an already-compiled subagent (`runnable`) |
| `AsyncSubAgent` | `TypedDict` | The remote/background subagent spec (Agent Protocol) |
| `FilesystemMiddleware`, `FilesystemPermission`, `FsToolName` | classes/types | The filesystem tools + `execute` + permission rules |
| `SubAgentMiddleware`, `AsyncSubAgentMiddleware` | classes | The `task` tool (synchronous) and the background tools (async) |
| `MemoryMiddleware` | class | Loads `AGENTS.md` into the system prompt |
| `RubricMiddleware` | class | Self-eval iteration against a rubric (optional, not a default) |
| `HarnessProfile`, `HarnessProfileConfig`, `register_harness_profile` | classes/functions | Per-model/provider behaviour profiles |
| `ProviderProfile`, `register_provider_profile` | classes/functions | Per-provider model initialisation hooks |
| `GeneralPurposeSubagentProfile` | class | On/off control for the default `general-purpose` subagent |

`[code]` - `deepagents/__init__.py` (the full `__all__` list),
`deepagents/graph.py`.

## Built-in middleware

The row order in this table follows the actual installation order (base stack
→ *user middleware* → tail stack), not an arbitrary one:

| Middleware | Enforcement point | When it applies |
|---|---|---|
| `SkillsMiddleware` | Main + any subagent declaring `skills=` | Loads progressive-disclosure skills into the system prompt |
| `FilesystemMiddleware` | Always, main + every subagent | Mandatory - the source of the `ls/read_file/write_file/edit_file/delete/glob/grep(/execute)` tools, the enforcer of `permissions`, and the evictor of large tool results |
| `SubAgentMiddleware` | The main agent (when inline subagents exist) | Mandatory when a `SubAgent`/`CompiledSubAgent` exists - the source of the `task` tool |
| `create_summarization_middleware` (→ `SummarizationMiddleware`) | Always, main + every subagent | Automatic compaction when tokens exceed a model-profile-based threshold |
| `PatchToolCallsMiddleware` | Always, main + every subagent | Patches dangling `ToolMessage`s in message history |
| `AsyncSubAgentMiddleware` | The main agent, only when an `AsyncSubAgent` exists | The background start/check/update/cancel/list tools |
| *(user middleware, `middleware=[...]`, inserted here)* | - | - |
| `_ToolExclusionMiddleware` (private) | The tail stack, only when a profile has `excluded_tools` | Filters tool names from any middleware before they reach the model |
| `AnthropicPromptCachingMiddleware` (+Bedrock/Fireworks conditionally) | Always, the tail stack | Provider-specific prompt caching, a no-op on other providers |
| `MemoryMiddleware` | The main agent, only when `memory=[...]` is set | Injects `AGENTS.md`'s contents into the system prompt |
| `HumanInTheLoopMiddleware` (langchain) | Main/subagent, only when the merged `interrupt_on` is non-empty | A human approval pause before a tool executes |
| `RubricMiddleware` | Not in the default stack - install manually through `middleware=[...]` | Re-iterates the answer against a rubric until it passes or `max_iterations` |
| `TodoListMiddleware` (langchain, **not** `deepagents`') | Not in the default stack - install manually | Explicit planning (the `write_todos` tool) for multi-step tasks |

`[code]` - `deepagents/graph.py` lines 361-402 (the official base+tail stack
order in the `middleware` parameter's docstring; the table order above was
corrected to match it exactly - see also
[`../deepagents/middleware.md`](../deepagents/middleware.md) for the same
base/tail slot table), plus each middleware's own file.

## Filesystem backend

| Backend | Character | Multi-user implications |
|---|---|---|
| `StateBackend` (the default) | Ephemeral, stored in LangGraph state, checkpointed automatically per step | Isolation = thread isolation at the checkpointer level; no built-in per-user scope |
| `FilesystemBackend(root_dir, virtual_mode=True, max_file_size_mb=10)` | Reads/writes directly to local disk; `virtual_mode` confines file operations to `root_dir` | A shared host filesystem - isolation between users is the caller's responsibility (a separate process/container per user), not the backend's |
| `LocalShellBackend` (extends `FilesystemBackend` + `SandboxBackendProtocol`) | The same as `FilesystemBackend` + `execute` through `subprocess.run(shell=True)` with no command validation; `virtual_mode` does **not** restrict `execute()` | Unisolated shell execution on the host - explicitly labelled "not the default" in `THREAT_MODEL.md`; unfit for multi-user use without additional sandboxing |
| `StoreBackend(namespace: NamespaceFactory, store=None)` | Persistent across threads through LangGraph's `BaseStore` | `namespace` is the official scoping *hook* - e.g. `lambda rt: (rt.server_info.user.identity,)` for per-user isolation `[docs]` |
| `CompositeBackend(default, routes={prefix: backend}, artifacts_root="/")` | Routes paths to different backends per prefix (e.g. `/memories/` → `StoreBackend`, the rest → `StateBackend`) | The hybrid pattern: fast ephemeral + scoped durable combined, suited to separating public and per-user areas within one agent |
| `ContextHubBackend(identifier, client=None)` | Persistent in a LangSmith Hub agent repo, with mutations serialised through a timed/locked `_MutationQueue` | One `identifier` = one shared repo; per-user scoping must come from your own `identifier`/path prefix |
| `LangSmithSandbox(sandbox)` | A `SandboxBackendProtocol` implementation through LangSmith's managed sandbox | Execution isolation follows LangSmith's sandbox guarantees rather than the host process |

Only `StoreBackend`, `CompositeBackend` (when routing to a `StoreBackend`),
and `ContextHubBackend` have an explicit scoping *hook*
(`namespace`/`identifier`). `StateBackend`, `FilesystemBackend`, and
`LocalShellBackend` don't - multi-user isolation for all three must be built
outside the backend (a separate process/container per user). `[code]` +
`[docs]` (the `THREAT_MODEL.md` quotations and the
`namespace=lambda rt: ...` example from
`docs.langchain.com/oss/python/deepagents/backends`, cited via Context7).

## Sources

**The version read**: `deepagents==0.7.8` (confirmed through
`deepagents.__version__` after `uv sync`, and the
`deepagents-0.7.8.dist-info` directory name), installed alongside
`langchain==1.3.16`, `langchain-anthropic==1.6.1`, `langgraph==1.2.11`,
`langgraph-checkpoint==4.2.0`, `langgraph-prebuilt==1.1.0` - all from PyPI,
2026-08-23, through `references/recipes/pyproject.toml`.

The `[code]` files read directly from
`references/recipes/.venv/lib/python3.13/site-packages/`:

- `deepagents/__init__.py`, `deepagents/_version.py`, `deepagents/graph.py` (in full)
- `deepagents/_models.py`, `deepagents/_excluded_middleware.py` (partially, for the `_harness_profile_for_model` behaviour and the `excluded_middleware` validation)
- `deepagents/backends/__init__.py`, `protocol.py`, `state.py` (in full), `filesystem.py`, `store.py`, `local_shell.py`, `composite.py`, `context_hub.py`, `langsmith.py` (module + class docstrings + the `__init__`/`execute` signatures)
- `deepagents/middleware/__init__.py`, `permissions.py` (in full), `_fs_interrupt.py` (partially), `_tool_exclusion.py` (in full), `_prompt_caching.py` (in full), `_message_eviction.py`, `_overflow_clip.py` (partially, the module header + key helpers), `filesystem.py` (the `FilesystemPermission`, `FilesystemMiddleware` classes, the `FsToolName` constant), `subagents.py`, `async_subagents.py`, `summarization.py`, `memory.py`, `skills.py`, `patch_tool_calls.py`, `rubric.py` (module + class docstrings + the `__init__` signatures)
- `deepagents/profiles/harness/harness_profiles.py` (partially, the module header + the scaffolding validation)
- `langchain/agents/factory.py` (the `create_agent` signature + docstring)
- `langchain/agents/middleware/human_in_the_loop.py`, `langchain/agents/middleware/todo.py` (the headers + key types)

The `[docs]` sources (cited through the Context7 MCP, library ids
`/langchain-ai/deepagents` and
`/websites/langchain_oss_python_deepagents`):

- `openwiki/architecture/overview.md` (langchain-ai/deepagents) - the Deep
  Agents/LangChain/LangGraph layering diagram
- `libs/deepagents/deepagents/graph.py` (the same excerpts as above, confirmed
  identical through Context7 and by reading the source directly)
- `docs.langchain.com/oss/python/deepagents/human-in-the-loop` - the example of
  overriding `interrupt_on` per subagent
- `docs.langchain.com/oss/python/deepagents/permissions` - the example of
  wholly replacing `permissions` in a subagent
- `docs.langchain.com/oss/python/deepagents/backends` - the
  `CompositeBackend` + `StoreBackend(namespace=lambda rt: ...)` example
- `libs/deepagents/THREAT_MODEL.md` (langchain-ai/deepagents) - cited through
  a direct WebFetch to
  `raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/THREAT_MODEL.md`,
  for the claims that `LocalShellBackend` is non-default, that `execute()`
  isn't bounded by `virtual_mode`, and that HITL is an opt-in mitigation
  rather than a default
- The `libs/` directory structure of the `langchain-ai/deepagents` repo
  (containing `acp`, `cli`, `code`, `deepagents`, `evals`, `partners`
  (including `daytona`), `talon`) - cited through a WebFetch to
  `github.com/langchain-ai/deepagents/tree/main/libs`, to confirm that the
  `libs/cli` and `libs/partners/daytona` packages referenced by archetypes
  01/02/07 genuinely exist, even though their exact APIs (`agent.json`,
  `DaytonaSandbox(...)`) were **not** verified in this task because both are
  packages separate from the installed `deepagents` core (see §Building this
  with deepagents in the relevant archetype files for the details not
  re-verified).

An honesty note: the `deepagents-cli`/`langchain_daytona` packages are **not**
installed in this environment (checked through `uv run pip list`), so the
claims about those two packages' exact APIs in the archetype files keep the
labels they already use (`[code]` citing the repo, not `[code]` from a local
installation) - they aren't re-verified by this file.
