# 1. Workspace Agent

## Definition

An agent that operates directly on the user's own filesystem/repo, with a
relatively unrestricted bash tool, to edit artifacts that **already
exist**. Sessions typically run for hours, are bound to one local
project/repo, and human control happens through per-edit approval or
per-commit review — not through a sandbox you can simply throw away.

Boundaries against neighbours: differs from **General Task Agent** (03)
because its scope is a single repo/machine rather than a broad mission
across systems; differs from **Generative Builder** (02) because the
artifact is existing code (edits) rather than a new project built from
scratch in a disposable sandbox; differs from **In-App Copilot** (05)
because its tool surface is a generic shell/filesystem rather than one
product's narrow API.

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | User's machine (local filesystem, often full shell) |
| Artifact | Edits to existing code/content |
| Horizon | One session (can run for hours, sometimes resumable across sessions) |
| Human control | Approve per edit/command, or review per commit |
| Domain surface | General (coding, any repo) |
| Interface | CLI or IDE |

## Harness consequences

1. **A safety gate is mandatory on every state-changing tool call** (file
   write, shell exec) — blast radius = the user's machine means mistakes
   cannot be undone through a UI, unlike a sandbox you just discard.
2. **Tool surface: one broad bash tool, not many narrow tools** — coding
   work needs arbitrary commands (test runner, package manager, linter)
   that cannot be enumerated upfront as separate tools.
3. **Context: aggressive compaction/summarization** — multi-hour sessions
   touch many large files; the context window runs out before the task
   finishes unless it is continuously trimmed and summarized.
4. **State & resume: checkpoint at session level** — coding sessions get
   interrupted often (network, laptop sleep, crash), and must resume from
   the last state without re-exploring the repo from scratch.
5. **Minimal/flat delegation** — most single-repo work needs no subagent;
   delegation only becomes relevant when a subtask needs an isolated
   context window (e.g. running a long test suite in the background).

## Example systems

- **Aider** `[code]` — `GitRepo.commit()` implements commit attribution
  logic that branches on the `aider_edits` flag: when a change originates
  from Aider, the commit's author/committer is marked differently from a
  human-written commit, not merely tagged as a generic "auto-commit".
  Source: `aider/repo.py` (github.com/Aider-AI/aider).
- **Cline** `[docs]` — has two explicit modes: Plan (explore the repo, ask
  clarifying questions, form a strategy) and Act (execute). Every file
  edit and terminal command requires user approval by default, with a
  toggle for auto-approve to run autonomously. Source:
  github.com/cline/cline.
- **OpenHands** `[docs]` — provides a Docker sandbox mode for local use
  ("Docker sandbox mode for laptop usage"), with the option of giving the
  agent full access to the user's filesystem when the sandbox is turned
  off. Source: github.com/All-Hands-AI/OpenHands.
- **Claude Code** `[inferred]` — from product behaviour: a per-tool
  permission gate (edit/bash/others) with an optional "auto-accept" mode,
  and the ability to resume a session from local history.
- **Cursor** `[inferred]` — a hybrid with In-App Copilot (05); see the
  hybrid matrix in `README.md`.

## Common pitfalls

1. **Auto-approve in headless/CI mode** deletes or overwrites important
   files with no undo trail — an auto-approved generic bash tool carries
   the full blast radius of the user's machine, with no sandbox to contain
   the damage.
2. **Context filled by reading large files whole** instead of via a
   summary/repo-map — the session crashes or hits the context limit before
   the task completes, especially in large repos.
3. **A shell tool with no scoping/allowlist** — destructive commands
   (`rm -rf`, `git push --force`) execute because a generic bash tool does
   not distinguish safe from dangerous commands at the enforcement point.
4. **An interrupted session with no checkpoint** — hours of work are lost
   entirely and the user has to re-explain the context from scratch,
   because no resumable session state exists.

## Building this with deepagents

- **Backend**: `LocalShellBackend` (extends the filesystem backend with
  `execute` via `subprocess.run(shell=True)`) rooted at the repo
  directory, or `FilesystemBackend(root_dir=...)` when `execute` is not
  needed. `[code]` — source:
  `libs/deepagents/deepagents/backends/local_shell.py`, cited in
  THREAT_MODEL.md (langchain-ai/deepagents).
- **Core middleware**: `FilesystemMiddleware` (default; registers `ls`,
  `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`,
  `execute`) plus the `SummarizationMiddleware` that `create_deep_agent()`
  installs for automatic compaction. `[code]` — source: `graph.py`
  (langchain-ai/deepagents).
- **Safety gate**: `interrupt_on={"execute": True, "write_file": True,
  "edit_file": True}` through the `interrupt_on` parameter of
  `create_deep_agent`, backed by `HumanInTheLoopMiddleware`. The
  per-tool configuration shape (boolean or a dict with
  `allowed_decisions`) matches the pattern exercised in `test_hitl.py`.
  `[code]`.
- **State & resume**: `checkpointer=<the application's own Postgres
  checkpointer>` through the `checkpointer` parameter — deepagents does
  not create a checkpointer of its own; the application injects it.
  `[code]` — source: `ARCHITECTURE.md` (langchain-ai/deepagents).
- **Subagents**: not used by default — and this is **not** a divergence.
  Of the 10 `create_deep_agent` calls across the maintainer repo's
  `examples/`, **5 pass no synchronous subagents at all**:
  `text-to-sql-agent/agent.py:45` (`subagents=[]`, with the comment "No
  subagents needed"), `llm-wiki/helpers.py:633`,
  `better-harness/better_harness/agent.py:206` and `:611`, and
  `async-subagent-server/server.py:155`. The nuance: the
  `general-purpose` subagent is still added automatically in all of them,
  so the `task` tool remains present unless disabled via
  `GeneralPurposeSubagentProfile(enabled=False)`. For this archetype the
  unit of work (one repo, one session) rarely needs context isolation
  across subtasks; add subagents through `subagents=[...]` only when a
  long subtask needs separate context (e.g. running and analysing a large
  test suite in the background). `[code]` — repo
  `langchain-ai/deepagents` commit `23b83ad`; see
  `../deepagents/conformance.md` D-01.

## Sources

- Aider `aider/repo.py` — `[code]` — https://github.com/Aider-AI/aider
- Cline README — `[docs]` — https://github.com/cline/cline
- OpenHands README — `[docs]` — https://github.com/All-Hands-AI/OpenHands
- deepagents `graph.py`, `THREAT_MODEL.md`, `ARCHITECTURE.md` — `[code]` —
  Context7 `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Claude Code, Cursor — `[inferred]` — closed-source product behaviour; no
  source access yet to cite as `[code]`.
