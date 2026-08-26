# `deepagents` per archetype — the correct construction

For each archetype in [`../archetypes/`](../archetypes/README.md): which
middleware, which backend, which subagents, which loop bounds, which
handlers. This joins archetype rationale to concrete API; the full
rationale is not repeated here.

Read [`extension-points.md`](extension-points.md) first — every
construction below is subject to the hard rule there. Every divergence
labelled `[ours]` is recorded in [`conformance.md`](conformance.md).

## Summary

| # | Archetype | Backend | Subagents | Gate | Loop bound |
|---|---|---|---|---|---|
| 01 | Workspace Agent | `LocalShellBackend(root_dir=repo)` | no (default) | `interrupt_on` per write/`execute` tool | moderate `recursion_limit` + `ToolCallLimitMiddleware` |
| 02 | Generative Builder | a sandbox backend (`DaytonaSandbox`, etc.) | optional | a gate only on the publish/deploy tool | loose `recursion_limit` |
| 03 | General Task Agent | `CompositeBackend(StateBackend, {"/memories/": StoreBackend})` | yes, several | at checkpoints, not per step | `ModelCallLimitMiddleware` + a repetition guard |
| 04 | Research/Analyst | `StateBackend` or `CompositeBackend` | yes, per sub-topic | none (read-only) | `ToolCallLimitMiddleware(tool_name="task")` |
| 05 | In-App Copilot | `StateBackend` | no | `undo_*` tools, not `interrupt_on` | strict `recursion_limit` |
| 06 | Workflow Agent | `StoreBackend(namespace=...)` | optional | async `interrupt_on` through a dashboard | strict `recursion_limit` + `ModelCallLimitMiddleware(exit_behavior="error")` |
| 07 | Computer-Use Agent | a sandbox backend for the browser session | optional | `interrupt_on` for irreversible actions | `ToolCallLimitMiddleware` per action tool |

---

## 01 — Workspace Agent

**Backend**: `LocalShellBackend(root_dir="<repo>", virtual_mode=True)`.
`virtual_mode` confines file operations to `root_dir` but does **not**
restrict `execute()` — the backend's own docstring says so. `[code]` —
`deepagents/backends/local_shell.py` lines 26-105.

**Middleware**: the default stack suffices. Add `TodoListMiddleware()`
only when the repo task is long and multi-step; it isn't required.

**Subagents**: not used by default — not a divergence; 5 of the 10
`create_deep_agent` calls in the maintainers' `examples/` also pass no
synchronous subagents. `[code]` — repo `langchain-ai/deepagents` commit
`23b83ad`, see [`conformance.md`](conformance.md) D-01.

**Gate**: `interrupt_on={"execute": True, "write_file": True,
"edit_file": True, "delete": True}` plus a mandatory `checkpointer`
(without one, an interrupt cannot be resumed).

⚠️ Don't use `permissions=` with this backend: `FilesystemMiddleware`
**raises `NotImplementedError`** for `permissions` plus a
`SandboxBackendProtocol` backend whose paths aren't scoped to a route.
`[code]` — `deepagents/middleware/filesystem.py` lines 1691-1700. There
are two official ways out:

1. Per-tool `interrupt_on`, or a `wrap_tool_call` command allow-list (the
   maintainers' `ShellAllowListMiddleware` pattern).
2. **Route every `permissions`-covered path to a non-execution backend.**
   The `_all_paths_scoped_to_routes` check passes when every rule pattern
   lives in a `CompositeBackend` route rather than the shell-capable
   default backend. This is exactly what `examples/llm-wiki/helpers.py`
   does (lines 548-565, 623-638): a `LangSmithSandbox` default, with
   `/raw/`, `/wiki/`, `/log.md`, `/AGENTS.md` routed to
   `FilesystemBackend(root_dir=workspace)`, and `permissions` touching
   only those four prefixes. `[code]` — repo `langchain-ai/deepagents`
   commit `23b83ad`.

**Loop bound**: `.with_config({"recursion_limit": 150})` — enough for a
long editing session, far below the `9_999` default.

```python
agent = create_deep_agent(
    model=ChatAnthropic(model_name="claude-sonnet-4-6"),
    system_prompt=WORKSPACE_PROMPT,
    backend=LocalShellBackend(root_dir=repo_path, virtual_mode=True),
    interrupt_on={"execute": True, "write_file": True, "edit_file": True, "delete": True},
    checkpointer=checkpointer,
).with_config({"recursion_limit": 150})
```

---

## 02 — Generative Builder

**Backend**: the sandbox family.
`DaytonaSandbox(sandbox=Daytona().create(), timeout=300)` from the
`langchain-daytona` package (keyword-only), or `deepagents`' built-in
`LangSmithSandbox(sandbox)`. For deployment through the `deepagents` CLI,
`agent.json`:
`{"backend": {"type": "sandbox", "sandbox_config": {"scope": "thread",
"policy_ids": [...]}}}` — the `sandbox_config` key is verified in
`libs/cli/deepagents_cli/deploy/project.py` and
`libs/cli/tests/unit_tests/deploy/test_project.py` lines 219-249.
`[code]` — repo `langchain-ai/deepagents` commit `23b83ad`.

**Middleware**: the default stack. `FilesystemMiddleware` automatically
exposes `execute` because a sandbox backend implements
`SandboxBackendProtocol`.

**Subagents**: optional. When there is a long separable phase (e.g.
"generate assets" vs "assemble pages"), use a `SubAgent` with narrow
`tools`.

**Gate**: `interrupt_on` only on your own publish/deploy tool
(`interrupt_on={"publish": True}`); the build/iterate loop is
deliberately ungated (`[ours]` D-02).

**Persistence**: no `checkpointer`/`store` for single-use sessions. If the
artifact must survive, add a durable route:
`CompositeBackend(default=sandbox_backend, routes={"/exports/": StoreBackend(namespace=...)})`
— an explicit choice, not a default.

**Loop bound**: a loose `recursion_limit` (e.g. 300) because
build-preview iterations really are numerous; the real bound comes from
the token budget (`ModelCallLimitMiddleware(thread_limit=...)`) rather
than step count.

---

## 03 — General Task Agent

**Backend**: `CompositeBackend(default=StateBackend(), routes={"/memories/":
StoreBackend(namespace=lambda rt: (user_id, "memories"))})` — everyday
work ephemeral, persistent memory durable and scoped per user. This is the
hybrid pattern that `FilesystemMiddleware`'s own docstring demonstrates.

**Middleware**:
- `TodoListMiddleware()` through `middleware=[...]` — explicit planning is
  this archetype's distinguishing feature, and this middleware is **not**
  part of `create_deep_agent`'s default stack. `[code]` — runtime
  verification: the default stack is `FilesystemMiddleware,
  SubAgentMiddleware, SummarizationMiddleware, PatchToolCallsMiddleware,
  AnthropicPromptCachingMiddleware`; the only place `TodoListMiddleware`
  appears in `deepagents` 0.7.8 is the `_openai_codex.py` profile.
- `memory=["/memories/AGENTS.md"]` for persistent context.
- `ModelCallLimitMiddleware(thread_limit=..., exit_behavior="end")`.

**Subagents**: several declarative `SubAgent`s with different `tools` and
`model` per subtask — exactly the pattern in
`examples/nvidia_deep_agent/src/agent.py` (researcher + data-processor)
and `examples/content-builder-agent/`.

**Gate**: review at checkpoints, not per step. `interrupt_on` only for
actions that leave the system (sending email, calling a third-party API).

**Loop bound**: `ModelCallLimitMiddleware` for budget, plus a guard
against identical repeated tool calls (`[ours]` D-03) —
`ToolCallLimitMiddleware` counts total calls, not repetitions, so it
doesn't catch an agent spinning in place.

---

## 04 — Research/Analyst

**Backend**: `StateBackend` suffices for a single research session; step
up to `CompositeBackend` with a durable route if the report must survive.

**Middleware**: the default stack. The built-in `SummarizationMiddleware`
matters here — large search results are automatically evicted to
`/large_tool_results/` by `FilesystemMiddleware` before they flood
context.

**Subagents**: one research `SubAgent` per sub-topic, with narrow `tools`
(`[web_search, think_tool]`) and **no** broad filesystem access. This is
exactly the maintainers' construction in `examples/deep_research/agent.py`.

```python
research_sub_agent: SubAgent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS,
    "tools": [web_search, think_tool],
}
agent = create_deep_agent(
    model=model,
    tools=[web_search, think_tool],
    system_prompt=ORCHESTRATOR_INSTRUCTIONS,
    subagents=[research_sub_agent],
    response_format=ResearchReport,
)
```

**Gate**: none — this archetype is read-only against the outside world.

**Output**: `response_format=<report schema>` to force the output shape.
⚠️ `response_format` validates the **shape**, not the correctness of the
contents; hallucinated citations still pass. Post-hoc provenance
validation is `[ours]` (D-04).

**Loop bound**: explicit limits in the orchestrator prompt
(`max_concurrent_research_units`, `max_researcher_iterations` — the
maintainers' pattern in `examples/deep_research/agent.py`) **plus**
`ToolCallLimitMiddleware(tool_name="task", thread_limit=N)` as structural
enforcement, because a prompt limit is only an instruction.

---

## 05 — In-App Copilot

**Tool surface**: `tools=[...]` containing thin wrappers around the host
product's API endpoints. The built-in filesystem tools are irrelevant.

**How to remove them** — two official paths, both far more appropriate
than `permissions`:

```python
# per agent, replacing the FilesystemMiddleware instance in place
agent = create_deep_agent(
    model=model,
    tools=product_tools,
    middleware=[FilesystemMiddleware(backend=backend, tools=["read_file"])],
)

# or, for every stack at once (main + subagents)
register_harness_profile(
    "anthropic:claude-sonnet-4-6",
    HarnessProfile(
        excluded_tools=frozenset({"write_file", "edit_file", "delete", "glob", "grep", "execute", "ls"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)
```

`read_file` **must** appear in `FilesystemMiddleware(tools=[...])` —
otherwise `ValueError`. `FilesystemMiddleware` itself cannot be removed
(`excluded_middleware` refuses it). `[code]` —
`deepagents/middleware/filesystem.py` lines 1670-1673;
`deepagents/graph.py` lines 238-265.

This is also the only archetype where disabling the `task` tool is
reasonable: `GeneralPurposeSubagentProfile(enabled=False)` plus no
synchronous subagents.

**Backend**: the default `StateBackend`. The source of truth lives in the
host product, not in the agent.

**Context**: `context_schema=` for per-call application state, not
cross-session `memory=` — this archetype's horizon is short.

**Gate**: an `undo_<action>` tool invoked from the host UI rather than
`interrupt_on` (`[ours]` D-05).

**Loop bound**: a strict `recursion_limit` (e.g. 25) — a copilot that
thinks for a long time is a UX regression.

---

## 06 — Workflow Agent

**Loop shape**: `create_deep_agent(...)` as one node inside a larger
LangGraph graph, or behind an event-triggered queue worker. `deepagents`
determines "what the LLM does when called", not "when it is called"
(`[ours]` D-06).

**Backend**: `StoreBackend(namespace=lambda rt: (tenant_id, "workflow"))`
— durable and scoped; no interactive session is keeping it alive.

**Idempotency**: an application-injected `checkpointer` plus a `thread_id`
derived from the event's idempotency key rather than random (`[ours]`
D-06b). A retried event lands on the same checkpoint.

**Gate**: `interrupt_on={"send_email": True}` still makes sense even with
no real-time human — a LangGraph interrupt means the run **stops and
waits**, and approval can arrive asynchronously through a dashboard or
Slack. This requires a durable `checkpointer`, not `MemorySaver`.

**Error handling**: this is the archetype that needs
`ToolRetryMiddleware`/`ModelRetryMiddleware` most, because no human is
retrying manually.

**Loop bound**: a strict `recursion_limit` plus
`ModelCallLimitMiddleware(thread_limit=..., exit_behavior="error")` —
`"error"` (not `"end"`) so an over-budget run appears as a failure on the
dashboard rather than finishing silently.

**Kill switch**: absent from `deepagents` (`[ours]` D-06c) — a database
flag the worker checks before invoking the agent.

---

## 07 — Computer-Use Agent

**Tool surface**: custom
`tools=[screenshot, click, type_text, scroll, verify_state]` mapping onto
an external browser driver. `deepagents` has no built-in computer-use
tools.

**Backend**: a sandbox backend for the browser session, equivalent to
archetype 02 — a crashed or abused browser session must not touch other
compute.

**Gate**: `interrupt_on={"submit_form": True, "click": {"allowed_decisions":
["approve", "reject"]}}` for irreversible actions. The
`InterruptOnConfig.when` predicate is useful here: interrupt only when the
clicked selector is on a risky list, not on every click.

**Verification**: the `verify_state` tool must be called after every UI
action, enforced through system prompt instructions (`[ours]` D-07).
`deepagents` has **no** middleware that enforces tool call ordering.
`PatchToolCallsMiddleware` is often assumed to do so — its role is only to
patch `ToolMessage`s for dangling/cancelled/malformed tool calls, not to
enforce ordering. `[code]` —
`deepagents/middleware/patch_tool_calls.py` lines 14-45.

Enforcement stronger than a prompt (though still not a structural
guarantee): a `wrap_tool_call` that refuses a second consecutive UI action
without a `verify_state` in between, returning
`ToolMessage(status="error")`. The same pattern as the maintainers'
`ShellAllowListMiddleware`.

**Loop bound**: `ToolCallLimitMiddleware(tool_name="click",
thread_limit=N, exit_behavior="end")` — the most brittle archetype, and
the one that most needs a hard per-action-tool bound.

## Sources

**Versions read**: `deepagents==0.7.8`, `langchain==1.3.16`, from
`references/recipes/.venv/lib/python3.13/site-packages/`.

`[code]` installed package: `deepagents/graph.py`,
`deepagents/backends/{local_shell,composite,store,state}.py`,
`deepagents/middleware/{filesystem,subagents,patch_tool_calls}.py`,
`deepagents/profiles/harness/{harness_profiles.py,_openai_codex.py}`,
`langchain/agents/middleware/{model_call_limit,tool_call_limit,tool_retry,model_retry}.py`.

`[code]` from `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21):
`examples/deep_research/agent.py`,
`examples/nvidia_deep_agent/src/agent.py`,
`examples/content-builder-agent/content_writer.py`,
`examples/text-to-sql-agent/agent.py`,
`examples/async-subagent-server/{supervisor,server}.py`,
`examples/better-harness/better_harness/agent.py`,
`examples/ralph_mode/ralph_mode.py`,
`libs/cli/deepagents_cli/deploy/project.py`,
`libs/cli/tests/unit_tests/deploy/test_project.py`,
`libs/code/deepagents_code/agent.py`,
`libs/partners/daytona/langchain_daytona/sandbox.py`.

Per-archetype rationale: [`../archetypes/`](../archetypes/README.md).
Divergences labelled `[ours]` (D-01 … D-07):
[`conformance.md`](conformance.md).
