# Serving topology - across archetypes

Written **once**, applying to all seven archetypes: deployment topology is
determined by **which tools the agent has installed**, not by its archetype's
identity. Two projects both called "Workflow Agent" can need entirely
different topologies when one has an `execute` tool and the other only narrow
third-party API tools - and two different archetypes (Workspace Agent,
Generative Builder) can need the **same** topology when both have `execute`.
Grouping topology per archetype in `deltas/*.md` would duplicate the same
decision seven times and still be wrong as soon as a project mixes tools
across categories - hence this file standing alone rather than a section in
each delta.

The deployment baseline (`_base.md`) and the component→bound→HPA signal table
are already pinned down in full in
[`../concepts/serving-topology.md`](../concepts/serving-topology.md) and
[`../concepts/scaling.md`](../concepts/scaling.md) - **not repeated here**.
This file answers one question neither of them does: for a *concrete project*
with a given tool surface, which component from that table genuinely needs
splitting from the orchestrator first, and what exactly changes when that
split happens.

## The tool surface determines which component to split

`serving-topology.md` lists five components (Gateway/SSE, Orchestrator, Tool
executor, Retrieval/embedding, State store). Every project starts from `_base`
- a modular monolith with all five "components" colocated in one deployable.
The right-hand column of the table below is which component **realistically
becomes the first split candidate** as load grows, determined purely from
which tools each archetype installs (cited from each archetype file's
`## Building this with deepagents`/`## Position on the 6 axes`) - not from the
archetype's name:

| Archetype | Tool surface (in brief) | First split candidate |
|---|---|---|
| 01 Workspace Agent | `execute` (a broad bash), through `LocalShellBackend`/a sandbox backend - see `deltas/01-workspace-agent.md` | **The tool executor** - `execute` is the CPU-bound phase (`resource-profiling.md`); without extra isolation its blast radius is the host machine (`sandboxing.md`) |
| 02 Generative Builder | `execute` in its own sandbox (`DaytonaSandbox`/equivalent) | **The tool executor** - the same reason as 01, but the backend is already a microVM from its `_base` delta (sandbox cost dominates earlier) |
| 03 General Task Agent | Mixed: `execute` **and/or** retrieval tools, depending on the subagents delegated to | **The tool executor AND/OR retrieval** - determined by the actual tools each subagent installs, not a fixed rule for this archetype |
| 04 Research/Analyst | `web_search`/retrieval, `think_tool` - no `execute` at all | **Retrieval/embedding** only - it never needs a separate tool executor because it has no CPU-bound tools |
| 05 In-App Copilot | Narrow tools into the host product's API, no `execute`, no retrieval of its own | **None** - the orchestrator alone suffices; there is no CPU/GPU-bound tool worth splitting |
| 06 Workflow Agent | Third-party API tools, sometimes `execute` depending on the concrete workflow | The same as row 03 - determined by the actual tools; "workflow" is not a topology signal |
| 07 Computer-Use Agent | click/type/screenshot through a browser automation backend (Playwright/CDP), ideally in a sandbox | **The tool executor** - browser automation is CPU/memory-bound just like `execute`, for the same isolation reasons (`sandboxing.md`) |

The direct consequence: **05 In-App Copilot never needs a separate tool
executor or retrieval** at any scale - not because that archetype is "small",
but because its tool surface structurally never has a CPU/GPU-bound candidate
to split. Conversely, two "06 Workflow Agent" projects can end up with
entirely different topologies when one installs `execute` and the other
doesn't - the 06 row deliberately gives no single answer.

## Migrating from a modular monolith to microservices

`_base.md` already writes three seams (the `Orchestrator` Protocol, the tool
executor through `SandboxBackendProtocol`, retrieval through `StoreBackend`)
so this migration is **a binding + manifest change** rather than a rewrite
(`serving-topology.md` §A modular monolith with the seams cut). Concretely:

### What changes: the binding

Today `app/api/deps.py`'s `build_orchestrator(model, checkpointer)` returns a
`DeepAgentsOrchestrator(...)` (in-process, `_base.md` §Binding). Once the tool
executor (or the orchestrator itself) is split into its own service, the only
thing that changes is **that function's body** - a new implementation
**satisfying the same Protocol**:

```python
"""RemoteOrchestratorClient -- the replacement binding for
DeepAgentsOrchestrator WHEN the tool executor/orchestrator is split into its
own service. It implements the SAME Orchestrator Protocol
(orchestrator/interface.py) -- build_orchestrator()'s return value
(app/api/deps.py) is switched to this. routes/turns.py doesn't change by a
single line; main.py's lifespan gains two lines to open/close the
httpx.AsyncClient this class needs (see the paragraph after this block).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.orchestrator.interface import Scope, TurnEvent


class RemoteOrchestratorClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base_url = base_url
        self._client = client

    async def run_turn(
        self, scope: Scope, turn_id: str, thread_id: str, user_input: str
    ) -> AsyncIterator[TurnEvent]:
        # Scope is passed explicitly in the payload -- NOT ambient state --
        # condition 4 of the modular monolith (serving-topology.md): once it
        # becomes a real network call, authorisation must be explicit too.
        payload = {
            "user_id": scope.user_id,
            "turn_id": turn_id,
            "thread_id": thread_id,
            "message": user_input,
        }
        async with self._client.stream(
            "POST", f"{self._base_url}/internal/turns", json=payload
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line.removeprefix("data: "))
                yield TurnEvent(**data)
```

`app/api/routes/turns.py` **doesn't change by a single line** - it receives
`orchestrator: Orchestrator = Depends(get_orchestrator)` (`_base.md`
§Binding) and calls `orchestrator.run_turn(...)` through the Protocol, never
knowing (or needing to know) whether its implementation is local or a network
call. This is exactly condition 1 of the modular monolith
(`serving-topology.md`): cross-component calls go through an explicit
interface rather than direct calls into internals.

**The one-file claim applies to the *implementation decision*, not to the
whole migration.** `RemoteOrchestratorClient` needs a `base_url` (new config,
`ORCHESTRATOR_SERVICE_URL` through `os.environ`, the same pattern as
`APP_DATABASE_URL`) and a `client: httpx.AsyncClient` - and that last one
must not be constructed inside `build_orchestrator()`: it needs an explicit
open/close lifecycle like `_base.md`'s checkpointer/DB pool
(`init_pool`/`close_pool`, `async with build_checkpointer(...)`), or it
becomes a connection never closed cleanly at shutdown - exactly the
contradiction `_base.md` avoids for every other resource. So migrating to
remote touches **two files**: `deps.py` (`build_orchestrator()` widening to
accept `http_client`/`base_url` and returning
`RemoteOrchestratorClient(...)`) and `main.py`'s lifespan (opening
`httpx.AsyncClient()` before calling `build_orchestrator`, closing it after
the drain):

```python
client = httpx.AsyncClient()
app.state.orchestrator = build_orchestrator(
    model, checkpointer, http_client=client, base_url=os.environ["ORCHESTRATOR_SERVICE_URL"]
)
...
await app.state.drain.wait_empty(timeout=DRAIN_TIMEOUT_S)
await client.aclose()  # after the drain, before the process exits -- the same order as close_pool()
```

What stays a single point is **which implementation is chosen** - that is the
original claim of modular monolith condition 1, and it holds; a new resource
arriving with a new implementation (here: a network connection) always needs
its lifecycle lines in `main.py`, like every other resource in this scaffold -
not an exception making the one-file claim a cover for a connection leak.

### What changes: the manifest

`k8s/deployment.yaml` (`_base.md`), previously one Deployment, splits into
two, each with its own scaling signal from `scaling.md`:

| | Before (`_base.md`) | After (split) |
|---|---|---|
| Deployment | One (`harness-orchestrator`), fixed replicas | Two: `harness-orchestrator` (in-flight turns) + `harness-tool-executor` (queue depth/CPU, `scaling.md` §Concrete configuration per component) |
| Service | One | Two - `harness-tool-executor` becoming the target of the network call from `RemoteOrchestratorClient`/the new backend above |
| Scaling | No HPA/KEDA in `_base.md` (deliberately, see `_base.md` §The basic K8s manifest) | A separate KEDA `ScaledObject` per Deployment, each with a `prometheus` trigger over its own gauge/queue depth - the concrete configuration is in `scaling.md`, not repeated here |
| Node pool | Homogeneous | If the split component is GPU-bound (retrieval), add a taint+toleration+nodeAffinity (`scaling.md` §GPU node pool) |

### What does NOT change: the logic

- The DDL schema (`persistence-schema.md`) and RLS - identical;
  `db/session.py` doesn't change.
- The `SandboxBackendProtocol`/`StoreBackend` contract used by
  `FilesystemMiddleware` inside `deepagents` - identical; its backend
  implementation (local vs an external microVM) has always been a swappable
  binding since `_base`, and this migration doesn't change its contract.
- The event streaming schema (`streaming-protocol.md`) and the reattach
  contract - the `TurnEvent` yielded by `Orchestrator.run_turn(...)` has the
  same shape whether generated by a local process or by a remote service
  forwarding upstream SSE (see `RemoteOrchestratorClient` above - it reparses
  events from the other service into the same `TurnEvent`, not a new schema).
- Guardrails and safety gates - the enforcement points (`guardrails.md`) still
  live in `middleware=[...]`/`interrupt_on=` when `create_deep_agent(...)` is
  called; moving processes doesn't move *where* a guardrail is evaluated.

## Sources

- `[code]` [`../concepts/serving-topology.md`](../concepts/serving-topology.md)
  - the component→bound→HPA signal table, the four modular monolith
  conditions, and the in-flight-turns vs RPS argument; not repeated here.
- `[code]` [`../concepts/scaling.md`](../concepts/scaling.md) - the concrete
  KEDA/taint configuration referenced in the manifest migration table, not
  repeated.
- `[code]` [`../concepts/resource-profiling.md`](../concepts/resource-profiling.md)
  - the basis for "the tool executor = the first split candidate as soon as
  `execute` exists", the five phases/four bounds argument.
- `[code]` [`../concepts/sandboxing.md`](../concepts/sandboxing.md) - the
  basis for why `execute`/browser automation needs extra isolation once split
  out, not merely for performance reasons.
- `[code]` `../archetypes/01..07-*.md` §Building this with deepagents/§Position
  on the 6 axes - the source for each row's tool surface in §The tool surface
  determines which component above, cited without re-reading.
- `[code]` `_base.md` - the `Orchestrator` Protocol and the three seams
  underpinning §Migrating in this file.
