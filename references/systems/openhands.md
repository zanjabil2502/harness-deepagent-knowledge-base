# OpenHands

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. An important note on repo identity: the name `OpenHands` today
points at **two** different repos. `All-Hands-AI/OpenHands` (redirected to
`OpenHands/OpenHands`) has had its contents replaced entirely by **Agent
Canvas** - a "self-hosted developer control center for coding agents and
automations" running OpenHands, Claude Code, Codex, or another ACP agent as the
chosen backend; this is no longer the coding agent itself. `[code]` - the
`README.md` of the `OpenHands/OpenHands` repo (read via `git clone --depth 1`,
2026-08-23). The original coding agent (its loop, tools, condenser, subagents,
sandbox) now lives in the separate repo **`OpenHands/software-agent-sdk`** ("A
clean, modular SDK for building AI agents with OpenHands V1"), with the
packages `openhands-sdk`, `openhands-tools`, `openhands-workspace`,
`openhands-agent-server`. This file documents **`software-agent-sdk`** because
that is what actually runs the seven axes below - not Agent Canvas, which is
only a multi-backend UI/orchestration on top of it. `[code]` - the directory
structure of `software-agent-sdk` (`git clone --depth 1`, its HEAD commit at
cloning time, 2026-08-23).

## Archetype

A **Workspace Agent (01)**, hybrid with **Generative Builder (02)** elements
through `RemoteWorkspace`/Docker (state = one isolated sandbox container,
pausable/resumable). Its blast radius touches the target workspace/repo (local
or a container), artifacts = code edits + answers, human control governed by a
per-risk `ConfirmationPolicy` (see axis 6), interfaces: a Python SDK + a CLI +
an agent server (headless, used by Agent Canvas as one of its backends).
`[code]` - `openhands-sdk/openhands/sdk/workspace/{local,base}.py`,
`openhands-workspace/openhands/workspace/docker/workspace.py`.

## 1. Loop shape

ReAct: `Agent.step()` (a subclass of `AgentBase`, required of every agent)
documents its own order - **"1. an LLM call → 2. execute the tool → 3. update
state → 4. if finished, set `execution_status = FINISHED`"**. `[code]` -
`openhands-sdk/openhands/sdk/agent/base.py` lines 630-648 (the `step`
docstring).

The outer loop is in `LocalConversation.run()`: `while True: step(); if
execution_status in (FINISHED, PAUSED, ...): break`. The model decides to stop
normally - through `FinishTool` (an explicit built-in tool, not merely "no more
tool_calls") - but the harness installs a `max_iteration_per_run` safety net
(default **500**, far tighter than `deepagents`' `recursion_limit=9999`
default): once iterations reach the limit without `FINISHED`, `run()` stops the
loop and sets `execution_status = ConversationExecutionStatus.ERROR`. `[code]`
- `openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py` lines
186, 218, 1902-2044;
`openhands-sdk/openhands/sdk/tool/builtins/finish.py`, the `FinishTool` class.

There is also a separate `StuckDetector` path
(`conversation/stuck_detector.py`, 14K) able to force `execution_status =
STUCK` - oscillation/no-progress detection independent of the iteration limit.
`[code]` (the filename & constants confirmed; its details weren't read in
full).

## 2. Context

`LLMSummarizingCondenser` (a `RollingCondenser` subclass) - LLM-based
compaction separate from the agent's LLM (the condenser's `llm` attribute can
be a different model from the main one, explicitly for cost/speed separation).
Its key parameters: `max_size` (default 240 events), `keep_first` (default 2,
early events never condensed), `minimum_progress` (default 0.1 - condensation
is refused as an error if it would forget less than 10% of events, preventing a
condensation that saves nothing meaningful). It is triggered by three
`Reason`s: `REQUEST` (manual), `TOKENS` (a token threshold), `EVENTS` (an event
count threshold). `[code]` -
`openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py`
lines 1-60. There are also a `NoOpCondenser` and a `PipelineCondenser`
(composing several condensers) - `[code]` (the filenames; contents not read in
full).

No filesystem-as-memory pattern equivalent to `deepagents`' was found (no
backend automatically evicting large tool results to a file) in the `context/`
modules read; cross-session memory is handled through `skills/` (see axis 7)
rather than the condenser layer. `[inferred]` - from the absence of an
equivalent mechanism in the `context/` and `skills/` directories read.

## 3. Tool surface

A few broad tools with explicit built-ins: `finish`, `think`, plus the main
working tools from the `openhands-tools` package (e.g. a terminal/bash, a file
editor) - `AgentBase.include_default_tools` maps built-in names to classes
through `BUILT_IN_TOOL_CLASSES`. `[code]` -
`openhands-sdk/openhands/sdk/agent/base.py` lines 160-165, 602-603, 714-722.
Additional tools are registered through the `tools=[Tool(name=...)]` parameter
when building an `Agent` (see the `register_agent` example in axis 4) - a
declarative pattern similar to `deepagents`', not one generic free-form
`execute` shell tool. `[code]` -
`openhands-sdk/openhands/sdk/subagent/registry.py`, its module docstring.

## 4. Delegation

There is an explicit subagent mechanism; it isn't flat: `register_agent(name,
factory_func, description=...)` registers an `AgentFactory` (a function
producing an `Agent` + an `AgentDefinition`) into a global registry
(`RLock`-protected). Subagent definitions can also be loaded from project/user
files through `load_project_agents` / `load_user_agents` (analogous to
`.claude/agents/*.md` or `AGENTS.md`). `[code]` -
`openhands-sdk/openhands/sdk/subagent/registry.py` lines 1-60,
`openhands-sdk/openhands/sdk/subagent/load.py`, `subagent/schema.py` (the
`AgentDefinition`). Because each subagent is a full `Agent` with its own tool
subset and `agent_context` (see the `security_expert` example in the registry
docstring), the result-return pattern follows the same `Agent`/`step()`
contract as the main agent - whether a subagent returns a summary or a full
transcript to its caller wasn't verified further in this task. `[code]`/`[inferred]`
- the registration structure is confirmed from source; the exact "result
returning to the caller" mechanism wasn't read down to the subagent tool's call
site in `tool/impl/`.

## 5. State & resume

`ConversationState` (31K, `conversation/state.py`) holds `execution_status`
(`RUNNING`/`FINISHED`/`ERROR`/`STUCK`/`PAUSED`/...), `active_branch()` for
transcript branching, and a list of unexecuted actions
(`get_unmatched_actions` - used by the *confirmation mode* path, see axis 6).
`[code]` - `openhands-sdk/openhands/sdk/conversation/state.py`,
`openhands-sdk/openhands/sdk/agent/agent.py` lines 645-651 (the
`get_unmatched_actions` usage in `step()`). `run()` can be called again to
resume from `execution_status='idle'`, with `max_iteration_per_run` passed
again on each resume - not accumulated across sessions. `[code]` -
`local_conversation.py` lines 770-810, 833.

The Docker sandbox (`DockerWorkspace`, the `openhands-workspace` package)
supports container `pause`/`resume` through `docker pause`/`docker unpause` -
the sandbox process state can be frozen without killing it, separate from the
conversation checkpoint. `[code]` -
`openhands-workspace/openhands/workspace/docker/workspace.py` lines 401-428.

## 6. Safety gate

`ConfirmationPolicyBase` (a `DiscriminatedUnionMixin` subclass) with three
concrete implementations: `AlwaysConfirm`, `NeverConfirm`, `ConfirmRisky`
(`threshold: SecurityRisk = HIGH` by default, `confirm_unknown: bool = True` by
default - an `UNKNOWN` risk is **fail-closed**, requiring confirmation unless
explicitly disabled). `should_confirm(risk)` is used *before* an action
executes; if a pending unconfirmed action exists, `step()` executes it at the
start of the next turn (`_execute_actions`) instead of calling the LLM again -
a "pause then continue" pattern like `deepagents`' `interrupt_on`. `[code]` -
`openhands-sdk/openhands/sdk/security/confirmation_policy.py` (in full),
`openhands-sdk/openhands/sdk/agent/agent.py` lines 645-651.

Risk levels come from `security/risk.py` (the `SecurityRisk` enum) and are
evaluated through dedicated analyzers - there is an `LLMAnalyzer`,
`ensemble.py` (combining several analyzers), and the
`_shell_ast.py`/`shell_parser.py`/`shell_semantics.py` modules parsing the
**shell command AST** to assess a command's risk before execution (rather than
a string regex). `[code]` - the file listing of
`openhands-sdk/openhands/sdk/security/*.py` (the parsers' contents weren't read
in detail).

Sandboxing: `LocalWorkspace` (directly in the host process) vs
`DockerWorkspace`/`RemoteWorkspace` (a
`ghcr.io/openhands/agent-server:latest` container, started through `docker run`
from `execute_command`, tracked through `_container_id`, and
stoppable/pausable/unpausable). `[code]` -
`openhands-workspace/openhands/workspace/docker/workspace.py` lines 65,
263-264, 331-428.

**A mismatch with `references/concepts/sandboxing.md` and
`resource-profiling.md`**: both files cite OpenHands through the paths
`openhands/core/config/sandbox_config.py` and
`openhands/runtime/impl/docker/docker_runtime.py` (on the optional
`memory_limit` mapped to Docker's `mem_limit`), sourced from PR
`All-Hands-AI/OpenHands#6616` and commit `db37f350` - both pinned to a
historical snapshot of the old Python repo. Those paths were **not found** in
either repo read in this task (`OpenHands/OpenHands` or
`OpenHands/software-agent-sdk`, checked through `find -iname sandbox_config.py
-o -iname docker_runtime.py`, 2026-08-23) - consistent with the large
architectural pivot discussed in `## Archetype` above. The
`memory_limit`/`mem_limit` claims in those two concept files are most likely
still accurate for the commit they cite, but are no longer verifiable in the
current repo; this file neither re-asserts nor disputes them, only records that
the repo has changed structure since that commit was cited. `[code]` (the file
search result, negative) plus a cross-reference note, not a correction.

## 7. Capability routing & policy

**A declarative manifest + deterministic matching in code - not an ML
classifier, and not purely prose + model judgement.** The `skills/trigger.py`
module defines three trigger types as distinct `pydantic.BaseModel`s:

- `KeywordTrigger(keywords: list[str])` - active when a keyword appears in the
  user's message.
- `TaskTrigger(triggers: list[str])` - active for particular task types, and
  able to modify the prompt.
- `PathTrigger(paths: list[str])` - active ("rules") when the agent touches a
  file matching a gitignore-style glob (`**`).

`[code]` - `openhands-sdk/openhands/sdk/skills/trigger.py` (in full).

Trigger matching happens **in code** rather than being left to model judgement:
`skills/skill.py` has the functions `_keyword_matches(keyword, message_lower)`
and `path_matches_glob(file_path, pattern)`, called from the
`match_trigger(message)` and `match_path_trigger(file_path)` methods on a skill
object. `[code]` - `openhands-sdk/openhands/sdk/skills/skill.py` lines 87, 164,
732-758. This is an explicit contrast with the `SkillsMiddleware` pattern in
`deepagents` and `claude-code.md` (see that file), which leaves skill selection
100% to model judgement over descriptions - OpenHands puts part of the routing
decision into deterministic code (keyword/path matching), with only the
**content** of a matching skill injected into the prompt/context for the model
to use. This is the pattern `references/concepts/policy-as-data.md` argues is
more verifiable than pure "prose as rules" - see that file for the full
argument.

Delegation to a subagent (axis 4) remains **model judgement**: the caller (the
main agent) picks which subagent to call from the `description` in its
`AgentDefinition`, with no separate classifier visible in the source read.
`[inferred]` - from the absence of any classifier module in `subagent/`.

## Sources

The repos were shallow-cloned (`git clone --depth 1`) on 2026-08-23 into a
local environment and read directly as files rather than through summaries:

- `OpenHands/OpenHands` (`github.com/OpenHands/OpenHands`, redirected from
  `All-Hands-AI/OpenHands`) - the `README.md` only, to confirm the identity
  pivot to Agent Canvas. `[code]`
- `OpenHands/software-agent-sdk` (`github.com/OpenHands/software-agent-sdk`)
  - the `[code]` files read:
  - `openhands-sdk/openhands/sdk/agent/base.py` (the `step` docstring, the
    `verify` method)
  - `openhands-sdk/openhands/sdk/agent/agent.py` lines 637-720 (`Agent.step`)
  - `openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py`
    lines 180-270, 700-780, 1900-2050 (`run()`, `max_iteration_per_run`,
    `execution_status`)
  - `openhands-sdk/openhands/sdk/conversation/state.py` (class names, the
    `get_unmatched_actions`/`active_branch` methods through grep)
  - `openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py`
    lines 1-90
  - `openhands-sdk/openhands/sdk/tool/builtins/finish.py` (the `FinishTool`
    class)
  - `openhands-sdk/openhands/sdk/subagent/registry.py` (in full, its first ~60
    lines + the docstring), `subagent/load.py`, `subagent/schema.py` (names &
    types through a listing)
  - `openhands-sdk/openhands/sdk/security/confirmation_policy.py` (in full)
  - `openhands-sdk/openhands/sdk/skills/trigger.py` (in full),
    `openhands-sdk/openhands/sdk/skills/skill.py` lines 87, 159-215, 550-760
  - `openhands-workspace/openhands/workspace/docker/workspace.py` lines 1-70,
    260-430
  - `openhands-sdk/openhands/sdk/workspace/{base,local}.py` (class names
    through grep)
- Org identity verification through the GitHub API
  `api.github.com/orgs/OpenHands/repos` to find `software-agent-sdk` as the
  core agent's new location - cited to explain why this file doesn't use the
  `OpenHands/OpenHands` repo.

An honesty note: the modules `security/_shell_ast.py`, `shell_parser.py`,
`shell_semantics.py`, `ensemble.py`, `llm_analyzer.py`, `toolshield_*.py`, and
`critic/`, `mcp/`, `marketplace/`, `hooks/` are listed through a directory
listing but **their contents weren't read** - nothing is claimed about how they
work in detail in this file.
