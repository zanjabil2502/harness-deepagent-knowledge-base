# Replay & forensics

## Problem

A real incident: one agent run does something it shouldn't — calls a
destructive tool, leaks something, wanders for 40 steps — and the team
needs to know **exactly** what happened in **that** run. This differs from
`evaluation.md`: it is not running many golden cases against a frozen
world to detect regressions, but reconstructing **one real execution that
already happened**, in a variable, uncontrolled world, for investigation.
Without a sufficient recording, "what happened" can only be guessed from
the final result — the tool call's actual arguments, the raw result it
received, which guardrail decisions fired or didn't, the model/prompt/
threshold versions active at the time — and if any of those went
unrecorded, the gap is permanent for that run and cannot be filled later.

The second problem: what must be recorded has to be decided **before** the
incident, not after — you cannot add logging to an incident retroactively.
A field that silently goes unrecorded (e.g. the system prompt version
actually in force, a tool call's raw arguments) is a gap discovered
precisely when it is most needed: during a live investigation.

## Pattern

### What is already recorded, and what isn't

`persistence-schema.md` already provides most of the raw material — this
file **proposes no new schema**, it only maps what suffices and what
remains a gap:

- **Per-step checkpoints** (`checkpoints`/`writes`, owned by the
  checkpointer library, with `thread_id` matched by convention to
  `conversations.id`) — the full graph state at every step boundary,
  enough to **re-run** execution exactly from that point (see
  §Reconstruction vs re-execution below). Its weakness is reported
  honestly in `persistence-schema.md`: the bytes are opaque, they are not
  covered by RLS, and they cannot be queried per field (you cannot
  `SELECT` a particular tool call argument out of a checkpoint blob
  without deserialising it).
- **`tool_calls`** (`message_id`, `sequence`, `tool_name`, `arguments`
  JSONB, `result` JSONB, `status`, timestamps) — complements the
  checkpoint weakness above: an ordinary table that can be queried ("show
  every tool call by this user with `tool_name=X` between 02:00 and
  03:00") with nothing to deserialise.
- **Gaps the Task 4 schema does not close** (reported here, not redesigned
  — out of scope for that task): (a) the model version actually used for
  that run — model versions change over time, and replaying yesterday's
  incident against today's model is not a faithful reconstruction; (b) the
  guardrail version/thresholds active at the time — the same gap already
  flagged in `guardrails.md` §In deepagents point 6 ("no built-in audit
  table"); (c) the active system prompt version — already flagged in this
  KB's production-readiness gate ("Prompt & policy versioning: cannot roll
  back"). All three need an **explicit version marker stored alongside the
  run** (e.g. as part of turn/trace metadata), rather than being assumed
  reconstructable from today's code — today's code is not the code that
  ran when the incident happened.
- **Per-step guardrail decisions** — have no home in the Task 4 Postgres
  schema (the `tool_calls` table records a tool's *result*, not *why* a
  guardrail let it through or blocked it). The right home is the
  observability trace (`observability.md` §Span per step), **provided**
  that trace's retention is long enough for investigation — if traces are
  deleted faster than the incident investigation window, guardrail
  decisions for old runs can no longer be reconstructed from anywhere.

### Reconstruction vs re-execution — two different activities under one word "replay"

- **Reconstruction (read-only)** — assembling a timeline from checkpoint
  history + `tool_calls` + already-recorded traces, without re-running
  anything. Always safe (no side effects, no extra cost), always possible
  as long as the recording still exists.
- **Re-execution** — continuing the graph from a specific checkpoint, or
  re-running the same input, and letting it run again. This answers a
  **different question** from reconstruction: not "what happened then" but
  "what happens if it runs now (with today's code/model/guardrails)" —
  useful for verifying a fix, but not forensic evidence about the original
  incident if the running code has changed since.

For forensic re-execution, tool calls **must** run through a mock/dry-run
implementation, never real destructive tools — unlike the `evaluation.md`
replay harness, which was designed against frozen tool responses from the
start; the risk here is higher because the input originates from a real
incident that may well have triggered a destructive action — re-executing
it literally repeats the damage.

## Trade-offs

- **Full trace/checkpoint retention (for forensics) vs storage cost plus
  retention/privacy obligations** (`retention-and-deletion.md` already
  defines deletion policy for application data) — forensics wants to keep
  things as long as possible, retention/privacy wants to delete on
  schedule or on request. Resolve it by tying trace/checkpoint retention
  to the retention schedule **already** defined for the data it derives
  from (not a second, separate retention clock) — cited, not redesigned
  here.
- **Reconstruction only vs re-execution** — reconstruction is always safe
  but can only answer from what was **already** recorded (if a field was
  never captured, reconstruction cannot fill it in); re-execution can
  reveal new behaviour (e.g. "does this fix address the case?") but has
  real cost (more model/tool calls) and risks side effects unless tool
  calls are mocked — for incident investigation, mocking is **mandatory**,
  not optional.
- **Checkpoints (literal graph state, executable from there) vs
  application tables (`tool_calls`/`messages`, queryable across many
  incidents)** — both are needed for different purposes; neither replaces
  the other. This duality is already established in
  `persistence-schema.md` and is not re-argued here.

## In deepagents

The per-step checkpoints that make re-execution possible in principle come
from the `checkpointer` that `deepagents` passes **through unchanged** to
`langchain.agents.create_agent` — `deepagents` never builds a checkpointer
of its own, and never restricts the capabilities of the one the
application injects. `[code]` — cited from `../systems/deepagents.md` §5
(State & resume), `persistence-schema.md` §checkpointer.

LangGraph (the foundation under `create_agent`/`create_deep_agent`)
documents this feature officially as **"time travel"**: every checkpoint
is stored under the key `(thread_id, checkpoint_id)`, and resuming from a
particular checkpoint (not merely the latest) is done by passing
`config={"configurable": {"thread_id": ..., "checkpoint_id": ...}}` to
`invoke(None, config)` — an input argument of `None` means "continue from
stored state" rather than starting fresh. A thread's checkpoint history is
readable through `get_state_history(config)`. `[docs]` —
`docs.langchain.com/oss/python/langgraph/use-time-travel`. `deepagents`
neither extends nor restricts this API — the `checkpointer` API it exposes
is exactly LangGraph's, because `deepagents` merely passes it through.

The concrete consequence for the patterns above: forensic re-execution
(from a specific checkpoint) and `evaluation.md` regression replay (from
the original input against frozen tools) technically use the same
`checkpointer` mechanism — they differ only in **starting point**
(mid-run checkpoint vs the start of a new run) and **whether tool calls
are mocked** (forensics: mandatory; regression: designed that way from the
outset) — not two separate systems to build.

## Sources

- `[code]` [`persistence-schema.md`](persistence-schema.md) §checkpointer,
  the `tool_calls` table, §In deepagents — the raw material for
  reconstruction (checkpoints plus application tables), and the gap that
  checkpoints are not covered by RLS and not queryable per field; cited
  without proposing a new schema.
- `[code]` [`guardrails.md`](guardrails.md) §In deepagents point 6 — the
  "no built-in audit table" gap for gate decisions, cited again as the
  same gap for per-step guardrail decisions.
- `[code]` [`observability.md`](observability.md) §Span per step — the
  right home for per-step guardrail decisions, provided trace retention is
  long enough.
- `[code]` [`evaluation.md`](evaluation.md) §Golden transcript + replay
  harness — referenced to distinguish regression replay from forensic
  replay; written in the same task, not re-argued here.
- `[code]` [`retention-and-deletion.md`](retention-and-deletion.md) — the
  application data deletion policy underpinning the argument that
  trace/checkpoint retention follows an existing schedule rather than a
  second clock.
- `[docs]` LangGraph "time travel" —
  `docs.langchain.com/oss/python/langgraph/use-time-travel`, resuming from
  a specific checkpoint via `config={"configurable": {"thread_id":,
  "checkpoint_id":}}` plus `invoke(None, config)`, and
  `get_state_history(config)`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5
  (State & resume) — `checkpointer`/`store` passed through unchanged by
  `deepagents`; a tier-1 reference verified in Task 3, cited without
  re-reading `deepagents` source in this task.
