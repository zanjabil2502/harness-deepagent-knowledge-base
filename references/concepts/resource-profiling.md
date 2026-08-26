# Resource profiling

## Problem

The default instinct for deploying an agent harness is the ordinary web app
instinct: one container, one resource request (`cpu: 1, memory: 2Gi`), one
HPA watching average CPU. That instinct quietly assumes one thing that is
wrong for agents: that a unit of work (one turn) is homogeneous —
CPU-dominant, or IO-dominant, but not both at once.

An agent turn is neither. Within that same turn, several phases run in
sequence with **opposing resource profiles**: the phase consuming the most
seconds (waiting on the LLM) barely uses CPU, while the shortest phase
(code execution) can saturate a whole core. If all five phases are
colocated in one pod and that pod is given a single resource
request/limit, that request has to be pinned to the **worst dimension**
(the code-execution CPU peak) — even though that dimension is only active
for a small fraction of the turn's life. The rest of the time, that
allocation sits idle.

## Pattern

### Five phases, four different bounds

| Phase | Bound | What happens | CPU | Memory | Network IO | Disk IO | GPU |
|---|---|---|---|---|---|---|---|
| LLM call | **IO** | Send the prompt, wait for / stream tokens from the provider over a socket | Near zero — the thread/coroutine sits waiting for bits from the network | Low (streaming buffers) | High — the longest stretch in the turn | - | - |
| Context assembly | **Memory** | Rebuild the transcript + tool results + memory into one prompt string from scratch on every call (see `session-state.md`) | A short burst (formatting/serialising) | Proportional to the context window in use — a large window × many concurrent turns = a lot of RAM | Low | - | - |
| Code exec (`execute`) | **CPU** + needs isolation | Compile/run the code the LLM wrote | Can hit 100% of one or more cores for the execution's duration | Medium-to-high depending on the workload | - | Can be high (build artifacts) | - |
| Embedding (retrieval) | **GPU** (or CPU for a small model) | Encode queries/documents into vectors, usually batched | Low on the host CPU | Medium (batch buffers) | - | - | High |
| Checkpoint write | **Disk IO** | `checkpointer.aput` to Postgres on every graph step | Near zero | Low | Medium | A DB write — commit-bound, not compute-bound | - |

Four different bounds (network IO, memory, CPU, GPU) plus one separate
disk-IO bound — five phases that cannot be reduced to a single "resource
usage" number per turn.

### Why colocation forces scaling on the worst dimension — computed, not assumed

Take an illustrative turn lasting ~20 seconds in total: the LLM call ~15s
(75%), code exec ~3s (15%), context assembly + embedding + checkpoint the
rest (~10%). For those 15 seconds of LLM call, the pod's CPU is
practically idle — the thread is waiting on a socket, not computing. For
those 3 seconds of code exec, CPU can be fully saturated on one or more
cores.

If one pod runs all five phases and the pod's resource request is pinned to
cover the code-exec peak (say `cpu: 2`), then for 85% of that turn's life
the 2 allocated (and paid-for) CPUs are >80% idle. Multiply by
concurrency: 100 parallel turns in the same pod means 200 vCPU allocated
to cover a peak that is only active simultaneously in a small fraction of
those 100 turns at any moment — the rest is idle capacity that still has
to be provisioned (and paid for), because the autoscaler cannot tell "this
pod is CPU-bound" from "this pod is in IO-wait" when the only signal is one
pod's average CPU utilisation.

A second, subtler consequence: if this pod's HPA scales on **CPU
utilization** (the most common default HPA metric), the code-exec phase is
what triggers scale-out — not because the orchestrator lacks capacity to
handle more turns (most of its time is IO-wait; one pod can hold hundreds
of concurrent turns asynchronously with no extra CPU), but because the tool
executor riding along in the same pod is busy. Scale-out adds **the whole
pod** — including LLM-wait capacity nobody needs — when the only thing
actually short is code-execution capacity. This is the core argument for
why `serving-topology.md` separates the HPA signal per component instead of
using one CPU signal for everything.

### Measuring phase dominance in a real deployment

The example above is illustrative — the real numbers differ per workload (a
large vs small system prompt, heavy vs light tool calls), so what's needed
isn't taking the table above at face value but a way to measure it yourself.
The cheapest instrumentation: record a **span** (a start and end timestamp) at
each phase boundary that already exists in the code — the same shape as the
`tool_calls.started_at`/`completed_at` already in `persistence-schema.md`
(Task 4), extended to the phases that don't yet have a table row of their own:
`context_assembly_start`/`_end` (before vs after the prompt is assembled,
before it goes to the model), `llm_call_start`/`_end` (request sent vs
response/stream finished), `checkpoint_write_start`/`_end` (before vs after
`checkpointer.aput`). Emit each span as a duration metric (e.g. a per-phase
Prometheus histogram with a `phase=` label), then read the result the same way
as the breakdown above: the summed duration of each `phase` over the total
turn duration gives the **share of time** per phase; set against the pod CPU-
seconds sampled over the same span window (standard container metrics, e.g.
`container_cpu_usage_seconds_total` from cAdvisor/kube-state-metrics) it gives
the share of **CPU work** per phase — two different numbers, both needed,
because the phase taking the most time (the LLM call) is not necessarily the
phase taking the most CPU (code exec). A phase with a large share of time but
little CPU is an IO/memory-bound candidate (scale it through concurrency,
`serving-topology.md`); a phase with a large share of CPU despite a short
duration is a candidate for splitting into its own component (the Tool
executor) so it doesn't drag the whole pod into scale-out.

## Trade-offs

- **Colocation (one pod, every phase) vs splitting per bound** `[ours]` —
  vanilla is one of two extremes: full colocation (one deployable, no
  network hop between phases, lower latency for light turns, but forcing
  provisioning to the worst dimension and mixing fault domains — a bug in
  code exec can exhaust the memory of the same pod running context
  assembly), or a full split from day one (each phase scaling on its own
  signal, but adding operational complexity — more services, network hops
  between calls). This KB takes the middle road: **a modular monolith with
  the seams cut** — one deployable today, with interfaces already correct
  so a later split is a change of binding rather than a rewrite (details in
  `serving-topology.md`).
- **A tight vs loose per-pod resource request** — a tight request (pinned
  to the average rather than the peak) saves money but gets the pod
  throttled or OOM-killed when code exec and context assembly happen to
  pile up together; a loose request (pinned to the peak) is safe but
  expensive, with large idle capacity throughout the IO-bound phases. This
  trade-off disappears once code exec is split into a component (the Tool
  executor) that scales on its own — the orchestrator pod no longer has to
  cover a CPU peak that isn't its own.
- **Batching embeddings vs synchronous per-turn** — batching several
  embedding requests before sending them to the GPU improves GPU
  utilisation (higher throughput per watt/second) but adds the latency of
  waiting for the batch to fill; synchronous per-turn (encode immediately)
  is low latency but leaves the GPU frequently idle waiting for the next
  request. This choice is driven by retrieval traffic volume, not a fixed
  architectural decision — discussed further in `scaling.md`.

## In deepagents

`deepagents` doesn't run a separate process per phase — all five phases
above happen inside one Python process running the LangGraph graph, in the
same order as the table:

| Phase | Concretely in deepagents | Source |
|---|---|---|
| LLM call | The `model.invoke`/`.stream` that `langchain.agents.create_agent` issues at each graph node — pure IO; deepagents adds no CPU work on this path | `[code]` `../systems/deepagents.md` §1 (Loop shape) |
| Context assembly | `SummarizationMiddleware` (token-threshold compaction) rebuilds `DeepAgentState.messages` into a prompt on each call — memory/string-formatting work, not CPU-heavy | `[code]` `../systems/deepagents.md` §2 |
| Code exec | `FilesystemMiddleware`'s `execute` tool, running through a backend implementing `SandboxBackendProtocol` — the built-in `LocalShellBackend` runs `subprocess.run(shell=True)` in the same process/host, so **the CPU and the risk belong entirely to that process**, unisolated unless the backend is swapped (see `sandboxing.md`) | `[code]` `../systems/deepagents.md` §6 (Safety gate, quoting `THREAT_MODEL.md`) |
| Embedding | Absent from `deepagents` core — `deepagents` does no embedding/vector search of its own; if retrieval is used it is an application tool (e.g. called through `StoreBackend`/a custom backend) running outside `deepagents`' control | `[inferred]` — concluded from the absence of any embedding primitive in `## Surface API`/`## Built-in middleware` of `../systems/deepagents.md` |
| Checkpoint write | The application-injected `checkpointer`, called on every graph step — `deepagents` passes it through to `create_agent` unchanged, building nothing of its own | `[code]` `../systems/deepagents.md` §5 (`deepagents/graph.py` lines 546-553, 922-931) |

The direct implication: because all five phases share the same Python
process in the default `deepagents` stack, splitting them into components
with their own scaling signals (§8.3) is **not** something `deepagents`
provides automatically — it is an application deployment decision (see
`serving-topology.md`), and the only ready-made seams `deepagents` already
gives for it are `SandboxBackendProtocol` (for code exec) and
`StoreBackend`/`CompositeBackend` (for durable state/retrieval) — both
interfaces, not built-in separate processes.

## Sources

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §1, §2,
  §5, §6 — a tier-1 reference already verified against the
  `deepagents==0.7.8` source in Task 3, cited here without re-reading the
  source.
- `[code]` OpenHands `openhands/core/config/sandbox_config.py` and
  `openhands/runtime/impl/docker/docker_runtime.py`, read through the diff
  of PR `All-Hands-AI/OpenHands#6616` ("Add memory limit option for Docker
  runtime"): the field `memory_limit: str | None = Field(default=None, ...
  None means no limit.")` maps to `mem_limit=self.config.sandbox.memory_limit`
  when the container starts — used as evidence that without an explicit
  limit, the CPU/memory-bound code-exec phase can consume the host's entire
  resources rather than just "its fair share", reinforcing why this phase
  needs provisioning separate from the IO-bound phases. Full isolation
  detail in `sandboxing.md`.

  > **Repo note (2026-08-23):** `All-Hands-AI/OpenHands` now redirects to
  > `OpenHands/OpenHands` ("Agent Canvas"); the original coding agent moved
  > to `OpenHands/software-agent-sdk`. The paths
  > `openhands/core/config/sandbox_config.py` and
  > `openhands/runtime/impl/docker/docker_runtime.py` above no longer exist
  > in the current repo structure — this claim still holds for the cited
  > commit `db37f350` / PR `#6616`, as a historical snapshot. See
  > [`../systems/openhands.md`](../systems/openhands.md).
- `[docs]` KEDA — the per-custom-signal scaling mechanism that makes
  splitting components practically useful, cited via WebFetch from
  `keda.sh/docs/latest/concepts/scaling-deployments/`. Full detail in
  `serving-topology.md` and `scaling.md`.
