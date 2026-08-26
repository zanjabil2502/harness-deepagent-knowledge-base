# Session state

## Problem

"State" in an agent system is five different things that happen to share a
name: the chat history the user sees, the slice of text actually sent to
the model on each call, the progress of one graph run that can be resumed,
facts that persist across sessions, and the files/documents the agent
produces. Until those five are separated there is no way to reason about
persistence — the question "does this need to live in Postgres?" has no
single answer, because the answer differs per layer.

Concrete symptoms of the confusion: context compaction is misread as
"deleting history" (when it only trims what is sent to the model); a chat
list feature is built on top of the checkpointer (which is not a product
database, see below); artifact bytes are stored directly in a message
column (bloating the transcript, and bloating context every time history
is reloaded).

**The sorting heuristic**: if this state were lost, **can it be
recomputed** from another source (transcript, memory, artifacts)? Yes → it
may be ephemeral on the AI/harness side (cache, in-memory, discarded after
the call). No → it must be durable in the backend. The sharp line:
**the backend owns truth, the AI owns a projection.**

## Pattern

### Five layers (§8.1)

| Layer | Store | Lifetime | Owner |
|---|---|---|---|
| Transcript | Append-only Postgres | permanent | Backend |
| Model context | Computed, Redis cache | 1 call | Harness |
| Run state | Checkpointer (Postgres) | 1 run, resumable | Harness |
| Memory | Postgres + vector | across sessions | Backend + AI |
| Artifacts | S3/GCS + metadata rows | permanent, versioned | Backend |

Check each layer against the heuristic above: a transcript cannot be
recomputed (it is the single source of truth for the conversation) →
durable, backend. Model context can be recomputed at any time from
transcript + memory + artifacts-by-reference → may be ephemeral. Run state
sits in between: recomputable in theory (replay the transcript from the
start) but expensive for long sessions — which is why the checkpointer
stays durable even though the harness owns it rather than the backend: its
content is the graph's working representation, not a product archive.

### Why transcript ≠ model context

These are not two names for the same thing, and conflating them is the
most common source of bugs at this layer:

- **Transcript** — the complete, permanent, append-only archive, owned by
  the backend. Old messages never disappear merely because they are no
  longer sent to the model.
- **Model context** — a projection **recomputed on every call** from the
  transcript (+ memory + artifacts-by-reference) through assembly:
  windowing, compaction/summarization, eviction of large tool results.
  Discarded, or briefly cached (e.g. in Redis), once the call finishes.

The consequence: compaction (e.g. `SummarizationMiddleware`, see
[`../systems/deepagents.md`](../systems/deepagents.md) §2) **does not
delete rows from the transcript** — it changes what gets sent to the model
on the next call. What the transcript records is the compaction *event*
pointing at the messages it replaced (see `compaction_events` in
[`persistence-schema.md`](persistence-schema.md)), not a message deletion.
Teams that conflate the two end up "deleting history" to save tokens, when
the only thing that should have been trimmed is what goes to the model —
the archive stays intact.

### Derived rules (§8.1)

- The transcript is a **tree**, not a list — editing an old message means a
  new message branching from the same `parent_id`, not overwriting (see
  [`persistence-schema.md`](persistence-schema.md)).
- The checkpointer is **not a product database** — don't build chat list or
  history browsing features on it. Its internal schema (`thread_id`,
  `checkpoint_id`, binary blobs) is optimised for resuming one thread, not
  for cross-user/cross-time queries.
- Artifacts go **by reference** — the transcript stores `artifact_id +
  version`, model context stores a handle plus a summary, and the real
  bytes live in an object store (see
  [`artifacts-and-canvas.md`](artifacts-and-canvas.md)).
- A tool call and its result are **first-class transcript rows**, not a
  JSON field buried inside a message — so they can be queried, redacted,
  and scoped per user independently.
- Idempotency keys go **per turn**, not per message — one turn can contain
  many tool calls, and a network retry or duplicate submit at turn level
  must not create a second turn.

## Trade-offs

- **Ephemeral vs durable per layer**: storing more (everything durable)
  avoids data loss but enlarges the RLS surface and storage cost;
  discarding more aggressively (everything ephemeral) is cheap but loses
  data that genuinely cannot be recomputed (e.g. nondeterministic tool
  call results — recalling an external API may return a different value or
  carry a billable side effect).
- **Tree vs flat list for the transcript**: a tree adds query complexity
  (you must walk from root to the active leaf — resolved through a
  persisted `conversations.active_leaf_id` pointer rather than recomputed
  per render; see `persistence-schema.md`), but a flat list cannot
  represent "the user edited a message then regenerated" without
  overwriting history — and losing that ability is losing data that cannot
  be recomputed.
- **Tool call as a separate row vs a field on the message**: a separate row
  needs an extra join to render one message bubble, but a buried JSON
  field cannot be indexed or redacted per row and makes selective
  retention hard (e.g. deleting a tool result containing PII without
  deleting its message).
- **A durable checkpointer even for "only" Run state**: the purely
  ephemeral alternative (replay the transcript from the start on every
  resume) saves storage but costs latency and tokens for long sessions —
  the same recompute-cost vs storage-cost trade-off as the heuristic
  above, just at a different point.

## In deepagents

`deepagents` does not build the Transcript layer at all — that is purely
the application's responsibility (see
[`persistence-schema.md`](persistence-schema.md)). What `deepagents`
provides are concrete mechanisms for the other three layers, through the
`checkpointer`/`store` it **passes through unchanged** to
`langchain.agents.create_agent` — `deepagents` never builds a
checkpointer/store of its own. `[code]` — see
[`../systems/deepagents.md`](../systems/deepagents.md) §5
(`deepagents/graph.py` lines 546-553, 922-931).

| Layer (spec) | Concretely in deepagents | Source |
|---|---|---|
| Transcript | Absent — `DeepAgentState.messages` (reduced by `DeltaChannel`) is the graph's working representation for resuming, not a permanent branching archive. The application still needs its own `messages` table. | `[inferred]` from the absence of this mechanism in §5/Backend filesystem of `../systems/deepagents.md` |
| Model context | `SummarizationMiddleware` (automatic token-threshold compaction) plus `FilesystemMiddleware` (evicting large tool results to the backend, replaced by a preview plus a path reference) | `[code]` `../systems/deepagents.md` §2 |
| Run state | `DeepAgentState` through the application-injected `checkpointer` — resumable per thread | `[code]` `../systems/deepagents.md` §5 |
| Memory | `MemoryMiddleware` (static — `AGENTS.md` content injected once at session start) plus `StoreBackend(namespace=...)` (durable across threads, requires an application-injected `store`) | `[code]` `../systems/deepagents.md` §2, §5, Backend filesystem |
| Artifacts | No built-in "artifact"/versioning primitive; `StoreBackend`/`CompositeBackend` can serve as the durable layer, but the S3 object store plus version metadata stays the application's job | `[code]`+`[inferred]` `../systems/deepagents.md` Backend filesystem |

The direct implication: if a project needs chat history that can be
searched, paginated, or branched across sessions (that is, a real
Transcript), it does **not** come free from the `checkpointer`. It has to
be built as the application's own `messages` table (see
`persistence-schema.md`), while the `checkpointer`/`store` injected into
`create_deep_agent` continue to serve Run state and durable Memory —
two different things that merely happen to both say "Postgres" in the
five-layer table above.

## Sources

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2
  (Context), §5 (State & resume), and §Backend filesystem — a tier-1
  reference already verified against `deepagents==0.7.8` source; cited
  directly here without re-reading the source because it was validated in
  Task 3.
- `[docs]` LangGraph — the `checkpoints`/`writes` schema and the
  `BaseCheckpointSaver` contract (`thread_id`, `checkpoint_ns`,
  `checkpoint_id`, `parent_checkpoint_id`), cited via Context7 from
  `docs.langchain.com/oss/python/langgraph/checkpointers` — used to verify
  the claim "the checkpointer is not a product database": its schema is
  optimised for single-thread lookup (PK `thread_id, checkpoint_ns,
  checkpoint_id`), not cross-user queries.
