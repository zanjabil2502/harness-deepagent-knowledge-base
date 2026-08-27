# Technical best practices - extracted from the official deepagents docs

Practices **stated by** the official documentation at
`docs.langchain.com/oss/python/deepagents/`, distilled from the 40-page
snapshot in
[`../upstream/deepagents-docs/`](../upstream/deepagents-docs/README.md).

## How to read this file

Every item names the page and line in the snapshot, so each claim can be
traced back to its original sentence. Three things to hold onto:

- **This is `[docs]`, not `[code]`.** When the installed package's source
  contradicts a documentation page, the source wins. In several items
  below that contradiction has already been found and is flagged.
- **Some "Tips" are product placement.** Of the 76 `<Tip>`/`<Warning>`
  blocks harvested, a dozen or so are invitations to use LangSmith
  (tracing, Deployments, Engine, Gateway, Sandboxes, Fleet). That isn't
  vendor-neutral engineering advice - "install observability" remains
  true, but the tool choice is yours. Product-linked items are gathered
  under §Read with skepticism rather than mixed into the technical ones.
- **Some warnings are stale.** The documentation still carries transition
  notes from older versions; the ones spotted are called out in place.

Items covering interpreters, PTC, and dynamic subagents are not repeated
here - they all live in
[`../concepts/code-orchestration.md`](../concepts/code-orchestration.md).

## 1. Invocation & multi-user

**Every invocation carries two run-level parameters, and they are
independent.** `thread_id` (through `config={"configurable": {...}}`)
determines the **conversation** - message history and checkpoints.
`context` carries **per-run** data that tools and middleware read:
`user_id`, API keys, feature flags, session metadata; its shape is
declared through `context_schema` and accessed through `runtime.context`.
Changing one does not affect the other, and they are almost always passed
together. `[docs]` - `going-to-production.md` lines 67-69, 322-324.

For a `user_id`-based multi-user pattern, this is exactly the right
separation: user identity must **not** be derived from `thread_id`,
because one user can have many threads and `thread_id` comes from the
client.

**Three primitives determine what is shared**: Thread (one conversation;
history and scratch files don't carry outside it), User (memory and files
may be private or shared; identity and authorisation come from your own
auth layer), Assistant (a configured agent instance). `[docs]` -
`going-to-production.md` lines 15-17.

**Build async from the start.** LLM workloads are I/O-bound; three
concrete recommendations: write natively async tools (LangChain runs sync
tools on a separate thread - it works, but adds threading overhead), use
async middleware hooks (`abefore_agent`, not `before_agent`), and await
external resource lifecycles (sandbox creation, MCP server connections).
`[docs]` - `going-to-production.md` lines 387-397.

## 2. Backends & filesystem

**Choose a backend by what must survive, not by convenience.**
`StateBackend` (the default) = per-thread scratch, surviving across turns
through the checkpointer but not across threads - **checkpointed at every
step, so avoid writing large files**. `StoreBackend` = cross-thread, and
must be scoped through a namespace factory. `CompositeBackend` = a mix,
per-thread scratch by default with cross-thread routes for specific paths
like `/memories/`. `[docs]` - `going-to-production.md` lines 551-561.

**`FilesystemBackend` and `LocalShellBackend` must not be used in deployed
agents.** The documentation names them explicitly as "inappropriate use
cases: web servers or HTTP APIs" and "production environments (such as web
servers, APIs, multi-tenant systems)". `[docs]` - `backends.md` lines 207,
346; `going-to-production.md` line 566.

Two details determine whether their protection is real:

- `virtual_mode=True` **must** accompany `root_dir` to enable path
  restrictions (blocking `..`, `~`, and absolute paths outside the root).
  The default is `virtual_mode=False`, which **provides no security at all
  even with `root_dir` set**. `[docs]` - `backends.md` line 230.
- On `LocalShellBackend`, `virtual_mode=True` provides **no security
  whatsoever**, because shell commands can reach any path on the system.
  `[docs]` - `backends.md` line 375.

This is the same pattern as the RLS-under-superuser finding in
[`../concepts/isolation-and-scoping.md`](../concepts/isolation-and-scoping.md):
a control that looks active while its prerequisite is unmet.

**Wrap `FilesystemBackend` in a `CompositeBackend`** for nearly every
case. The reason isn't style: deepagents writes its own internal data to
the backend - large tool results offloaded to `/large_tool_results/` and
conversation history to `/conversation_history/`. With a bare
`FilesystemBackend`, all of that lands on real disk under `root_dir`,
mixed in with project files. Route `/workspace/` to `FilesystemBackend`
and leave the rest on `StateBackend`. `[docs]` - `backends.md` line 322;
`customization.md` line 1947. See [`middleware.md`](middleware.md)
§`artifacts_root` for the mechanism that decides where those prefixes
actually write.

**`StoreBackend`'s namespace is already mandatory, no longer advice.**
The documentation says "The `namespace` parameter will be **required** in
v0.5.0" (`[docs]` - `backends.md` line 631) - a transition warning that
has already passed. In `deepagents==0.7.8`, `namespace` is a keyword-only
argument **with no default**, so forgetting it fails at construction
rather than silently sharing data. `[code]` -
`deepagents/backends/store.py` lines 99-104.

**Backend methods outside a graph run have no effect.** Calling
`state_backend.upload_files(...)` outside graph execution does not take
effect until the graph runs. `[docs]` - `backends.md` line 191.

**The backend factory pattern is deprecated** as of 0.5.0 - pass a
constructed backend instance, not a factory function. `[docs]` -
`backends.md` line 1075.

## 3. Context

**Context compression is already on with no extra middleware.** Every
`create_deep_agent` already includes offloading and summarization; nothing
needs installing. `[docs]` - `context-engineering.md` line 811.

Its default numbers are worth knowing before tuning anything:

- Offloading happens when a tool's input **or** result exceeds **20,000
  tokens**. Large results are replaced by a file path plus a 10-line
  preview; large inputs are trimmed to a pointer once session context
  crosses **85%** of the model's window. `[docs]` -
  `context-engineering.md` lines 831-841.
- Summarization triggers at **85% of `max_input_tokens`** from the model
  profile, keeps **10%** of tokens as recent context, and falls back to
  **170,000 tokens / 6 messages** when the model profile is unavailable.
  If a model call raises `ContextOverflowError`, the agent immediately
  falls back to summarization and retries. `[docs]` -
  `context-engineering.md` lines 860-866.
- Summarization writes two things: a structured summary in context
  (session intent, artifacts, next steps) **and** a text rendering of the
  original conversation to the filesystem as the canonical record.
  `[docs]` - `context-engineering.md` lines 852-856.

**Trim tool schemas before any compression runs.** Unused built-in tools
still send their full schema **every turn**. `excluded_tools` on a harness
profile removes them and shrinks the baseline prompt for the whole run -
this is configuration rather than automatic compression, and it acts
earlier than either. `[docs]` - `context-engineering.md` line 315.

**Summarization tokens leak into streaming.** Filter through metadata:
`metadata.get("lc_source") == "summarization"`. Without it, the internal
summary appears in the UI as an assistant answer. `[docs]` -
`context-engineering.md` lines 869-881.

**Binary tool output goes to the backend rather than being returned
whole.** When a tool produces an image or large binary data, save the
artifact to the backend and return a short text description plus a
path/URL. Built-in compression does **not** shrink images or lower their
resolution, so media that enters context stays there at full size.
`[docs]` - `multimodal.md` line 64; `context-engineering.md` lines
844-846.

**Six practices the documentation summarises itself**: start from the
right input context (minimal memory for always-relevant conventions,
focused skills for per-task capability); delegate heavy work to subagents;
if debugging shows a subagent producing long output, add summarising
guidance to its `system_prompt`; use the filesystem for large output;
document the long-term memory structure to the agent; pass user
metadata/API keys/static configuration through `context`. `[docs]` -
`context-engineering.md` lines 1210-1216.

## 4. Delegation & subagents

**The result contract is set through the subagent's `system_prompt`, and
that really is the only lever.** The explicit recommendation: instruct the
subagent to return a summary rather than raw data - the documentation's
example uses "Return only the essential summary (under 500 words). Do NOT
include raw search results or detailed tool outputs." `[docs]` -
`context-engineering.md` lines 1024-1036. This is the practical side of
the result contract in
[`../concepts/delegation.md`](../concepts/delegation.md).

**For large data, the subagent writes to a file and the parent reads what
it needs** - rather than returning it through a message. `[docs]` -
`context-engineering.md` line 1040.

**Running an agent without the `task` tool** requires two things at once:
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`
**and** passing no synchronous subagents through `subagents=`.
`SubAgentMiddleware` is only installed when at least one synchronous
subagent exists. Async subagents are unaffected. `[docs]` -
`profiles.md` line 68; `subagents.md` line 71.

**Don't use `excluded_middleware` for that.** Listing
`FilesystemMiddleware`, `SubAgentMiddleware`, or the internal permission
middleware in `excluded_middleware` raises `ValueError` - all of them are
required scaffolding. To hide their tools from the model without removing
the middleware, use `excluded_tools`. `[docs]` - `profiles.md` line 68;
`subagents.md` line 71. The enforcement mechanism is in
[`middleware.md`](middleware.md) §Exclusion.

## 5. Skills

This page is relevant twice: as a way of giving the agent capability, and
as the specification this KB itself follows.

**Two layers, two budgets.** Each skill's frontmatter enters the system
prompt at discovery; its body is only read on activation. Hence: concise
frontmatter, a `SKILL.md` body **under 5,000 tokens**, and the Agent
Skills specification's recommendation of `SKILL.md` **under 500 lines**.
Keeping both small lets many skills load without crowding the context
window. `[docs]` - `skills.md` lines 197, 214.

**`description` is the only information the agent sees when choosing.** It
must state **what** the skill does **and when** to activate it, with
keywords that can be matched. "Helps with PDFs." is named by the
documentation as an example too vague for reliable matching. `[docs]` -
`skills.md` lines 199-212.

**A few well-scoped skills beat many overlapping ones.** Overlapping
descriptions make the agent activate the wrong skill or hesitate between
options; if two skills serve similar purposes, consolidate them. The more
similarly-described skills exist, the worse the agent gets at picking the
right one. `[docs]` - `skills.md` lines 212, 239-243.

**File references one level from `SKILL.md`.** Deeply nested reference
chains force the agent through several reads before reaching the
information. The agent does **not** discover supporting files on its own -
`SKILL.md` must state what each file contains and when to use it.
`[docs]` - `skills.md` lines 230, 1776.

**Three silent failures to check when a skill doesn't activate**: a
`SKILL.md` over **10 MB** is skipped at discovery with no error; the
frontmatter `name` must match the parent directory name; and when the same
skill name appears in several sources, **the last source wins** - an old
or empty skill from a later path can override the intended one. `[docs]` -
`skills.md` lines 1841, 1766-1768.

**Skills are not automatically present inside a sandbox.** Skill files
outside the container are unavailable until copied in. `[docs]` -
`skills.md` line 1780.

## 6. Memory

**The default is user scope.** Its scope table: `(user_id)` for per-user
preferences and context (called the "recommended default"),
`(assistant_id)` for instructions shared by one assistant, `(org_id)` for
read-only policies across all users. `[docs]` - `going-to-production.md`
lines 425-429.

**Shared memory is a prompt injection vector.** If one user can write to
memory that another user's conversation reads, a malicious user can inject
instructions into shared state. Mitigation is layered: default to user
scope; make shared policies **read-only** and populate them from
application code (not by the agent); require human approval before the
agent writes to sensitive paths; enforce through `permissions`
(declarative) or a backend policy hook (custom logic). `[docs]` -
`going-to-production.md` lines 431-433; `memory.md` lines 473-486.

**Concurrent writes to the same file = last-write-wins.** Rarely a problem
for user-scoped memory (one user usually has one active conversation), but
real for assistant/organisation scope. Mitigation: serialise through
background consolidation, or split memory into separate files per topic to
reduce contention. `[docs]` - `memory.md` lines 488-492.

**Several agents in one deployment** are separated by adding
`assistant_id` to the namespace, e.g.
`namespace=lambda rt: (rt.server_info.assistant_id, rt.server_info.user.identity)`.
`[docs]` - `memory.md` lines 494-508.

**A scheduled consolidation must stay in sync with its lookback window.**
If the cron runs more often than the lookback, the same conversations are
reprocessed; less often, and memories falling outside the window are lost.
`[docs]` - `memory.md` line 466.

## 7. Permissions

**Evaluation is first-match-wins, and when no rule matches the call is
ALLOWED.** This permissive default determines the shape of the rule list:
specific rules first, a closing `deny` on `/**` last. The documentation
includes a wrong example that becomes exactly this bug - `/workspace/**`
in allow mode placed before `/workspace/.env` in deny mode, so the deny is
never reached. `[docs]` - `permissions.md` lines 53, 193-236.

In the framing of [`../concepts/guardrails.md`](../concepts/guardrails.md),
a default with no closing rule is **fail-open**.

**The coverage of `operations` is less intuitive than its names**:
`"read"` covers `ls`, `read_file`, `glob`, `grep`; `"write"` covers
`write_file`, `edit_file`, `delete`. `[docs]` - `permissions.md` lines
49-51.

**`interrupt` patterns must be anchored with a literal leading segment**
(e.g. `/secrets/**`, not `/**/secrets`). Bulk tools (`ls`, `glob`, `grep`,
and `delete` on a directory) fire the interrupt when their search subtree
**could** intersect the rule's prefix, so an unanchored pattern over-fires
conservatively. `[docs]` - `permissions.md` line 91.

**Subagents inherit the parent's permissions; setting `permissions` in a
subagent spec REPLACES the parent's rules entirely**, rather than adding
to them. `[docs]` - `permissions.md` line 239.

**With a `CompositeBackend` whose default is a sandbox, every permission
path must sit under a known route prefix** - anything else raises
`NotImplementedError`, including a `/**` covering every route. The reason
is principled: a sandbox permits arbitrary command execution, so
path-based restrictions alone cannot prevent filesystem access through the
shell. `[docs]` - `permissions.md` lines 286, 316-340.

**Pick the right tool**: `permissions` for path-based allow/deny rules on
the built-in filesystem tools; a backend policy hook when custom
validation logic is needed (rate limiting, audit logging, content
inspection) or when custom tools must be controlled. `[docs]` -
`permissions.md` line 18.

## 8. Human-in-the-loop

**A checkpointer is mandatory.** HITL needs state that survives between
interrupt and resume; without a checkpointer the pattern cannot work.
`[docs]` - `human-in-the-loop.md` lines 880-895.

**Resume uses the same config and `thread_id`.** `[docs]` -
`human-in-the-loop.md` lines 896-907.

**The `decisions` order must match the `action_requests` order exactly** -
one decision per action, in sequence. `[docs]` - `human-in-the-loop.md`
lines 909-929.

**Match configuration to risk level** rather than applying one uniformly:
high risk gets the full `["approve", "edit", "reject"]`, medium risk drops
`edit`, low risk gets `False` (no interrupt at all). `[docs]` -
`human-in-the-loop.md` lines 931-949.

**Edit tool arguments conservatively.** Large modifications to the
original arguments can make the model re-evaluate its approach and
potentially execute the tool several times or take unexpected actions.
`[docs]` - `human-in-the-loop.md` line 334.

## 9. Fault tolerance & budgets

**A taxonomy of errors by who fixes them** - the most reusable table in
the entire documentation, and one that maps directly onto the blueprint's
failure modes:

| Error kind | Who fixes it | Strategy | Mechanism |
|---|---|---|---|
| Transient (network, rate limits) | The system, automatically | Retry with exponential backoff | `ModelRetryMiddleware`, `ToolRetryMiddleware` |
| LLM-recoverable (tool failure, parsing) | The LLM | Convert to an error `ToolMessage` and let the model adjust | `ToolErrorMiddleware` |
| Needs a human (missing info, unclear instructions) | A human | Pause with `interrupt()` | `interrupt_on` |
| Provider outage | The system, automatically | Fall back to another model | `ModelFallbackMiddleware` |
| Excessive calls (runaway loop) | The system, automatically | Cap model & tool calls per run | `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware` |
| Unexpected | The developer | **Let it propagate** | no middleware |

`[docs]` - `fault-tolerance.md` lines 15-22.

The last row is the most frequently violated: "Do not catch what you
cannot handle." `ToolErrorMiddleware` only surfaces exceptions whose
content you explicitly return; the rest propagate and stop the run - which
is the desired behaviour. `[docs]` - `fault-tolerance.md` lines 130-138.

**Limit retries to tools that actually benefit.** A failing `read_file`
won't be helped by a retry; a timing-out web search probably will. That is
why `ToolRetryMiddleware` accepts `tools=[...]` and `retry_on=(...)`.
`[docs]` - `fault-tolerance.md` line 212.

**Two different budgets, both needed.** `run_limit` bounds a single
invocation (resetting each turn); `thread_limit` bounds the whole
conversation and **requires a checkpointer**. `[docs]` -
`fault-tolerance.md` line 187. This is exactly the distinction discussed
in [`../concepts/cost-control.md`](../concepts/cost-control.md).

**Provider rate limits are configured on the model, not in middleware** -
through `rate_limiter=InMemoryRateLimiter(...)` at `init_chat_model`. Note
the name: **in-memory**, so on a multi-process deployment each process has
its own bucket and the effective limit multiplies by the process count.
`[docs]` - `fault-tolerance.md` lines 148-166; the note about
multi-process implications is `[inferred]` from the class's name and
nature, and has not been tested.

**Integration exceptions carry an `is_retryable` flag** that the retry
middleware honours by default (`ModelAuthenticationError`,
`ModelRateLimitError`, `ModelTimeoutError`, etc.). `[docs]` -
`fault-tolerance.md` line 215.

## 10. Custom middleware

**Do not mutate instance attributes after initialisation.** This is the
most operationally important warning in the entire documentation for a
multi-user server pattern: `self.x += 1` inside a hook causes race
conditions, because many operations run concurrently - subagents, parallel
tools, and parallel invocations on different threads. To track a value
across hook invocations, use **graph state**, which is per-thread scoped
by design. `[docs]` - `customization.md` lines 1480-1516.

The consequence for implementation: one middleware instance is **shared**
across conversations and across users. All per-user state must live in
graph state or be keyed by `thread_id`, never as an attribute. The same
failure shape appears in `CodeInterpreterMiddleware` (see
[`../concepts/code-orchestration.md`](../concepts/code-orchestration.md)
§Per-user isolation).

## 11. Sandboxes & secrets

**Never put secrets inside a sandbox.** API keys, tokens, database
credentials - anything injected through environment variables, mounted
files, or the `secrets` option can be read and exfiltrated by an agent
whose context has been injected. This applies **even** to short-lived or
narrowly scoped credentials: if the agent can access them, so can an
attacker. `[docs]` - `sandboxes.md` line 2080;
`going-to-production.md` line 861.

If you must anyway, the documentation calls it "remains an unsafe
workaround" and demands four things at once: HITL for **every** tool call
(not just the sensitive ones), blocking or restricting network access from
the sandbox, credentials as narrowly scoped and short-lived as possible,
and monitoring of outbound traffic. `[docs]` - `sandboxes.md` line 2092.
The recommended path keeps secrets **out entirely**: an auth proxy that
injects credentials into outbound requests.

**Assistant-scoped sandboxes accumulate state.** Files, installed
packages, and other state grow without bound. Configure a TTL with the
sandbox provider, use snapshots to reset periodically, or build cleanup
logic. `[docs]` - `sandboxes.md` lines 709, 929;
`going-to-production.md` line 652.

## 12. Streaming & observability

**For new applications, use event streaming** rather than branching on
`stream_mode`. The typed-projection API introduced in Deep Agents v0.6
gives separate iterators per projection (subagents, messages, tool calls,
values) that can be consumed independently. `[docs]` - `streaming.md`
line 10.

**Audit the agent's memory writes through traces**: every file write
appears as a tool call. `[docs]` - `memory.md` line 510. The claim is
vendor-neutral even though the example is LangSmith - what matters is
that memory writes are observable as tool calls, whatever the tracing
backend.

## 13. Migration & version compatibility

**Rolling back from v0.6.0 is unsupported once threads have persisted.**
v0.6.0 moved message history and agent files to `DeltaChannel`, which
writes checkpoints in a format earlier versions cannot read. Downgrading
switches the channels back to non-delta and leaves existing delta
checkpoints unreadable - producing incomplete or incorrect state
reconstruction. The general principle: **never move a persisted channel
between delta and non-delta representations.** `[docs]` -
`changelog-py.md` line 78.

For systems with long-lived conversations this means upgrading deepagents
across 0.6.0 is a one-way operation needing a migration plan or discarded
threads - not merely a version bump.

## Read with skepticism

The items below appear as "Tips" in the documentation but are product
recommendations rather than neutral engineering practice. The principle
behind them is often right; the tool choice remains yours:

- Tracing/observability through LangSmith - appearing on at least nine
  pages (`backends.md:25`, `customization.md:143`, `overview.md:178`,
  `subagents.md:1007`, `sandboxes.md:687`, `mcp.md:70`, `memory.md:510`,
  `rag.md:272`, `going-to-production.md:36`), several accompanied by
  advice to install LangSmith Engine. **The principle is correct** (a
  harness without traces cannot be diagnosed, see
  [`../concepts/observability.md`](../concepts/observability.md)); the
  implementation need not be this vendor.
- Checkpointers, auth, RBAC, cron, and webhooks are described mainly as
  LangSmith Deployments features (`going-to-production.md` lines 327-368,
  412). For self-hosting on VMs/K8s, what applies is the primitives
  (`thread_id`, `context`, the LangGraph checkpointer, store namespaces),
  not the platform.
- Managed sandboxes, the LLM gateway, and Fleet (`sandboxes.md:687`,
  `quickstart.md:111`, `comparison.md:65`) - entirely product offerings.

Beyond that, two documentation warnings have fallen behind the code:
`namespace` "will be required in v0.5.0" (already mandatory in 0.7.8, §2
above), and the version requirement `langchain-quickjs>=0.2.0` (the
package itself demands `>=0.3.5`, see
[`../concepts/code-orchestration.md`](../concepts/code-orchestration.md)).

## Sources

- `[docs]` [`../upstream/deepagents-docs/`](../upstream/deepagents-docs/README.md)
  - a verbatim 40-page snapshot taken 2026-08-26 from
  `docs.langchain.com/oss/python/deepagents/`. Every line number in this
  file refers to that snapshot, not to the live web pages, which can
  change. The most-used pages: `going-to-production.md`,
  `fault-tolerance.md`, `context-engineering.md`, `backends.md`,
  `permissions.md`, `skills.md`, `memory.md`, `human-in-the-loop.md`,
  `sandboxes.md`, `customization.md`, `changelog-py.md`.
- `[code]` `deepagents/backends/store.py` lines 99-104 (package
  `deepagents==0.7.8`, venv
  `../recipes/.venv/lib/python3.13/site-packages/`) - `namespace` as a
  keyword-only argument with no default, the basis for correcting the
  "will be required in v0.5.0" warning.
- `[code]` [`middleware.md`](middleware.md) §`artifacts_root`, §Exclusion
  - the mechanisms behind the `CompositeBackend` recommendation and the
  `excluded_middleware` refusal; cited without re-reading the source.
- `[inferred]` One claim is flagged in place: the multi-process
  implication of `InMemoryRateLimiter`, inferred from the class's name and
  nature, untested.
