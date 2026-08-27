---
name: agent-harness-kb
description: Use when designing an agent harness, building on deepagents, or reviewing an agent project — loop shape, context engineering, tools & delegation, guardrails, and idiomatic deepagents construction. Four modes: looking up (a dictionary of terms and deepagents symbols to where they are defined), weighing (brainstorming directions, trade-offs, "what kind of system is this"), building (a blueprint, then a scaffold), and reviewing (auditing existing code against the KB, findings only). Focused on the harness itself; the serving and persistence layers are available but not the main path.
---

# Agent Harness Engineering Knowledge Base

A knowledge base on **agent harness engineering** and how to build on
**deepagents** idiomatically. Take any project description, classify its
archetype, then compose its harness decisions: loop shape, context management,
tool surface, delegation, and guardrails.

**Scope boundary.** This skill's main path stops at the harness and deepagents
construction. The **serving and persistence** layers (schemas, RLS, topology,
scaling) exist in full under `concepts/`, in the Data & Runtime fields, but are
**not the main path** — open them only once a project reaches that point. Mixing
them in early drowns the harness decisions in infrastructure decisions.

## The diagnostic procedure

```
project description (in any shape)
   ↓ fill in the 6 discriminating axes
Archetype (hybrids allowed)
   ↓ archetypes/NN-*.md → the harness constraints that archetype forces
   ↓ cross-check concepts/ (Cognition · Interface · Assurance) + systems/INDEX.md
HARNESS BLUEPRINT                      → blueprint-template.md
   ├─ loop shape        — who decides it stops?
   ├─ context           — compaction vs prompt caching, what enters the context
   ├─ tool surface      — many narrow tools vs few broad ones
   ├─ delegation        — subagents? the result contract back? depth limits?
   ├─ capability & policy — a declarative manifest vs prose + model judgement
   └─ guardrails        — 6 points, each: policy + point + failure mode
   ↓
DEEPAGENTS CONSTRUCTION                ← the end of the main path
   deepagents/lifecycle.md    — where you can hook in
   deepagents/middleware.md   — ordering & dangerous interactions
   deepagents/extension-points.md — don't write custom code where a hook exists
   deepagents/per-archetype.md    — the correct construction per archetype
   deepagents/conformance.md      — is the pattern idiomatic vs maintainer practice

── scope boundary ─────────────────────────────────────────────
Below here only matters once the harness is decided:
   serving & persistence  → concepts/, the Data & Runtime fields
   project scaffold       → scaffolds/_base.md + deltas/ + serving.md
   release gate           → the production-readiness checklist
```

Every stage above lands here:

| Stage | Reference |
|---|---|
| Archetype classification | the "7 archetypes" list below |
| Concepts cross-check | the "5 `concepts/` fields" list below |
| Systems cross-check | [systems/INDEX.md](references/systems/INDEX.md) |
| Blueprint (the contract, output #1) | [blueprint-template.md](references/blueprint-template.md) |
| **Review findings (the contract of reviewing mode)** | [review-template.md](references/review-template.md) |
| **deepagents lifecycle — one turn's flow** | [deepagents/lifecycle.md](references/deepagents/lifecycle.md) |
| **Middleware — ordering & dangerous interactions** | [deepagents/middleware.md](references/deepagents/middleware.md) |
| **Extension points + anti-patterns** | [deepagents/extension-points.md](references/deepagents/extension-points.md) |
| **Construction per archetype** | [deepagents/per-archetype.md](references/deepagents/per-archetype.md) |
| **Handlers & error patterns** | [deepagents/handlers.md](references/deepagents/handlers.md) |
| **Best practices stated by the official documentation** | [deepagents/best-practices.md](references/deepagents/best-practices.md) |
| deepagents config — the full API | [deepagents/api-reference.md](references/deepagents/api-reference.md) |
| deepagents config — conformance vs vanilla | [deepagents/conformance.md](references/deepagents/conformance.md) |
| deepagents internals — what calls what | [deepagents/graph/](references/deepagents/graph/README.md) |
| Verbatim upstream documentation (the `[docs]` material) | [upstream/deepagents-docs/](references/upstream/deepagents-docs/README.md) |
| Base scaffold (output #2, layer 1) | [scaffolds/_base.md](references/scaffolds/_base.md) |
| Per-archetype scaffold deltas (layer 2) | [scaffolds/deltas/](references/scaffolds/deltas/) |
| Base skills for tagged output (table/chart/diagram/formula) | [scaffolds/skills/](references/scaffolds/skills/README.md) |
| Serving/deploy scaffold (layer 3) | [scaffolds/serving.md](references/scaffolds/serving.md) |
| **Glossary — terms & symbols → locations** | [GLOSSARY.md](references/GLOSSARY.md) |
| Project overview, source labels, installation | [README.md](README.md) |

## The 6 discriminating axes (quick classification)

| Axis | Question |
|---|---|
| Blast radius | What does it touch? the user's machine / a sandbox / SaaS data / the outside world |
| Artifact | What is its output? editing what exists / creating something new / an answer / an action in another system |
| Horizon | One shot / one session / living in the background |
| Human control | Approve each step / review at the end / no human |
| Domain surface | General or vertical |
| Interface | CLI / IDE / canvas / chat / embedded API |

The primary cut for an initial classification: **artifact × blast radius**.

## The 7 archetypes

Hybrids are normal and recorded explicitly (e.g. Cursor = Workspace Agent +
In-App Copilot, Manus = General Task Agent + Computer-Use Agent).

1. [Workspace Agent](references/archetypes/01-workspace-agent.md)
2. [Generative Builder](references/archetypes/02-generative-builder.md)
3. [General Task Agent](references/archetypes/03-general-task-agent.md)
4. [Research/Analyst](references/archetypes/04-research-agent.md)
5. [In-App Copilot](references/archetypes/05-in-app-copilot.md)
6. [Workflow Agent](references/archetypes/06-workflow-agent.md)
7. [Computer-Use Agent](references/archetypes/07-computer-use-agent.md)

## The `concepts/` fields — the harness core first

Coverage is determined by field, not by whatever topic came to mind.

- **Cognition** — [agent-loop](references/concepts/agent-loop.md), [planning](references/concepts/planning.md), [delegation](references/concepts/delegation.md), [code-orchestration](references/concepts/code-orchestration.md), [context-engineering](references/concepts/context-engineering.md), [memory](references/concepts/memory.md), [policy-as-data](references/concepts/policy-as-data.md), [skill-composition](references/concepts/skill-composition.md)
- **Interface** — [tool-design](references/concepts/tool-design.md), [mcp](references/concepts/mcp.md), [agent-protocols](references/concepts/agent-protocols.md), [streaming-protocol](references/concepts/streaming-protocol.md), [human-in-the-loop](references/concepts/human-in-the-loop.md), [structured-output](references/concepts/structured-output.md), [multilingual](references/concepts/multilingual.md)
- **Assurance** — [guardrails](references/concepts/guardrails.md), [evaluation](references/concepts/evaluation.md), [security](references/concepts/security.md), [observability](references/concepts/observability.md), [cost-control](references/concepts/cost-control.md), [replay-and-forensics](references/concepts/replay-and-forensics.md)

### The second layer — open when the project reaches serving & persistence

Not the main path. Decisions here only matter once the harness's shape is
settled; opening them earlier drowns the harness decisions.

- **Data** — [session-state](references/concepts/session-state.md), [persistence-schema](references/concepts/persistence-schema.md), [artifacts-and-canvas](references/concepts/artifacts-and-canvas.md), [retention-and-deletion](references/concepts/retention-and-deletion.md)
- **Runtime** — [serving-topology](references/concepts/serving-topology.md), [resource-profiling](references/concepts/resource-profiling.md), [isolation-and-scoping](references/concepts/isolation-and-scoping.md), [sandboxing](references/concepts/sandboxing.md), [queueing-and-backpressure](references/concepts/queueing-and-backpressure.md), [scaling](references/concepts/scaling.md)

## Four usage modes

The material is the same; what differs is **which parts you read** and what
comes out. Every file's five-section frame encodes all four deliberately.

| | **Looking up** (the dictionary) | **Weighing** (brainstorming) | **Building** | **Reviewing** (audit) |
|---|---|---|---|---|
| Starts from | one term or symbol name | a question, a hunch, an idea with no shape yet | an existing project description | an existing codebase |
| Sections read | [`GLOSSARY.md`](references/GLOSSARY.md), then the canonical file it points to | `## Problem`, `## Trade-offs`; in archetypes: `## Example systems`, `## Common pitfalls`; `systems/INDEX.md` | `## Pattern`, `## In deepagents`; in archetypes: `## Harness consequences`, `## Building this with deepagents` | [`review-template.md`](references/review-template.md); `deepagents/extension-points.md` §Anti-patterns; `guardrails.md` §Six points; `deepagents/per-archetype.md` |
| Output | a term's meaning, or the `file:line` of a symbol's definition in source | decisions with their reasons and what was traded — not necessarily one blueprint | a Harness Blueprint, then a scaffold | findings with severity + `file:line`, **reported, never applied** |

**Looking up** is a lookup, not a flow. The glossary gives a one-line meaning
for the KB's own vocabulary (blast radius, fail-deferred, result contract) plus
the file covering it in full; for `deepagents` symbols (`CompositeBackend`,
`SubAgentMiddleware`) it gives the definition's location in source, derived
from the AST graph rather than from memory.

**Weighing** is for when the question is still "what kind of system is this
really" or "has anyone built this already". Its route isn't the diagnostic
procedure above — start from the 6 axes as a menu, `systems/INDEX.md` to see
what exists, then the relevant concept's `## Trade-offs`. Here the explanation
**is** the output, and stopping without a blueprint is legitimate.

**Building** uses the diagnostic procedure above and ends at a blueprint, then
a scaffold — here the explanation isn't the output.

**Reviewing** runs the diagnostic procedure **backwards**: read the code, name
the harness decisions it actually made, then compare those against what its
archetype demands. Its output is findings, never edits — the fix is a separate,
explicitly requested step. Details in
[`review-template.md`](references/review-template.md).

What comes out of weighing flows into building, and what reviewing finds flows
into either — a finding with a stated reason fills a blueprint line unweighed.
