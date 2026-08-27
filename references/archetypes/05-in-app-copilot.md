# 5. In-App Copilot

## Definition

An agent that lives **inside** one product and may only act through that
product's own API (tag, resolve, insert a block, change a cell) - its tool
surface is deliberately narrow because it is bounded by the host
application's domain. Its horizon is short (one conversation/document/
ticket), and because its actions appear immediately in that same product's
UI, undo/rollback becomes critical: failing to correct a mistake costs
more here than in other archetypes.

Boundaries against neighbours: differs from **Workspace Agent** (01)
because its tool surface is a narrow product API rather than a generic
shell/filesystem; differs from **Workflow Agent** (06) because a human is
always actively using the application while the copilot acts, rather than
it running unsupervised in the background.

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | The host product's SaaS data (documents, tickets, boards) |
| Artifact | Actions in another system (the product itself) or in-place content edits |
| Horizon | Short - one conversation/document/ticket |
| Human control | Drafts/suggestions to review, or fast undo after the action |
| Domain surface | Vertical - bound to one product |
| Interface | API embedded in the product's UI (panel, inline suggestion) |

## Harness consequences

1. **Tools = the product's API, not generic tools** - every tool exposed to
   the agent must map 1:1 to an official product endpoint/action, because
   the blast radius is deliberately bounded by that product's domain.
2. **Undo/rollback is the primary safety gate**, not approval before the
   action - many in-app copilots choose a "draft first, send later" UX or
   "instant action but easy to undo", because per-step approval would kill
   the speed that justifies the product's existence.
3. **A short horizon forces fast context assembly** - there is no time for
   lengthy research; the relevant context (the active document, related
   tickets) must already be available from the host application's state
   rather than gathered through the agent's own search loop.
4. **State: mostly owned by the host application, not the agent** - the
   agent must not keep a copy of product state as its own source of truth;
   it reads and writes through the product's API so that two divergent
   sources of truth never exist.

## Example systems

- **Chatwoot Captain (Copilot)** `[code]` -
  `Captain::ReplySuggestionService#perform` makes a single LLM call
  (`make_api_call` with a system prompt plus a formatted conversation
  transcript), with no tool-calling loop and no automatic action - the
  result comes back as a draft for a human to edit or send. Actions that
  genuinely touch ticket state (resolve, add label, handoff) live in a
  separate tier (`enterprise/lib/captain/tools/`) as explicit tools, not
  as part of this draft-reply flow - code-level confirmation that "draft
  first" and "act through product tools" really are two different paths,
  not one autonomous loop. Source:
  `lib/captain/reply_suggestion_service.rb` (github.com/chatwoot/chatwoot).
- **Notion AI** `[inferred]` - from product behaviour: writes/edits blocks
  in place inside the currently open document, with undo through Notion's
  standard Ctrl+Z.
- **Figma AI** `[inferred]` - from product behaviour: actions limited to
  layers and components in the open file, never touching other files.
- **Salesforce Agentforce** `[inferred]` - from product behaviour: actions
  run through Salesforce objects/APIs (update a record, send an email),
  not free-form tools.

## Common pitfalls

1. **A product API tool that is too broad** (e.g. "update any record")
   instead of being scoped to the currently active object - the blast
   radius silently widens from "this document" to "the whole workspace"
   without the user realising.
2. **No undo path for certain actions** - once an action executes (send an
   email, delete a row) the product has no native rollback for it, even
   though this archetype's safety gate rests on undo rather than upfront
   approval.
3. **Context assembly using stale state** - the copilot reads a document/
   ticket snapshot from the start of the session, then writes back without
   checking whether a collaborator changed it - a silent overwrite.
4. **An "overconfident" draft** sent automatically with no review pause
   because the UX over-optimises for speed - this archetype fails most
   often at exactly this speed-vs-review trade-off.

## Building this with deepagents

- **Tool surface**: custom `tools=[...]` on `create_deep_agent` rather than
  the built-in `FilesystemMiddleware` - each tool is a thin wrapper around
  one host product API endpoint, mapped by hand. deepagents' built-in
  filesystem/bash is irrelevant for this archetype unless disabled through
  `permissions`. `[code]` - source: the `create_deep_agent` signature
  (`tools`, `permissions`), `graph.py`.
- **Safety gate**: `[ours]` not per-tool-call `interrupt_on` (that is the
  Workspace Agent pattern), but an explicit `undo_<action>` tool paired
  with each product action tool, invoked from the host UI rather than from
  the agent loop. deepagents' vanilla `HumanInTheLoopMiddleware` is
  designed for approve/edit/reject **before** execution; we diverge to an
  "act first, undo available" pattern because this archetype's short
  horizon makes an approval pause feel like a UX regression against a host
  product that is already fast.
- **Context**: no cross-session `memory=[...]`; context comes from host
  application state injected into `system_prompt`/`context_schema` per
  call, because a short horizon means there is no cross-document memory
  the agent needs to maintain. `[code]` - the `context_schema` parameter
  exists in `create_deep_agent`'s signature.
- **Backend/state**: the default `StateBackend` is enough (thread-scoped,
  not durable) - no `StoreBackend`/durable filesystem is needed because no
  file artifact must survive; the source of truth stays in the host
  product. `[code]` - source: `ARCHITECTURE.md`.

## Sources

- Chatwoot Captain `lib/captain/reply_suggestion_service.rb` - `[code]` -
  https://github.com/chatwoot/chatwoot
- deepagents `graph.py`, `ARCHITECTURE.md` - `[code]` - Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Notion AI, Figma AI, Salesforce Agentforce - `[inferred]` -
  closed-source product behaviour.
