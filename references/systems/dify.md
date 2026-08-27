# Dify

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. `langgenius/dify`, a Python (Flask, `api/`) + TS (`web/`)
platform for building LLM applications through **visual workflows (DAGs)**
and/or **agent apps**. Chosen as the **workflow platform** exemplar per the T2
candidates in spec §10.

## Archetype

A structural hybrid unlike any other system in this grid: Dify itself is a
**platform** producing two application kinds of different archetypes - an
"Agent App" (`api/core/app/apps/agent_app/`, close to an **In-App Copilot
(05)**: a per-conversation horizon, limited tools) and a "Workflow App"
(`api/core/app/apps/workflow/`, close to a **Workflow Agent (06)**: a
node-based DAG, triggerable through
`trigger_schedule`/`trigger_webhook`/`trigger_plugin` with no human in the
loop). `[code]` - the listing of `api/core/app/apps/*` (`agent_app`,
`agent_chat`, `workflow`, `advanced_chat`, `chat`, `completion`, `pipeline`),
`api/core/workflow/nodes/{trigger_schedule,trigger_webhook,trigger_plugin}/`.

## 1. Loop shape

Two different agent runners, **both** loop-until-done with a hard iteration
limit from user configuration rather than merely a distant safety net:

- **`FunctionCallAgentRunner`** - provider-native tool calling. The loop:
  `iteration_step = 1; max_iteration_steps =
  min(app_config.agent.max_iteration, 99) + 1; while function_call_state and
  iteration_step <= max_iteration_steps: ...`. If iteration reaches the limit
  **and** `tool_calls` are still pending, the harness raises
  `AgentMaxIterationError` - it doesn't stop silently. `[code]` -
  `api/core/agent/fc_agent_runner.py` lines 46, 101, 119-148, 302-303, 403.
- **`CotAgentRunner`** (an ABC, subclassed for chat/completion) - a
  text-based ReAct pattern (Thought/Action/Observation parsed from the
  response, through `ActionDict`/`scratchpad`), used for models **without**
  native tool-calling support. Its loop and iteration limit have exactly the
  same structure as `FunctionCallAgentRunner`'s (`max_iteration_steps =
  min(...,99)+1`, `AgentMaxIterationError` on the final iteration if
  `scratchpad.action` is still set). `[code]` -
  `api/core/agent/cot_agent_runner.py` lines 33, 40, 49, 79-80, 106-191, 266.

The absolute maximum of **99 iterations** (`min(app_config.agent.max_iteration,
99)`) is locked in code - a user can set it lower through the app config, never
higher. `[code]` - both runners, the identical line
(`min(app_config.agent.max_iteration, 99) + 1`).

Who decides it stops (the normal case): the model, by producing no further tool
call/action - `function_call_state` becomes falsy. Who decides it stops (the
emergency case): the harness, through `AgentMaxIterationError` - different from
`deepagents` (a very high limit, purely a safety net) and closer to OpenHands'
philosophy (`max_iteration_per_run=500` can also produce an `ERROR` status).

## 2. Context

The compaction mechanism's details weren't verified in this task -
`api/core/memory/` exists as a directory separate from `api/core/agent/`
(cross-turn conversation memory for chat apps), but its contents weren't read.
`[code]` (the listing) / no mechanism is claimed without further verification.

## 3. Tool surface

**A different paradigm from an ordinary agent loop**: Dify's tool surface is
largely not "a list of tools for one runtime model" but a **catalogue of node
types in a visual DAG** the user assembles in the UI, each node type a distinct
execution unit: `agent`/`agent_v2` (nodes wrapping
`FunctionCallAgentRunner`/`CotAgentRunner`), `datasource`, `knowledge_index`,
`knowledge_retrieval`, `human_input` (see axis 6), and
`trigger_plugin`/`trigger_schedule`/`trigger_webhook`. `[code]` - the listing
of `api/core/workflow/nodes/*` (9 type-specific subdirectories; other node
types such as `llm`/`code`/`if-else`/`iteration` are presumably registered in a
`NodeType` module that wasn't found directly through grep in this task - see
the honesty note).

Inside one `agent` node, the tool surface is more conventional: tool providers
are catalogued through `core/tools/` - `builtin_tool` (built in, e.g.
`providers/time/`, `providers/audio/`), `plugin_tool` (the third-party plugin
ecosystem), `mcp_tool` (external MCP servers), and **`workflow_as_tool`** (see
axis 4). `[code]` - the listing of
`api/core/tools/{builtin_tool,plugin_tool,mcp_tool,workflow_as_tool}/`.

## 4. Delegation

**Not subagent spawning** - its main composition mechanism is **another
workflow as a tool**: `WorkflowTool` (`core/tools/workflow_as_tool/tool.py`, a
`Tool` subclass) wraps an already-published workflow app as a tool callable
from another agent/workflow - complete with trace context propagation across
calls (`ParentTraceContext`/`extract_parent_trace_context_from_args`,
`extract_trace_session_id_from_args`) so observability stays connected across
workflow-as-tool boundaries. `[code]` -
`api/core/tools/workflow_as_tool/tool.py` lines 1-50.

This is a different composition pattern from `deepagents`'/OpenHands' `task`
tool: not "call another agent with a prompt" but "call another DAG pipeline
with structured input (a tool parameter schema)" - the result returning as a
structured `ToolInvokeMessage` rather than a prose summary of a subagent's
transcript. `[code]` - the `ToolInvokeMessage` import in
`api/core/tools/workflow_as_tool/tool.py`.

## 5. State & resume

The DB schema's details weren't verified (this task didn't read Dify's
migrations or SQLAlchemy models). What is confirmed: `models.workflow.Workflow`
as a persistent entity referenced by `WorkflowTool` (`workflow_app_id` in its
constructor) - a workflow is a stored object with a stable identity, not
redefined on each call. `[code]` - the `models.workflow.Workflow` import and
the `workflow_app_id` parameter in `WorkflowTool.__init__`
(`api/core/tools/workflow_as_tool/tool.py`).

## 6. Safety gate

Two gate mechanisms at different levels:

- **The `human_input` node** - a generic DAG node for pause-and-wait-for-human,
  with the submodules `pause_reason.py` (a structured pause reason),
  `session_binding.py` (binding a paused session to a specific identity), and
  `boundary.py`. This is a gate at the **workflow design** level (whoever
  assembles the DAG can place this node at any point), not an automatic
  per-risky-tool gate like `deepagents`' `interrupt_on` or OpenHands'
  `ConfirmationPolicy`. `[code]` - the listing of
  `api/core/workflow/nodes/human_input/*.py` (8 files).
- **Input/output moderation** - `core/moderation/base.py`: the abstract class
  `Moderation(Extensible, ABC)`, with `ModerationInputsResult`/
  `ModerationOutputsResult` results carrying a `flagged: bool` field and an
  `action: ModerationAction` (`DIRECT_OUTPUT` - reply with a preset response
  without continuing to the model, or `OVERRIDDEN` - the content is replaced).
  Installed at two separate points: `input_moderation.py` (before the LLM/agent
  runs) and `output_moderation.py` (before the result goes to the user) -
  exactly points 1 and 4 of the six guardrail enforcement points in design spec
  §8.4. Its concrete implementations: `keywords/` (deterministic) and
  `openai_moderation/` (model-based, an external provider) - the same
  cheap-first tiering pattern as the §8.4 argument. `[code]` -
  `api/core/moderation/base.py` lines 1-30; the listing of
  `api/core/moderation/{keywords,openai_moderation,api}/`.

## 7. Capability routing & policy

**Static per-app configuration + a visual node catalogue - not a classifier,
and not runtime model judgement choosing an architecture.** The loop strategy
choice (`FunctionCallAgentRunner` vs `CotAgentRunner`) and the node types in a
DAG are decided **at app design time** (by the app's author in the UI/config,
based on whether the target model supports native tool calling), not by the
model itself choosing between modes at runtime. `[code]` - the existence of two
separate runner classes with nearly identical signatures shows the choice
happens in the app configuration layer (`app_config.agent`) rather than as
dynamic dispatch within one loop.

Inside one `agent` node, tool selection remains standard **model judgement**
(the model picks a tool from the list that node exposes) - no additional
classifier was found. The tool providers themselves
(`builtin_tool`/`plugin_tool`/`mcp_tool`/`workflow_as_tool`) are a
**declarative registry**: which tools are available to a node is determined by
that node's configuration (chosen by the user in the UI), not automatically.
`[code]` - the structure of `core/tools/tool_manager.py`,
`core/tools/__base/tool_provider.py` (filenames confirmed, contents not read in
detail).

## Sources

The `langgenius/dify` repo was shallow-cloned (`git clone --depth 1`) on
2026-08-23 and read directly as files:

- `api/core/agent/fc_agent_runner.py` - lines 46, 101, 119-148, 302-303, 403
  (the loop, `max_iteration_steps`, `AgentMaxIterationError`)
- `api/core/agent/cot_agent_runner.py` - lines 33-49, 79-80, 106-191, 266 (the
  loop, `ActionDict`, `scratchpad`)
- `api/core/moderation/base.py` - lines 1-30 (in full for the part cited:
  `ModerationAction`, `ModerationInputsResult`, `ModerationOutputsResult`, the
  `Moderation` class)
- `api/core/tools/workflow_as_tool/tool.py` - lines 1-50 (the imports, the
  `WorkflowTool` class, the `workflow_app_id` constructor)
- Directory listings (file/folder names through `find`/`ls`, contents not read
  in full): `api/core/app/apps/*` (7 app types), `api/core/workflow/nodes/*` (9
  typed subdirectories), `api/core/workflow/nodes/human_input/*.py` (8 files),
  `api/core/tools/{builtin_tool,plugin_tool,mcp_tool,workflow_as_tool}/`,
  `api/core/moderation/{keywords,openai_moderation,api}/`, `api/core/memory/`

An honesty note: searching for `class NodeType` through `grep -rln` in
`api/core/workflow/` found no complete node-type enum definition (likely
defined in a module outside `nodes/`, e.g. a shared `core/workflow/enums.py`
package that wasn't found or read) - the node type list in axis 3 is limited to
subdirectories genuinely visible through the listing, **not** Dify's complete
node list (common types like `llm`, `code`, `if-else`, `iteration`, and
`http-request`, widely known from Dify's public documentation, were **not**
re-verified in source in this task - neither their presence nor absence is
claimed). `api/core/memory/`, the workflow DB schema, and the details of
`tool_manager.py`/`tool_provider.py` were **not** read - only their existence
is cited.
