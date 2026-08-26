# Retention & deletion

## Problem

"Delete user X" sounds like a single `DELETE`, but agent state is spread
across five layers in several systems (§8.1): the Postgres transcript, the
Postgres checkpointer, the artifact object store, and — the two most
frequently missed — the **vector index** for memory/RAG and the
observability **trace store**. An `ON DELETE CASCADE` foreign key only
reaches what lives inside one Postgres database; the other three systems
(object store, external vector DB, trace store) know nothing about
`user_id` until they are called explicitly. If the cascade list is
incomplete, the "deletion" succeeds in the UI (rows vanish from chat
history) while PII lives on forever in observability traces or the vector
index.

## Pattern

### The complete cascade list

| Layer | Store | Delete action | Mechanism |
|---|---|---|---|
| Transcript | Postgres — `conversations`, `messages`, `tool_calls`, `turns`, `compaction_events` | `DELETE FROM conversations WHERE user_id = ...` — the rest follows through `ON DELETE CASCADE` (see `persistence-schema.md`) | SQL, one transaction |
| Checkpoint (Run state) | The checkpointer library's own `checkpoints`/`writes` tables, not the application schema | Call `checkpointer.adelete_thread(thread_id)` per deleted `conversation_id` — **not** a manual `DELETE` against the checkpointer's tables, whose schema isn't owned by the application's migrations | `[docs]` checkpointer API, called from the app |
| Artifacts (object store) | S3/GCS plus `artifacts`/`artifact_versions` (see `artifacts-and-canvas.md`) | Delete every object at `content_ref` for all of the user's versions, then `DELETE FROM artifacts` (cascading to `artifact_versions`/`message_artifact_refs`) | Storage API (idempotent, retried) + SQL |
| Memory rows | Postgres `memory_entries`, or durable `StoreBackend` files where used | `DELETE FROM memory_entries WHERE user_id = ...`; for anything under `StoreBackend`: `store.adelete(namespace, key)` per key returned by `store.asearch((user_id,))` | SQL + `[docs]` LangGraph `store.adelete`/`asearch` |
| **Vector index** | An `embedding` column on `memory_entries` (pgvector) **or** an external vector DB (Pinecone/Weaviate/Qdrant) separate from Postgres | Colocated pgvector: deleted automatically by the `DELETE FROM memory_entries` above. External: **a separate delete-by-metadata API call is mandatory** — no foreign key forces it, which is why it is the easiest to miss | `[inferred]` — general external vector DB behaviour; there is no cross-vendor standard API for this |
| **Trace store** | External observability/tracing (LangSmith, Langfuse, an OpenTelemetry backend) | A separate API call or retention policy is **mandatory** to purge traces tagged with `user_id` — a trace store is almost always a third-party system that doesn't automatically follow deletions in the product | `[inferred]` — general third-party trace store behaviour, not a design decision of ours |

The last two rows are bold because they are **the most frequently
missed**: both the vector index and the trace store usually live in
systems that don't consider themselves part of a user's lifecycle — a
vector DB is treated as search infrastructure, a trace store as internal
tooling — until an audit or a deletion request finds PII remnants in both.

### Order of operations (a saga, not one transaction)

Deletion across these five layers cannot be a single ACID transaction —
the object store, checkpointer, external vector DB, and trace store are
separate systems. A partial-failure-safe order:

1. Mark the user for deletion (transactionally: set `deleted_at` or
   enqueue a deletion job) — a commit point that cannot half-fail.
2. Cascade Postgres (transcript, tool calls, turns, compaction events,
   memory rows, artifact metadata) in one transaction — fast and atomic
   because it all lives in the same database.
3. Object store: delete every artifact `content_ref` — idempotent, safe to
   retry if the job is interrupted.
4. Checkpointer: `adelete_thread` per `conversation_id`.
5. External vector index (unless colocated pgvector): delete-by-metadata
   on `user_id`.
6. Trace store: purge/redact through the provider's API or retention
   policy.
7. Mark the job complete and record it in an audit log **without**
   including the content just deleted (an audit log that re-stores PII you
   claimed to delete defeats the deletion entirely).

Steps 3-6 should ideally be a background job with per-step retry (not part
of the HTTP request that deletes rows in step 2) — if step 5 fails because
the external vector DB is down, step 2 is already complete and the job can
retry from step 5 alone without repeating the Postgres cascade.

## Trade-offs

- **Hard delete vs soft delete (tombstone)** — hard delete (the
  `ON DELETE CASCADE` schema in `persistence-schema.md`) is simple and
  immediately compliant with a deletion request, but destroys evidence an
  abuse investigation or audit trail might need. A tombstone (`deleted_at`
  plus a filter in the RLS policy) gives a recovery/investigation window,
  but PII lives on until the scheduled hard-purge job runs — meaning a
  tombstone **defers** retention rather than resolving it; you still need
  a hard-purge job running steps 2-6 once the retention window passes. The
  realistic production pattern: tombstone first, scheduled hard-purge
  after a grace period (e.g. 30 days).
- **Synchronous vs asynchronous jobs for steps 3-6** — synchronous (all
  steps in one request) gives instant certainty ("everything is deleted"
  at the 200 response), but the request can time out if one external API
  is slow, and partial failure becomes hard to retry granularly.
  Asynchronous (a job queue per step) tolerates partial failure but needs
  status tracking ("deletion in progress") and the user gets no instant
  confirmation.
- **Colocated vector index (pgvector) vs external** — colocation removes
  this gap entirely (it follows the ordinary `DELETE FROM memory_entries`,
  with no extra saga step), but a managed external vector DB is usually
  cheaper at scale and its search is more mature. This is the same
  trade-off noted in `persistence-schema.md` about the optional
  `embedding VECTOR(...)` column.

## In deepagents

`deepagents` runs no retention/deletion job of any kind — consistent with
`checkpointer`/`store` being **passed through unchanged** to
`langchain.agents.create_agent` (`deepagents` builds neither itself),
`[code]` — see
[`../systems/deepagents.md`](../systems/deepagents.md) §5. Consequently,
calling `checkpointer.adelete_thread(...)`/`store.adelete(...)` in steps
4-5 above is application code using exactly the same checkpointer/store
that was injected into `create_deep_agent` — not an API of `deepagents`
itself.

One additional cascade matters when `FilesystemBackend`/
`LocalShellBackend` is used: both read and write directly to host disk
(`root_dir`), and isolation between users is **not** the backend's
responsibility but that of a separate process/container per user,
`[code]` — see
[`../systems/deepagents.md`](../systems/deepagents.md) §Backend filesystem
(quoting `THREAT_MODEL.md`). If that backend holds per-user state
surviving across sessions (rather than a single-use sandbox that gets
discarded), deletion must sweep that directory too — entirely outside the
Postgres schema above.

## Sources

- `[docs]` LangGraph — `checkpointer.delete_thread`/`adelete_thread`
  ("removes all checkpoints and associated write records for a specified
  thread"), cited via Context7 from
  `docs.langchain.com/oss/python/langgraph/checkpointers`.
- `[docs]` LangGraph — `store.adelete(namespace, key)` and
  `store.asearch(namespace)` for enumerating keys before deletion, cited
  via Context7 from `docs.langchain.com/oss/python/langgraph/stores`.
- `[code]` LibreChat `packages/data-schemas/src/schema/message.ts` line 233
  (`messageSchema.index({ expiredAt: 1 }, { expireAfterSeconds: 0 })`) and
  `packages/data-schemas/src/schema/toolCall.ts` line 61 — real precedent
  for automatic TTL-index-based deletion (temporary chat/tool-call records
  that auto-expire). Postgres has no native TTL index like MongoDB; the
  equivalent pattern is a scheduled job (`pg_cron` or an external worker)
  scanning an `expired_at`/`deleted_at` column — recorded here as
  `[inferred]` pattern translation, not claimed as a built-in Postgres
  feature.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5,
  §Backend filesystem — a tier-1 reference already verified in Task 3,
  cited here without re-reading the source.
