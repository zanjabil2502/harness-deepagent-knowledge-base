# 6. Workflow Agent

## Definition

An agent triggered by events (webhook, cron, queue message) that runs
**with no human actively watching** - unlike the five archetypes before
it, which always have an operator at the end of the session. Because there
is no human in the loop, the guarantees that normally come from human
review (correcting mistakes) must be replaced entirely by system
mechanisms: retry, idempotency, observability, and a kill switch.

Boundaries against neighbours: differs from **General Task Agent** (03)
because there is no explicit LLM-based planning per run - the shape is
more often a deterministic DAG/graph with LLM nodes at a few points;
differs from **In-App Copilot** (05) because no human is actively using an
application while the run happens.

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | The external systems it integrates with (third-party APIs, databases) |
| Artifact | Actions in other systems (send a message, update a record, call a webhook) |
| Horizon | Repeating/background, event-triggered |
| Human control | No human in the loop during a run; review happens in logs/dashboards afterwards |
| Domain surface | General (a platform) or vertical (a specific workflow) |
| Interface | None - trigger-based, with observability through a separate dashboard |

## Harness consequences

1. **Retry with backoff on every step**, not just at run level - with
   nobody watching, a transient failure (rate limit, network timeout) that
   isn't retried automatically means the run fails permanently and nobody
   knows until someone checks.
2. **An idempotency key per run/step** - trigger events can be delivered
   twice (webhook retries, queue restarts), and without idempotency any
   action with side effects (send an email, create a record) is duplicated.
3. **Observability as a substitute for human eyes** - since no operator
   watches the process live, every step must leave a trail (structured
   logs, traces) rich enough to reconstruct what happened after the fact.
4. **A kill switch at workflow level, not just per run** - if a workflow
   turns out to be broken (e.g. a loop accidentally triggering itself),
   there must be a way to disable the entire trigger without waiting for
   each in-flight run to finish one by one.

## Example systems

- **n8n** `[code]` - the AI Agent node (`ToolsAgent` V3) enforces an
  iteration limit through `checkMaxIterations()`, called at the start of
  each agent execution: once `iterationCount` in the response metadata
  reaches `maxIterations`, the function raises `NodeOperationError` and
  stops the run - a loop bound genuinely enforced in code, not merely a UI
  option. Source:
  `packages/@n8n/nodes-langchain/nodes/agents/Agent/agents/ToolsAgent/V3/helpers/checkMaxIterations.ts`
  (github.com/n8n-io/n8n).
- **Zapier (AI agents/Zaps)** `[inferred]` - from product behaviour: a
  trigger event fires a chain of cross-application actions with no active
  operator mid-execution.
- **Cron agent (a common pattern)** `[inferred]` - from the general
  behaviour of scheduler+LLM setups: the job runs periodically without a
  human trigger, and results are checked through logs or a notification
  after the run finishes.

## Common pitfalls

1. **Retry without idempotency** - a step retried after a partial failure
   (e.g. the email was sent but recording the confirmation failed)
   re-executes a side effect that should have happened once.
2. **Errors swallowed silently** - the workflow fails midway with no
   notification, and because nobody is watching in real time the failure
   only surfaces once downstream systems have been broken for days.
3. **No granular kill switch** - one misconfigured workflow keeps running
   (e.g. firing thousands of paid API calls) because disabling it requires
   a code change and redeploy rather than a single toggle.
4. **An LLM inside a deterministic DAG treated as if it were
   deterministic** - an LLM step can produce different output per run for
   the same input, yet the next step in the workflow is written as though
   its output always has exactly the same shape.

## Building this with deepagents

- **Loop shape**: `[ours]` deepagents is a conversation/mission harness
  (triggered by a human message or a written task), not an event-trigger
  engine. For this archetype we place `create_deep_agent(...)` as one node
  inside a larger LangGraph graph (or behind a queue worker) that external
  events trigger - deepagents handles "what the LLM does when called", not
  "when it is called". Non-interactive use **has official precedent**: in
  `examples/async-subagent-server/server.py` the agent is built at line
  155 (`_agent = create_deep_agent(`) then invoked at line **174**
  (`result = await _agent.ainvoke(...)`) from inside `_execute_run`
  (line 169), dispatched as an `asyncio.ensure_future` task at line **287**
  under the HTTP endpoint `POST /threads/{thread_id}/runs` (line **234**) -
  with no human in the loop; and `examples/ralph_mode/` runs entirely
  unsupervised. What remains ours here is not "it may be used
  non-interactively", but the division of responsibility: we place
  triggers, queues, and scheduling outside `deepagents` because the
  library does not provide them. `[code]` - repo `langchain-ai/deepagents`
  commit `23b83ad`; see `../deepagents/conformance.md` D-06.
- **Idempotency**: `create_deep_agent`'s `checkpointer` parameter exists
  precisely for this - the application injects its own LangGraph
  checkpointer; deepagents does not create one. `[code]` - source:
  `ARCHITECTURE.md`. `[ours]` `ARCHITECTURE.md` only states that the
  checkpointer is injected by the application - it says nothing about how
  `thread_id` is formed. Our recommendation: derive `thread_id` from the
  event's idempotency key (rather than random/session-generated, the
  common pattern in deepagents' interactive examples), so a retried event
  lands on the same checkpoint instead of creating a new run. This is our
  pattern, not something the library guarantees or documents.
- **Safety gate**: `interrupt_on` for high-risk actions (e.g.
  `send_email: True`) is still installed even with no real-time human - an
  interrupt in LangGraph means the run stops and waits for async approval
  through a separate channel (dashboard/Slack) rather than failing
  outright. `[code]` - source: `test_hitl.py`.
- **Kill switch**: `[ours]` deepagents has no built-in "stop all runs" API
  - that is the responsibility of the orchestrator/queue layer above it
  (e.g. a database flag checked before each LangGraph node executes). We
  say this explicitly so the scaffold does not wrongly assume
  `create_deep_agent` provides a built-in kill switch.

## Sources

- n8n `packages/@n8n/nodes-langchain/nodes/agents/Agent/agents/ToolsAgent/V3/helpers/checkMaxIterations.ts`
  - `[code]` - https://github.com/n8n-io/n8n
- deepagents `ARCHITECTURE.md`, `test_hitl.py` - `[code]` - Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Zapier, the common cron agent pattern - `[inferred]` - product behaviour
  or a general pattern, closed-source or not specific to one
  implementation.
