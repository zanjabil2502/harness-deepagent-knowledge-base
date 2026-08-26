# Letta

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. An important identity note, the same pattern as OpenHands': the
`letta-ai/letta` repo (the original candidate in spec §10 for "cross-session
memory") has been **archived**. Its own `README.md` states: *"This repository
now serves as a landing page for the Letta project. The retired Letta V1
server source is preserved on the `archive` branch... The current source code
lives in `letta-ai/letta-code`"*. `[code]` — the `README.md` of the
`letta-ai/letta` repo (`git clone --depth 1`, 2026-08-23; the last commit
before archiving: `87fd37a chore: archive the legacy server repository`).
Modern Letta (npm `@letta-ai/letta-code`) is a **coding-agent harness** (an
interactive CLI + an App Server + Slack/Telegram/Discord/WhatsApp/Signal
channels), no longer a pure "memory API platform" — this file documents
`letta-code` because that is the software genuinely running today, and records
explicitly that cross-session memory (the reason Letta was a T2 candidate) has
changed shape: from a purely memory-block REST API into a **git-backed
per-agent memory filesystem** on top of a server that still exposes the older
memory-block primitives through `@letta-ai/letta-client`.

## Archetype

A **Workspace Agent (01)** — an interactive terminal CLI with bash/file tools,
permission modes, and OS-level sandboxing (see axis 6), structurally very
parallel to `claude-code.md` (the difference: Letta can be read as `[code]`,
Claude Code cannot). Its horizon can be long (an App Server + async channels:
Slack/Telegram/cron). `[code]` — `letta-ai/letta-code`'s `README.md`, the
`src/channels/`, `src/cron/` directory structure.

## 1. Loop shape

Model turn execution (an LLM call ⇄ tool call) runs **server-side**, invoked
through `@letta-ai/letta-client` (the `MessageCreate` type from
`resources/agents/agents`) — `letta-code` itself doesn't implement its own
ReAct loop; it is a client of the Letta agent server (self-hosted through
`letta server` or Letta Cloud). `[code]` — the
`@letta-ai/letta-client/resources/agents/agents` import in
`src/queue/turn-queue-runtime.ts` line 1; the `README.md` ("Run the App Server
for local or self-hosted agents").

What `letta-code` **does** implement is **merging input before a turn is
sent**: `QueuedTurnInput` has three kinds — `"user"` (a user message),
`"task_notification"`, `"cron_prompt"` — merged through `mergeQueuedTurnInput`
(the `appendContentParts`, `normalizeUserContent` helpers) into one
`MessageCreate.content` before being sent to the server. This is a
multi-source input coalescing pattern (interactive chat + async task
notifications + cron), not a tool-calling loop. `[code]` —
`src/queue/turn-queue-runtime.ts` lines 1-30.

## 2. Context

Two different memory layers coexist:

- **Classic memory blocks** (the MemGPT/Letta V1 inheritance) — the labels
  `persona` and `human` (`MEMORY_BLOCK_LABELS = ["persona", "human"]`), loaded
  from `.mdx` files in `src/agent/prompts/<label>.mdx` and sent to the server
  through `@letta-ai/letta-client`'s `CreateBlock` type. A version note: the
  per-project fields (`skills`/`loaded_skills`) were **removed** from memory
  blocks (the ticket reference `LET-7353` in a code comment) — skills are now
  injected through a *system reminder* rather than a memory block. `[code]` —
  `src/agent/memory.ts` lines 1-21.
- **A git-backed memory filesystem ("MemFS")** — the new layer: each agent has
  a `~/.letta/agents/<agentId>/memory/` directory on disk, and `memory-git.ts`
  (2128 lines) manages that directory as a **real git repo**: commits, hooks,
  worktrees, a config lock, and its own commit signing
  (`memory-git-hooks.ts`, `memory-git-signing.ts`,
  `memory-git-config-lock.ts`, `memory-worktree.ts`). The module comment names
  the migration explicitly: *"With git-backed memory, most sync/hash logic is
  removed"* — the old version used manual hashing, the current one uses git as
  its versioning engine. `[code]` — `src/agent/memory-filesystem.ts` lines
  1-30 (the module docstring, the constant `MEMORY_FS_ROOT = ".letta"`).

This is a far more literal form of "cross-session memory" than most other
systems in this grid — not a vector store or a summary, but **git history that
can be diffed, rolled back, and branched** exactly like code.

## 3. Tool surface

The built-in tool list's details weren't verified (a `src/tools/` module
exists but its contents weren't read in this task) — however, the built-in
skill frontmatter shows a minimal per-skill tool pattern: the `memory` skill
(memory defragmentation, see axis 4) is given only `tools: Bash, TaskOutput` —
a small explicit subset rather than the main agent's whole tool surface.
`[code]` — the `src/agent/subagents/builtin/memory.md` frontmatter (lines
1-7). `[inferred]` for generalising to the main agent's tool surface (unread).

## 4. Delegation

There is an explicit and mature subagent mechanism:
`src/agent/subagents/manager.ts` + `subagent-launcher.ts` +
`context-budget.ts` (**subagents have their own token/context budget, separate
from the parent's** — `buildMinimalParentMemorySection`/
`shrinkParentMemorySection`/`hardTruncateReflectionPrompt` show parent memory
is injected into a subagent in trimmed form rather than in full) +
`spawnSubagent` (async, with a comment noting the timing "runs after several
async yields"). `[code]` — `src/agent/subagents/manager.ts` lines 92-189, 340,
726-803 (function names & docstrings; the implementation details weren't read
in full).

A subagent is defined as **a skill with extra frontmatter**:
`launchProfile: memory-subagent` in `subagents/builtin/memory.md` — the same
pattern as an ordinary skill (Markdown + YAML frontmatter) but with a
`launchProfile` marking it as spawnable as a separate subagent process rather
than injected as instructions into the main agent. `[code]` — the
`src/agent/subagents/builtin/memory.md` frontmatter.

**The result returning to the caller**: the `memory` skill is defined
explicitly as *"You run autonomously and return a **single final report** when
done. You **cannot ask questions** mid-execution."* — a fire-and-report
contract, not interactive, not a full transcript. `[code]` — `memory.md` lines
9-10.

## 5. State & resume

Three different state layers:

| Layer | Mechanism |
|---|---|
| The conversation transcript | The Letta server (through `@letta-ai/letta-client`) — not read in detail in this task |
| Agent memory | A per-agent git repo at `~/.letta/agents/<id>/memory/` (axis 2) |
| Pending turns | `QueuedTurnInput` (`user`/`task_notification`/`cron_prompt`) merged before sending |

`[code]` — `src/agent/memory-filesystem.ts` (the path constants),
`src/queue/turn-queue-runtime.ts` (the `QueuedTurnInput` type).

Resume: `resolve-startup-agent.ts` and `reconcile-existing-agent-state.ts`
exist as separate modules (filenames confirmed, contents unread) — showing
there is an explicit "reconnect to an existing agent" path when the CLI
restarts, consistent with an "agent as a persistent server-side entity" model
rather than a single-use session. `[code]` (the listing) / `[inferred]` (the
resume mechanism's details).

## 6. Safety gate

A **four-mode** permission system, similar in philosophy to Claude Code's but
with a different default:

```ts
export type PermissionMode = "standard" | "acceptEdits" | "unrestricted" | "strict";
export const DEFAULT_PERMISSION_MODE: PermissionMode = "unrestricted";
```

**An honest finding**: the default mode is `"unrestricted"`, not the strictest
one — contrasting with the common assumption that "a modern coding-agent
harness defaults to asking for approval". The code also preserves migrations
of the older mode names: `"default"` → `"standard"`,
`"bypassPermissions"`/`"fullAccess"` → `"unrestricted"` (literal
backwards-compatibility strings from earlier versions). `[code]` —
`src/permissions/mode.ts` lines 3-32.

Real OS-level sandboxing, with two backends: **Seatbelt** (macOS,
`sandbox/seatbelt.ts`) and **bubblewrap/`bwrap`** (Linux, `sandbox/bwrap.ts`),
both driven by the same declarative `FsSandboxPolicy` — `baseWritableRoots`,
`deniedRoots`, `readonlyRoots`, `writableRoots`, `restrictWrites`, with an
explicit application order: *"global write-deny → baseWritableRoots →
deniedRoots → writableRoots → readonlyRoots"* (specificity winning through
order rather than nesting depth). The concrete use cited in a code comment:
giving a memory subagent broad write access to `~/.letta` while still
**denying** access to another agent's `~/.letta/agents` (cross-agent memory
isolation) — except for a narrow carve-out for its own memory (`writableRoots`
beating `deniedRoots`). `[code]` — `src/sandbox/policy.ts` lines 1-40 (the
module docstring, the `FsSandboxPolicy` interface);
`src/permissions/cross-agent-guard.ts` (the filename, confirmed through a
reference in `policy.ts`'s comments).

## 7. Capability routing & policy

**Pure prose + model judgement, with four priority-layered sources** — the
same pattern as Agent Skills (Anthropic), which `deepagents` also uses. Skills
are discovered from:

1. Project skills (`.agents/skills/`, with a legacy `.skills/` fallback) —
   the highest priority, overriding.
2. Agent skills (`~/.letta/agents/{agent-id}/memory/skills/`).
3. Global skills (`~/.letta/skills/`).
4. Bundled skills (inside the npm package) — the lowest priority, the
   defaults.

`[code]` — `src/agent/skills.ts` lines 1-9 (the module docstring). Each skill
is a Markdown file with YAML frontmatter (`name`, `description`, `tools`,
`model`, optionally `launchProfile` for a subagent) — the model picks a skill
from the visible `description`, with no code classifier matching
keywords/paths as in OpenHands (`skills/trigger.py`, see `openhands.md`). This
is the same explicit contrast discussed in
`references/concepts/skill-composition.md` and
`references/concepts/policy-as-data.md`: source layering (project > agent >
global > bundled) is **declarative precedence** (who wins on a name clash),
but **which skill is relevant for a given turn** remains entirely model
judgement — there is no runtime decision enforced by code beyond the source
override order. `[code]` — `src/agent/skills.ts`,
`src/agent/skill-sources.ts` (the `SkillSource`/`ALL_SKILL_SOURCES` type
names).

## Sources

Two repos were shallow-cloned (`git clone --depth 1`) on 2026-08-23 and read
directly as files:

- `letta-ai/letta` (`github.com/letta-ai/letta`) — the `README.md` in full, to
  confirm its archived status and the new source's location. `git log
  --oneline -1` confirmed: `87fd37a chore: archive the legacy server
  repository (#3430)`.
- `letta-ai/letta-code` (`github.com/letta-ai/letta-code`, npm
  `@letta-ai/letta-code`):
  - `README.md` in full
  - `src/agent/memory.ts` lines 1-21 (`MEMORY_BLOCK_LABELS`, the `LET-7353`
    migration docstring)
  - `src/agent/memory-filesystem.ts` lines 1-60 (the module docstring, the
    `MEMORY_FS_ROOT`, `MEMORY_FS_AGENTS_DIR`, `MEMORY_FS_MEMORY_DIR` path
    constants)
  - `src/agent/subagents/manager.ts` lines 92-189, 340, 726-803 (function
    names through grep — contents not read in full)
  - `src/agent/subagents/builtin/memory.md` — in full (the frontmatter + the
    task description body)
  - `src/agent/skills.ts` lines 1-40 (the module docstring + the
    `getBundledSkillsPath` function)
  - `src/permissions/mode.ts` — in full (its first 32 lines, the
    `PermissionMode` type, `DEFAULT_PERMISSION_MODE`, `migratePermissionMode`)
  - `src/sandbox/policy.ts` lines 1-40 (the module docstring, the
    `FsSandboxPolicy` interface)
  - `src/queue/turn-queue-runtime.ts` lines 1-40 (the `QueuedTurnInput` type,
    the `MessageCreate` import from `@letta-ai/letta-client`)
  - Directory listings to confirm the structure (contents not read in detail):
    `src/permissions/*.ts` (>30 files — `sandbox-policy.ts`,
    `cross-agent-guard.ts`, `workspace-sandbox.ts`, `read-only-shell.ts`,
    etc.), `src/sandbox/{bwrap,seatbelt,wrap,availability}.ts`,
    `src/channels/{slack,telegram,discord,whatsapp,signal}/`, `src/cron/`,
    `src/agent/memory-git*.ts` (2128 lines in `memory-git.ts`, not read in
    full)

An honesty note: the actual tool-calling loop (an LLM turn ⇄ tools) runs on
the Letta **server** (a separate package/repo, possibly closed or in another
repo not verified in this task) — the axis 1 claims are limited to what
`letta-code` (the client) does before sending a turn, not how the server
executes it. `memory-git.ts` (2128 lines) and the `SubagentExecutor`
equivalent in `manager.ts` were **not** read in full — the claims are limited
to the module docstrings and function names cited.
