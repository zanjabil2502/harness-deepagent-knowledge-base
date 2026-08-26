# Delta 06 — Workflow Agent

Base: [`../_base.md`](../_base.md). This file is **only** the difference. The
full rationale:
[`../../archetypes/06-workflow-agent.md`](../../archetypes/06-workflow-agent.md)
§Building this with deepagents.

## Replace

- **Triggers & routes**: `_base` triggers a turn through `POST /turns` +
  `GET /turns/{id}/events` (SSE, with a human watching in real time). This
  archetype **has no** real-time human — `api/routes/turns.py` is replaced
  by an event consumer (a webhook handler/cron/queue worker) calling
  `Orchestrator.run_turn(...)` directly, with the result written to a
  log/dashboard rather than streamed to a waiting HTTP connection.
  `[ours]` archetype 06: `create_deep_agent(...)` is placed as one node in
  a larger LangGraph graph (or behind a queue worker) triggered by an
  external event — deepagents handles "what the LLM does when called", not
  "when it is called", which is outside the library's responsibility.
- **Deriving `thread_id`**: `_base` accepts `thread_id` as a request
  parameter from a human client. Here `thread_id` is derived from the
  trigger event's idempotency key (e.g. a hash of a webhook's
  `delivery_id`), **not** from a human session/conversation — so a retry of
  the same event (a webhook retry, a queue restart) lands on the same
  checkpoint rather than creating a new run. `[ours]` archetype 06:
  `ARCHITECTURE.md` only states that the checkpointer is
  application-injected and says nothing about how `thread_id` is formed —
  this is our pattern, not something the library guarantees or documents.
- **Resolving `Scope`**: `ScopeMiddleware` (`_base`) reads `user_id` from an
  authenticated human HTTP request header — inapplicable here because the
  trigger isn't a human request. The `Scope` for one workflow run is derived
  from the **workflow's configuration** (the owning `user_id`, stored when
  the workflow was registered), read by the event consumer before calling
  `Orchestrator.run_turn(...)` — not from the same HTTP middleware.

## Add

- **Idempotency at the admission point**: the event consumer must enforce
  idempotency at the queue infrastructure level (dedupe by `delivery_id`)
  **in addition to** the `thread_id` idempotency above — two layers, because
  checkpointer resume prevents duplicate *LLM work*, not duplicate *tool
  side effects* that already happened before a crash (archetype 06's
  `## Common pitfalls`, point 1).
- **Safety gate**: `interrupt_on` for high-risk actions (e.g.
  `send_email: True`) is still installed even with no real-time human — its
  approval is asynchronous through a separate channel (a dashboard/Slack)
  rather than waiting on an SSE connection (which this archetype doesn't
  have). `[code]` sourced from `test_hitl.py`.
- **A workflow-level kill switch**: a database flag checked by the event
  consumer **before** calling `Orchestrator.run_turn(...)` for that
  workflow. `[ours]` archetype 06: `deepagents` has no built-in "stop every
  run" API — this is the application's orchestrator/queue layer's
  responsibility, stated explicitly so the scaffold doesn't wrongly assume
  `create_deep_agent` provides a built-in kill switch.

## Remove

- **`GET /turns/{turn_id}/events` (SSE)** — nobody is watching in real time;
  this archetype's observability comes through structured logs + OTel traces
  (`_base.md` §Observability is used as-is), not a stream.
- **`lifecycle/drain.py`'s `start_turn()`/`end_turn()` called from the SSE
  generator** (the `_base` pattern) — called from the event consumer
  instead; the mechanism (a gauge + `wait_empty` at shutdown) is unchanged.
