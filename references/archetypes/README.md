# AI Assistant archetypes

A classification map. Take a project description, answer the 6 questions
below, then match it to one (or a combination) of the 7 archetypes. Each
archetype file carries the harness consequences that position forces.

## The 6 discriminating axes

| Axis | Question |
|---|---|
| Blast radius | What does it touch? user's machine / sandbox / SaaS data / the outside world |
| Artifact | What does it output? edits to what exists / something new / an answer / actions in other systems |
| Horizon | One shot / one session / lives in the background |
| Human control | Approve every step / review at the end / no human at all |
| Domain surface | General or vertical |
| Interface | CLI / IDE / canvas / chat / embedded API |

The primary cut for initial classification: **artifact × blast radius** —
those two axes alone separate 6 of the 7 archetypes.

## The 7 archetypes

| # | Archetype | Examples | Harness consequences |
|---|---|---|---|
| 1 | [Workspace Agent](01-workspace-agent.md) | Claude Code, Cursor, Aider, OpenHands | Permission gate, broad bash tool, aggressive compaction, resume |
| 2 | [Generative Builder](02-generative-builder.md) | Figma Make, v0, Lovable, bolt.new | Sandbox, state = 1 artifact, fast iteration, short persistence |
| 3 | [General Task Agent](03-general-task-agent.md) | Abacus DeepAgent, Manus | Explicit planning, subagents, filesystem-as-memory, long horizon |
| 4 | [Research/Analyst](04-research-agent.md) | Deep Research, Perplexity, Elicit | search→read→synthesize loop, token budget, provenance mandatory |
| 5 | [In-App Copilot](05-in-app-copilot.md) | Notion AI, Figma AI, Agentforce | Tools = the product's API, short horizon, undo/rollback critical |
| 6 | [Workflow Agent](06-workflow-agent.md) | Zapier/n8n agents, cron agents | No human in the loop → retry, idempotency, observability, kill switch |
| 7 | [Computer-Use Agent](07-computer-use-agent.md) | Operator, browser agents | see→click→verify loop, narrow but deep tools, the most brittle |

## Hybrid matrix

Hybrids are normal — most real products combine two archetypes rather than
being one pure type. Record the combination explicitly; don't force a
single label.

| System | Combination | Why |
|---|---|---|
| Cursor | 1 (Workspace) + 5 (In-App Copilot) | Edits the local repo through bash/file tools (1) while also offering a chat panel that answers from a codebase index without editing anything (5) — two different modes of human control in one product. `[inferred]` |
| Manus | 3 (General Task) + 7 (Computer-Use) | Accepts a broad mission and delegates through explicit planning (3), but executes through a sandboxed browser — look at the page, click, verify (7). `[inferred]` |
| Replit Agent | 2 (Generative Builder) + 1 (Workspace Agent) | Starts from nothing like a Generative Builder (building a new app in a sandbox), but once the app exists its workspace persists — shell, git, and files across sessions like a Workspace Agent. `[inferred]` |

## The deployment dimension is orthogonal

The seven archetypes above answer **"what kind of assistant is this"**.
The question **"how is it served"** — local single-user CLI vs multi-user
service on K8s, one process vs distributed, synchronous vs streaming — is
a different and independent axis. A Workspace Agent can be a local CLI
(Aider) or a multi-user service (Claude Code as part of a managed
product); it stays archetype 1 in both cases.

`[ours]` We deliberately separate the deployment dimension from the
archetype taxonomy and place it under `references/concepts/` in the
Runtime field (`serving-topology.md`, `scaling.md`). The vanilla approach
common to AI product taxonomies is to mix the two (e.g. making "CLI agent"
vs "hosted agent" categories in their own right) — we diverge because that
explodes 7 archetypes into dozens of variants that differ only in how they
are served, not in their harness contract.
