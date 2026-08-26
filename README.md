# Agent Harness Engineering Knowledge Base

A knowledge base on agent harness engineering, packaged as a **Claude Code
Skill**. Given any project description — goals, output, journey, constraints,
in any shape — this KB helps produce three things in sequence:

1. **An archetype classification** — what kind of AI assistant this is (of 7
   archetypes, hybrids allowed).
2. **A Harness Blueprint** — concrete architectural decisions across 7 axes
   (loop shape, context, tool surface, delegation, state & resume,
   guardrails, deployment & resources).
3. **A scaffold** — a production-grade project structure ready to code
   against, on top of `deepagents`.

This is not a template repo to `cp -r`, and not a `deepagents` tutorial. Its
scaffold is a specification plus snippets verified against source; the depth
lives in `references/`, with `SKILL.md` as only a thin router.

Every claim in this KB is labelled with its source: `[code]` (read directly
from source), `[docs]` (official documentation), `[inferred]` (concluded from
a closed-source product's behaviour), or `[ours]` (this project's own design
decision, always naming the vanilla alternative and the reason for diverging —
listed in full in
[`references/deepagents/conformance.md`](references/deepagents/conformance.md)).
A small number of `[code]` labels cite another part of this KB (e.g.
`systems/deepagents.md`) rather than source directly — legitimate as long as
the part cited is *itself* source-verified: `[code]` there means "transitive
from a claim already read from source elsewhere", not a loosened definition.
The counts below tally labels as they are, including those transitive
citations.

## Install

This repo **is** the skill: the repo root = the skill root, with `SKILL.md` at
the top level. There is no build step, no `pip install`, and **no API key** —
this skill is purely markdown files Claude Code reads.

### The usual way: install it as a plugin

This repo is simultaneously its own **marketplace** and **plugin**. No clone,
no symlink — two commands inside Claude Code:

```
/plugin marketplace add zanjabil2502/harness-deepagent-knowledge-base
/plugin install agent-harness-kb@harness-deepagent-kb
```

Claude Code downloads, places, and updates it. To pull the latest version
later:

```
/plugin marketplace update harness-deepagent-kb
```

### The alternative: a symlink, for contributors

Use this if you want to edit the KB rather than just use it — local changes
apply immediately with no reinstall.

```bash
git clone https://github.com/zanjabil2502/harness-deepagent-knowledge-base.git
cd harness-deepagent-knowledge-base

mkdir -p ~/.claude/skills                              # all projects
ln -s "$(pwd)" ~/.claude/skills/agent-harness-kb
# or, from one project's root only:
# mkdir -p .claude/skills && ln -s /path/to/repo .claude/skills/agent-harness-kb
```

Don't install both at once — the same skill from two sources makes it unclear
which one is active.

### Confirm it loads

Start a new Claude Code session, then ask for something that fits one of the
three modes in [`SKILL.md`](SKILL.md) §Three usage modes, e.g. *"what is
fail-deferred"* (looking up) or *"I want to build an agent that can edit files
in a local repo, what kind is that"* (weighing). If the skill is active, the
answer references files under `references/`.

### Prerequisites

| For | You need |
|---|---|
| Using the skill | Claude Code. That's all. |
| Running `tools/*.py` | Python 3.10+, standard library only — no `pip install` |
| Running `references/recipes/` | [`uv`](https://docs.astral.sh/uv/) (optional, see below) |

### Optional: re-verifying `[code]` claims

This KB cites the `deepagents` source down to line numbers. To prove those
citations still hold, set up the recipes venv:

```bash
cd references/recipes && uv sync    # pins deepagents 0.7.8
```

Once that venv exists, `python3 tools/check_kb.py` also checks that 53 source
files are still identical to their state when the AST graph was built.
Without the venv that check is skipped and the rest still runs.

### Update

If installed as a plugin, run this inside Claude Code:

```
/plugin marketplace update harness-deepagent-kb
```

If using the symlink:

```bash
git pull
python3 tools/check_kb.py     # the structural gate; must print "OK: semua cek lulus"
```

## How to use it

There are three modes, described in [`SKILL.md`](SKILL.md) §Three usage
modes: **looking up** (starting from one term or symbol, output: its meaning
or where it is defined), **weighing** (starting from a question or an
unformed idea, output: decisions with their reasons) and **building**
(starting from a project description, output: a blueprint then a scaffold).
The example below walks through building, whose path is the longest.

### An example: from a project description to a blueprint

Say the project description is: *"A CLI running in a developer's local repo,
able to read/edit files and run shell commands (tests, linters, package
managers), sessions lasting hours, every edit/command needing the developer's
approval."*

**1. Fill in the 6 discriminating axes**
([`references/archetypes/README.md`](references/archetypes/README.md)):

| Axis | This project's value |
|---|---|
| Blast radius | The user's machine (the local filesystem + shell) |
| Artifact | Edits to existing code |
| Horizon | One session, possibly hours |
| Human control | Approval per edit/command |
| Domain surface | General (any repo's code) |
| Interface | CLI |

**2. Classify the archetype** → it matches
[`references/archetypes/01-workspace-agent.md`](references/archetypes/01-workspace-agent.md)
(**Workspace Agent** — real examples: Claude Code, Cursor, Aider, OpenHands).
No hybrid here (compare Cursor = 1+5 when there is also an in-app IDE panel).

**3. Read that archetype's harness consequences** — a safety gate on every
state-changing tool call, a broad bash tool surface (rather than many narrow
tools), aggressive compaction, session-level checkpoints — then cross-check
`references/concepts/` (e.g. `guardrails.md` §8.4 for the gate's shape,
`sandboxing.md` for why `LocalShellBackend` at this blast radius needs a
mandatory rather than optional gate) and `references/systems/` for comparable
systems (Aider, Claude Code, OpenHands).

**4. Compose the Harness Blueprint** — copy
[`references/blueprint-template.md`](references/blueprint-template.md) and
fill in each section (the 7 axes, the 5 state layers, the 6 guardrail points,
deployment & resources, isolation & scoping, the `deepagents` config) with
this project's decisions. For archetype 01 that means, among other things:
`interrupt_on` for the `write_file`/`execute` tools,
`backend=LocalShellBackend(root_dir=repo)` with a mandatory gate (see D-09 in
`conformance.md` for why this is a deliberate divergence rather than a safe
default), and a per-session checkpointer.

**5. Scaffold** — combine
[`references/scaffolds/_base.md`](references/scaffolds/_base.md) (the
archetype-agnostic production-grade structure) with the archetype 01 delta
([`references/scaffolds/deltas/01-workspace-agent.md`](references/scaffolds/deltas/01-workspace-agent.md))
and [`references/scaffolds/serving.md`](references/scaffolds/serving.md) for
the deployment topology.

**6. The mandatory gate** — before the scaffold counts as finished, satisfy
the **production-readiness checklist** in
[`references/blueprint-template.md`](references/blueprint-template.md#checklist-production-readiness)
(tracing, an eval harness, budget guards, retry/idempotency, a context
overflow policy, secrets management, a human gate + audit log, prompt/policy
versioning, a kill switch & sandbox).

The blueprint each project produces is worth keeping — it becomes candidate
material for the next T2/T3 entry (see below).

## Adding a tier-3 entry (`systems/INDEX.md`)

The KB distinguishes research depth per system through 3 tiers (spec §10):

- **T1** — a deep dissection (`deepagents` only).
- **T2** — the full 7-axis grid, one `references/systems/<name>.md` file per
  system, using the frame in
  [`references/systems/_template.md`](references/systems/_template.md).
  Requires research from source, not a summary.
- **T3** — a cheap index: name + archetype + one line of distinguishing
  character, with no separate file. This is what new harnesses/infrastructure
  discovered later get added as, so coverage grows without restructuring the
  grid.

To add a T3 entry, add one row to the **Tier 3** table in
[`references/systems/INDEX.md`](references/systems/INDEX.md):

```
| <Name> | <Archetype, or "Infrastructure — ..."> | T3 | <one line of distinguishing character> | <its multilingual design status, or "Not applicable"> | `[code]`/`[docs]`/`[inferred]` |
```

The rules:

- Be honest about the source label — if it wasn't read from source, it is
  `[inferred]` or `[docs]`, not `[code]`.
- The Multilingual column records *whether that system has an explicit
  design* separating intent from expression (not merely UI string i18n) —
  its absence is a legitimate finding to record, not a column to leave empty.
- If research on that system grows deep enough to fill the 7-axis grid,
  promote it to T2: create a new file from `_template.md` and move its row
  from the Tier 3 table to the Tier 2 table.

## The validator

`tools/check_kb.py` is the KB's structural gate — it checks that every
archetype/concept/system file has its required sections (each its own frame)
and at least one source label, that no internal link is dead, that `SKILL.md`
stays thin (≤150 lines), and that **every `[ours]` is listed in the
`references/deepagents/conformance.md` roster** — checked in both directions,
so a new undeclared `[ours]` claim and a stale roster line number both fail.
Run it from the repo root:

```bash
python3 tools/check_kb.py
```

A successful run prints `OK: semua cek lulus`, exit code 0. Run it after
adding or editing any file under `references/`, `SKILL.md`, or `README.md`.

## The deepagents source graph (optional)

This KB contains judgements — what is idiomatic, what is an anti-pattern. For
**completeness** (what exists, what calls what, what breaks if X changes),
derive the graph from the source:

```bash
# graphify skips anything inside a .venv, so copy it to an ordinary path first
cp -r references/recipes/.venv/lib/python3.13/site-packages/deepagents /tmp/deepagents-src
graphify /tmp/deepagents-src
```

A code-only corpus → pure AST extraction, zero LLM tokens, zero API keys. Its
output lands in `graphify-out/`; move its contents into
[`references/deepagents/graph/`](references/deepagents/graph/README.md), where
it lives as a skill reference. Three files are committed
(`GRAPH_REPORT.md`, `graph.json`, `manifest.json`); large,
machine-specific, or absolute-path-bearing derivatives stay git-ignored.
Regenerate after `deepagents` bumps a version, then diff the result to see
what changed — `tools/check_kb.py` will refuse first if the graph is no longer
in sync with the installed source.

A graph can't say what is **correct** — only what **exists**. The idiomatic
verdict still comes from `references/deepagents/conformance.md`.

To check the dominance of the `[code]` label (most of the KB's claims must be
read from source rather than guessed):

```bash
grep -roh '\[\(code\|docs\|inferred\|ours\)\]' references/ | sort | uniq -c
```

As of the last verification (the final fix wave review, 2026-08-23), counted
over the git-tracked `.md` files under `references/`: `[code]` 594, `[docs]`
115, `[inferred]` 114, `[ours]` 74 — `[code]` clearly dominant (more than 2.5×
the next largest label). The command above (without `--include`) can count
slightly higher if `references/recipes/.venv/` exists locally (dependencies
installed for the recipes, `.gitignore`d, not part of the KB's content) — see
`.superpowers/sdd/2026-08-23-agent-harness-kb/task-12-report.md` for the exact
figures and commands. All 5 required fields under `references/concepts/`
(Cognition, Interface, Data, Runtime, Assurance) have been checked and **no
field is weak** — every file in all five has at least one `[code]` reference
(checked per file rather than per field, so not a single file is pure
guesswork).
