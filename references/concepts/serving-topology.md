# Serving topology

## Problem

The default instinct for deploying a new HTTP service — one Deployment, one
Service, an HPA on CPU or requests-per-second (RPS) behind a reverse proxy
with default timeouts — is designed for requests finishing in tens to
hundreds of milliseconds. One agent turn can run for **minutes**, consisting
of several LLM calls alternating with tool calls (see
`resource-profiling.md`). All three — the HTTP timeout, the rolling deploy,
and the RPS-based HPA — quietly assume "short requests", and break in
different ways once that assumption is wrong:

1. **Default HTTP timeouts cut the turn off mid-flight.** Nginx's
   `proxy_read_timeout` defaults to 60 seconds, and AWS ALB's idle timeout
   defaults to 60 seconds `[docs]`. Both are gap timeouts (the maximum
   interval between data reads), not total-duration timeouts — a streaming
   response emitting bytes every few seconds doesn't trigger them. But as
   soon as one hop on the path (an internal proxy, an ingress controller, a
   cloud load balancer) isn't reconfigured or doesn't support the same
   streaming/keep-alive, a minutes-long turn dies mid-way with a 502/504 and
   no notification to the application.
2. **Rolling deploys kill in-flight turns.** Kubernetes' default rolling
   update sends `SIGTERM` to the old pod as soon as the new pod is ready,
   with `terminationGracePeriodSeconds` defaulting to 30 seconds `[docs]`. A
   turn waiting on a minutes-long LLM call or mid-way through a long tool
   call dies with its pod unless there is drain logic.
3. **An RPS-based HPA misreads long-lived IO-bound load.** RPS measures the
   arrival rate of new requests per second; a good proxy for load where
   request duration is short and uniform, but blind to **concurrency** — how
   many turns are active at once. Elaborated below.

## Pattern

### Component → bound → HPA signal (§8.3)

| Component | Bound | HPA signal |
|---|---|---|
| Gateway / SSE | IO | Active connections (not RPS — a gateway holds connections open rather than processing quickly and releasing) |
| Orchestrator | IO-dominant | **In-flight turns**, not RPS |
| Tool executor | CPU + memory | Queue depth, CPU |
| Retrieval / embedding | GPU or CPU | Batch queue, GPU utilisation |
| State store | IO/disk | Not a pod — scale through read replicas/connection pooling, not an HPA |

The concrete configuration per row (KEDA triggers, GPU node pools, etc.) is
in `scaling.md`; this file explains **why** the orchestrator row differs from
the RPS default, and **what** must be provided for that signal to be usable.

### Why RPS is wrong for the orchestrator — and what has to be defended

RPS = the arrival rate of new requests per second. A valid proxy for short
CRUD loads because there `concurrency ≈ RPS × request duration`, with
request duration nearly constant (tens to hundreds of ms) — so RPS and
concurrency move together and RPS is safe as a load signal.

Once request duration rises from milliseconds to minutes, that relationship
changes drastically (Little's law: `concurrency = arrival_rate × duration`).
Two examples with identical RPS but entirely different pod load:

- 10 turns/second arriving, each finishing in 100ms → average concurrency
  ~1 active turn. The pod is barely loaded.
- 10 turns/second arriving, each running 5 minutes → average concurrency
  ~3000 turns active simultaneously. The pod can run out of memory (each
  in-flight turn holds its assembled context, see `resource-profiling.md`)
  long before RPS looks high on any dashboard.

An HPA watching RPS can't distinguish these two — the number is "10" in both
cases. It will fail to scale out in the second case (low RPS while the pod
is dying under thousands of concurrent turns), and potentially
over-provision in cases like the first (RPS looks high even though each pod
could hold far more concurrency, because an IO-bound orchestrator can hold
hundreds of async turns per pod with no extra CPU — see
`resource-profiling.md`). The correct signal isn't arrival rate but **how
many turns are open right now** — in-flight turns.

Real precedent for this pattern: Ray Serve, a production serving framework,
already scales on **ongoing/in-flight requests per replica**
(`target_ongoing_requests`) rather than RPS, for exactly the same reason —
varying request durations need a concurrency signal, not a rate signal.
`num_replicas="auto"` in Ray Serve defaults to `target_ongoing_requests: 2`.
`[docs]` — `docs.ray.io/en/latest/serve/autoscaling-guide.html`, cited via
WebFetch. This isn't an exotic pattern this KB invented; it is the pattern
another production serving system already chose for exactly this problem.

**What must be provided in Kubernetes for in-flight-turn scaling to be
usable:**

1. The orchestrator must expose a **gauge metric** — not a counter — of how
   many turns are currently running in that process: incremented when a turn
   starts, decremented when it finishes/fails/is cancelled. Exposed through
   a Prometheus-format `/metrics` endpoint per pod.
2. Prometheus (or a compatible system) scrapes that endpoint across every
   orchestrator pod and stores the time series.
3. A **KEDA `ScaledObject`** with a `prometheus` trigger pointing at an
   aggregate query (e.g. average in-flight turns per pod) — KEDA translates
   that value into a custom/external-metric HPA object managed natively by
   Kubernetes. `[docs]` — KEDA supports `prometheus`, `metrics-api`, and
   External Scaler triggers for custom metrics; a ScaledObject generates and
   manages its own HPA, cited via WebFetch from
   `keda.sh/docs/latest/concepts/scaling-deployments/`.
4. That trigger's `threshold` is pinned **below** the concurrency limit that
   is memory-safe per pod (that information comes from
   `resource-profiling.md`: each in-flight turn holds its context assembly
   in memory) — not an arbitrary number.
5. Pod lifecycle must align with this signal, not just the metric:
   scale-down must not kill a pod still holding in-flight turns — see the
   rolling-deploy solution below; the principle is the same for HPA
   scale-down.

### Three long-turn problems and their mitigations

| Problem | Cause | Mitigation |
|---|---|---|
| Default HTTP timeouts | A 60s `proxy_read_timeout`/idle timeout is the default on nearly every hop (nginx, ALB) `[docs]` | SSE streaming with periodic keep-alive frames (resetting the gap timeout on each event, since it isn't a total-duration timeout), raising the timeout explicitly on **every** hop (not just one), or — more failure-resistant — not holding one HTTP connection for the whole turn at all: return `turn_id` immediately and let the client reattach (see `queueing-and-backpressure.md`) |
| Rolling deploys cutting in-flight turns | `SIGTERM` + a 30s default grace period as soon as the new pod is ready `[docs]` | A `preStop` hook that stops accepting new turns then waits for in-flight ones to finish (drain) before exiting; `terminationGracePeriodSeconds` raised above the p99 turn duration; the readiness probe disabled first so the Service stops sending new turns to that pod while in-flight ones finish; and if the drain window expires before a turn completes, checkpointer resumability (`session-state.md`) is the safety net — the turn can continue on another pod from its last checkpoint |
| An RPS-based HPA misreading load | RPS is blind to concurrency for requests of varying duration | In-flight turns as the signal (see above), not RPS |

All three come from the same wrong assumption for agents: that one unit of
HTTP work is short. Their solutions share one theme too: make the turn an
entity that **outlives** the single connection/pod/HTTP request carrying it
— reattachable, resumable, and measurable for concurrency independently of
the HTTP request that triggered it.

### A modular monolith with the seams cut

> `_base` = a modular monolith with the seams already cut. One deployable,
> but orchestrator / executor / retrieval separated behind interfaces, so
> splitting into microservices = changing a binding + a manifest, not a
> rewrite. (§8.3)

That isn't a slogan — there are concrete conditions for the "just change the
binding" claim to genuinely hold later rather than being an empty promise:

1. **Cross-component calls go through explicit interfaces, not direct calls
   into internal functions/objects.** The orchestrator calls the tool
   executor through a contract (e.g. `execute(command, cwd) -> Result`),
   rather than importing the executor module and calling its internals
   directly. Without this, "splitting into a service" means finding and
   rewriting every call site rather than swapping an implementation in one
   place.
2. **Arguments and results at the interface boundary must be serializable
   (JSON/msgpack), not raw Python objects (file handles, DB connections,
   closures).** An in-process interface can get away with in-memory objects
   today — once split into a real service, that boundary becomes a real
   network call, and non-serializable objects force a contract rewrite
   rather than a binding change.
3. **No shared mutable state reached by a shortcut outside the interface**
   (e.g. the orchestrator reading the executor's local files directly, or
   depending on a global variable in the same process). Such shortcuts are
   unwritten coupling discovered only after the two components move to
   different hosts.
4. **The interface accepts the scope object explicitly as a parameter**
   (`(user_id)` or `(tenant_id, user_id)`, see
   `isolation-and-scoping.md`), rather than relying on ambient state
   (thread-locals, process variables) that happens to be correct while every
   component shares one process. Once it becomes a real network call,
   authorisation must be explicit in the payload/token too — not "safe
   because it's one machine".

`deepagents` already provides two of these three seams natively through
interfaces, elaborated in `## In deepagents` below — this KB chooses to use
them rather than build interfaces from scratch.

## Trade-offs

- **A monolith vs splitting from day one** `[ours]` — vanilla is splitting
  from the start (orchestrator, executor, retrieval as separate services
  from day one), which gives independent scaling immediately but adds
  network hop latency and operational complexity (deployment, discovery,
  cross-service observability) for a load that early in a project may not
  need it. This KB chooses a modular monolith with the seams cut (§8.3)
  instead, deferring the cost of splitting until it is genuinely needed (one
  component's traffic far outgrowing the others'), at the cost of the
  discipline to write the interfaces correctly from the start (the four
  conditions above) — if that discipline lapses, the later migration is
  still a rewrite and those seams were an empty promise.
- **Raising timeouts vs detaching the turn from the HTTP connection** —
  raising the timeout at every hop is simpler (the request-response model is
  unchanged) but brittle: one hop nobody reconfigured, or third-party
  infrastructure (a CDN, a WAF) with an unchangeable hard timeout, still
  cuts the turn off. Detaching the turn from the HTTP connection (turn_id +
  reattach, `queueing-and-backpressure.md`) is more failure-resistant but
  changes the API model from synchronous request-response to
  submit-then-poll/subscribe — a larger change to the client contract.
- **Draining on rolling deploy vs accepting a cut turn and resuming from a
  checkpoint** — draining (waiting for in-flight turns before the pod dies)
  never cuts a turn and needs no complex resume logic in the app, but holds
  up the rollout (a new deploy waits for the longest-running turn, which can
  be a while for minutes-long turns). Resuming from a checkpoint (letting
  the pod die, the turn continuing on another pod from its last checkpoint)
  frees the rollout from waiting, but needs a genuinely resumable
  checkpointer (`session-state.md`) and user tolerance for a turn that
  appears to "pause". The realistic pattern is both at once — draining as
  the primary route, resume as the safety net if the drain window expires.

## In deepagents

Two of the three "modular monolith" seams above already exist as built-in
`deepagents` interfaces rather than needing to be built:

- **The tool executor** — every tool execution through `FilesystemMiddleware`
  calls a backend implementing `SandboxBackendProtocol` (`execute()`). That
  is already an interface: `LocalShellBackend` (in-process, unisolated) and
  a custom implementation (e.g. an E2B/Daytona wrapper, see
  `sandboxing.md`) both satisfy the same contract and are called by the
  orchestrator the same way. `[code]` —
  [`../systems/deepagents.md`](../systems/deepagents.md) §6, §Filesystem
  backend.
- **Retrieval/durable state** — `StoreBackend(namespace=...)` is the
  official scoping *hook* into the application-injected `store`;
  `CompositeBackend` routes paths to different backends per prefix. Both are
  interfaces that already separate "where durable state lives" from
  orchestrator logic. `[code]`+`[docs]` —
  [`../systems/deepagents.md`](../systems/deepagents.md) §Filesystem backend
  (the `namespace=lambda rt: (rt.server_info.user.identity,)` example from
  `docs.langchain.com/oss/python/deepagents/backends`).

**The orchestrator itself** = the LangGraph graph assembled by
`create_deep_agent`/`create_agent` — `deepagents` forces no deployment
topology on it; wherever that graph is invoked (one FastAPI process, one
Kubernetes Job, one queue worker) is entirely an application decision
outside `deepagents`. Consequently the in-flight turns signal discussed
above is **not** provided by `deepagents` — the gauge metric has to be
written by the application at the point where it calls `.invoke`/`.stream`
on the graph, incrementing before the call and decrementing in a
`finally`/completion callback. `[inferred]` — concluded from the absence of
any built-in metrics/observability primitive in `## Surface API`/`##
Built-in middleware` of `../systems/deepagents.md`.

## Sources

- `[docs]` KEDA — `ScaledObject`, the
  `prometheus`/`metrics-api`/External Scaler triggers, and the relationship
  with Kubernetes' native HPA, cited via WebFetch from
  `keda.sh/docs/latest/concepts/scaling-deployments/`.
- `[docs]` Ray Serve — the `target_ongoing_requests` autoscaling model
  (in-flight requests per replica, not RPS), with `num_replicas="auto"`
  defaulting to `target_ongoing_requests: 2`, cited via WebFetch from
  `docs.ray.io/en/latest/serve/autoscaling-guide.html`.
- `[docs]` Nginx — the 60-second default `proxy_read_timeout` as a gap
  timeout (not total duration), cited via WebSearch from the Nginx timeout
  configuration documentation.
- `[docs]` AWS Elastic Load Balancing — the 60-second default idle timeout,
  cited via WebSearch from the official AWS ELB idle timeout configuration
  announcement/documentation.
- `[docs]` Kubernetes — rolling update behaviour (`SIGTERM` to the old pod
  as soon as the new one is ready) and the 30-second default
  `terminationGracePeriodSeconds` — standard Kubernetes knowledge,
  cross-confirmed through the same taint/toleration and pod lifecycle
  documentation cited in `scaling.md`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §6,
  §Filesystem backend — a tier-1 reference verified in Task 3, cited
  without re-reading the source.
- `[code]` `resource-profiling.md` (this KB) — the concurrency vs RPS
  argument builds on the phases-within-a-turn breakdown explained there.
