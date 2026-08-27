# Streaming protocol

## Problem

Two different mistakes come from the same source: treating streaming as a UX
garnish (tokens appearing progressively rather than waiting for a whole
answer) instead of as a **contract** for a long-running, multi-step process.

First, the SSE vs WebSocket choice is often decided by team familiarity or
fashion rather than the communication direction actually needed - ending up
with WebSockets (infrastructure complexity: an upgrade handshake, sticky
sessions at the load balancer, manual reconnect) for a pattern that only
needs the server pushing output one way.

Second, and more expensive: the stream is treated as the **only** place
agent events live - so as soon as the client's connection drops (a mobile
network dropping, a tab closed and reopened, a server behind a load balancer
restarted during a deploy), the events that passed during the disconnect are
**permanently lost** unless something else stored them. For an ordinary
agent turn that is merely bad UX (the user sees a truncated answer,
refreshes, gets the full version). For a turn waiting on HITL approval (see
[`human-in-the-loop.md`](human-in-the-loop.md)) it is serious: a client that
reconnects without knowing an approval gate is waiting means that turn is
silently stuck until somebody happens to notice.

## Pattern

### SSE vs WebSocket - when each

| Dimension | SSE (Server-Sent Events) | WebSocket |
|---|---|---|
| Direction | Server → client only; the client sends messages through ordinary HTTP requests (POST) outside the stream | Full duplex, both directions on the same connection |
| Protocol | Plain HTTP - passes through standard HTTP proxies/load balancers with no extra configuration | Needs an upgrade handshake (`Upgrade: websocket`); some proxies/LBs need explicit configuration (sticky sessions, different timeouts) |
| Reconnect | Built into the browser (`EventSource`) - automatic reconnect plus a `Last-Event-ID` header carrying the last event id received, with no extra client code `[docs]` | No protocol-level reconnect; it must be written manually in the client (detect `onclose`, open a new connection, resend state) |
| Message framing | Simple `event:`/`data:`/`id:`/`retry:` text lines, one direction | Free binary/text frames, the application defines its own |

**When SSE**: a turn-based interaction pattern - one user request triggers
one output stream (tokens, tool call events, results), with subsequent
requests (including HITL approval decisions) going through ordinary
request/response endpoints rather than the stream itself. This is the
default agent loop pattern (`agent-loop.md`): the user sends, the server
responds with a stream, done. `EventSource`'s automatic reconnect plus
`Last-Event-ID` also aligns directly with the reattach requirement below -
the protocol already provides half of the needed mechanism with no extra
client code.

**When WebSocket**: a need for bidirectional push **outside** a single
turn's boundary - many independent event streams multiplexed on one
connection, server-initiated events not triggered by a particular client
request (other users' presence, a background job completion notification,
collaborative canvas editing - see
[`artifacts-and-canvas.md`](artifacts-and-canvas.md)), or a client needing to
send data mid-stream without opening a new HTTP request (audio/voice duplex,
live cursors). The `_base` default for a chat/agent turn interface is
**SSE** - its needs match the turn-based pattern above; WebSockets are added
only when a concrete feature (real-time collaboration, voice) genuinely
needs duplex.

### The event schema

One event envelope per SSE `data:` line (or one WebSocket frame), with these
minimum fields:

```json
{
  "event_id": "01J...",      // a monotonic ULID/sequence PER TURN, used for Last-Event-ID & reattach
  "turn_id": "uuid",
  "type": "message.delta",
  "data": { "...": "..." },
  "ts": "2026-08-23T10:00:00Z"
}
```

The minimum event types one agent turn needs:

| `type` | When it is sent | `data` contents |
|---|---|---|
| `turn.started` | The turn begins processing | `{ "message_id": ... }` |
| `message.delta` | Each chunk of the answer's text tokens | `{ "text_delta": "..." }` |
| `tool_call.delta` | Each chunk of a tool call's arguments as the model forms them | `{ "index": 0, "name": "...", "args_delta": "..." }` - see §Rendering partial tool calls |
| `tool_call.result` | A tool call finished executing | `{ "tool_call_id": ..., "status": "success"/"error", "result": ... }` |
| `interrupt` | A HITL gate was raised, the turn is waiting | `{ "action_requests": [...], "review_configs": [...] }` - the exact shape from `human-in-the-loop.md` |
| `turn.completed` | The turn finished normally | `{ "message_id": ... }` |
| `turn.error` | The turn stopped on an error (not an interrupt) | `{ "message": "..." }` |
| `heartbeat` | Periodically (e.g. every 15-30 seconds) while no other event occurs | `{}` - purely to stop proxies/LBs closing an idle SSE connection |

### Rendering partial tool calls

Streamed tool call arguments arrive as chunks of a JSON string that is **not
valid** until complete. The concrete grounding in `langchain`:
`AIMessageChunk.tool_call_chunks: list[ToolCallChunk]`, where each
`ToolCallChunk` has `name` (optional, usually only on the first chunk),
`args` (a JSON string fragment), `id`, and `index` - chunks sharing an
`index` are combined by **string concatenation** (`left.args + right.args`),
not object merging. `[code]` - `langchain_core/messages/tool.py`'s
`ToolCallChunk` class, `langchain_core/messages/ai.py`'s `AIMessageChunk`
class and its `tool_call_chunks` field.

The client rendering rules follow directly from that mechanism:

1. Buffer `args_delta` per `index` (one tool call being formed = one
   buffer); don't try to `JSON.parse` each fragment.
2. Show progress as continuously growing argument text (e.g. a read-only
   text area that expands), **don't** try to render structured fields from
   incomplete JSON - a partial-tolerant JSON parser may be used for UI
   preview, but its output is never used for any decision.
3. A new tool call may **be executed or displayed as a real decision**
   (including entering a HITL gate) only from `tool_call.result`, or once
   `message.delta`/`tool_call.delta` stop and the final chunks have combined
   into valid JSON - never from a partial buffer still growing.

### Reattach after a client disconnect

This is the requirement that forces a **durable per-turn event log** rather
than an ephemeral broadcast-only stream. The flow:

1. The client stores the `turn_id` plus the last `event_id` received (for
   SSE, `EventSource` does this automatically through `Last-Event-ID`; for
   WebSockets, the application must store it client-side itself).
2. On reconnect, the client sends `(turn_id, last_event_id)` - for SSE this
   arrives automatically as a `Last-Event-ID` header on the new GET request
   `[docs]` (the WHATWG HTML spec's `EventSource` algorithm: *"If the
   EventSource object's last event ID string is not the empty string... Set
   ('Last-Event-ID', lastEventIDValue) in request's header list"*).
3. The server checks that turn's status. **The durable log isn't a new event
   table** - it is a projection of the transcript already required by
   [`persistence-schema.md`](persistence-schema.md): the `messages.status`
   column (`'complete'`/`'streaming'`/`'error'`) says whether anything needs
   resuming at all, and the `tool_calls` table (`status`
   `'pending'`/`'success'`/`'error'`, one row per tool call) gives the
   **granularity** of what is definitively finished.
   - If `messages.status = 'complete'` - send back the full final content;
     no stream resume is needed at all.
   - If `'streaming'` - send every `tool_calls` row already
     `'success'`/`'error'` as replayed `tool_call.result` events, then
     splice into the live tail from that point.
   - If the turn is stopped at a HITL gate - the same `interrupt` event is
     resent (its state does still exist, see `## In deepagents`), so a
     reconnecting client immediately learns an approval is waiting rather
     than silently losing that signal.

**The chosen granularity `[ours]`: per unit (message/tool call), not per
token.** Individual token deltas (`message.delta`/`tool_call.delta`) are
**never persisted one by one** - that would generate one row per token for
zero benefit once the unit finishes (once a message/tool call is
`'complete'`, its content already exists in full in the `content`/`result`
column and the individual deltas are useless). What is persisted
incrementally are the `messages`/`tool_calls` rows themselves, updated as
each unit completes. The token-by-token live tail still runs through an
ephemeral pub/sub path (e.g. Redis Pub/Sub or an in-process broadcast) that
is a **layer above** the durable transcript rather than a parallel store - if
the live connection drops mid-unit, the maximum reattach gap is "losing the
token deltas of ONE in-progress unit", not the whole turn history, and the
client can immediately re-request that unit's content (if the harness
checkpoints its partial progress periodically) or simply wait for it to
finish. The rejected vanilla: persisting every token delta as its own row
(perfect reattach down to the token, but a row explosion for data never read
again once its unit completes) - see `## Trade-offs`.

This **uses** the transcript model of
`persistence-schema.md`/`session-state.md` as-is rather than building a
parallel store - those files own the table schemas; this file owns the
event/reattach contract built on top of them.

## Trade-offs

- **SSE vs WebSocket** - discussed in §Pattern; in brief: SSE is
  infrastructurally simpler and gets automatic reconnect free for a one-way
  pattern (most agent turn cases), while WebSockets are needed for genuine
  duplex at the cost of infrastructure complexity plus manual reconnect.
- **Durability per token vs per unit vs none** - per token gives the most
  precise reattach (not one character lost) but bloats storage with data
  that is useless once its unit finishes; per unit (this project's choice)
  leaves a small gap (the deltas of one unfinished unit at disconnect time)
  with the same storage already required for the transcript; no durability
  at all (a purely ephemeral stream, a full restart on every disconnect) is
  cheapest but unacceptable for a system with HITL gates - a waiting
  approval can vanish from the client's view entirely.
- **Managed pub/sub (Redis Streams/Pub-Sub) vs DB polling for fanning the
  live tail out to many gateway pods** - managed pub/sub adds an
  infrastructure component but has low latency and doesn't burden Postgres
  with high-frequency polling; DB polling needs no new component but adds
  repeated read load and higher latency. This is a Gateway/SSE component
  decision whose scaling is owned by
  [`serving-topology.md`](serving-topology.md) (HPA signal: active
  connections) - this file only notes that the event/reattach contract above
  assumes neither; both can satisfy it.

## In deepagents

`langgraph` (the foundation of `deepagents`) has native streaming mechanisms
that feed directly into the event schema above, but does **not** solve
cross-connection reattach on its own:

- **`stream_mode`** on LangGraph's `.stream()`/`.astream()`: `"values"`
  (full state per step), `"updates"` (a delta per node/task), `"messages"`
  (per-token LLM streaming as `(chunk, metadata)` tuples - the direct source
  of `message.delta`/`tool_call.delta` above through
  `AIMessageChunk.tool_call_chunks`), `"custom"` (free data through
  `StreamWriter`), `"checkpoints"` (an event per checkpoint created),
  `"tasks"` (start/finish events per task, including errors). These can be
  combined as a list to receive several modes at once. `[code]` -
  `langgraph/types.py` (`StreamMode = Literal["values", "updates",
  "checkpoints", "tasks", "debug", "messages", "custom"]`),
  `langgraph/pregel/main.py`'s `stream_mode` parameter docstring on
  `.stream()`.
- **`durability`** (`"sync"`/`"async"`/`"exit"`) governs **when** a
  checkpoint is persisted relative to step execution - this parameter
  directly determines how far reattach can be trusted: `"sync"` persists
  before the next step begins (safest for reattach - the checkpoint always
  reflects a genuinely completed step, at the cost of extra latency per
  step); `"async"` (the default) persists while the next step runs (better
  throughput, with a small window where a crash can lose the last step's
  checkpoint); `"exit"` persists only when the graph finishes entirely
  (cheapest, but worst for mid-run reattach - there is almost no checkpoint
  to resume from if the process dies mid-way). `[code]` -
  `langgraph/pregel/main.py`'s `durability` parameter docstring on
  `.stream()`.
- **HITL interrupts are automatically part of the checkpoint** -
  `interrupt()` (used by `HumanInTheLoopMiddleware`, see
  [`human-in-the-loop.md`](human-in-the-loop.md)) stops the graph at that
  point and its state persists through the same `checkpointer` that keeps
  Run state (`../systems/deepagents.md` §5). So half of reattach for a turn
  in HITL - "the waiting approval state isn't lost" - comes free from
  `langgraph`'s existing resume mechanism and needn't be rebuilt. `[code]` -
  cited from `../systems/deepagents.md` §6.
- **What `langgraph` does NOT solve**: `.stream()`/`.astream()` is a Python
  generator bound to the process and connection that invoked it. If client
  A's connection drops and the same gateway process (or another one)
  continues a run that was interrupted/checkpointed, `langgraph` gives back
  **checkpointed state to continue executing** (`Command(resume=...)`), not
  **a replay of the token deltas already broadcast to the old connection**.
  Those are two different things: the first is "continue executing a stopped
  graph", the second is "replay what client A already saw before the drop".
  `langgraph` provides only the first. `[inferred]` - concluded from
  `.stream()`'s contract as a per-invocation generator
  (`langgraph/pregel/main.py`) and the absence of any "resume watching an
  existing broadcast" mechanism in the modules read - bridging the two (the
  per-turn event log in §Reattach) remains the application gateway layer's
  responsibility; `deepagents`/`langgraph` don't provide it.

## Sources

- `[code]` `langgraph/types.py` - read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langgraph/types.py`,
  the `StreamMode` definition.
- `[code]` `langgraph/pregel/main.py` - read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py`,
  the `stream_mode`, `durability`, and `subgraphs` parameter docstrings on
  `.stream()`.
- `[code]` `langchain_core/messages/ai.py`, `langchain_core/messages/tool.py`
  - read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langchain_core/messages/`,
  the `AIMessageChunk` class (the `tool_call_chunks` field) and
  `ToolCallChunk` (`name`/`args`/`id`/`index`, the per-`index` combination
  semantics).
- `[docs]` The WHATWG HTML Standard - §9.2 Server-sent events
  (`https://html.spec.whatwg.org/multipage/server-sent-events.html`), cited
  via WebFetch for the `EventSource` reconnect algorithm (the
  `Last-Event-ID` header, the `id:`/`retry:` fields, the
  implementation-defined default reconnect delay).
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5, §6 -
  a verified tier-1 reference, cited for the checkpointer and interrupts.
- `[code]` [`persistence-schema.md`](persistence-schema.md) - the `messages`
  (`status` column) and `tool_calls` (`status` column) tables, cited as the
  durable log underpinning reattach; the schema is unchanged by this file.
- `[code]` [`session-state.md`](session-state.md) - the ephemeral vs durable
  heuristic per layer, cited to justify "token deltas ephemeral, message/tool
  call units durable".
- `[code]` [`human-in-the-loop.md`](human-in-the-loop.md) - the `interrupt`
  payload shape, cited for the event schema; its mechanism isn't repeated.
