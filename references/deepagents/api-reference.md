# `deepagents` - API reference

A parameter reference for every public `deepagents` entrypoint, read from
the installed package's source (not the README). For the architectural
picture read [`../systems/deepagents.md`](../systems/deepagents.md) first;
this file is the detail layer beneath it.

Convention: types and defaults are written **exactly** as they appear in
the signature. Parameters marked ⚠️ are the most commonly misused - the
reason is given in the effect column.

## `create_deep_agent(...)`

`[code]` - `deepagents/graph.py` lines 268-288 (signature), 289-579
(docstring), 580-944 (implementation).

Returns a `CompiledStateGraph`, already wrapped in
`.with_config({"recursion_limit": 9_999, "metadata": {...}})`.

| Parameter | Type | Default | Effect |
|---|---|---|---|
| `model` | `str \| BaseChatModel \| None` | `None` ⚠️ | `None` is **deprecated since 0.5.3** and removed in 1.0.0 - it triggers `warn_deprecated` and then uses `ChatAnthropic(model_name="claude-sonnet-4-6")`. A `provider:model` string is resolved through `resolve_model` (`deepagents/_models.py`). The chosen model also determines the active `HarnessProfile` via `_harness_profile_for_model`. |
| `tools` | `Sequence[BaseTool \| Callable \| dict] \| None` | `None` | **Additive** - merged with the middleware's built-in tools, never replacing them. To remove built-in tools use `HarnessProfile.excluded_tools` or `FilesystemMiddleware(tools=[...])`, not this parameter. Each tool's description can be overridden by a profile through `tool_description_overrides`. |
| `system_prompt` | `str \| SystemMessage \| None` | `None` | The `USER` slot in the `USER` → `BASE` → `SUFFIX` assembly, separated by blank lines. `BASE`/`SUFFIX` come from `HarnessProfile.base_system_prompt`/`system_prompt_suffix`. `None` plus an empty profile = an empty authored system prompt (since 0.7.0 `deepagents` no longer writes its own base prompt; `BASE_AGENT_PROMPT` is deprecated). A `SystemMessage` preserves any existing `cache_control` markers. |
| `middleware` | `Sequence[AgentMiddleware]` | `()` ⚠️ | Inserted **after** the base stack and **before** the tail stack. An entry whose `.name` matches an existing stack member **replaces it in place**; a new name is inserted after the last core member. See [`middleware.md`](middleware.md) - this "replace by name" behaviour is the most common source of silent bugs. |
| `subagents` | `Sequence[SubAgent \| CompiledSubAgent \| AsyncSubAgent] \| None` | `None` | Routed by dict shape: a `graph_id` key → `AsyncSubAgent`; a `runnable` key → `CompiledSubAgent`; otherwise a declarative `SubAgent`. The `general-purpose` subagent is added automatically unless the caller already supplies one with that name or a profile disables it. |
| `skills` | `list[str] \| None` | `None` | POSIX paths relative to the backend root. Installs `SkillsMiddleware` at the **very front** of the stack. Later sources override earlier ones for the same skill name. |
| `memory` | `list[str] \| None` | `None` | Paths to `AGENTS.md` files. Installs `MemoryMiddleware(add_cache_control=True)` in the **tail** stack, after the prompt-caching middleware - this ordering is deliberate so that memory updates don't invalidate the Anthropic cache prefix. |
| `permissions` | `list[FilesystemPermission] \| None` | `None` ⚠️ | Enforced by `FilesystemMiddleware` at the **tool** level, not the backend level - direct backend use bypasses permissions. Rules are evaluated in order, first match wins; no match = allowed. `mode="interrupt"` automatically generates `interrupt_on` entries (see `handlers.md`). Combining `permissions` with a `SandboxBackendProtocol` backend **raises `NotImplementedError`** unless every path is scoped to a non-execution route. |
| `backend` | `BackendProtocol \| None` | `None` → `StateBackend()` ⚠️ | The default is `StateBackend` (ephemeral, living in LangGraph state), **not** `LocalShellBackend`. The `execute` tool is only useful when the backend implements `SandboxBackendProtocol`. Factories (callables) have been rejected since 0.7 - pass an instance. |
| `interrupt_on` | `dict[str, bool \| InterruptOnConfig] \| None` | `None` | Merged with entries generated from `permissions` (user entries win per tool name). If the merge is empty, `HumanInTheLoopMiddleware` is not installed at all. Declarative `SubAgent`s inherit this; `CompiledSubAgent` and `AsyncSubAgent` **do not**. |
| `response_format` | `ResponseFormat[ResponseT] \| type[ResponseT] \| dict \| None` | `None` | Passed to `create_agent`. Validates the output's **shape** only, not the correctness of its contents. |
| `state_schema` | `type[DeepAgentState] \| None` | `None` → `DeepAgentState` ⚠️ | Must subclass `DeepAgentState` so the `DeltaChannel` reducer on `messages` survives - **not validated at runtime** (a TypedDict cannot be `issubclass`-checked), so getting it wrong only surfaces as bloating checkpoints. Passed to declarative `SubAgent`s, **not** to `CompiledSubAgent`/`AsyncSubAgent`. The docstring recommends putting extra fields in a middleware's `state_schema` rather than here. |
| `context_schema` | `type[ContextT] \| None` | `None` | Immutable run-scoped context, passed through unchanged to `create_agent`. |
| `checkpointer` | `Checkpointer \| None` | `None` | Passed through unchanged. `deepagents` never builds a checkpointer of its own. Required when using `interrupt_on`. |
| `store` | `BaseStore \| None` | `None` | Passed through unchanged. `StoreBackend(store=None)` takes the store from the LangGraph execution context. |
| `debug` | `bool` | `False` | Passed through unchanged. |
| `name` | `str \| None` | `None` | Passed through unchanged, and included in the `lc_agent_name` metadata. |
| `cache` | `BaseCache \| None` | `None` | Passed through unchanged. |

**What this signature does not have** (frequently assumed to): there is no
`recursion_limit`, `max_iterations`, `timeout`, `temperature`, `verbose`,
`memory_store`, `todo`, or `planning`. Loop bounds are set through
`.with_config({"recursion_limit": N})` or `config=` at `invoke` time (see
[`handlers.md`](handlers.md)).

## `DeepAgentState`

`[code]` - `deepagents/graph.py` lines 70-73.

`AgentState` with one difference: the `messages` field is annotated
`DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)`, dropping
checkpoint growth from O(N²) to O(N). Subclass this rather than
`AgentState` when using `state_schema=`.

## Subagent specs

`[code]` - `deepagents/middleware/subagents.py` lines 36-243;
`deepagents/middleware/async_subagents.py` lines 34-79.

| Key | Shape | Required | Notes |
|---|---|---|---|
| `name` | `str` | yes | Used by the model as the `task` tool's `subagent_type` argument. |
| `description` | `str` | yes | This is what the model reads to decide on delegation - write it action-oriented. |
| `system_prompt` | `str` | yes (`SubAgent`) | The harness profile still prepends/appends `BASE`/`SUFFIX` around it. |
| `tools` | `Sequence[...]` | no | ⚠️ If the `tools` key is **absent**, the subagent inherits the main agent's `tools`. If present but `[]`, the subagent gets no caller tools at all (middleware tools remain). |
| `model` | `str \| BaseChatModel` | no | Resolved separately, and selects its own `HarnessProfile`. |
| `middleware` | `list[AgentMiddleware]` | no | The same replace-by-name rule applies. This is the official path for a per-subagent `FilesystemMiddleware(tools=[...])`. |
| `interrupt_on` | `dict[...]` | no | When present it **replaces** the top-level inheritance rather than adding to it. |
| `skills` | `list[str]` | no | Installs a `SkillsMiddleware` specific to that subagent. |
| `permissions` | `list[FilesystemPermission]` | no | When present it **entirely replaces** the parent's rules rather than adding to them. |
| `response_format` | `ResponseFormat \| type \| dict` | no | When set, the JSON-serialised `structured_response` becomes the `ToolMessage` content, replacing last-message extraction. |
| `runnable` | `Runnable` | yes (`CompiledSubAgent`) | Its state schema **must** have a `messages` key, otherwise `_return_command_with_state_update` raises `ValueError`. |
| `graph_id` | `str` | yes (`AsyncSubAgent`) | The presence of this key is what routes the spec to `AsyncSubAgentMiddleware`. |
| `url`, `headers` | `str`, `dict[str, str]` | no (`AsyncSubAgent`) | The Agent Protocol endpoint and auth headers. |

## Backends

`[code]` - `deepagents/backends/*.py`, each one's `__init__` signature.

| Constructor | Signature | Notes |
|---|---|---|
| `StateBackend()` | no arguments | The default. Ephemeral; file contents live in LangGraph state. |
| `FilesystemBackend(root_dir=None, virtual_mode=True, max_file_size_mb=10)` | positional | `root_dir=None` → cwd. `virtual_mode=True` blocks `..`, `~`, and absolute paths outside `root_dir` for **file operations** - it is not a sandbox. |
| `LocalShellBackend(root_dir=None, *, virtual_mode=True, timeout=DEFAULT_EXECUTE_TIMEOUT, max_output_bytes=100_000, env=None, inherit_env=False)` | ⚠️ | Subclasses `FilesystemBackend` plus `SandboxBackendProtocol`. Its own docstring states that `virtual_mode` provides **no security whatsoever** once the shell is active. |
| `StoreBackend(*, namespace: NamespaceFactory, store=None)` | keyword-only | `namespace` is the only official scoping *hook*. Wildcard `*` is rejected. `store=None` → taken from the LangGraph execution context. |
| `CompositeBackend(default, routes, *, artifacts_root="/")` | `default` & `routes` positional | Route prefixes must start with `/` and should end with `/`. Longest prefix match wins. |
| `ContextHubBackend(identifier, client=None)` | positional | Persistent in a LangSmith Hub agent repo. |
| `LangSmithSandbox(sandbox)` | positional | Wraps a LangSmith-managed sandbox. |
| `DaytonaSandbox(*, sandbox, timeout=30*60, sync_polling_interval=0.1)` | keyword-only | A separate package, `langchain-daytona`, not part of `deepagents`. `[code]` - `libs/partners/daytona/langchain_daytona/sandbox.py` lines 30-59 (repo `langchain-ai/deepagents`). |

## `FilesystemMiddleware(...)`

`[code]` - `deepagents/middleware/filesystem.py` lines 1620-1744.

All keyword-only.

| Parameter | Default | Effect |
|---|---|---|
| `backend` | `None` → `StateBackend()` | If installed manually through `middleware=[...]`, it **must** receive the same backend the agent uses; otherwise the agent has two different filesystems. |
| `system_prompt` | `None` | Replaces the filesystem prompt fragment. |
| `custom_tool_descriptions` | `None` | A map of tool name → description. |
| `tool_token_limit_before_evict` | `20000` | Tool results above this threshold are written to the backend and replaced with a preview. `None` disables eviction. |
| `human_message_token_limit_before_evict` | `50000` | The same, for the most recent `HumanMessage`. |
| `max_execute_timeout` | `3600` | The upper bound on the per-command timeout the model may request. |
| `grep_max_count` | `1000` | Caps total matches; `None` disables the default cap. |
| `tools` | `None` → all ⚠️ | A `list[FsToolName]` or `"all"`. `FsToolName = Literal["ls","read_file","write_file","edit_file","delete","glob","grep","execute"]`. `read_file` **must** be in the list, otherwise `ValueError`. Tools outside the list are not registered at all (not merely hidden). |
| `_permissions` | `None` | Private - go through `create_deep_agent(permissions=...)`, not directly. |

A note on surface: with the default `StateBackend`, the tool node contains
`delete, edit_file, execute, glob, grep, ls, read_file, task, write_file`.
`execute` **is registered** but filtered out of the model's view during
`wrap_model_call` because the backend does not support execution.
`[code]` - verified at runtime,
`FilesystemMiddleware._filter_unsupported_tools_and_apply_prompt`
(`middleware/filesystem.py` lines 3018-3064, called from
`wrap_model_call` line 3094).

## `FilesystemPermission`

`[code]` - `deepagents/middleware/filesystem.py` lines 384-417.

A dataclass with `operations: list[FilesystemOperation]`,
`paths: list[str]`, `mode: Literal["allow","deny","interrupt"] = "allow"`.
Paths **must** begin with `/` and may contain neither `..` (`ValueError`)
nor `~` (`NotImplementedError`).

## Profiles

`[code]` - `deepagents/profiles/harness/harness_profiles.py`,
`deepagents/profiles/provider/provider_profiles.py`.

`register_harness_profile(key, profile)` - `key` is either `"provider"` or
`"provider:model"`. Registration is **additive/merging**, not replacing.
The relevant `HarnessProfile` fields: `base_system_prompt`,
`system_prompt_suffix`, `tool_description_overrides`, `excluded_tools`,
`excluded_middleware`, `extra_middleware`, `general_purpose_subagent`.

⚠️ `excluded_middleware` **refuses** `FilesystemMiddleware` and
`SubAgentMiddleware` (required scaffolding) with a `ValueError` at profile
construction; an entry matching nothing in the stack is also a
`ValueError`. To remove the `task` tool, use
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`
and pass no synchronous subagents - not `excluded_middleware`.

`HarnessProfileConfig` is the **declarative** variant of `HarnessProfile`,
for profiles loaded from YAML/JSON. One difference:
`excluded_middleware` accepts only **string** names, not classes - because
a config file cannot import. `register_harness_profile` accepts both and
converts `HarnessProfileConfig` to `HarnessProfile` at registration time,
so there is no manual conversion step.
`HarnessProfileConfig.from_harness_profile` goes the other way, using a
middleware's `serialized_name` when available so the round-trip to a
config file stays stable. `[code]` -
`deepagents/profiles/harness/harness_profiles.py` lines 192-330 (the
class), 439 (`from_harness_profile`).

`register_provider_profile(key, profile)` governs the **model
construction** phase, orthogonal to `HarnessProfile`, which governs
runtime behaviour once the model exists.

This file's coverage of `deepagents.__all__` (19 names): **18 covered**.
The exception: `__version__`, a version string constant with no
parameters - outside the scope of a parameter reference.

## Sources

**Versions read**: `deepagents==0.7.8`, from
`references/recipes/.venv/lib/python3.13/site-packages/`, alongside
`langchain==1.3.16` and `langchain-anthropic==1.6.1`.

`[code]` files read for this document:

- `deepagents/__init__.py`, `deepagents/graph.py` (in full)
- `deepagents/middleware/filesystem.py` (`FilesystemPermission`, `FsToolName`, `FilesystemMiddleware.__init__`, `wrap_model_call`, `wrap_tool_call`)
- `deepagents/middleware/subagents.py`, `async_subagents.py` (the TypedDict specs, `_return_command_with_state_update`)
- `deepagents/middleware/patch_tool_calls.py`, `_prompt_caching.py`, `_state.py`, `_tool_exclusion.py`, `_fs_interrupt.py` (in full)
- `deepagents/middleware/summarization.py` (`create_summarization_middleware`, `compute_summarization_defaults`)
- `deepagents/backends/__init__.py`, `state.py`, `store.py`, `filesystem.py`, `local_shell.py`, `composite.py` (`__init__` signatures plus class docstrings)
- `deepagents/profiles/harness/harness_profiles.py` (the `HarnessProfile` fields, `register_harness_profile`)
- `langchain/agents/factory.py`, `langchain/agents/middleware/types.py`

`[code]` sources outside the installed package, read from a
`git clone --depth 1` of `langchain-ai/deepagents` (commit `23b83ad`,
2026-08-21):

- `libs/partners/daytona/langchain_daytona/sandbox.py` - the
  `DaytonaSandbox.__init__` signature
