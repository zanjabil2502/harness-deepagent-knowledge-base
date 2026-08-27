# Artifacts & canvas

## Problem

Artifacts (documents, code, canvases) produced by an agent tend to be large and
repeatedly edited. Putting their bytes straight into a transcript message column
breaks two things at once: the transcript balloons with every edit (each edit =
a new message holding a full copy), and the model context balloons every time
history is reloaded into the model - even though the model rarely needs the full
content, only that the artifact exists and which version is under discussion.
Second problem: without an explicit version, "edit the artifact" becomes an
overwriting `UPDATE` - the change history and any undo capability are gone.

## Pattern

### The by-reference rule

- **The transcript** stores `artifact_id + version` - a pointer, not bytes.
- **The model context** stores a handle (`artifact_id`, title, kind) plus a
  short summary - enough to know the artifact exists and to reference it
  through a tool, without its content consuming tokens on every call.
- **The actual bytes** live in an object store (S3/GCS); Postgres holds
  metadata plus the object key.

### The versioning schema

Extends the tables in [`persistence-schema.md`](persistence-schema.md) -
run after that schema (it needs `users` and `messages`).

```sql
CREATE TABLE artifacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    kind        TEXT NOT NULL CHECK (kind IN ('text', 'code', 'image', 'sheet')),
    title       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX artifacts_user_idx ON artifacts (user_id, created_at DESC);

CREATE TABLE artifact_versions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id      UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id),
    version          INT NOT NULL,
    edit_mode        TEXT NOT NULL CHECK (edit_mode IN ('initial', 'rewrite', 'patch')),
    storage_backend  TEXT NOT NULL DEFAULT 's3',
    content_ref      TEXT NOT NULL,  -- object store key, e.g. s3://bucket/artifacts/<id>/<version>
    byte_size        BIGINT,
    checksum         TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, version)
);
CREATE INDEX artifact_versions_artifact_idx ON artifact_versions (artifact_id, version DESC);

-- By-reference with real integrity: the transcript holds artifact_id +
-- version through a row that can carry an FK, not just a field inside
-- messages.content JSONB (Postgres cannot FK into JSONB).
CREATE TABLE message_artifact_refs (
    message_id   UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    artifact_id  UUID NOT NULL,
    version      INT NOT NULL,
    user_id      UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (message_id, artifact_id, version),
    FOREIGN KEY (artifact_id, version) REFERENCES artifact_versions (artifact_id, version)
);

ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY artifacts_scope ON artifacts
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE artifact_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY artifact_versions_scope ON artifact_versions
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE message_artifact_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_artifact_refs FORCE ROW LEVEL SECURITY;
CREATE POLICY message_artifact_refs_scope ON message_artifact_refs
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
```

`version` is a monotonic integer per `artifact_id` (`UNIQUE (artifact_id,
version)`), not a timestamp. `[ours]` - vanilla, as demonstrated by Vercel's
`ai-chatbot` `lib/db/schema.ts`: the `document` table uses a **composite
primary key `(id, createdAt)`**, deriving the version from `createdAt` with
no separate version column. `[code]` - read directly from
`raw.githubusercontent.com/vercel/chatbot/main/lib/db/schema.ts`. We chose an
explicit integer because timestamps aren't guaranteed monotonic under
concurrent writes or clock skew, and a human version ("v3") reads more
clearly than a raw timestamp in the UI - the consequence being that the app
must compute `MAX(version) + 1` inside the same transaction as the insert
(or `SELECT ... FOR UPDATE` on the `artifacts` row to prevent a race).

Every edit - rewrite or patch - is an `INSERT` of a new `artifact_versions`
row, never an `UPDATE` of existing content. This is confirmed as real
practice in `ai-chatbot`: `saveDocument()` in `lib/db/queries.ts` lines
323-325 calls `db.insert(document)` for every document save, invoked from
both edit tools below. `[code]`.

### Full rewrite vs patch

`ai-chatbot` exposes **two separate tools** for editing one artifact,
`[code]` read from `lib/ai/tools/update-document.ts` and
`lib/ai/tools/edit-document.ts`:

| Aspect | Full rewrite (`updateDocument`) | Patch (`editDocument`) |
|---|---|---|
| Original tool description | *"Full rewrite of an existing artifact. Only use for major changes where most content needs replacing. Prefer editDocument for targeted changes."* | *"Make a targeted edit to an existing artifact by finding and replacing an exact string. Preferred over updateDocument for small changes. The old_string must match exactly."* |
| Mechanism | The model regenerates the **entire** content through `streamText` (a fresh LLM call, `smoothStream`), the result overwriting the full draft | The app performs a plain `content.replace(old_string, new_string)` (or `replaceAll` if `replace_all: true`) - no second LLM call |
| Token/latency cost | High - proportional to the whole document's length; the LLM has to re-emit parts that didn't change at all | Low - the model emits only `old_string`/`new_string`, independent of document length |
| Failure mode | Can drift silently - unintended parts get regenerated differently | Explicit and safe - hard-fails if `old_string` isn't found exactly in `document.content` (`"old_string not found in document"`), never overwriting the wrong thing |
| When to use | Large restructuring, more than half the content changing, or the initial draft (`onCreateDocument`) | Targeted changes - a typo, one function, one paragraph; this is the one **preferred by default** according to its own tool description |

Both end in the same `INSERT` of a new version row (see "The versioning
schema" above) - the difference is only in *how* the new content is
produced, not *how* it is stored. `edit_mode` in `artifact_versions` records
which was used (`'rewrite'` / `'patch'` / `'initial'` for the first draft)
so the version history can answer "was this a full regeneration or a small
patch" without opening a diff.

## Trade-offs

- **By-reference vs inline** - inline (artifact bytes directly in
  `messages.content`) is simpler to read back (no join to the object store),
  but violates the transcript vs model context boundary: every history
  reload drags the full artifact bytes into context. By-reference needs one
  extra round-trip (fetching `content_ref`) but keeps the context cheap.
- **Rewrite vs patch** - rewrite is cheap to implement (one code path: "ask
  the model to rewrite it") but expensive in tokens and prone to silent
  drift; patch is token-cheap and fail-safe but needs a sufficiently unique
  `old_string` (the model must include surrounding context so the match
  isn't ambiguous) - `ai-chatbot` handles that with an explicit instruction
  in the tool description ("Include 3-5 surrounding lines for uniqueness"),
  not separate validation.
- **`version INT` vs `createdAt` as the version** - discussed above; the
  trade-off in essence is simple-but-race-prone (timestamps) vs
  explicit-but-needing-insert-coordination (a monotonic integer).
- **One `artifact_versions` row per edit forever** - full history plus undo
  for free, but storage grows linearly with edit count. At very high edit
  volume (e.g. a realtime canvas, keystroke by keystroke) this pattern needs
  to become periodic checkpoints plus diffs rather than one row per
  keystroke - not yet relevant for document/code-level artifacts edited
  through discrete tool calls as above.

## In deepagents

`deepagents` has no built-in "artifact"/versioned-document primitive -
there is no `update_document`/`edit_document` tool in any base stack
(`create_deep_agent`). What it does provide is a filesystem backend usable
as the durable layer beneath one, `[code]` - see
[`../systems/deepagents.md`](../systems/deepagents.md) §Filesystem backend:

| Backend | Which layer here it suits |
|---|---|
| `StateBackend` (default) | Ephemeral drafts during one run - not where *permanent* artifacts live |
| `FilesystemBackend` / `LocalShellBackend` | Working files on the host disk - isolation between users is the caller's responsibility, unsuitable for multi-user artifacts without a separate process/container |
| `StoreBackend(namespace=...)` | Closest to "durable across threads" - but still has no notion of versions or `edit_mode`; the app layers versioning on top |
| `CompositeBackend` | The hybrid pattern: route `/artifacts/` to `StoreBackend`, the rest to `StateBackend` - the app still has to write its own `artifact_versions` schema (the tables above) for structured metadata |

The consequence: the `artifacts`/`artifact_versions`/`message_artifact_refs`
schema above, and the rewrite-vs-patch decision as two separate tools, is
something that must be written explicitly as application tools (like
`update-document.ts`/`edit-document.ts` in `ai-chatbot`) and attached
through the `tools=[...]` parameter of `create_deep_agent` - not something
that comes from `deepagents` itself.

## Sources

- `[code]` Vercel `ai-chatbot` (`vercel/chatbot`, the repo renamed from
  `ai-chatbot`) `lib/db/schema.ts` - the `document` and `suggestion` tables,
  the composite primary key `(id, createdAt)`; read in full via
  `raw.githubusercontent.com/vercel/chatbot/main/lib/db/schema.ts`.
- `[code]` `lib/ai/tools/update-document.ts` - the full-rewrite tool, its
  verbatim description, the `documentHandler.onUpdateDocument` call.
- `[code]` `lib/ai/tools/edit-document.ts` - the patch tool, its verbatim
  description, the `content.replace`/`replaceAll` mechanism plus the
  explicit error when `old_string` isn't found.
- `[code]` `lib/db/queries.ts` lines 310-325 (`saveDocument`) - confirmation
  that both tools end in `db.insert(document)`, not `update`.
- `[code]` `artifacts/text/server.ts` - confirmation that `onUpdateDocument`
  issues a fresh `streamText` (a full LLM call) for the rewrite case.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Filesystem backend - a tier-1 reference already verified in Task 3,
  cited here without re-reading the source.
