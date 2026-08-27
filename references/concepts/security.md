# Security

## Problem

A model has no structural way to distinguish "an instruction from the
legitimate user" from "text that happens to appear in a tool result" - both
enter the context as equally convincing tokens, and models are trained to
follow convincing instructions whatever their source. In an agent loop, most
of the content entering the context is **not** from the user: web fetch
results, retrieved document contents, API responses, the contents of files
read by tools. Every one of those is an attack path that never passes
through the input filter at all (which typically only inspects the user's
first message) - an attacker needn't talk to the chat, only plant
instructions in a web page/document/email the agent **will** read on behalf
of a legitimate user. `[docs]` The OWASP Gen AI Security Project labels this
LLM01:2025 Prompt Injection, with the *indirect* variant matching exactly
the pattern above: "attackers embed instructions in documents, websites, or
other content that the LLM later processes" - and ranks it risk #1 for the
second edition running.

The second problem is the first combined with agency: an agent usually holds
one service identity (the operator's API key, a service account, a bot
token) used for **all** users, rather than a narrow per-user identity. If
executed tool calls use that service identity's full authority - rather than
authority narrowed to the user and the action being requested - the agent
becomes a *confused deputy*: its service identity is legitimate, but the
scope of its actions should not be that large. `[docs]` OWASP GenAI states
exactly this combination: "the combination of tools performing actions on
behalf of users with exposure to untrusted input effectively allows
attackers to make these tools do whatever they want" (LLM06:2025 Excessive
Agency) - prompt injection and confused deputy aren't two independent risks;
one is the way in for the other.

The third problem is specific to multi-user systems: retrieval (RAG) has an
authorisation surface of its own, separate from the application database.
`isolation-and-scoping.md` and `persistence-schema.md` already establish the
`user_id` + RLS scope model for the application's Postgres tables - this
file **proposes no new model** - but the retrieval index (a vector store, a
search engine) is often **not** that same Postgres, doesn't automatically
inherit the RLS enforced on those tables, and can leak through a bug shaped
exactly like the manual `WHERE` case described in `isolation-and-scoping.md`
§Problem - only in a different system.

The fourth problem: an agent that writes code (the Generative Builder
archetype) can put real secrets into generated files - either because the
secret is in the context already (an env var/connection string read and then
quoted back as an example) or because the agent generates a placeholder that
happens to be validly shaped and is later treated as a real secret.

## Pattern

### Prompt injection through tool results - layered defence, not one filter

No single guardrail closes this alone; three complementary layers (drawn
from `guardrails.md` points 1-3, not re-proposed here):

1. **Mark untrusted content explicitly** - tool/retrieval results are
   tagged (a delimiter/role metadata) as data rather than instructions when
   they enter state (guardrail point 2). This is a signal for the other
   guardrails and for the model, **not** a prevention - a tag doesn't stop a
   model that still decides to follow instructions inside the tagged data.
2. **Least-privilege tool scope as the second defence** - even if an
   injection succeeds in persuading the model, the model can only call tools
   allowlisted for that role/context (guardrail point 3). A successful
   injection with restricted tools = a small blast radius.
3. **Instructions arriving through tool results never get a shortened
   gate** - if the agent "infers" a new instruction from a tool result and
   immediately executes it, that is a new instruction and must pass the same
   approval/allowlist gate as an instruction from the user (guardrail point
   3, the approval gate) - no shortcut because "the instruction sounded
   reasonable".

### Confused deputy & narrowing token scope

The countermeasure: never hand the agent a full service-identity credential
to use as-is on every tool call. Instead, **mint a narrow credential per
turn/tool call** reflecting (a) the `user_id` being processed and (b) the
minimum action that tool needs - not the service identity's full authority:

- For Postgres access: this is **exactly** the `SET LOCAL
  app.current_user_id` pattern already established in
  `isolation-and-scoping.md` - the connection the tool uses remains one DB
  identity, but RLS forces every query on that connection to be scoped to
  the active `user_id` regardless of what the model asks for. An agent
  successfully persuaded to run an arbitrary query still cannot see another
  user's rows - not because the model is honest, but because Postgres
  enforces it beyond the model's reach.
- For external APIs (Slack, GitHub, etc.): if the provider supports
  narrowly scoped tokens (a per-repo GitHub App installation token, a
  per-user Slack OAuth token), use those per turn - not one app-wide bot
  token injected into every tool call regardless of who asked.

### Authorisation leaks in multi-user retrieval

The scope model remains `user_id` as established in
`isolation-and-scoping.md`/`persistence-schema.md`. What differs here:
retrieval often has a **second index** (a separate vector store, a search
engine) not covered by Postgres RLS, and the authorisation filter in that
index has to be enforced separately:

- **Filter the scope inside the ANN query, before top-k is computed** - not
  by taking top-k from the whole index and discarding results that aren't
  the user's (a query that "forgets" that filter still returns top-k from
  the whole index, a bug shaped identically to the forgotten manual `WHERE`
  in `isolation-and-scoping.md` §Problem, only in a vector store rather
  than Postgres).
- If the vector store in use supports native metadata filters (e.g. a
  `user_id` filter applied **before** the similarity search rather than as
  an application post-filter), use it - an application post-filter means the
  top-k similarity scores were computed across cross-user candidates, and if
  that post-filter is forgotten on one endpoint, the leak is identical to
  forgetting to install RLS.

### Secret scanning in generated code

The enforcement point is the same as `guardrails.md` point 4 (Output) - not
re-proposed here; only two secret sources need different handling:

- **Real secrets already in the context** (env vars, a connection string a
  tool read and the model then quoted into a new file) - prevented at the
  Input/Retrieval point by redaction before that content enters the context
  at all (the same pattern as `PIIMiddleware`, but with secret-pattern
  detectors: `sk-…`, `AKIA…`, PEM private key headers, etc.), not filtered
  afterwards at Output.
- **A placeholder that happens to look valid** - prevented at the
  Output/pre-write point: scan the diff about to be written for secret
  patterns, before `write_file`/`edit_file` commits to disk. The tooling is
  the same as for human-written code (e.g. the gitleaks/trufflehog class) -
  agent-written code needs no special treatment; only the installation point
  must be **before** the commit rather than after (see the fail-closed
  failure mode in `guardrails.md` for this line).

## Trade-offs

- **Narrowly scoped tokens per tool call vs one shared service credential**
  - narrow tokens are genuine defence in depth (the blast radius of an
  injection/compromise is limited to one user and one action, exactly what
  closing the confused deputy requires) but add real infrastructure cost (a
  token minting service, rotating short-lived credentials, per-provider
  integration work). A shared credential is cheap up front - which is why
  confused deputy is common in early-stage agent products - but narrowing
  must be adopted as soon as a tool touches anything privileged, not
  deferred indefinitely.
- **Tagging untrusted content vs trusting the model's judgement** - tagging
  is cheap (deterministic, applied once in the tool wrapper) but doesn't
  stop injection on its own - it only signals the next layer. It must be
  combined with a tool allowlist (point 3), not stand alone.
- **A scope filter inside the ANN query vs a separate index per user** - an
  in-query filter is operationally cheaper (one index, one ingest pipeline)
  but every query must remember to apply the filter (the same bug shape as
  the manual `WHERE` - in a codebase that lives long enough, one will
  certainly be forgotten, the same argument as `isolation-and-scoping.md`);
  a separate index per user makes that mistake structurally impossible (you
  cannot query the wrong index without naming it explicitly) at the cost of
  an index count growing linearly with users - sensible only for a bounded
  user population (on-prem enterprise, dozens of tenants), not consumer
  scale with millions.

## In deepagents

`deepagents` has no built-in retrieval/web fetch tool, and
`PatchToolCallsMiddleware` only patches dangling `ToolMessage`s in history -
it doesn't mark content trust levels. `[code]` - cited from
`../systems/deepagents.md` §Built-in middleware. Consequently:

- **Marking untrusted content** is 100% the responsibility of the custom
  tools the application installs (retrieval/web fetch), through the content
  of the `ToolMessage` returned or through a `wrap_tool_call` hook wrapping
  the result before it enters state - as described in `guardrails.md` §In
  deepagents point 2, not re-proposed here.
- **Narrowing token scope for Postgres** uses exactly the pattern
  established in `isolation-and-scoping.md` §In deepagents: `deepagents`
  never creates a DB connection itself, so `SET LOCAL app.current_user_id`
  is installed in the custom tool layer that creates that connection -
  executed per transaction, not once per pooled connection.
- **`FilesystemBackend`/`LocalShellBackend` have no scoping *hook*** - the
  same fact already recorded in `isolation-and-scoping.md` §In deepagents,
  relevant again here because if one agent process serves many users on
  these backends, that process itself **is** the deputy holding the host
  filesystem identity - isolation between users has to be built at the
  process/container layer, not something that comes free from `deepagents`.
  `[code]` - cited from `../systems/deepagents.md` §Filesystem backend.
- **`StoreBackend(namespace=...)`** remains the official scoping *hook* for
  durable cross-thread state - re-cited from `isolation-and-scoping.md`, not
  re-proposed here.
- **Pre-write secret scanning** is installed at the same point as
  `guardrails.md` §In deepagents point 4 (`after_model`, or a hook before
  `write_file`/`edit_file` commits) - `deepagents` has no built-in mechanism
  for it.

## Sources

- `[docs]` OWASP Gen AI Security Project -
  `genai.owasp.org/llmrisk/llm01-prompt-injection` (LLM01:2025 Prompt
  Injection, direct vs indirect) and `genai.owasp.org/llmrisk/llm06-...`
  (LLM06:2025 Excessive Agency, quoted directly on the combination of
  tools-acting-on-behalf-of-users + untrusted input = confused deputy).
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) - the
  `user_id` scope model, the `SET LOCAL app.current_user_id` pattern,
  `FORCE ROW LEVEL SECURITY`, the `FilesystemBackend`/`StoreBackend` facts -
  re-cited without proposing a new model, per the task instruction.
- `[code]` [`persistence-schema.md`](persistence-schema.md) - the RLS DDL
  underpinning the argument that "authorisation is enforced in the DB, not
  in application code that can forget".
- `[code]` [`guardrails.md`](guardrails.md) - points 1-4 (input tagging,
  tool allowlist, approval gate, Output secret scanning) referenced
  repeatedly in this file as concrete enforcement points, not re-proposed.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §Built-in
  middleware (`PatchToolCallsMiddleware`), §Filesystem backend - a tier-1
  reference verified in Task 3, cited without re-reading the `deepagents`
  source in this task.
