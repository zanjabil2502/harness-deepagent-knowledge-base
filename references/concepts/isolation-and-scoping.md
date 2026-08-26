# Isolation & scoping

## Problem

"Multi-user" and "multi-tenant" are often used interchangeably despite being
different isolation models, and choosing wrongly at the start is expensive
in both directions: building full multi-tenancy (schema-per-tenant, tenants
as first-class entities in every query) when the product has only one kind
of customer (individuals) is over-engineering that adds complexity with no
buyer; conversely, hardcoding `user_id` into queries with no explicit
migration path makes adding tenants later a large schema migration rather
than a column addition.

The second problem is more dangerous: the most common way to enforce scope
is `WHERE user_id = :current_user` in every query — and there **will
certainly** be one query that forgets it once the codebase lives long enough
(a new query written in a hurry, a join missing the scope on one side, an
admin script that's "just one-off"). That one query missing its filter is a
leak of another user's data, instantly, with no visible error — the request
still succeeds with a 200, only its content belongs to someone else.

## Pattern

### Multi-user vs multi-tenant

| Axis | Multi-user | Multi-tenant |
|---|---|---|
| Isolation unit | One `user_id` row | One organisation (`tenant_id`), containing many `user_id`s |
| Scope object | `(user_id)` | `(tenant_id, user_id)` |
| Data model | Every table `user_id`-scoped, flat | `user_id`-scoped tables **plus** a `tenant_id` column/context bounding things before `user_id` |
| Who sees whom | User A never sees user B's data, full stop | Users within the same tenant can share resources (a workspace, billing, cross-user admin); users of other tenants never see anything |
| Real examples | Personal ChatGPT, personal Claude.ai | A Slack workspace, a Notion workspace, B2B SaaS products |
| Complexity | Low — one scope column, one policy | Higher — two scope levels, cross-user admin policy within a tenant, plus a possible colocation vs physical isolation decision per tenant |

This project's assumption (§8.2, per the global constraint): **multi-user
today, multi-tenancy as a migration path** — not built out from the start.

### A scope object, not a hardcoded `user_id`

All data access goes through one **scope object** whose shape changes as the
product grows while its usage points in the code do not:

```
Today:            scope = (user_id,)
After migration:  scope = (tenant_id, user_id)
```

Code calling queries/setting the RLS context always goes through this scope
object rather than inserting a raw `user_id` in each separate place. The
consequence: adding `tenant_id` later means changing the **scope object's
shape in one place** plus adding a column and new DB policies, not
retracing every application query ever written. This is consistent with
`persistence-schema.md`'s decision: the Task 4 DDL **deliberately doesn't**
add a `tenant_id` column now even though industry precedent (LibreChat)
already has one — the YAGNI argument being that a column used nowhere only
adds surface with no benefit, and the later migration (`ALTER TABLE ... ADD
COLUMN tenant_id`) demands no table redesign because the scope object is
already the single point that changes.

### Why RLS rather than a manual `WHERE`

Enforcement lives in **Postgres Row-Level Security**, not a manual `WHERE`
per query. The reason is exactly `## Problem`: one query forgetting the
filter = a cross-user leak, and that will certainly happen in a codebase
that lives long enough — this isn't speculation, it is a statement about a
human error rate that doesn't decline over time; what declines is the
**number of places where that error can occur**. A manual `WHERE` has one
enforcement point per query (N failure points, N = every query ever written
and yet to be written). RLS has one enforcement point per table, evaluated
by Postgres itself at row level **regardless of the query's shape** — even
`SELECT *` with no `WHERE` at all returns only rows belonging to the active
scope, because Postgres inserts the policy predicate into the execution plan
before the query runs, rather than depending on the application to write it
correctly.

The concrete implementation is exactly what `persistence-schema.md` already
pins down — this file **doesn't change it**, only explains its reasoning:

```sql
-- The app MUST set this session variable per connection/transaction BEFORE any query:
SET LOCAL app.current_user_id = '<uuid of the logged-in user>';

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;  -- applies to the table owner too
CREATE POLICY conversations_scope ON conversations
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
```

Three details make this pattern genuinely fail-closed rather than merely
fail-safe-in-the-common-case:

- **`FORCE ROW LEVEL SECURITY`** — without it, the table owner role (usually
  the one the application connects as) **bypasses** RLS entirely. RLS
  enabled but not forced is RLS that does nothing for a normal application
  connection.
- **`current_setting(..., true)`** — the second argument `true` makes
  `current_setting` return `NULL` (rather than raising) if the session
  variable was never set. `NULL = user_id` is always `false` in SQL, so the
  policy falls to "no rows visible" — failing closed to empty, not open to
  every row, and not crashing the request.
- **Connection pooling is a new leak vector that must be guarded
  explicitly** — if a pooled connection is reused across users without
  `SET LOCAL` being reset per request/transaction, a `current_setting` that
  "wasn't reset" isn't `NULL` but the previous user's value. `SET LOCAL`
  (not `SET`) is used deliberately because it ends automatically at the
  transaction boundary — but the application must still call it in **every**
  new transaction, not once per connection.

### The prerequisite that voids all of it: the app must not connect as a superuser

`FORCE ROW LEVEL SECURITY` makes policies apply to the **table owner**. It
does **not** apply to superusers or roles with `BYPASSRLS` — both bypass
policies entirely. `[docs]` PostgreSQL: *"Superusers and roles with the
BYPASSRLS attribute always bypass the row security system."*

The consequence is harsh: an application connecting as `postgres` has RLS
enabled, forced, with policies — and **protecting zero rows**.

What makes this dangerous isn't the mistake but its **silence**: the catalog
audit stays green. `relrowsecurity = t`, `relforcerowsecurity = t`,
`policies > 0` are all true, and none of them measures whether the role the
application uses is subject to those policies. `[ours]` The vanilla approach
is to check the catalog as above and declare it sufficient; we diverge
because that check passes on a configuration protecting nothing.

**What to do instead:**

```sql
CREATE ROLE app_rw LOGIN PASSWORD '...' NOBYPASSRLS;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rw;
-- then enforce it as an invariant, not as a note:
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw' AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'app_rw can bypass RLS';
  END IF;
END $$;
```

**The only valid evidence** is running a cross-user query **as the
application role** and seeing it return zero rows — not reading the catalog.
This was found while using this KB to build a real project: an isolation
test run as `postgres` passed while proving nothing, and only failed
(correctly) once moved to a non-superuser role.

## Trade-offs

- **RLS vs a manual `WHERE`** — a manual `WHERE` is easier to trace locally
  (read one function, see all its filters right there, with no DB session
  state outside the query text to know about) but its correctness depends
  100% on the discipline of every query author, including migrations, admin
  scripts, and raw ORM queries that easily forget. RLS moves that invariant
  into the database, enforced even for queries written by someone else in
  the future who doesn't know the rule exists — at a cost: every DB
  connection (including those created by pools/background workers) must
  discipline itself to set `app.current_user_id` per transaction, and RLS
  predicates through subqueries/JOINs aren't always sargable (discussed in
  `persistence-schema.md` for `compaction_event_messages` — a direct scope
  column chosen over a JOIN for the sake of a cheap query planner, the same
  pattern applying to any indirectly scoped table).
- **`(user_id)` now vs `(tenant_id, user_id)` from the start** — adding
  `tenant_id` from day one avoids a later schema migration but adds
  complexity (a column, an index, a policy, the "which tenant admin may see
  whom" decision) for a need with no buyer yet — YAGNI until multi-tenancy
  is genuinely built. This is the same decision `persistence-schema.md`
  already made, not a new one in this file.
- **Shared-schema + RLS vs schema-per-tenant vs database-per-tenant** —
  relevant once the migration to multi-tenancy actually happens.
  Shared-schema (one schema, `tenant_id`/`user_id` columns, RLS) is cheap
  for many small tenants (one migration covers all), but isolation is "only"
  as strong as the RLS policy. Schema-per-tenant gives stronger isolation (a
  cross-tenant query bug is harder to write — different namespaces) at an
  operational cost growing linearly with tenant count (migrations run N
  times). Database-per-tenant gives the strongest isolation (the blast
  radius to other tenants is zero, suited to a single on-prem enterprise
  customer — in that case the whole database **does** belong to one tenant
  and isolation comes free) but is the most expensive for many small
  tenants. This project's assumption (multi-user first) makes shared-schema
  + RLS the default; the others become relevant only if an
  enterprise/on-prem-per-customer segment appears.

## In deepagents

`deepagents` has no notion of users or tenants at all — scoping is 100% the
calling application's responsibility, consistent with the "the BE owns the
truth" pattern in `session-state.md`. Two concrete points where the
application must inject scope:

- **The checkpointer** — the application passes `thread_id` to the
  `checkpointer` injected into `create_deep_agent`, and it is **equated by
  convention** with `conversations.id` (not an FK — different subsystem,
  different migration; established in `persistence-schema.md`). Its scoping
  is enforced at the application level (a thread is only requested for a
  `conversation_id` that already passed Postgres RLS on the `conversations`
  table), **not** by native Postgres RLS on the checkpointer library's own
  `checkpoints`/`writes` tables — a gap reported honestly in
  `persistence-schema.md`, repeated here because this file is precisely
  about scope enforcement: if stricter multi-tenant isolation reaching the
  checkpoint layer is needed, that requires a custom checkpointer, not
  something that comes free from application table RLS.
- **`StoreBackend(namespace=...)`** — the official scoping *hook* for
  durable cross-thread state. From the documentation:
  `namespace=lambda rt: (rt.server_info.user.identity,)` for per-user
  isolation; the same pattern simply extends to
  `(rt.server_info.tenant.id, rt.server_info.user.identity)` once the
  migration to multi-tenancy happens — exactly following the `(user_id)` →
  `(tenant_id, user_id)` scope object above. `[code]`+`[docs]` —
  [`../systems/deepagents.md`](../systems/deepagents.md) §Filesystem
  backend.

`FilesystemBackend`/`LocalShellBackend` (reading/writing directly to the
host disk) have **no** scoping *hook* — isolation between users for both has
to be built outside the backend (a separate process/container per user), a
fact already recorded in `deepagents.md` and `retention-and-deletion.md`.
`[code]` — [`../systems/deepagents.md`](../systems/deepagents.md)
§Filesystem backend.

## Sources

- `[code]` [`persistence-schema.md`](persistence-schema.md) — the RLS DDL
  (`FORCE ROW LEVEL SECURITY`, `USING`/`WITH CHECK`,
  `current_setting(..., true)`) already executed against a live Postgres 16,
  with all ten `user_id`-bearing tables carrying forced RLS policies (Task
  4) — this file doesn't change that DDL, only explains its reasoning in
  more depth.
- `[code]` [`session-state.md`](session-state.md) — the
  `thread_id = conversation.id` convention and the BE-owns-truth vs
  AI-projection split that underpins why scoping is enforced at the
  application/DB layer rather than in `deepagents`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Filesystem backend — a tier-1 reference verified in Task 3, cited
  without re-reading the source.
- `[code]` LibreChat `packages/data-schemas/src/schema/message.ts` — an
  indexed `tenantId` column sitting alongside a schema that still runs
  single-tenant, the real precedent already cited in
  `persistence-schema.md` for the "scope object is `user_id` today,
  `tenant_id` is the migration path" argument; re-cited here as a
  reference, not re-read.
