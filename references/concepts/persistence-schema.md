# Persistence schema

## Problem

An ad hoc agent state schema fails in a recurring pattern: history stored as
a flat list, so "edit a message then regenerate" overwrites the old history;
tool calls stored as a JSON field inside a message, so they can't be
queried/redacted per row; compaction replacing the original message content
directly (the transcript is lost too, not just the context trimmed); a
network retry on one turn creating a second turn because there is no
idempotency key; and one table missing its `user_id` column so it leaks
between users - a certainty in a codebase that lives long enough (§8.2).

The DDL below is the direct answer: pasteable into `psql` as-is.

## Pattern

The `CREATE TABLE` order already follows FK dependency order - run it top to
bottom.

```sql
-- ============================================================
-- Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
-- CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector, optional - only if
--                                          -- memory embeddings are stored in
--                                          -- Postgres, see memory_entries.

-- ============================================================
-- Identity & scope
-- ============================================================
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- [ours] A local users table exists here so this schema is runnable
-- standalone in psql. In a real deployment identity rows are often owned by
-- an external IdP (e.g. Supabase auth.users, Clerk) and this table becomes a
-- foreign table/view rather than the source of truth. Vanilla: no local
-- users table at all, with user_id in other tables just an opaque UUID with
-- no local FK.

-- ============================================================
-- Conversations & turns (an idempotency key per turn)
-- ============================================================
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);
CREATE INDEX conversations_user_id_idx ON conversations (user_id, created_at DESC);

-- One "turn" = one unit of user request -> agent response (including every
-- tool call within it). idempotency_key is sent by the client per turn
-- (e.g. a UUID the client generates on submit) so a network retry or a
-- duplicate submit doesn't create a second turn: a second INSERT with the
-- same (user_id, idempotency_key) fails the UNIQUE constraint, and the app
-- simply catches that error and returns the existing turn.
CREATE TABLE turns (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id),
    idempotency_key  TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'completed', 'failed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX turns_conversation_id_idx ON turns (conversation_id, created_at);

-- ============================================================
-- The transcript as a TREE, not a list
-- ============================================================
CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    parent_id        UUID REFERENCES messages(id) ON DELETE SET NULL,
    turn_id          UUID REFERENCES turns(id) ON DELETE SET NULL,
    user_id          UUID NOT NULL REFERENCES users(id),
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content          JSONB NOT NULL,  -- a parts array; artifact refs live here,
                                       -- see artifacts-and-canvas.md
    status           TEXT NOT NULL DEFAULT 'complete'
                       CHECK (status IN ('complete', 'streaming', 'error')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation_parent_idx ON messages (conversation_id, parent_id);
CREATE INDEX messages_conversation_created_idx ON messages (conversation_id, created_at);
CREATE INDEX messages_turn_id_idx ON messages (turn_id);

COMMENT ON COLUMN messages.parent_id IS
  'NULL = a root message in the conversation. Editing an old message = '
  'INSERTing a new row with the same parent_id as the old version (not an '
  'UPDATE) -> it branches.';

-- The active path is PERSISTED, not recomputed from timestamps. The naive
-- "the leaf with the largest created_at in the conversation" heuristic is
-- wrong as soon as the user switches back to an old branch and continues it
-- -- that branch's leaf is not the global max(created_at), yet it is what
-- should be the active path.
ALTER TABLE conversations
    ADD COLUMN active_leaf_id UUID REFERENCES messages(id) ON DELETE SET NULL;

COMMENT ON COLUMN conversations.active_leaf_id IS
  'A pointer to the message at the end of the active path the user is '
  'viewing/continuing. The active path = the walk from the root to this row '
  'through parent_id (no separate recursive algorithm is needed for '
  'resolution -- this pointer is the resolution). Updated by the app at two '
  'moments only, in the same transaction as the change that triggers it: '
  '(1) fork -- INSERT the new message, then UPDATE conversations SET '
  'active_leaf_id = <the new message id>; '
  '(2) branch switch -- the user picks an old branch, UPDATE active_leaf_id '
  'to that branch''s existing leaf (the message with no child in that '
  'branch, found once at switch time rather than recomputed on every '
  'render). See session-state.md for why this is persisted rather than '
  'computed.';

-- ============================================================
-- Tool calls as FIRST-CLASS transcript rows
-- ============================================================
CREATE TABLE tool_calls (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id   UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id),
    sequence     INT NOT NULL DEFAULT 0,  -- order within one message (>1 tool call/turn is possible)
    tool_name    TEXT NOT NULL,
    arguments    JSONB NOT NULL,
    result       JSONB,
    status       TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'success', 'error')),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (message_id, sequence)
);
CREATE INDEX tool_calls_message_id_idx ON tool_calls (message_id);
CREATE INDEX tool_calls_user_tool_idx ON tool_calls (user_id, tool_name, started_at DESC);

-- ============================================================
-- Compaction events -> pointing at the messages REPLACED, not deleting them
-- ============================================================
CREATE TABLE compaction_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id    UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id            UUID NOT NULL REFERENCES users(id),
    summary_message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    reason             TEXT NOT NULL DEFAULT 'token_threshold'
                          CHECK (reason IN ('token_threshold', 'manual', 'tool_result_evict')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE compaction_event_messages (
    compaction_event_id UUID NOT NULL REFERENCES compaction_events(id) ON DELETE CASCADE,
    message_id           UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id               UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (compaction_event_id, message_id)
);
CREATE INDEX compaction_event_messages_message_idx ON compaction_event_messages (message_id);

COMMENT ON TABLE compaction_events IS
  'Old messages are NOT deleted on compaction -- the transcript stays '
  'permanent. summary_message_id points at the new summary message; '
  'compaction_event_messages points at the original messages summarised. '
  'It is the model context (the ephemeral layer) that stops sending the '
  'original messages to the model, not the transcript losing its rows -- '
  'see session-state.md.';

-- ============================================================
-- Cross-session memory (Postgres + vector) -- the minimal rows for the
-- "Memory" layer in the 5-layer table; the full design is in
-- concepts/memory.md (the Cognition field, not written in this task).
-- ============================================================
CREATE TABLE memory_entries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    key         TEXT,
    value       TEXT NOT NULL,
    -- embedding VECTOR(1536),  -- enable after CREATE EXTENSION vector
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_entries_user_idx ON memory_entries (user_id, updated_at DESC);
```

### Row-Level Security - scope enforcement, not a manual `WHERE` (§8.2)

```sql
-- The app MUST set this session variable per connection/transaction BEFORE any query:
--   SET LOCAL app.current_user_id = '<the logged-in user uuid>';

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;  -- applies to the table owner too
-- NOTE: FORCE does not apply to superusers / BYPASSRLS. The application MUST
-- connect as a non-superuser role -- see isolation-and-scoping.md §The
-- prerequisite that voids all of it. Connecting as `postgres` = RLS with zero
-- effect.
CREATE POLICY conversations_scope ON conversations
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
CREATE POLICY messages_scope ON messages
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY tool_calls_scope ON tool_calls
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE memory_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY memory_entries_scope ON memory_entries
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE turns FORCE ROW LEVEL SECURITY;
CREATE POLICY turns_scope ON turns
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE compaction_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE compaction_events FORCE ROW LEVEL SECURITY;
CREATE POLICY compaction_events_scope ON compaction_events
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

-- compaction_event_messages is scoped through ITS OWN user_id column
-- (denormalised at insert time) rather than through a JOIN to
-- compaction_events/messages -- the same choice as the reason given in
-- Trade-offs for this junction table: a USING clause through a JOIN subquery
-- isn't sargable and is slower on large tables.
ALTER TABLE compaction_event_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE compaction_event_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY compaction_event_messages_scope ON compaction_event_messages
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

-- The same pattern applies to artifacts/artifact_versions/
-- message_artifact_refs (see artifacts-and-canvas.md) -- each table scoped
-- through its own user_id column rather than through a JOIN to
-- conversations. `current_setting(..., true)` (the second argument) makes
-- the policy fail closed to "no rows" if the session variable was never
-- set, rather than raising mid-request.
```

### Deliberately NOT given DDL here: the checkpointer

The `checkpoints`/`writes` tables belonging to the checkpointer library (e.g.
`langgraph-checkpoint-postgres`) are deliberately not redefined here. Their
schema `[docs]`:

```sql
CREATE TABLE checkpoints (
    thread_id             TEXT NOT NULL,
    checkpoint_ns          TEXT NOT NULL DEFAULT '',
    checkpoint_id           TEXT NOT NULL,
    parent_checkpoint_id   TEXT,
    type                    TEXT,
    checkpoint              BYTEA,
    metadata                 JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

Why they aren't part of this application schema: those tables are migrated
and owned by the checkpointer library itself, not by the application's
migrations - changing their shape (e.g. adding a `user_id` column) risks
breaking on a library update. The `thread_id` in that table is **equated by
convention** with `conversations.id` (not an FK - different subsystem,
different migration), and its scoping is enforced at the application level (a
thread is only requested for a `conversation_id` that passed the
`conversations` RLS), not by native Postgres RLS on the checkpoint tables
themselves. This is an honestly reported gap rather than a hidden one - see
`session-state.md` for why a checkpointer isn't the product's database.

## Trade-offs

- **A persisted `active_leaf_id` pointer vs a recursive resolution
  algorithm** - the alternative not chosen: store the tree as-is and compute
  the active path whenever needed through an explicit per-node rule (e.g.
  "at each branch point, the child with the largest `created_at` wins,
  recursively from the root"). That avoids an extra column plus the app's
  obligation to keep it in sync, but recursion per render is more expensive
  for deep trees, and "the newest child wins at each branch point" can still
  be wrong when a user edits two different branches then returns to the
  first - that rule needs supplementing with "which branch was last chosen"
  state at every point, which ends up being a per-node pointer anyway, only
  more complex than one pointer per conversation. We chose a single pointer
  (`active_leaf_id`) because its resolution is trivial (one column, one
  UPDATE per fork/switch) and unambiguous.
- **The junction table (`compaction_event_messages`) carrying its own
  `user_id`** even though it could be reached through a JOIN to
  `messages`/`compaction_events`. `[ours]` - vanilla: RLS through a subquery
  (`message_id IN (SELECT id FROM messages WHERE user_id = ...)`), which
  isn't sargable and is slower on large tables. We chose a direct scope
  column plus the redundancy trade-off (it must be written consistently in
  the same transaction as the insert) for the sake of a cheap RLS policy
  uniform across every table.
- **`version INT` vs a timestamp as the version** - discussed in
  `artifacts-and-canvas.md`, relevant here too because the same pattern
  could apply to `memory_entries` if a change history of memory facts is
  needed (the schema above deliberately adds no versioning to memory -
  YAGNI until there is a real need for "the history of how this memory
  changed").
- **Soft delete vs hard delete at this layer** - the schema above uses
  `ON DELETE CASCADE` (hard) down from `conversations`; if legal retention
  needs tombstones, change it to `deleted_at TIMESTAMPTZ` plus a filter in
  the RLS policy. The full trade-off is in `retention-and-deletion.md`.
- **`checkpoints`/`writes` not being covered by Postgres RLS** (see above)
  is a deliberate trade-off: keeping the checkpointer schema consistent with
  the upstream library vs uniform scope enforcement. If stricter
  multi-tenant isolation is needed at this layer, the alternative is a
  custom checkpointer adding its own scope column - not done here because
  deepagents passes the checkpointer through unchanged (see `In deepagents`
  below), so changing it means stepping outside the contract the application
  injected.

## In deepagents

The `checkpointer` and `store` used to fill the tables above (indirectly -
through the `thread_id = conversation_id` convention, not an FK) are passed
through **unchanged** by `deepagents` to `langchain.agents.create_agent`;
`deepagents` never builds a checkpointer/store of its own. `[code]` - see
[`../systems/deepagents.md`](../systems/deepagents.md) §5
(`deepagents/graph.py` lines 546-553, 922-931). So the
`messages`/`tool_calls`/`compaction_events` schema above is purely the
responsibility of the application calling `create_deep_agent` - no part of
`deepagents` writes to these tables.

## Sources

- `[code]` LibreChat `packages/data-schemas/src/schema/toolCall.ts`
  (`danny-avila/LibreChat`, read through
  `raw.githubusercontent.com/danny-avila/LibreChat/main/...`) - real
  precedent for "tool calls as a separate collection/table" referencing
  `messageId`/`conversationId`, with `blockIndex`/`partIndex` for ordering
  within one message (mapped to the `sequence` column in `tool_calls` above,
  an `[ours]` naming simplification).
- `[code]` LibreChat `packages/data-schemas/src/schema/message.ts` - its
  `parentMessageId` line confirms the tree pattern through a per-row parent
  pointer (not a list), and its indexed `tenantId` column sitting alongside
  a schema that still runs single-tenant is real precedent for "the scope
  column is `user_id` today, `tenant_id` is the migration path" in §8.2.
  `[ours]` - the schema above deliberately doesn't copy the `tenant_id`
  column now: §8.2 asks for a scope object at the application level, not a
  DB column, so adding a column used nowhere is YAGNI until multi-tenancy is
  genuinely built (the later migration is simply `ALTER TABLE ... ADD COLUMN
  tenant_id`, demanding no table redesign).
- `[code]` Open WebUI `backend/open_webui/models/chats.py` - `Chat.chat =
  Column(JSON)`: the entire message tree (`parentId`/`childrenIds`/`currentId`)
  lives in **one JSON column per chat**, not normalised SQL rows. This
  contrasts directly with the `[ours]` choice above (normalised `messages`
  rows with a `parent_id` FK) - Open WebUI's vanilla is one JSON blob per
  conversation. We chose normalised rows because we need first-class
  per-message tool calls and per-row RLS, neither of which is obtainable
  from the contents of a JSON blob.
- `[docs]` LangGraph - the `checkpoints`/`writes` schema and the
  `BaseCheckpointSaver` contract, cited via Context7 from
  `docs.langchain.com/oss/python/langgraph/checkpointers`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 - for
  the "In deepagents" section (a tier-1 reference already verified in Task
  3, cited here without re-reading the source).
