# Harness Blueprint template

Copy this file per project. Fill in every section - don't delete the frame
lines already filled in from the KB's framework; add the project's specific
decisions in the columns provided.

## Project summary

- **Name:**
- **Short description:**
- **Domain (general/vertical):**

## Archetype

- **Primary archetype:**
- **Secondary archetype (if hybrid):**

| Axis | This project's value |
|---|---|
| Blast radius | |
| Artifact | |
| Horizon | |
| Human control | |
| Domain surface | |
| Interface | |

## The 7 harness axes

The last column is the reading to do before filling in the decision column -
without it, an axis gets filled from habit rather than from an already-mapped
trade-off.

| # | Axis | Decision | Weigh first |
|---|---|---|---|
| 1 | Loop shape | | [`agent-loop`](concepts/agent-loop.md), [`planning`](concepts/planning.md) |
| 2 | Context | | [`context-engineering`](concepts/context-engineering.md), [`memory`](concepts/memory.md) |
| 3 | Tool surface | | [`tool-design`](concepts/tool-design.md), [`mcp`](concepts/mcp.md), [`structured-output`](concepts/structured-output.md) |
| 4 | Delegation | | [`delegation`](concepts/delegation.md), [`code-orchestration`](concepts/code-orchestration.md) - are subagents chosen by the model per turn, or dispatched from code? |
| 5 | State & resume | | [`session-state`](concepts/session-state.md), [`streaming-protocol`](concepts/streaming-protocol.md) |
| 6 | Safety gate | | [`human-in-the-loop`](concepts/human-in-the-loop.md), [`guardrails`](concepts/guardrails.md) - each point: policy + enforcement point + failure mode |
| 7 | Capability routing & policy | | [`policy-as-data`](concepts/policy-as-data.md), [`skill-composition`](concepts/skill-composition.md), [`multilingual`](concepts/multilingual.md) |

## Interface & output

| Question | Decision | Weigh first |
|---|---|---|
| Who calls this harness - our own UI, an editor, or another agent? | | [`agent-protocols`](concepts/agent-protocols.md) |
| Any output beyond prose that needs rendering (tables, charts, diagrams, formulas)? | | [`scaffolds/skills/`](scaffolds/skills/README.md) |

## State & data

Five layers, with one dividing line: the BE owns the truth, the AI owns a
projection.

| Layer | Store | Lifetime | Owner | Project decision |
|---|---|---|---|---|
| Transcript | Append-only Postgres | permanent | BE | |
| Model context | Computed, Redis cache | 1 call | Harness | |
| Run state | Checkpointer (Postgres) | 1 run, resumable | Harness | |
| Memory | Postgres + vector | cross-session | BE + AI | |
| Artifacts | S3/GCS + metadata rows | permanent, versioned | BE | |

## Guardrails

Every point must have a policy + an enforcement point + a failure mode.
Fail-open for moderation, fail-closed for authorisation - undecided, the
default becomes an accident.

| # | Point | Policy | Enforcement point | Failure mode |
|---|---|---|---|---|
| 1 | Input | | | |
| 2 | Retrieval/context | | | |
| 3 | Tool/action | | | |
| 4 | Output | | | |
| 5 | Loop | | | |
| 6 | System | | | |

## Deployment & resources

One agent turn is a mixed workload - don't force one pod to do all of it.

| Component | Bound | HPA signal | Project decision |
|---|---|---|---|
| Gateway / SSE | IO | active connections | |
| Orchestrator | IO-dominant | in-flight turns | |
| Tool executor | CPU + memory | queue depth, CPU | |
| Retrieval / embedding | GPU or CPU | batch queue, GPU utilisation | |
| State store | IO/disk | not a pod | |

- **Initial topology (monolith/split):**

## Isolation & scoping

- **Default:** multi-user (`user_id`), not multi-tenant unless stated otherwise.
- **This project's scope object:**
- **Enforcement (RLS/other):**

## The deepagents config

```yaml
# fill in the actual deepagents configuration: subagents, middleware, tools, checkpointer
```

## Production-readiness checklist

The mandatory gate before a scaffold counts as finished. This is the KB's only
copy of this checklist - reference this section from other files rather than
copying it.

- [ ] Tracing & observability
- [ ] An eval harness (including multilingual)
- [ ] Budget & cost guards
- [ ] Retry, timeout, idempotency
- [ ] A context overflow policy
- [ ] Secrets & config management
- [ ] A human gate + audit log
- [ ] Prompt & policy versioning
- [ ] A kill switch & sandbox
