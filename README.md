# Agent Harness Engineering Knowledge Base

A knowledge base on agent harness engineering, packaged as a **Claude Code
Skill**. Give it any project description (goals, output, journey, constraints,
in any shape) and it helps you produce three things in sequence:

1. **An archetype classification.** What kind of AI assistant this is, from 7
   archetypes. Hybrids are normal.
2. **A Harness Blueprint.** Concrete architectural decisions across 7 axes:
   loop shape, context, tool surface, delegation, state & resume, guardrails,
   deployment & resources.
3. **A scaffold.** A production-grade project structure ready to code against,
   on top of `deepagents`.

It also reviews an agent project you already have, reporting findings without
editing anything.

This is not a template repo to `cp -r`, and not a `deepagents` tutorial. The
scaffold is a specification plus snippets verified against source. The depth
lives in `references/`; `SKILL.md` is only a thin router.

**Contents**

- [Quick start](#quick-start) · [The four modes](#the-four-modes) ·
  [Commands](#commands) · [A worked example](#a-worked-example)
- [What is inside](#what-is-inside) · [How claims are labelled](#how-claims-are-labelled)
- Maintaining: [the validator](#the-validator) ·
  [releasing a new version](#releasing-a-new-version) ·
  [adding a tier-3 entry](#adding-a-tier-3-entry) ·
  [the source graph](#the-deepagents-source-graph-optional)

## Quick start

This repo **is** the skill: the repo root is the skill root, with `SKILL.md` at
the top level. There is no build step, no `pip install`, and **no API key**.
The skill is markdown files that Claude Code reads.

**Install it as a plugin.** This repo is simultaneously its own marketplace and
plugin, so two commands inside Claude Code are enough:

```
/plugin marketplace add zanjabil2502/harness-deepagent-knowledge-base
/plugin install agent-harness-kb@harness-deepagent-kb
```

**Or symlink it, if you want to edit the KB** rather than just use it. Local
changes then apply immediately, with no reinstall:

```bash
git clone https://github.com/zanjabil2502/harness-deepagent-knowledge-base.git
cd harness-deepagent-knowledge-base

mkdir -p ~/.claude/skills                              # all projects
ln -s "$(pwd)" ~/.claude/skills/agent-harness-kb
# or, from one project's root only:
# mkdir -p .claude/skills && ln -s /path/to/repo .claude/skills/agent-harness-kb
```

Do not install both ways at once. The same skill from two sources makes it
unclear which one is active.

**Confirm it loaded.** Start a new Claude Code session and ask for something
that fits one of the four modes, for example *"what is fail-deferred"* (looking
up) or *"I want to build an agent that can edit files in a local repo, what
kind is that"* (weighing). If the skill is active, the answer cites files under
`references/`.

**Getting updates.** If you installed it as a plugin:

```
/plugin marketplace update harness-deepagent-kb
```

If you symlinked it:

```bash
git pull
python3 tools/check_kb.py     # the structural gate; must print "OK: all checks passed"
```

### What you need

| For | Requirement |
|---|---|
| Using the skill | Claude Code. That is all. |
| Running `tools/*.py` | Python 3.10+, standard library only. No `pip install`. |
| Running `references/recipes/` | [`uv`](https://docs.astral.sh/uv/), optional. See below. |

**Optional: re-verify the `[code]` claims yourself.** The KB cites `deepagents`
source down to line numbers. To prove those citations still hold, set up the
recipes venv:

```bash
cd references/recipes && uv sync    # pins deepagents 0.7.8
```

Once that venv exists, `python3 tools/check_kb.py` additionally checks that 53
source files are still byte-identical to their state when the AST graph was
built. Without the venv that one check is skipped and the rest still runs.

## The four modes

The material is the same in every mode. What differs is which parts get read
and what comes out. [`SKILL.md`](SKILL.md) §Four usage modes has the full
table.

| Mode | Starts from | Output |
|---|---|---|
| **Looking up** | one term or symbol | its meaning, or the `file:line` where it is defined |
| **Weighing** | a question or an unformed idea | decisions with their reasons; a blueprint is not required |
| **Building** | a project description | a Harness Blueprint, then a scaffold |
| **Reviewing** | an existing codebase | findings with severity and `file:line`, reported and never applied |

### Commands

Installed as a plugin, the modes also get typed entry points. The prefix is the
**plugin** name (`agent-harness-kb`), not the marketplace name:

| Command | Mode | Edits code? |
|---|---|---|
| `/agent-harness-kb:lookup` | looking up | no |
| `/agent-harness-kb:brainstorm` | weighing | no |
| `/agent-harness-kb:blueprint` | building | no |
| `/agent-harness-kb:review` | reviewing | **no, forbidden in the command itself** |
| `/agent-harness-kb:refactor` | follow-on to a review | **yes, the only one** |
| `/agent-harness-kb:evaluate` | building an eval harness | no |

`review` and `refactor` are split deliberately. A review that silently rewrites
code destroys the independent reading it exists to provide. The skill still
activates on its own from its description; commands are for when you want to
pick the mode yourself.

A review covers four layers, in order: structure, HITL, end-to-end flow, and
three separately graded verdicts on best process, best technical, and best
implementation. The contract is [`references/review-template.md`](references/review-template.md).

## A worked example

From a project description to a blueprint, the longest of the four paths.

Say the description is: *"A CLI running in a developer's local repo, able to
read/edit files and run shell commands (tests, linters, package managers),
sessions lasting hours, every edit and command needing the developer's
approval."*

**1. Fill in the 6 discriminating axes**
([`references/archetypes/README.md`](references/archetypes/README.md)):

| Axis | This project's value |
|---|---|
| Blast radius | The user's machine: the local filesystem plus a shell |
| Artifact | Edits to existing code |
| Horizon | One session, possibly hours |
| Human control | Approval per edit and per command |
| Domain surface | General, any repo's code |
| Interface | CLI |

**2. Classify the archetype.** It matches
[`references/archetypes/01-workspace-agent.md`](references/archetypes/01-workspace-agent.md),
the **Workspace Agent** (real examples: Claude Code, Cursor, Aider, OpenHands).
No hybrid here; compare Cursor, which is 1+5 when there is also an in-app IDE
panel.

**3. Read that archetype's harness consequences:** a safety gate on every
state-changing tool call, a broad bash tool surface rather than many narrow
tools, aggressive compaction, session-level checkpoints. Then cross-check
`references/concepts/` (for example `guardrails.md` §8.4 for the gate's shape,
and `sandboxing.md` for why `LocalShellBackend` at this blast radius needs a
mandatory rather than optional gate) and `references/systems/` for comparable
systems.

**4. Compose the Harness Blueprint.** Copy
[`references/blueprint-template.md`](references/blueprint-template.md) and fill
in each section: the 7 axes, the 5 state layers, the 6 guardrail points,
deployment & resources, isolation & scoping, and the `deepagents` config. For
archetype 01 that means, among other things, `interrupt_on` for the
`write_file` and `execute` tools, `backend=LocalShellBackend(root_dir=repo)`
with a mandatory gate (see D-09 in `conformance.md` for why that is a
deliberate divergence and not a safe default), and a per-session checkpointer.

**5. Scaffold.** Combine
[`references/scaffolds/_base.md`](references/scaffolds/_base.md), the
archetype-agnostic production-grade structure, with the archetype 01 delta
([`references/scaffolds/deltas/01-workspace-agent.md`](references/scaffolds/deltas/01-workspace-agent.md))
and [`references/scaffolds/serving.md`](references/scaffolds/serving.md) for
the deployment topology.

**6. Pass the mandatory gate.** Before the scaffold counts as finished, satisfy
the **production-readiness checklist** in
[`references/blueprint-template.md`](references/blueprint-template.md#production-readiness-checklist):
tracing, an eval harness, budget guards, retry and idempotency, a context
overflow policy, secrets management, a human gate plus audit log, prompt and
policy versioning, a kill switch and sandbox.

Keep the blueprint each project produces. It becomes candidate material for the
next tier-2 or tier-3 entry.

## What is inside

```
SKILL.md                     the router, capped at 150 lines
commands/                    6 typed entry points, one per mode
references/
├── archetypes/              7 archetypes + the 6 discriminating axes
├── concepts/                31 files across 5 fields, each with stated trade-offs
├── systems/                 14 dissected systems + a tier-3 index
├── deepagents/              construction: lifecycle, middleware, extension
│   └── graph/               points, per-archetype, conformance, API, AST graph
├── scaffolds/               _base + 7 archetype deltas + serving + tag skills
├── recipes/                 4 runnable scripts, verified by construction
├── upstream/                verbatim vendor documentation snapshots
├── blueprint-template.md    the output contract of building mode
├── review-template.md       the output contract of reviewing mode
└── GLOSSARY.md              generated: 20 terms + 32 symbols
tools/                       check_kb.py, build_glossary.py, fetch_upstream_docs.py
```

## How claims are labelled

Every claim carries its source:

| Label | Meaning |
|---|---|
| `[code]` | Read directly from source |
| `[docs]` | Official documentation |
| `[inferred]` | Concluded from a closed-source product's behaviour |
| `[ours]` | This project's own design decision |

An `[ours]` claim always names the vanilla alternative and the reason for
diverging, and every one of them is listed in
[`references/deepagents/conformance.md`](references/deepagents/conformance.md).
The validator checks that roster in both directions, so an undeclared claim and
a stale line number both fail.

A small number of `[code]` labels cite another part of this KB (for example
`systems/deepagents.md`) rather than source directly. That is legitimate as
long as the cited part is itself source-verified: `[code]` there means
"transitive from a claim already read from source elsewhere", not a loosened
definition.

To check that `[code]` dominates, which it must:

```bash
grep -roh '\[\(code\|docs\|inferred\|ours\)\]' references/ | sort | uniq -c
```

As of the last verification (2026-08-23), counted over git-tracked `.md` files
under `references/`: `[code]` 594, `[docs]` 115, `[inferred]` 114, `[ours]` 74.
`[code]` is clearly dominant, more than 2.5 times the next largest label. The
command above can count slightly higher if `references/recipes/.venv/` exists
locally, since those are installed dependencies rather than KB content. All 5
required fields under `references/concepts/` were checked per file, not per
field, and every file in all five has at least one `[code]` reference.

## The validator

`tools/check_kb.py` is the structural gate. It checks that:

- every archetype, concept, and system file has its required sections and at
  least one source label;
- no internal link is dead, and no link points at a file that is untracked
  (alive for the author, dead for anyone cloning);
- `SKILL.md` stays thin, at most 150 lines;
- every `[ours]` claim appears in the conformance roster, checked both ways;
- skill assets follow the Agent Skills spec, where violations are silent;
- the AST graph still matches the installed `deepagents` source;
- `GLOSSARY.md` is identical to a fresh rebuild.

Run it from the repo root:

```bash
python3 tools/check_kb.py
```

A successful run prints `OK: all checks passed` and exits 0. Run it after
adding or editing anything under `references/`, `SKILL.md`, or `README.md`.

## Releasing a new version

**Bump the version, or nobody receives the change.** `claude plugin update`
compares version numbers, not commits. If `version` is unchanged, it reports
*"already at the latest version"* and the installed copy keeps the old tree,
however many commits have been pushed.

1. Bump `version` in **both** files, keeping them equal:
   - `.claude-plugin/plugin.json`
   - the plugin entry inside `.claude-plugin/marketplace.json`
2. `python3 tools/check_kb.py`, then commit and push.
3. Users pick it up with `/plugin marketplace update harness-deepagent-kb`,
   which refreshes the catalogue, followed by a plugin update. **A restart is
   required** before new commands appear.

Use a minor bump for a new mode, a new command, or new reference material; a
patch bump for corrections that add no surface.

## Adding a tier-3 entry

The KB distinguishes research depth per system through 3 tiers:

- **T1**, a deep dissection. `deepagents` only.
- **T2**, the full 7-axis grid, one `references/systems/<name>.md` file per
  system, using [`references/systems/_template.md`](references/systems/_template.md).
  It requires research from source, not a summary.
- **T3**, a cheap index: name, archetype, and one line of distinguishing
  character, with no separate file. New harnesses and infrastructure get added
  this way, so coverage grows without restructuring the grid.

To add a T3 entry, add one row to the **Tier 3** table in
[`references/systems/INDEX.md`](references/systems/INDEX.md):

```
| <Name> | <Archetype, or "Infrastructure - ..."> | T3 | <one line of distinguishing character> | <its multilingual design status, or "Not applicable"> | `[code]`/`[docs]`/`[inferred]` |
```

The rules:

- Be honest about the source label. If it was not read from source it is
  `[inferred]` or `[docs]`, never `[code]`.
- The Multilingual column records whether that system has an *explicit design*
  separating intent from expression, not merely UI string i18n. Its absence is
  a legitimate finding to record, not a column to leave empty.
- If research on a system grows deep enough to fill the 7-axis grid, promote it
  to T2: create a file from `_template.md` and move its row between tables.

## The deepagents source graph (optional)

This KB contains judgements: what is idiomatic, what is an anti-pattern. For
completeness instead (what exists, what calls what, what breaks if X changes),
derive the graph from source:

```bash
# graphify skips anything inside a .venv, so copy it to an ordinary path first
cp -r references/recipes/.venv/lib/python3.13/site-packages/deepagents /tmp/deepagents-src
graphify /tmp/deepagents-src
```

A code-only corpus means pure AST extraction: zero LLM tokens, zero API keys.
Output lands in `graphify-out/`. Move its contents into
[`references/deepagents/graph/`](references/deepagents/graph/README.md), where
it lives as a skill reference. Three files are committed (`GRAPH_REPORT.md`,
`graph.json`, `manifest.json`); large, machine-specific, or absolute-path
derivatives stay git-ignored.

Regenerate after `deepagents` bumps a version, then diff the result to see what
changed. `tools/check_kb.py` refuses first if the graph is no longer in sync
with the installed source.

A graph cannot say what is **correct**, only what **exists**. The idiomatic
verdict still comes from `references/deepagents/conformance.md`.
