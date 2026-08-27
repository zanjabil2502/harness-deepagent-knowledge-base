# 3. General Task Agent

## Definition

An agent that accepts a broad, open-ended mission ("research, then build a
report, then send an email"), writes an explicit plan before executing,
delegates subtasks to subagents with isolated context, and lives across
sessions/days - using the filesystem as persistent memory rather than only
the context window.

Boundaries against neighbours: differs from **Workspace Agent** (01)
because it isn't bound to one repo/bash tool - its goal is "complete the
mission", not "edit this code"; differs from **Research/Analyst** (04)
because its output artifact can be mixed (files, actions, answers) rather
than only a written, cited answer; differs from **Computer-Use Agent**
(07) because the core of its harness is explicit planning plus delegation,
not a see-click-verify loop (though the two often appear together as a
hybrid - see `README.md`).

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | Wide sandbox, sometimes touching the outside world (browsing, external tools) |
| Artifact | Mixed - answers, files, or actions, determined by the mission |
| Horizon | Lives in the background, across sessions/days |
| Human control | Review at checkpoints/at the end, rarely per-step approval |
| Domain surface | General |
| Interface | Chat plus an "activity"/process tab |

## Harness consequences

1. **Explicit planning as its own step** before execution - a broad mission
   without a written plan makes the agent oscillate or lose scope midway;
   the plan becomes a contract that can be re-checked.
2. **Delegation through subagents for context isolation** - without it the
   main context window fills with subtask detail irrelevant to the next
   decision; subagents let that detail die in their own context and send
   only a compact report back up.
3. **State: filesystem-as-memory**, not just messages in the context
   window - a cross-session horizon needs state that survives process or
   browser-tab restarts, not something that vanishes the moment context is
   trimmed.
4. **Loop shape: a large step/time budget, but a kill switch and
   no-progress detection are mandatory** - long duration means runaway
   loops or uncontrolled cost unless something detects an agent spinning
   in place.

## Example systems

- **CrewAI** `[code]` - under `Process.hierarchical`, `Crew` enforces
  `check_manager_llm()` (refusing to run without `manager_llm`/
  `manager_agent` set), then `_create_manager_agent()` sets
  `allow_delegation = True` on the manager and **forbids it from having
  tools of its own** (`crew.py` raises if the manager is given tools) -
  delegation is forced to happen through other agents rather than the
  manager doing the work itself. Source:
  `lib/crewai/src/crewai/crew.py` (github.com/crewAIInc/crewAI).
- **Manus** `[inferred]` - a hybrid with Computer-Use Agent (07); see the
  hybrid matrix in `README.md`.
- **Abacus DeepAgent** `[inferred]` - from product behaviour: accepts
  free-text missions, shows an explicit plan/todo, and runs in the
  background beyond a single chat session.

## Common pitfalls

1. **The plan is written once at the start and never revised** - once a
   mid-execution finding changes the original premise, the agent keeps
   chasing a stale plan because there is no explicit replanning step.
2. **Subagents without a clear result contract** - the report coming back
   is a long transcript instead of a structured summary, so the caller's
   context balloons anyway - losing the entire benefit of context
   isolation.
3. **No oscillation/no-progress detection** - the agent repeats the same
   sequence of tool calls without advancing, and because the horizon is
   long by design this can run for a while (and cost a lot) before a human
   notices.
4. **Filesystem-as-memory used without a schema** - scratch files pile up
   unstructured across sessions, so the next session struggles to find
   relevant state and the agent re-reads everything from the start.

## Building this with deepagents

- **Planning**: `TodoListMiddleware` - unlike the other middleware, this
  one is **not** in `create_deep_agent()`'s default stack and must be added
  explicitly through `middleware=[TodoListMiddleware()]`. `[code]` -
  source: `graph.py` (langchain-ai/deepagents).
- **Delegation**: `subagents=[{"name": ..., "description": ..., "model":
  ..., "system_prompt": ..., "tools": [...]}, ...]` passed to
  `create_deep_agent(subagents=...)`, which builds `SubAgentMiddleware`
  and the `task` tool that invokes them. `[code]` - source:
  `middleware/subagents.py`, example
  `examples/content-builder-agent/README.md`.
- **State & memory**: a `store`-type `backend` (`StoreBackend`, durable
  across threads) for files that must live across sessions, combined with
  `memory=["./AGENTS.md"]` for persistent context loaded into the system
  prompt each session. `[code]` - source: `ARCHITECTURE.md`,
  `examples/content-builder-agent/README.md`.
- **Loop budget & kill switch**: `[ours]` deepagents ships no built-in
  "no-progress detector" - what exists is LangGraph's generic
  `recursion_limit`, per-tool `interrupt_on`, and (from
  `langchain.agents.middleware`, not `deepagents` itself)
  `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware` for *counting*
  model/tool calls per thread or per run. `[code]` -
  `langchain/agents/middleware/model_call_limit.py`,
  `tool_call_limit.py`; see also
  [`../concepts/guardrails.md`](../concepts/guardrails.md) point 5. We
  still diverge by adding custom middleware (detecting the same tool call
  repeated N times in a row → force a stop) because none of the three
  detects *repetition* - `recursion_limit` and both limit middlewares only
  count, preventing a syntactically endless loop, but not detecting an
  agent that is semantically spinning in place well before its budget runs
  out.

## Sources

- CrewAI `lib/crewai/src/crewai/crew.py` - `[code]` -
  https://github.com/crewAIInc/crewAI
- deepagents `graph.py`, `middleware/subagents.py`, `ARCHITECTURE.md`,
  `examples/content-builder-agent/README.md` - `[code]` - Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Manus, Abacus DeepAgent - `[inferred]` - closed-source product behaviour.
