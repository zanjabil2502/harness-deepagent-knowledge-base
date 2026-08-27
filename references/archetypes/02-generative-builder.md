# 2. Generative Builder

## Definition

An agent that builds a **new** artifact (app, website, deck) from scratch
inside a sandbox it owns, with live preview as the primary iteration loop.
Its state is a single versioned artifact rather than a general filesystem,
and the sandbox's own persistence is short - once the session ends, the
artifact must be published/exported or it is lost.

Boundaries against neighbours: differs from **Workspace Agent** (01)
because it never touches the user's existing repo/machine - it always
starts from nothing in its own sandbox; differs from **Computer-Use
Agent** (07) because it generates its own code/assets rather than driving
a third-party UI through see-click-verify.

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | Its own sandbox (container/webcontainer, not the user's machine) |
| Artifact | Something new (app/site/deck from scratch) |
| Horizon | One session, one artifact |
| Human control | Review at the end / through interactive preview, little per-step approval |
| Domain surface | General, but often wrapped as a vertical ("app builder") |
| Interface | Canvas/preview pane |

## Harness consequences

1. **A sandbox is mandatory, not optional** - generated code is executed
   immediately (`npm install`, dev server), and that must not touch the
   user's machine or production data; the blast radius has to stay
   confined to compute the system owns.
2. **State = a single versioned artifact**, not a general filesystem - the
   mental model is one "project" per session, so context, undo, and
   publish all revolve around a single object rather than a free-form file
   graph like a Workspace Agent.
3. **Loop shape: full rewrite vs granular patch** is chosen explicitly per
   turn - full rewrite is cheap for large structural changes but wasteful
   for small ones; the two need different tool paths.
4. **Short persistence by design** - sandboxes are ephemeral and can
   expire; the artifact becomes the backend's property through an explicit
   publish/export step rather than living forever in sandbox compute.

## Example systems

- **bolt.diy** `[code]` - one `WebContainer` instance is booted per session
  (`WebContainer.boot({coep: 'credentialless', workdirName, forwardPreviewErrors: true})`),
  and a `webcontainer.on('preview-message', ...)` listener captures
  uncaught exceptions/unhandled rejections from the preview iframe and
  forwards them as an `actionAlert` to the UI - the sandbox and its
  preview error signal are configured explicitly in code, not merely
  claimed in marketing. Source: `app/lib/webcontainer/index.ts`
  (github.com/stackblitz-labs/bolt.diy) - the open-source fork of
  bolt.new.
- **v0 (Vercel)** `[inferred]` - from product behaviour: live React/Next.js
  preview per iteration, one artifact per conversation.
- **Lovable** `[inferred]` - from product behaviour: scaffolds a full app
  from a prompt, iterating through chat with a live preview.
- **Figma Make** `[inferred]` - from product behaviour: the artifact is one
  interactive prototype per session, with instant preview.

## Common pitfalls

1. **The sandbox expires before the user exports** - work is lost because
   there is no explicit publish/save-to-storage step separate from the
   sandbox lifecycle.
2. **Full rewrite for a small change** - wasteful in tokens, and it resets
   runtime UI state (scroll position, form contents) on every iteration
   because the whole artifact is rewritten instead of patched.
3. **Preview lag or a silently failing build** - the user doesn't know the
   last iteration is broken until they refresh, because no explicit "build
   failed" signal is returned into the conversation loop.
4. **The sandbox becomes an abuse vector** (crypto miner, unrestricted
   network egress) when sandbox resources and network policy aren't
   bounded - a blast radius of "our own sandbox" still carries real cost
   if it isn't isolated.

## Building this with deepagents

- **Backend**: a sandbox-family backend - e.g. `DaytonaSandbox` from the
  partner package `langchain_daytona`
  (`backend = DaytonaSandbox(sandbox=..., timeout=300)`), or through the
  deepagents CLI with `agent.json`:
  `{"backend": {"type": "sandbox", "sandbox_config": {"scope": "thread",
  "policy_ids": [...]}}}`. `[code]` - source:
  `libs/partners/daytona/README.md` and `libs/cli/README.md`
  (langchain-ai/deepagents).
- **Middleware**: the default `FilesystemMiddleware` (`write_file`,
  `edit_file`, `execute` tools) runs on top of that sandbox backend rather
  than local disk - every filesystem operation is automatically confined
  to the sandbox. `[code]` - source: `middleware/filesystem.py`.
- **Persistence**: no `checkpointer`/`store` for short sessions that are
  meant to be discarded; if the artifact must survive across threads (e.g.
  the user returns tomorrow to continue the same project), add a
  `StoreBackend` as a durable route - an explicit choice, not a default.
  `[code]` - source: `ARCHITECTURE.md`.
- **Safety gate**: `[ours]` minimal interrupts, or no `interrupt_on` at
  all for the build/iterate loop, with the gate installed only on the
  publish/deploy tool. Vanilla deepagents does not force HITL - the
  default is `interrupt_on=None` - so this is not a divergence from the
  library but a deliberate product choice: this archetype's human control
  is "review at the end through the preview", not approving every step the
  way a Workspace Agent (01) does.

## Sources

- bolt.diy `app/lib/webcontainer/index.ts` - `[code]` -
  https://github.com/stackblitz-labs/bolt.diy
- deepagents `libs/partners/daytona/README.md`, `libs/cli/README.md`,
  `middleware/filesystem.py`, `ARCHITECTURE.md` - `[code]` - Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- v0, Lovable, Figma Make - `[inferred]` - closed-source product behaviour.
