# Scaling

## Problem

`serving-topology.md` establishes **which signal** is correct per
component (in-flight turns, not RPS, for the orchestrator; queue depth for
the tool executor; batch queue/GPU utilisation for retrieval). This file
answers the next operational question: **how that signal is actually
configured in Kubernetes**, plus two extra problems characteristic of
agent workloads that never appear with ordinary CPU HPAs — execution
sandbox cold start, and nodes that have GPUs but sit in a pool mixed with
CPU-only ones.

The default instinct "every component uses the same CPU HPA" fails twice:
it fails on signal (covered in `serving-topology.md`), and it fails on
node placement — a CPU-only pod scheduled onto a GPU node wastes the most
expensive allocation in the cluster on work that doesn't need it, and a
GPU pod scheduled onto a node without a GPU cannot run at all.

## Pattern

### Concrete configuration per component

| Component | Signal (from `serving-topology.md`) | Concrete K8s mechanism |
|---|---|---|
| Gateway / SSE | Active connections | A KEDA `ScaledObject` with a `prometheus` trigger over an active-connections-per-pod gauge (usually already exposed by the ingress controller/gateway itself) |
| Orchestrator | In-flight turns | A KEDA `ScaledObject` with a `prometheus` trigger over the application's in-flight-turns gauge (see `serving-topology.md` for how to expose it) — KEDA generates the HPA object from this `[docs]` |
| Tool executor | Queue depth, CPU | If the turn queue (`queueing-and-backpressure.md`) is backed by a real queue (Redis list, RabbitMQ), KEDA has a native scaler for it; if it is only a custom queue-depth gauge, the same `prometheus` trigger. KEDA **Scaling Modifiers** allow combining two triggers (queue depth + CPU) into one scaling formula rather than a simple OR `[docs]` |
| Retrieval / embedding | Batch queue, GPU utilisation | A small dedicated pool, not per-request HPA — concurrency-based (see the Ray Serve `target_ongoing_requests` pattern in `serving-topology.md`), scaled to a minimum or to zero through KEDA scale-to-zero because GPU nodes are the most expensive line item |
| State store | Not a pod | Scale through read replicas plus connection pooling (e.g. PgBouncer), not HPA — Postgres does not "add pods" to absorb load |

### Sandbox cold start: warm pool vs on-demand

Isolated code execution (`sandboxing.md`) has a non-zero cold start —
microVMs (E2B, Daytona) need boot time before they can accept commands.
Both providers offer **pause/resume** primitives precisely to cut this
cost: E2B's `lifecycle.on_timeout: "pause"` (resuming from a memory
snapshot when `keep_memory=True`, far faster than creating a new one) and
Daytona's `auto_pause_interval` (default 60 minutes for sandbox classes
that support pausing) `[code]` — already quoted in full in `sandboxing.md`
from each SDK's source.

The scaling implication: instead of creating a sandbox from scratch on
every tool call (a full cold start on the interactive critical path), an
operator can hold a **warm pool** — a small number of already-created,
paused sandboxes, resumed the moment a tool call arrives and refilled in
the background as the pool drains. Pool size is driven by the same signal
as the Tool executor in the table above (a rising trend in tool-exec queue
depth → grow the warm pool before demand actually arrives), not by a
static number.

### GPU node pools with taints

Retrieval/embedding needs GPUs; the other components (gateway,
orchestrator, tool executor) do not. Without an explicit marker the
Kubernetes scheduler may place CPU-only pods on GPU nodes (wasting that
node's GPU allocation on work that never uses it) or, conversely, fail to
place GPU pods at all when the GPU nodes are full of other pods. The
standard mechanism is **taint + toleration**: a taint is applied to the
node, making it reject any pod without a matching toleration `[docs]`.

```bash
# Mark the GPU node so it rejects pods without a matching toleration
kubectl taint nodes gpu-node1 nvidia.com/gpu=true:NoSchedule
```

```yaml
# Embedding/retrieval pod: matching toleration plus a GPU resource request
tolerations:
  - key: "nvidia.com/gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
resources:
  limits:
    nvidia.com/gpu: 1
```

The taint keeps CPU-only pods (which lack that toleration) off GPU nodes
entirely; `nodeSelector`/`nodeAffinity` on the embedding pod ensures the
opposite direction — GPU pods only land on nodes that actually have GPUs.
The two mechanisms complement rather than replace each other: taints
protect the node from the wrong pods, affinity steers pods to the right
node `[docs]` — cited via WebFetch from
`kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/`.

## Trade-offs

- **Sandbox warm pool vs pure on-demand** — a warm pool cuts first-tool-call
  latency (resume instead of cold boot), which matters when code execution
  is on the interactive critical path (a user is waiting). The cost:
  paying for idle sandbox capacity waiting to be used, plus the
  operational complexity of keeping the pool filled. Pure on-demand pays
  nothing for idle capacity, but every first tool call takes the full cold
  start — acceptable when tool execution isn't interactive (e.g.
  background jobs) or when volume is low enough that consecutive cold
  starts are rare.
- **GPU taints vs no taints (letting the scheduler place freely)** — no
  taints is simpler (one homogeneous node pool, no tolerations to
  configure) but risky: a CPU-only pod that happens to land on a GPU node
  wastes the cluster's most expensive allocation, and that node also
  shares its non-GPU resources (CPU/memory) with pods that shouldn't be
  there, reducing capacity for the GPU workloads that genuinely need it.
  Taints trade a little stranded capacity (if the GPU pool is larger than
  demand, those nodes can only host pods that tolerate the taint — with no
  demand they sit idle and cannot be "borrowed" by other workloads) — for
  workloads that explicitly separate GPU-bound components (§8.3), taints
  remain the safer default.
- **A generic HPA (one metric, one formula) vs KEDA Scaling Modifiers
  (several triggers combined)** — a generic HPA is simple to understand
  and debug (one number, one threshold), but cannot capture a component
  genuinely bounded on two dimensions at once (the Tool executor: queue
  depth **and** CPU, either of which can be the bottleneck depending on
  workload). Scaling Modifiers capture that through a formula, at the cost
  of configuration that is harder to reason about and debug when scaling
  behaves unexpectedly.

## In deepagents

`deepagents` does not run inside Kubernetes and knows nothing about
HPA/KEDA/node pools/taints — every mechanism in this file operates in the
deployment layer **above** `deepagents`, purely the responsibility of the
application wrapping it. One directly relevant point: the tool-exec
queue-depth/latency signal that drives the sandbox warm pool above **can
be computed from data that already exists**, without inventing a new
metric source — the `started_at`/`completed_at` columns on the
`tool_calls` table (`persistence-schema.md`, Task 4) are enough to derive
wait duration and tool-call volume trends, because every `execute` call
through `SandboxBackendProtocol` (`sandboxing.md`) is recorded as the same
kind of tool call row as any other tool. `[code]` —
[`persistence-schema.md`](persistence-schema.md), the `tool_calls` table.

## Sources

- `[docs]` KEDA — `ScaledObject`, the `prometheus` trigger, Scaling
  Modifiers (a formula combining several triggers), scale-to-zero, cited
  via WebFetch from `keda.sh/docs/latest/concepts/scaling-deployments/`.
- `[docs]` Ray Serve — the concurrency-based model
  (`target_ongoing_requests`) underpinning the retrieval/embedding pool
  pattern here, cited via WebFetch from
  `docs.ray.io/en/latest/serve/autoscaling-guide.html` (full detail
  already quoted in `serving-topology.md`).
- `[docs]` Kubernetes — taints/tolerations (`kubectl taint`, `NoSchedule`,
  the dedicated-node pattern with `nvidia.com/gpu`), cited via WebFetch
  from
  `kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/`.
- `[code]` E2B (`e2b/sandbox/main.py`, `e2b/sandbox_sync/main.py`) and
  Daytona (`daytona/common/daytona.py`) — the pause/resume lifecycle
  parameters underpinning the warm pool pattern, read directly from the
  PyPI packages `e2b==2.45.1` and `daytona==0.205.1`, already quoted in
  full in `sandboxing.md`.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — the
  `tool_calls` table (`started_at`, `completed_at`) as a source for
  cold-start/queue-depth signals without new metrics, Task 4.
- `[code]` [`serving-topology.md`](serving-topology.md),
  [`sandboxing.md`](sandboxing.md) — the component→bound→HPA-signal table
  and the sandbox isolation spectrum underpinning the concrete
  configuration in this file.
