# LibreChat

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. LibreChat itself (`danny-avila/LibreChat`, Node/Express +
MongoDB + React) is a multi-user backend layer: auth, transcripts, an endpoint
registry, an Agent Builder UI. Its actual agent loop does **not** live in that
repo - `api/package.json` declares the dependency `"@librechat/agents":
"^3.6.9"`, a separate package from the `danny-avila/agents` repo (built on
`@langchain/langgraph`). This file reads **both**: `LibreChat` for axis 5 (the
transcript/agent schemas) and `danny-avila/agents` for axes 1-2-4-6 (the loop,
compaction, delegation, HITL) - because that is the code actually executing
them. `[code]` - `api/package.json` lines 50-52 (the `danny-avila/LibreChat`
repo, `git clone --depth 1`, 2026-08-23).

## Archetype

A **Workspace Agent (01)** from the "Agents" endpoint's perspective (bash/file
tools through MCP, see axis 3), overlapping with an **In-App Copilot (05)**
because LibreChat is fundamentally a multi-user multi-provider chat with agents
as one endpoint among ordinary chat endpoints (OpenAI/Anthropic/etc.). Its
interface: a web chat (React) + a REST API; human control through the
`askUserQuestion` HITL interrupt (axis 6) rather than default per-tool-call
approval. `[code]` - `packages/data-schemas/src/schema/agent.ts` (the `tools`,
`skills`, `provider`, `model` fields - the agent endpoint configuration per
Mongo document), `librechat-agents/src/hitl/`.

## 1. Loop shape

ReAct on top of `@langchain/langgraph`'s `StateGraph`. `Graph.ts` builds the
workflow: `.addEdge(START, agentNode).addConditionalEdges(agentNode,
routeMessage).addEdge(summarizeNode, agentNode).addEdge(toolNode,
agentContext.toolEnd ? END : agentNode)`. `[code]` - `danny-avila/agents`
`src/graphs/Graph.ts` lines 5062-5066.

`routeMessage(state, config)` - a pure function determining the next edge:
1. If a *pending preempt return* is registered for this `agentId` (a turn
   interrupted then continued), return to `agentNode` in the **same** Pregel
   superstep (not a graph restart) - so the model continues as one assistant
   message rather than a new one.
2. If `state.summarizationRequest != null`, route to `summarizeNode`.
3. Otherwise call `toolsCondition(state, toolNode, invokedToolIds)` - the
   standard LangGraph pattern: `tool_calls` present → `toolNode`, none →
   `END`.

`[code]` - `src/graphs/Graph.ts` lines 4853-4872. Who decides it stops: **the
model** (by no longer calling a tool), checked through the `toolsCondition`
condition - unlike `deepagents` (an explicit iteration limit) or OpenHands (an
explicit `FinishTool`); LibreChat/`@librechat/agents` doesn't feature a special
"finish" tool in the modules read. `[inferred]` - from the absence of any tool
named `finish`/`done` in the `src/tools/` directories seen (`local/`,
`search/`, `cloudflare/`, `subagent/`).

If `agentContext.toolEnd === true`, `toolNode` goes straight to `END` - a "one
tool call then stop" mode (used for single-tool agents, not the default
multi-turn ReAct). `[code]` - `src/graphs/Graph.ts` line 5066.

## 2. Context

`summarizeNode` - a separate graph node, triggered through the
`summarizationRequest` state field (not a middleware inserting itself
automatically at every step like `deepagents`' `SummarizationMiddleware`; here
compaction is an **explicit graph edge**: `agentNode → routeMessage →
summarizeNode → agentNode`). `[code]` - `src/graphs/Graph.ts` lines 4868-4870,
5065; `src/summarization/node.ts` (1712 lines, not read in full detail - the
module name and its call sites confirmed).

No filesystem-as-memory pattern (evicting large tool results to a re-readable
path) was found in the `src/summarization/` or `src/tools/` directories read -
compaction here is purely summarising old messages within the graph state,
without moving anything to external storage. `[inferred]`.

## 3. Tool surface

The `src/tools/` directory holds relatively few, broad built-in tool
categories: `local/` (local execution), `search/`, `cloudflare/` (third-party
provider tools), `subagent/` (the delegation tool, see axis 4) - not a large
catalogue of narrow single-purpose tools. `[code]` - the listing of
`danny-avila/agents/src/tools/*`. On LibreChat's own side, an agent Mongo
document has a `tools: [String]` field (the list of selected tool names) and
`tool_kwargs` - each agent's tool surface is **configured per agent** through
the Agent Builder UI rather than being one fixed global tool set. `[code]` -
`packages/data-schemas/src/schema/agent.ts` lines 43-52.

## 4. Delegation

There are two distinct delegation routes; it isn't flat:

- **Subagent task delegation** - `src/tools/subagent/` contains
  `SubagentExecutor.ts` (4086 lines), `SubagentExecutionRegistry.ts`,
  `SubagentReplay.ts`, `InMemorySubagentTaskStore.ts`, `runtimeLimits.ts`.
  `SubagentExecutionRegistry` tracks subagent executions through a
  `SubagentExecutionAddress` (`baseChildThreadId`, `branchChildThreadId`,
  `currentChildRunId`) and a `SubagentExecutionIdentity` - each subagent call
  has **its own LangGraph checkpoint thread**
  (`SUBAGENT_THREAD_ID_PREFIX = 'subagent:'`), not merely a synchronous
  function call. `[code]` -
  `src/tools/subagent/SubagentExecutionRegistry.ts` lines 1-40.
- **Multi-agent handoff** - `MultiAgentGraph` (`extends StandardGraph`)
  classifies edges into `handoffEdges` vs direct edges (`handoffSourceIds`).
  An agent with **only** handoff edges can route dynamically to any
  destination; an agent with **both** (handoff + direct) uses LangGraph's
  `Command` for exclusive routing - if a handoff occurs only the handoff
  destination runs; if not, the direct edges run (potentially in parallel).
  Choosing the handoff destination is a **named handoff tool call** by the
  model (`handoff_instructions` injected into the prompt) - not a separate
  classifier. `[code]` - `src/graphs/MultiAgentGraph.ts` lines 38, 95,
  292-304, 397-428.

**The result returning to the caller**: a subagent has its own
thread/checkpoint that can be *replayed* (`SubagentReplay.ts`,
`SUBAGENT_RESUME_ATTEMPT_CONFIG_KEY`) - the structure supports granular
per-subagent resume, but the exact contract of "what comes back into the
caller's `ToolMessage`" wasn't read down to the implementation detail of a
`SubagentExecutor.executeTask` equivalent. `[inferred]` - the registry and
replay structures are confirmed `[code]`; the result mapping's contents
weren't verified further in this task.

## 5. State & resume

LibreChat's transcript is a **tree**, not a list: the Mongo `message.ts` schema
has an explicit `parentMessageId` field - branching through message edits
produces a new child node from the same parent, exactly the pattern
`references/concepts/persistence-schema.md` argues is mandatory for the
transcript layer. `[code]` -
`packages/data-schemas/src/schema/message.ts` line 41 (the `parentMessageId`
field), `packages/data-schemas/src/schema/convo.ts`.

The Mongo `agent` document (`agent.ts`) stores a per-agent `recursion_limit` -
an official bound similar to OpenHands' `max_iteration_per_run` or
`deepagents`' `recursion_limit`, but here a **data field**, configured per
agent through the UI rather than one global default. `[code]` -
`packages/data-schemas/src/schema/agent.ts` (the `recursion_limit` field).

Granular subagent resume through
`SubagentReplay`/`SubagentExecutionRegistry` (axis 4) - a LangGraph checkpoint
per child thread, separate from the main thread's checkpoint. `[code]` - see
axis 4.

## 6. Safety gate

HITL based on **typed structured interrupts** rather than general per-tool
approval: the `src/hitl/` module implements `askUserQuestion` (one question)
and `askUserQuestions`/`askUserQuestionsInterrupt` (a batch, at most **4**
questions per interaction - the constant `MAX_ASK_USER_QUESTIONS = 4`). The
payload is validated through runtime type guards
(`isAskUserQuestionOption`/`isAskUserQuestionOptions`) before the interrupt is
sent to the client - not trusted raw from model output. Answer keys are
validated through the regex `ASK_USER_QUESTION_ID_PATTERN =
/^[A-Za-z][A-Za-z0-9_-]{0,63}$/`. `[code]` -
`src/hitl/askUserQuestionsInterrupt.ts` (in full, lines 1-50 read + the
constants).

This is a gate for **clarification**, different from the
**approval-before-tool-execution** gate that is the default pattern in
`deepagents` (`interrupt_on`) and OpenHands (`ConfirmationPolicy`) - no
equivalent per-tool approval module was found in the `src/hitl/` read; tool
approval is likely handled at the LibreChat (backend) level through an MCP
tool-approval UI rather than in this `@librechat/agents` package.
`[inferred]` - from the scope of the `hitl/` module, which holds only three
`askUserQuestion*` files.

Sandboxing: local tool execution (`src/tools/local/`) wasn't verified further
for process/OS isolation in this task - the directory name is confirmed, its
contents unread. `[code]` (the listing) / no isolation is claimed without
further verification.

## 7. Capability routing & policy

**A declarative manifest for agent configuration + model judgement for runtime
routing/handoff - not a separate classifier.**

- **The configuration level (who this agent is, which tools it has)**: the
  Mongo `agent` document - `name`, `description`, `instructions`, `provider`,
  `model`, `tools: [String]`, `skills: [String]`, `skills_enabled: Boolean`,
  `recursion_limit` - created through the Agent Builder UI and stored as data
  rather than decided by a model at runtime. This is a manifest pattern in
  line with `references/concepts/policy-as-data.md`'s argument: per-agent
  tool/skill configuration is a verifiable rule, placed as data rather than
  prose. `[code]` - `packages/data-schemas/src/schema/agent.ts`.
- **The runtime level (which agent handles the next turn, in a multi-agent
  topology)**: pure model judgement through a handoff tool call -
  `handoff_instructions` injected into the prompt, the model calling a handoff
  tool named after the destination; `MultiAgentGraph` only provides the
  already-declared *edges* (`handoffEdges`), with no classifier choosing
  automatically. `[code]` - `src/graphs/MultiAgentGraph.ts` lines 38, 95,
  292-304.
- Choosing the **agent/endpoint** at the conversation level (a Workspace agent
  vs an ordinary chat endpoint) is an explicit user choice in the UI, neither a
  classifier nor model judgement - outside `danny-avila/agents`' scope.
  `[inferred]` - from the structure of the `agent`/`convo` schemas storing
  `endpoint`/`agent_id` per conversation rather than a classification result.

## Sources

Two repos were shallow-cloned (`git clone --depth 1`) on 2026-08-23 and read
directly as files:

- `danny-avila/LibreChat` (`github.com/danny-avila/LibreChat`):
  - `api/package.json` lines 50-52 (the `@librechat/agents` dependency)
  - `packages/data-schemas/src/schema/agent.ts` lines 1-60 (the `tools`,
    `skills`, `recursion_limit`, `provider`, `model` schema fields)
  - `packages/data-schemas/src/schema/message.ts` line 41 (`parentMessageId`)
  - `packages/data-schemas/src/schema/convo.ts` (a listing, cited for the
    transcript-tree correlation)
  - `api/app/clients/`, `api/server/services/Agents/`,
    `api/server/controllers/agents/` (directory listings, contents not read in
    detail - used to confirm the actual agent loop isn't in this repo)
- `danny-avila/agents` (`github.com/danny-avila/agents`, npm
  `@librechat/agents@3.6.9`, its repo resolution confirmed through
  `registry.npmjs.org/@librechat/agents`):
  - `src/graphs/Graph.ts` lines 4853-4906, 5030-5066 (`routeMessage`, the
    `StateGraph` wiring)
  - `src/graphs/MultiAgentGraph.ts` lines 38-45, 95-100, 292-304, 397-428
    (handoff vs direct edges, the pattern docstrings)
  - `src/hitl/askUserQuestionsInterrupt.ts` lines 1-50 (in full for the part
    cited)
  - `src/tools/subagent/SubagentExecutionRegistry.ts` lines 1-40
  - `src/summarization/node.ts`, `src/tools/subagent/SubagentExecutor.ts`,
    `SubagentReplay.ts`, `InMemorySubagentTaskStore.ts`, `runtimeLimits.ts` (a
    listing + `wc -l`, contents not read in full detail)

An honesty note: `SubagentExecutor.ts` (4086 lines) and `Graph.ts` (5500 lines)
are large files **not** read in full - the claims in this file are limited to
the lines actually cited above. Any tool-level approval mechanism beyond
`askUserQuestion*` wasn't found in the `@librechat/agents` package; it likely
lives in LibreChat backend code not read in detail in this task.
