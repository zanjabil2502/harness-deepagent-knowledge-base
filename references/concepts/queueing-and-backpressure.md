# Queueing & backpressure

## Problem

The naive request-response model - accept an HTTP request, run the turn
inline in that same handler, return the response when it finishes - works
for requests that complete in milliseconds. For an agent turn running for
minutes (see `resource-profiling.md`, `serving-topology.md`), that model
breaks in three distinct ways:

1. **No backpressure** - a burst of new turns fills the entire worker pool
   while each waits for an LLM/tool call to finish, subsequent requests
   queue uncontrolled at the TCP/load balancer level, and the only lever
   available is refusing connections outright at the very front layer.
2. **No priority** - a latency-sensitive turn (a user waiting in the UI)
   and a batch/background turn (a scheduled job, a retry) are treated
   identically; a burst of the latter can delay the former without bound.
3. **No reattach** - the HTTP connection holding the turn is the client's
   only route to the result. A closed browser tab, a dropped mobile
   connection, or a load balancer cutting the socket → the running turn
   (which may already have called a paid or non-idempotent tool) is
   orphaned: still running on the server, with no way for the client to
   learn its outcome.

## Pattern

### Turns enter a queue rather than executing inline

A turn is accepted, given a `turn_id` (a per-turn idempotency key, already
specified in `persistence-schema.md` - the `turns.idempotency_key` and
`turns.status` columns), then **placed on a queue**, and the HTTP handler
returns immediately with the `turn_id` - it does not wait for the turn to
finish. A separate worker pool pulls from the queue and executes. This
separates three things previously fused into one request-response:
**accepted** (the turn is recorded and has a `turn_id`), **running** (a
worker is processing it), and **finished** (the result is available) -
each visible through `turns.status` (`pending` → `completed`/`failed`).

### Backpressure: queue depth as a signal, not only an HPA lever

Queue depth is the signal already mapped to the Tool executor row in
`serving-topology.md`'s HPA table (`queue depth, CPU`) - but backpressure
isn't only about automatic scale-out. At the admission point, if the queue
crosses a threshold, the system must **explicitly reject new turns** (a
clearly retriable response, rather than silently piling up without bound)
instead of accepting everything and letting memory/connections accumulate
until the process falls over. Real precedent for the "queue first, don't
fan every request straight through to the execution side" pattern exists in
LiteLLM: its proxy provides `scheduler_acompletion()` on the Router, which
places a request on a queue then **polls** whether a healthy deployment
exists and whether the request has reached the head of the queue, with a
default `polling_interval` of 3ms and an optional per-request
`default_priority` `[code]` - `litellm/router.py`
(`Router.scheduler_acompletion`, the `polling_interval` and
`default_priority` parameters), cited via WebFetch/WebSearch from
`docs.litellm.ai/docs/scheduler` and the `BerriAI/litellm` source.

### Priority: a lower value wins, as in LiteLLM

The LiteLLM proxy supports a priority queue based on key priority levels -
`priority` is sent per call, and a lower value means higher priority
`[docs]` - cited from `docs.litellm.ai/docs/scheduler`.

**The committed `turns` schema (`persistence-schema.md`) has no such
column** - today the turn queue is pure FIFO (workers pull in
`created_at` order, with no queue-jumping path). The LiteLLM-shaped
priority above is a forward recommendation, not something already
built: `[ours]` - vanilla
(and what the current schema runs) is pure FIFO, sufficient for a load
whose items are uniform in value. Adding a `priority INT` column to `turns`
only pays off once turn classes genuinely differ in value (e.g.
interactive turns and batch jobs sharing one queue) - and the evidence must
be real (the queue actually full and high-value turns actually delayed),
not assumed up front. If that column is added, workers pull by priority
first and FIFO within a priority; an anti-starvation mechanism (aging) is
deliberately not prepared now - YAGNI until there is real evidence of low
priority starving, and if needed it is a local addition to the "fetch the
next turn" query, not another schema change.

### Reattach after a client disconnect

Because a turn has a durable `turn_id` and its status is stored
(`turns.status`) independently of the HTTP connection that triggered it,
**the turn does not stop when the client disconnects** - the worker
finishes it anyway. A reconnecting client (a refreshed tab, the app
reopened) simply:

- `GET /turns/{turn_id}` - fetch the status plus the result-so-far if the
  turn is still running, or the final result if it has finished.
- Re-subscribes to that turn's event stream (a new SSE with the same
  `turn_id`) to keep receiving new events from that point, not from the
  beginning.

This deliberately diverges from the assumption "connection dropped = turn
cancelled" - that assumption is wrong for a turn that may already have
called a paid or non-idempotent tool (an external API call, a file write)
before the drop; cancelling it because a tab was closed discards work
already done and can leave half-finished side effects that are never
reported to the user.

## Trade-offs

- **Queue-then-execute vs inline execution** - inline is simpler and lower
  latency for a system that rarely overloads (no extra queue component to
  maintain), but has no backpressure lever beyond refusing raw TCP
  connections, and cannot prioritise. Queueing first adds components (a
  queue + worker pool + status polling/subscription) but makes load
  explicit and controlled - a sensible decision once turns are long enough
  and bursty enough to need that control; for low or steady traffic,
  inline remains valid and simpler.
- **A priority queue vs pure FIFO** - FIFO is simple and fair by
  construction (no turn unexpectedly jumps the queue), but high-volume
  low-value turns (batch jobs) can delay interactive turns without bound
  if both share one queue. A priority queue solves that but opens the risk
  of starving the low-priority class if the high class keeps arriving -
  its mitigation (aging) is deliberately not built now, YAGNI until there
  is real evidence.
- **Reattach through polling/a new SSE vs a persistent WebSocket** -
  re-polling/SSE scales more easily behind a stateless load balancer: any
  pod can serve `GET /turns/{id}` because the status is read from
  Postgres, not from one process's memory, and an automatic reconnect
  lands on any pod without sticky sessions. A persistent WebSocket with
  state in one process's memory needs sticky sessions (the reconnect must
  land on the same pod) or extra pub/sub infrastructure (e.g. Redis
  pub/sub) so turn events can be fanned out to whichever pod receives the
  reconnect - lower update latency, heavier infrastructure.

## In deepagents

The concept of a "turn" and its HTTP queue lies entirely outside
`deepagents` - `deepagents` is an invoke-a-graph library and knows nothing
about HTTP requests or queues; this is purely the application's
responsibility, like the Transcript in `session-state.md`. What
`deepagents` **does** already provide, in exactly the same shape ("detach,
check status by id, reattach"), is at the **async subagent** level, one
layer below the turn: `AsyncSubAgentMiddleware` provides tools to
start/check/update/cancel/list background tasks, stored in
`AsyncSubAgentState.tasks` (a `task_id -> AsyncTask` dict) - the status is
cached then **re-checked against the server**, not assumed from local
memory. `[code]` -
[`../systems/deepagents.md`](../systems/deepagents.md) §5 (`Surface API`:
`AsyncSubAgentMiddleware`, `AsyncSubAgent`).

The turn-level queue pattern in this file can use exactly that shape one
level higher: an addressable `turn_id`, a status enum that is
polled/subscribed to, and "re-check against the source of truth" (here:
Postgres `turns.status`) instead of trusting a local cache - the shape
isn't the same by coincidence, this is the general pattern for
asynchronous work that outlives the connection that triggered it, and
`deepagents` already applies it at its own layer.

## Sources

- `[code]` LiteLLM `litellm/router.py` - `Router.scheduler_acompletion()`,
  the `polling_interval` (3ms default) and `default_priority` parameters,
  read via WebFetch over the `BerriAI/litellm` source and cross-confirmed
  against the documentation.
- `[docs]` LiteLLM - priority semantics (a lower value = higher priority)
  and the `[BETA] Request Prioritization` queue model, cited via WebSearch
  from `docs.litellm.ai/docs/scheduler`.
- `[code]` [`persistence-schema.md`](persistence-schema.md) - the `turns`
  schema (`idempotency_key`, `status`) that this file's turn-addressable
  design is built on, Task 4.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 -
  `AsyncSubAgentMiddleware`/`AsyncSubAgentState.tasks` as precedent for the
  detach/reattach pattern inside `deepagents` itself, a tier-1 reference
  verified in Task 3, cited without re-reading the source.
- `[code]` `serving-topology.md`, `resource-profiling.md` (this KB) - the
  argument for queue depth as the Tool executor signal builds on the
  component→bound→HPA signal table explained there.
