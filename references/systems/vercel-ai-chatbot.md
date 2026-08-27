# Vercel `ai-chatbot`

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. `vercel/ai-chatbot`, Next.js App Router + the Vercel AI SDK
(`ai@7.0.15`, `@ai-sdk/react@4.0.16`) + Postgres (Drizzle) + optional Redis.
Chosen as the **artifact/canvas** exemplar per the T2 candidates in spec §10.
A naming note: the GitHub API confirms `vercel/ai-chatbot` has been renamed to
`vercel/chatbot` (`api.github.com/repos/vercel/ai-chatbot` returns
`"message": "Moved Permanently"`) - consistent with what
`references/concepts/artifacts-and-canvas.md` §Sources already records. The repo
was still cloned through the old URL (`git clone` follows the redirect
automatically), so what this file reads is the current `vercel/chatbot` content;
the filename `vercel-ai-chatbot.md` is kept per the file list in the task brief.

## Archetype

**In-App Copilot (05)** with **Generative Builder (02)** elements through its
*artifact* system (code/text/sheet documents created and edited as objects
separate from the chat transcript, canvas-like). A short horizon per HTTP turn
(`maxDuration = 60`), a narrow and fixed tool surface (5 named tools), no
subagent delegation. `[code]` - `app/(chat)/api/chat/route.ts` lines 49,
271-278.

## 1. Loop shape

Bounded ReAct: `streamText({ ..., stopWhen: isStepCount(5), tools: {...} })`
from the Vercel AI SDK - the harness installs a **hard 5-step limit** on tool
calls per turn (`isStepCount(5)`), not merely a far-off safety net (unlike
`deepagents`' `recursion_limit=9999` or OpenHands'
`max_iteration_per_run=500` - here 5 is the normal operating limit, not an
emergency one). Within those 5 steps the model decides to stop earlier by not
calling another tool; the SDK enforces the ceiling. `[code]` -
`app/(chat)/api/chat/route.ts` lines 269, 305.

## 2. Context

There is no compaction/summarisation on this path - `messages: modelMessages`
is passed straight from `convertToModelMessages(uiMessages)` with no condenser.
No history-summarising module was found in the `lib/ai/` read. `[inferred]` -
from the absence of any summariser/condenser import in
`app/(chat)/api/chat/route.ts` or `lib/ai/*`.

Instead, the **artifact** system moves large content (code/text/sheet
documents) **out** of the chat transcript from the start rather than through
later eviction: the `createDocument`/`updateDocument` tools write to the
`document` table (Postgres), and the transcript holds only the tool result
(usually a summary/diff) - the *artifact-by-reference* pattern argued in
`references/concepts/artifacts-and-canvas.md` and the derived rule in design
spec §8.1. `[code]` - `lib/artifacts/server.ts` lines 1-45 (`DocumentHandler`,
`saveDocument`), `lib/db/schema.ts` lines 73-90 (the `document` table).

## 3. Tool surface

A few explicitly named, fixed tools that don't change per turn: `getWeather`,
`createDocument`, `editDocument`, `updateDocument`, `requestSuggestions`. With
one **deterministic** exception: if the model is a *reasoning model* that
doesn't support tool calling (`isReasoningModel && !supportsTools`),
`activeTools` is set to an empty array - the tool surface is cut entirely based
on model capability, checked in code rather than decided by the model. `[code]`
- `app/(chat)/api/chat/route.ts` lines 269-278, 306-316.

## 4. Delegation

**Flat, no subagents.** No spawn-another-agent mechanism, task tool, or handoff
was found in `app/(chat)/api/chat/route.ts` or `lib/ai/` - one `streamText`
call, one model, tools executed inline within the same SDK loop. `[inferred]` -
from the absence of any subagent/delegation module in the directories read.

## 5. State & resume

- **The transcript**: the `message` table (`Message_v2`) in Postgres, converted
  back and forth through `convertToModelMessages`/`convertToUIMessages`.
  `[code]` - `lib/db/schema.ts` line 42, `lib/utils.ts` (the
  `convertToUIMessages` function referenced in the `route.ts` import at line
  43).
- **Versioned artifacts**: the `document` table uses a **composite primary key
  `(id, createdAt)`** - every document edit is a **new row**, not an in-place
  `UPDATE`; `suggestion` references a specific document version through
  `(documentId, documentCreatedAt)`. This is an append-only versioning pattern
  matching "S3/GCS + metadata rows, permanent, versioned" in design spec §8.1
  exactly (here Postgres rows rather than an object store, but the append-only
  principle is the same). `[code]` - `lib/db/schema.ts` lines 73-114.
- **Stream resume**: a `stream` table + `createStreamId({chatId, streamId})` +
  `resumable-stream` (the npm package `resumable-stream`,
  `createResumableStreamContext`). **Explicitly conditional on `REDIS_URL`**:
  `if (!process.env.REDIS_URL) { return; }` before
  `streamContext.createNewResumableStream(...)` is called - without Redis,
  stream resume is **silently inactive** (not an error, not an automatic
  fallback). `[code]` - `app/(chat)/api/chat/route.ts` lines 405-421. The
  reattach endpoint `GET /api/chat/[id]/stream` in the source read **only
  returns `Response(null, {status: 204})`** - the endpoint body that would
  normally read `streamContext.resumableStream(...)` to splice a dropped
  connection has no content in the cloned snapshot. `[code]` -
  `app/(chat)/api/chat/[id]/stream/route.ts` (in full, 3 lines). **An honest
  finding**: this contrasts with the common expectation of "Vercel ai-chatbot =
  the complete resumable stream example" - at the commit read, the GET reattach
  path appears to be a stub/placeholder rather than an active implementation.
  Whether this is a temporary regression, a refactor in progress, or reattach
  having moved to another mechanism (e.g. client polling of
  `getMessagesByChatId`) was not verified - stated as an uncertainty rather
  than claimed as a bug. `[code]` (the file's contents as they are) +
  `[inferred]` (the interpretation of its cause).

## 6. Safety gate

There is no per-tool approval gate (the available tools create content rather
than performing destructive/shell actions). The gates that exist operate at the
**request** level rather than the tool-call level: `checkBotId` (bot detection
before processing runs) and `checkIpRateLimit` are called at the start of the
`POST` handler, plus `entitlementsByUserType` limiting model quota per user
type. `[code]` - the `botid/server`, `checkIpRateLimit`, and
`entitlementsByUserType` imports in `app/(chat)/api/chat/route.ts` lines 15,
40-41. There is no code execution sandbox - a "code" artifact merely *stores*
code text, with no evidence of server-side code execution in the files read.
`[inferred]`.

## 7. Capability routing & policy

**Deterministic in code, based on model metadata - not model judgement, not a
trained classifier, not a per-request manifest.** The only capability branch
found: `activeTools: isReasoningModel && !supportsTools ? [] : [...5 fixed
tools]` - model properties (`isReasoningModel`, `supportsTools`, both static
fields from the model catalogue in `lib/ai/models.ts`) determine the tool
surface, evaluated per request but deterministic for the same model. `[code]` -
`app/(chat)/api/chat/route.ts` lines 269-278; `getCapabilities` and
`getModelAvailability` imported from `lib/ai/models.ts` (lines 18-19).

There is no additional skill/mode routing mechanism (no skill registry, no
inter-agent handoff) - this system's capability routing scope is far narrower
than `deepagents`/OpenHands/LibreChat's because it genuinely has one agent and
one fixed tool set. `[inferred]` - from the scope of `lib/ai/` read (`tools/`,
`models.ts`, `prompts.ts`, `providers.ts`).

## Sources

The `vercel/ai-chatbot` repo was shallow-cloned (`git clone --depth 1`) on
2026-08-23 and read directly as files:

- `app/(chat)/api/chat/route.ts` - in full (470 lines): the imports (1-45),
  `getStreamContext`/`createResumableStreamContext` (13, 60-68), the `POST`
  handler, the `streamText` call (260-330), `consumeSseStream` + the
  `REDIS_URL` gate (405-425)
- `app/(chat)/api/chat/[id]/stream/route.ts` - in full (3 lines)
- `app/(chat)/api/chat/schema.ts` - its filename confirmed, contents not read
  in detail
- `lib/artifacts/server.ts` - lines 1-50 (`DocumentHandler`,
  `createDocumentHandler`, the `CreateDocumentCallbackProps` type)
- `lib/db/schema.ts` - lines 28-134 (`chat`, `message`, `vote`, `document`,
  `suggestion`, `stream` - table names & primary keys)
- `lib/ai/tools/*.ts` - a listing (`create-document.ts`, `edit-document.ts`,
  `get-weather.ts`, `request-suggestions.ts`, `update-document.ts`)
- `package.json` lines 22-40 (`ai@7.0.15`, `@ai-sdk/react@4.0.16`,
  `@ai-sdk/provider@4.0.2`, `@ai-sdk/otel@1.0.15`)

An honesty note: `lib/ai/models.ts`, `lib/ai/prompts.ts`,
`lib/ai/providers.ts`, and the contents of the three `artifacts/*/server.ts`
files (`code/server.ts`, `sheet/server.ts`, `text/server.ts`) were only cited
through imports/listings and **not** read in full - the claim that
`isReasoningModel`/`supportsTools` are static fields in `models.ts` is inferred
from the `getCapabilities`/`getModelAvailability` function names rather than
from reading the type definitions directly.
