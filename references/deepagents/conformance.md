# Conformance audit — this KB vs the maintainers' official examples

Answering the question: **is the way this KB uses `deepagents` actually
reasonable, or an arbitrary modification that happens to work.**

## The limits of this audit — read first

Three things bound how far this audit can conclude, and all three must be
stated before the table is read:

1. **`langchain-ai/deepagents-quickstarts` has been archived.** Its last
   commit, `31f9a02` (2026-01-23), is titled *"docs: deprecate repo, point
   to main deepagents examples"*; its README now says only "⚠️ This repo
   has moved … This repo is archived and no longer updated." Its contents
   are down to **one** example (`deep_research/`), and its
   `pyproject.toml` still pins `deepagents>=0.2.6` — five minor releases
   below the 0.7.8 this KB documents. Comparing 0.7.8 patterns against an
   example pinned to 0.2.6 would return "absent" for almost every
   parameter, and that conclusion would mean nothing.
2. **The audit was therefore widened** to
   `langchain-ai/deepagents/examples/` (14 examples, where the
   maintainers moved the quickstarts) and `libs/code/deepagents_code/`
   (the official CLI/TUI — the maintainers' own production code on top of
   `deepagents`). The table below has separate columns for each, so
   "absent from quickstarts" isn't confused with "absent from maintainer
   practice".
3. **`deepagents` is still young.** Much of its surface has no settled
   community practice. Some of this KB's recommendations are our
   judgement, not canon — that is what the `[ours]` label and the roster
   at the end are for.

Method: `git clone --depth 1` of both repos and `grep` against source, not
documentation summaries. The main repo at commit `23b83ad` (2026-08-21).

## Conformance table

Column **QS** = `deepagents-quickstarts` (archived, one example).
Column **EX** = `deepagents/examples/` (14 examples).
Column **CODE** = `libs/code/deepagents_code/` (the official CLI).

| # | Pattern this KB uses | QS | EX | CODE | Notes |
|---|---|---|---|---|---|
| P-01 | `create_deep_agent(model=<explicit instance>)` | yes | yes | yes | Every example passes an explicit model; none relies on `model=None`. |
| P-02 | `subagents=[<SubAgent dict>]` with narrow `tools` | yes | yes | yes | `deep_research`, `nvidia_deep_agent`, `content-builder-agent`. |
| P-03 | Custom `tools=[...]` | yes | yes | yes | |
| P-04 | Long-prose `system_prompt=` | yes | yes | yes | |
| P-05 | `backend=FilesystemBackend(root_dir=...)` | no | yes | variant | `text-to-sql-agent`, `better-harness`, `llm-wiki` (as a route). The CLI uses it inside a `CompositeBackend`. |
| P-06 | `memory=["./AGENTS.md"]` | no | yes | yes | `text-to-sql-agent`, `nvidia_deep_agent`, `content-builder-agent`. |
| P-07 | `skills=["./skills/"]` | no | yes | yes | `text-to-sql-agent`, `content-builder-agent`. |
| P-08 | `CompositeBackend(default=..., routes={...})` | no | yes | yes | `nvidia_deep_agent`, `llm-wiki`. |
| P-09 | `StoreBackend(namespace=lambda rt: ...)` | no | **no** | no | Only in docstrings/documentation, **not** in a single maintainer example. → **D-08** |
| P-10 | `LocalShellBackend(root_dir=...)` | no | **no** | variant | Examples use `LangSmithSandbox`/Modal/`FilesystemBackend`; the CLI uses a managed sandbox. → **D-09** |
| P-11 | A sandbox backend (`DaytonaSandbox` etc.) | no | variant | yes | `llm-wiki` uses `LangSmithSandbox`; `DaytonaSandbox` appears only in the `libs/partners/daytona` README. → **D-17** |
| P-12 | `permissions=[FilesystemPermission(...)]` | no | yes | yes | `llm-wiki/helpers.py` lines 548-565, 633-638. |
| P-13 | `interrupt_on={...}` | no | variant | yes | In `examples/` it appears only **as a commented-out line** (`nvidia_deep_agent/src/agent.py:85,98`); real usage lives in the CLI. → **D-10** |
| P-14 | Application-injected `checkpointer=` | no | yes | yes | `async-subagent-server/supervisor.py` (`MemorySaver`). |
| P-15 | `context_schema=` | no | yes | yes | `nvidia_deep_agent`. |
| P-16 | `AsyncSubAgent` (Agent Protocol) | no | yes | no | `async-subagent-server/`. |
| P-17 | `recursion_limit` through `.with_config`/`config=` | no | yes | yes | `better-harness:225`, `libs/code/deepagents_code/agent.py:3110`. |
| P-18 | `middleware=[...]` on `create_deep_agent` | no | **no** | yes | Zero examples in `examples/`; the CLI uses it heavily (`agent_middleware`, ~15 custom middlewares). → **D-11** |
| P-19 | Custom `AgentMiddleware` | no | **no** | yes | `ShellAllowListMiddleware`, `LocalContextMiddleware`, `ManagedMemoryGuardMiddleware`, etc. in `libs/code`. → **D-11** |
| P-20 | `TodoListMiddleware()` added explicitly | no | **no** | no | Its only use in all of `deepagents` 0.7.8 is the `_openai_codex.py:77` profile. → **D-12** |
| P-21 | `response_format=` on `create_deep_agent` | no | **no** | no | Present in the signature and documented for `SubAgent`, but zero examples. → **D-13** |
| P-22 | Custom `state_schema=` | no | **no** | variant | The CLI uses `state_schema=` on `create_agent` (not `create_deep_agent`) in `reliable_rubric.py`, `goal_rubric.py`. → **D-14** |
| P-23 | `HarnessProfile` / `register_harness_profile` | no | **no** | no | Used only by `deepagents` itself for its own built-in profiles. → **D-15** |
| P-24 | `agent.json` for deployment | no | yes | — | **Four** at project level (`deploy-coding-agent`, `deploy-content-writer`, `deploy-gtm-agent`, `deploy-mcp-docs-agent`) plus **one** at subagent level (`deploy-gtm-agent/subagents/market-researcher/`). The first three contain only `{name, runtime}`; only `deploy-gtm-agent` has a `description`; the subagent-level one contains `{description, model_id}` with no `runtime`. **Zero** of them use the `backend` key. → **D-16** |
| P-25 | An outer loop around `invoke` | no | variant | no | `ralph_mode` does it, but with a **fresh thread per iteration** and the filesystem as memory — a context strategy, not a step bound. |
| P-26 | Subagents loaded from a config file | no | variant | yes | `content-builder-agent` does it through a custom YAML helper, with an explicit comment that "`deepagents` doesn't natively load subagents from files". Official precedent that writing your own config loader is reasonable. |
| P-27 | `RubricMiddleware` | no | no | yes | This KB describes it as an optional non-default; consistent. |

## Divergence log

Nineteen entries, covering every `no` row and most `variant` rows. **Four
`variant` rows deliberately have no entry of their own** — P-05, P-25, and
P-26 because their reason is fully covered in that row's Notes column and
no decision of ours needs defending (all three are maintainer patterns we
follow as-is); P-11 defers to D-17. No pattern needs removing: not one
`no`/`variant` stands without a written reason, whether in a D-xx entry or
in the Notes column.

For per-archetype divergences (D-01…D-07) the source is the `[ours]`
labels already present in `references/archetypes/`.

### D-01 — Archetype 01 without subagents — **FALSE PREMISE, must be corrected**

- **What we do**: the Workspace Agent (01) deliberately uses no subagents.
- **The KB's vanilla claim**: *"Vanilla deepagents examples
  (`content-builder-agent`, `deep_research`) almost always include at
  least one subagent"*
  (`references/archetypes/01-workspace-agent.md:104`, repeated in
  `references/scaffolds/deltas/01-workspace-agent.md:47`).
- **Audit finding**: that claim is **not true**. Of the 10
  `create_deep_agent` calls in `examples/`, **5 pass no synchronous
  subagents at all**: `text-to-sql-agent/agent.py:45` (`subagents=[]`,
  with the comment "No subagents needed"), `llm-wiki/helpers.py:633`,
  `better-harness/better_harness/agent.py:206` and `:611`, and
  `async-subagent-server/server.py:155`. An important nuance: the
  `general-purpose` subagent is still added automatically in all of them,
  so the `task` tool is always present unless disabled through a profile.
- **Conclusion**: this is **not a divergence**. There is nothing to
  defend as a deviation — what needs fixing is the vanilla claim.
  **Required action**: downgrade the `[ours]` label at
  `archetypes/01-workspace-agent.md:104` and
  `scaffolds/deltas/01-workspace-agent.md:47` to `[code]`, and replace
  "almost always includes a subagent" with the 5-of-10 fact above. Not
  done in that task because it lay outside the files it was allowed to
  touch.
- **Cost of leaving it**: a reader concludes that not using subagents is
  unusual, then adds subagents that aren't needed — token cost and
  complexity with no benefit.

### D-02 — Archetype 02 without `interrupt_on` in the build loop

- **What we do**: a gate only on the publish/deploy tool.
- **Vanilla**: `interrupt_on=None` is `create_deep_agent`'s default, and
  zero `examples/` actively install `interrupt_on` (P-13).
- **Reason**: this archetype's human control is a preview review at the
  end, not per-step approval.
- **Status**: **not a divergence from the library** — a product choice
  that happens to coincide with the default. Its `[ours]` label is
  correct because the product decision is ours, not because the library
  differs.
- **Cost if wrong**: an irreversible action (deploying to production)
  passes without approval. The mitigation already exists: a gate on the
  publish tool.

### D-03 — A repeated tool-call guard for archetype 03

- **What we do**: custom middleware that stops the agent when it calls the
  same tool with identical arguments N times in a row.
- **Vanilla**: `recursion_limit` (default `9_999`),
  `ModelCallLimitMiddleware`, and `ToolCallLimitMiddleware`. All three
  count **quantity**; none detects **repetition**.
- **Reason for diverging**: quantity limits prevent an endless loop but
  don't detect an agent spinning in place while burning budget.
- **The correct shape**: a `wrap_tool_call` returning
  `ToolMessage(status="error")` — the official extension path, and the
  same pattern the maintainers use in `ShellAllowListMiddleware`. A
  verified working code example is in [`middleware.md`](middleware.md).
- **Cost if wrong**: a false positive stops an agent legitimately
  retrying (e.g. polling). The threshold must therefore account for tools
  that are legitimately idempotent-repetitive.

### D-04 — Post-hoc citation provenance validation (archetype 04)

- **What we do**: match every citation in `response_format` against real
  `web_search` tool call results in the transcript.
- **Vanilla**: `response_format` alone. Zero maintainer examples use it
  on `create_deep_agent` (P-21).
- **Reason for diverging**: `response_format` validates shape, not
  correctness of content — hallucinated citations pass schema validation.
- **Cost if wrong**: an over-strict validator rejects legitimate
  citations (e.g. ones that come from the model's knowledge rather than a
  search). An explicit decision is needed: is a claim without a tool call
  rejected or flagged?

### D-05 — `undo_*` tools instead of `interrupt_on` (archetype 05)

- **What we do**: each product action tool is paired with an
  `undo_<action>` tool, invoked from the host UI.
- **Vanilla**: `HumanInTheLoopMiddleware` —
  approve/edit/reject/respond **before** execution.
- **Reason for diverging**: a short horizon; an approval pause feels like
  a UX regression against the host product.
- **Worth knowing**: there is a middle option that is vanilla and may be
  more appropriate — `InterruptOnConfig.when`, a predicate deciding per
  call whether an interrupt is needed. Low-risk actions pass, high-risk
  ones are gated. Consider this before building a full undo engine.
- **Cost if wrong**: actions that cannot be undone (sending email,
  calling a third-party webhook) have no safety net at all.

### D-06 — `create_deep_agent` as a node in an event-driven graph (archetype 06)

- **What we do**: `create_deep_agent(...)` inside an event-triggered
  graph/worker rather than as an interactive loop.
- **The KB's vanilla claim**: *"Vanilla deepagents usage in the
  documentation/examples is always an interactive loop triggered by a
  human"* (`references/archetypes/06-workflow-agent.md:82`).
- **Audit finding**: that claim is **too strong**.
  `examples/async-subagent-server/server.py` calls
  `await _agent.ainvoke(...)` at line **174**, from inside `_execute_run`
  (line 169), dispatched as an `asyncio.ensure_future` task at line
  **287** under the HTTP endpoint `POST /threads/{thread_id}/runs`
  (line **234**) — with no human in the loop.
  `examples/ralph_mode/` runs unsupervised. The `deploy-*` examples are
  deployed services, not REPLs.
- **Conclusion**: non-interactive use **has official precedent**. What
  remains true and remains `[ours]` is the division of responsibility:
  `deepagents` determines "what the LLM does when called", with
  triggers/queues outside. **Recommended action**: soften the "always an
  interactive loop" sentence at `archetypes/06-workflow-agent.md:82`.
- **Cost of leaving it**: a reader assumes using `deepagents` outside an
  interactive context is risky or unsupported, then builds an unnecessary
  harness of their own.

### D-06b — `thread_id` derived from the event's idempotency key

- **What we do**: `thread_id` = a function of the event's idempotency
  key.
- **Vanilla**: `examples/async-subagent-server/supervisor.py:57` uses
  `str(uuid.uuid4())`; no maintainer example derives `thread_id` from
  event identity.
- **Reason for diverging**: a retried event must land on the same
  checkpoint rather than starting a new run.
- **Cost if wrong**: two **different** events with colliding keys share
  conversation history — cross-event context leakage. The key must be
  genuinely unique per event, not per event type.

### D-06c — A kill switch outside `deepagents`

- **What we do**: a database flag the worker checks before invoking the
  agent.
- **Vanilla**: there is no kill switch API in `deepagents`; only
  `interrupt()` (a cooperative pause per run).
- **Status**: **not a divergence** — this is a statement about a missing
  feature, not a replacement for a library pattern. Its `[ours]` label
  marks that the kill switch design is ours.
- **Cost if wrong**: infrequent flag checks mean an already-"killed" run
  still finishes its current step.

### D-07 — Verification after UI actions through prompt convention (archetype 07)

- **What we do**: a `verify_state` tool that must be called after every UI
  action, enforced through system prompt instructions.
- **Vanilla**: there is no tool-ordering enforcement mechanism in
  `deepagents`. `PatchToolCallsMiddleware` does **not** do this (it only
  patches dangling `ToolMessage`s) — verified from
  `middleware/patch_tool_calls.py`.
- **Reason for diverging**: computer-use has no guarantee that an
  action's result equals the visible result.
- **Available reinforcement**: a `wrap_tool_call` refusing a second
  consecutive UI action without a `verify_state` in between. Stronger
  than a prompt, still not a structural guarantee.
- **Cost if wrong**: the model ignores the prompt convention and keeps
  clicking blindly. A prompt is not enforcement.

### D-08 — `StoreBackend(namespace=...)` as the per-user isolation pattern

- **What we do**: `StoreBackend(namespace=lambda rt: (user_id, ...))` for
  durable per-user-scoped files. **Two different compositions are used in
  this KB, and their artifact behaviour is not the same** — see
  [`middleware.md`](middleware.md) §`artifacts_root`:
  - `scaffolds/_base.md:157-168` and archetypes 03/06 use a **plain**
    `StoreBackend`. `artifacts_root` falls to the `"/"` branch
    (`middleware/summarization.py:598`), so `/conversation_history/`, its
    media, and `/large_tool_results/` **all** land inside the user's
    namespace. Full isolation with no extra configuration. `[code]`
  - the `04_custom_backend.py` recipe uses
    `CompositeBackend(default=StateBackend(), routes={"/memories/": StoreBackend(namespace=...)})`.
    Here `/memories/` is durable and scoped, but
    `/conversation_history/` **matches no route** and falls to
    `StateBackend` — ephemeral. Not a leak (`StateBackend` is
    per-thread), but conversation summaries don't persist. `[code]`
- **Vanilla**: this pattern exists **only in docstrings** —
  `FilesystemMiddleware` (`middleware/filesystem.py:1602-1614`) and
  `StoreBackend.__init__` (`backends/store.py:110-117`) demonstrate it,
  but **zero** maintainer examples use it. Examples needing persistence
  use `FilesystemBackend(root_dir=...)`.
- **Reason for diverging**: the maintainer examples are all local
  single-tenant (CLI, notebook, script). This KB targets multi-user
  services, and `namespace` is the **only** official per-user scoping
  *hook*.
- **What is actually isolated — wider than "the user's files"**. `[code]`
  `BackendProtocol` (`backends/protocol.py:378`) declares 18 methods
  (`ls`/`read`/`grep`/`glob`/`write`/`edit`/`delete`/`upload_files`/`download_files`,
  each plus an async variant), and its consumers are **not only the file
  tools**. Verified by reading the call sites in `middleware/`:

  | Middleware | Backend methods called | What lands in the backend |
  |---|---|---|
  | `filesystem.py` | `ls read grep glob write edit delete` (+async) | the user's working files |
  | `summarization.py:1102,1155,1218,1233` | `upload_files download_files write edit` (+async) | **conversation summaries and offloaded inline media** |
  | `_message_eviction.py:134,154` | `write awrite` | **tool message contents evicted from context** |
  | `memory.py:295,329` | `download_files adownload_files` | **cross-session memory files** |
  | `skills.py:613,639,679,705` | `ls als download_files adownload_files` | **the skills the agent can see** |

  Four of those five consumers are not file tools — they are other
  features that happen to need somewhere to put bytes. The consequence
  cuts both ways:

  **The risk is larger than it looks.** A wrong `namespace` doesn't leak
  files alone; it leaks another user's conversation summaries, transcript
  fragments offloaded during eviction, their memory, and their skill
  list. Reading `filesystem.py` alone would miss this entire class of
  leak — which is why `extension-points.md` places the backend, not
  `create_deep_agent`, as the primary extension point.

  **But the protection is also larger.** Because all five go through the
  same protocol, one correct `namespace` locks all five at once — and
  because that parameter is mandatory and the agent is assembled per turn
  (`scaffolds/_base.md:183-185`), there is no path where one is scoped
  and another isn't. This is a design strength that wasn't captured when
  this entry was first written.
- **Cost if wrong** — and here it matters to separate real risk from
  imagined. At the API level **nothing** can fail silently: `namespace`
  is a **mandatory** keyword-only parameter typed
  `Callable[[Runtime[Any]], tuple[str, ...]]`
  (`backends/store.py:41,99-104`), forgetting it is a `TypeError` at
  construction, and namespace components are validated against
  `_NAMESPACE_COMPONENT_RE` so oddly-shaped values are rejected. The
  remaining exposure is twofold, both beyond the library's reach:
  (a) **the correctness of the application's own `scope.user_id`** —
  `scaffolds/_base.md:160` deliberately uses `user_id` from the `Scope`
  produced by `ScopeMiddleware` rather than
  `rt.server_info.user.identity` as the documentation example does; if
  `Scope` is filled wrongly (e.g. an unvalidated header), `namespace`
  returns a tuple that is **valid** for the **wrong** user, and no layer
  beneath can catch it;
  (b) **zero multi-tenant maintainer examples**, so this pattern has no
  field evidence at all. Together these make it the divergence with the
  highest failure cost in the whole KB. What closes it: an end-to-end
  isolation test at the application layer (two users, one path, confirm
  neither can read the other), not another reading of the API.

### D-09 — `LocalShellBackend` for archetype 01

- **What we do**: `LocalShellBackend(root_dir=repo)` for the Workspace
  Agent.
- **Vanilla**: zero maintainer examples use it. Those needing a shell use
  a managed sandbox (`LangSmithSandbox` in `llm-wiki`, Modal in
  `nvidia_deep_agent`); the official CLI also uses a sandbox.
- **Reason for diverging**: archetype 01 is **defined** by a "user's
  machine" blast radius — that is the point, not an accident.
- **Cost if wrong**: very high, and the maintainers' `THREAT_MODEL.md`
  already says so: an unisolated shell, `virtual_mode` not restricting
  `execute()`, files readable/writable outside `root_dir` through the
  shell. Its absence from the maintainer examples is **consistent** with
  that warning — not evidence the backend is wrong, but evidence the
  maintainers don't treat it as a safe default. This KB must keep pairing
  the choice with a mandatory HITL gate, and it does.

### D-10 — `interrupt_on` as the primary gate

- **What we do**: per-tool `interrupt_on` for archetypes 01, 06, 07.
- **Vanilla**: in `examples/`, `interrupt_on` appears only **as a
  disabled comment** (`nvidia_deep_agent/src/agent.py:85,98`:
  `# "interrupt_on": {"execute": True} # enable human in the loop`).
  Real usage lives in `libs/code`, but through its own derived middleware
  (`AsyncApprovalHITLMiddleware`) rather than the plain `interrupt_on`
  parameter.
- **Reason for diverging**: examples are designed to run without
  friction; a real product doesn't have that luxury.
- **Cost if wrong**: `interrupt_on` is **useless without a
  `checkpointer`** — there is nowhere to store the pause point. Every
  scaffold using `interrupt_on` must pair it with a durable checkpointer
  (not `MemorySaver`) if its approval is asynchronous. The official CLI
  pattern shows that for non-interactive modes the more appropriate path
  is to **refuse** through `wrap_tool_call` rather than interrupt —
  because interrupt/resume splits the trace across several runs.

### D-11 — Custom middleware through `middleware=[...]`

- **What we do**: recommending custom middleware for guards, audit, and
  limits (archetypes 03, 07).
- **Vanilla**: **zero** examples in `examples/` use the `middleware=`
  parameter.
- **However**: `libs/code/deepagents_code/agent.py` — the maintainers'
  own production code — builds an `agent_middleware` list containing a
  dozen custom middlewares (`ShellAllowListMiddleware`,
  `LocalContextMiddleware`, `ManagedMemoryGuardMiddleware`,
  `ConfigurableModelMiddleware`, `ServerHooksMiddleware`, …) and passes
  it through `create_deep_agent(middleware=agent_middleware)` (lines
  3098-3110).
- **Conclusion**: this pattern is **idiomatic**; its absence from
  `examples/` is a matter of example scope (each deliberately focuses on
  one feature), not a signal that custom middleware is discouraged. No
  substantive divergence.
- **Cost if wrong**: the most common mistake isn't "using middleware" but
  using it at the wrong layer — see
  [`extension-points.md`](extension-points.md) anti-patterns #1 and #2.

### D-12 — `TodoListMiddleware` added explicitly (archetype 03)

- **What we do**: `middleware=[TodoListMiddleware()]` for explicit
  planning.
- **Vanilla**: zero maintainer examples. The only use of
  `TodoListMiddleware` in `deepagents` 0.7.8 is the harness profile
  `profiles/harness/_openai_codex.py:77`, which installs it through
  `extra_middleware` for Codex models.
- **Reason for diverging**: explicit planning is archetype 03's
  distinguishing axis; without it the archetype doesn't exist.
- **An important note the audit found**: the maintainers install it
  through `HarnessProfile.extra_middleware`, not `middleware=[...]`. The
  difference is real — `extra_middleware` also applies to declarative
  subagents and the GP subagent, whereas `middleware=[...]` applies only
  to the main agent (and to the GP subagent **only** if its name
  overrides the default GP slot). For a delegation-heavy archetype 03,
  subagents will not have `write_todos`. If planning inside subagents is
  also wanted, the path is a profile.
- **Cost if wrong**: planning assumed active across the whole agent tree
  turns out to exist only at the root.

### D-13 — `response_format` on `create_deep_agent`

- **What we do**: using it to force a report's shape (archetype 04).
- **Vanilla**: present in the signature and documented at length for
  `SubAgent`, but zero maintainer examples use it at the main agent
  level.
- **Reason for diverging**: archetype 04's output is consumed by a
  program, not a human.
- **Cost if wrong**: `response_format` changes the graph's shape (adding
  a structured-output tool and extra edges). Its combination with
  `interrupt_on` and subagents hasn't been widely exercised in the field
  — test it on a real path before relying on it.

### D-14 — Custom `state_schema=`

- **What we do**: naming it as an extension point, with the note that the
  **recommended** way is a middleware's `state_schema`.
- **Vanilla**: zero examples use `create_deep_agent(state_schema=)`. The
  CLI uses `state_schema=` but on `create_agent` directly
  (`reliable_rubric.py:244`, `goal_rubric.py:1453,1498`).
- **Conclusion**: this KB's recommendation (prefer a middleware's
  `state_schema`) **agrees** with `create_deep_agent`'s own docstring and
  with CLI practice. Not a divergence.
- **Cost if wrong**: a `state_schema` not derived from `DeepAgentState`
  loses the `DeltaChannel` reducer — checkpoints grow O(N²), and **no**
  runtime validation complains.

### D-15 — `HarnessProfile` as a recommended extension point

- **What we do**: [`extension-points.md`](extension-points.md) recommends
  `register_harness_profile` as the official alternative to
  copy-pasting `create_deep_agent`.
- **Vanilla**: no external users in the maintainers' repo — only
  `deepagents` itself uses it for its built-in profiles, and the module
  is marked **beta** ("may receive minor changes in future releases").
- **Reason**: it is the only official path for changing the stack across
  every agent and subagent at once. The alternative (copying `graph.py`)
  is far worse.
- **Cost if wrong**: a beta API can change in a minor release. This
  recommendation must be revisited every time `deepagents` bumps a minor
  version. **This is the `[ours]` recommendation with the highest API
  change risk.**

### D-16 — `agent.json` with `backend.sandbox_config` (archetype 02)

- **What we do**: `references/archetypes/02-generative-builder.md`
  demonstrates `{"backend": {"type": "sandbox", "sandbox_config": {"scope":
  "thread", "policy_ids": [...]}}}`.
- **Verification status**: this claim was previously **unverified**
  because `deepagents-cli` wasn't installed. It is now **verified from
  source**: `libs/cli/deepagents_cli/deploy/project.py` lines 239-240 and
  290-322 normalise that key, and
  `libs/cli/tests/unit_tests/deploy/test_project.py` lines 219-249 pin
  down its exact shape
  (`{"type": "sandbox", "sandbox_config": {"scope": "agent",
  "policy_ids": ["p-1"], "idle_ttl_seconds": 900,
  "delete_after_stop_seconds": 300}}`). Valid `scope` values: `"thread"`
  and `"agent"`; `"workspace"` is rejected. The old form
  `{"type": "thread_scoped_sandbox", "sandbox": {...}}` is normalised to
  the new one.
- **The divergence that remains**: **not a single example `agent.json`**
  uses the `backend` key — all three (`deploy-coding-agent`,
  `deploy-content-writer`, `deploy-gtm-agent`) contain only `name`,
  `description`, and `runtime.model.model_id`. So the key is real, but
  the maintainers haven't demonstrated its use.
- **Cost if wrong**: the CLI schema changes without deprecation and the
  scaffold's `agent.json` fails to deploy. There is already precedent:
  the old `sandbox` form was deprecated into `sandbox_config`.

### D-17 — `DaytonaSandbox(sandbox=..., timeout=300)` (archetypes 02 & 07)

- **Verification status**: previously **unverified** because
  `langchain_daytona` wasn't installed. Now **verified from source**:
  `libs/partners/daytona/langchain_daytona/sandbox.py` lines 30-36 —
  `DaytonaSandbox(*, sandbox: daytona.Sandbox, timeout: int = 30*60,
  sync_polling_interval: SyncPollingInterval = 0.1)`, all
  **keyword-only**, `sandbox` mandatory, the class deriving from
  `BaseSandbox` which satisfies `SandboxBackendProtocol`. The package
  README demonstrates exactly the form this KB uses.
- **Divergence**: zero examples in `examples/` use it (those needing a
  sandbox use `LangSmithSandbox` or Modal). The package also ships
  separately with its own version cycle.
- **Cost if wrong**: a dependency on a partner package not covered by
  `deepagents` CI. A safer alternative for this KB would be to name
  `LangSmithSandbox` as the primary example (it lives in `deepagents`
  core and is used by `llm-wiki`), with `DaytonaSandbox` as a variant.

## What remains unverified

Nothing. Both items pending from the previous task (the CLI `agent.json`
and `DaytonaSandbox`) were resolved by `git clone`ing the
`langchain-ai/deepagents` repo — see D-16 and D-17. The packages
themselves remain **uninstalled** in `references/recipes/.venv`, so both
were verified from **the maintainers' source and tests**, not from
execution. What would settle it fully:
`uv add deepagents-cli langchain-daytona` in `references/recipes/`, plus a
recipe that constructs a `DaytonaSandbox` and parses an `agent.json`.

## Recorded residue

Found during the audit, initially outside the files that task was allowed
to touch; all five were fixed in the following wave (2026-08-23, see the
Status column):

| Location | Issue | Fix | Status |
|---|---|---|---|
| `archetypes/01-workspace-agent.md`, `scaffolds/deltas/01-workspace-agent.md`, `per-archetype.md` §01 | The claim "vanilla almost always includes a subagent" is untrue (D-01) | Replaced with the 5-of-10 fact plus each call site's location; the label downgraded `[ours]` → `[code]` in all three places | **done** |
| `archetypes/06-workflow-agent.md` | The claim "vanilla is always a human-triggered interactive loop" is too strong (D-06) | Replaced: `async-subagent-server/server.py` line 174 (`ainvoke`), 169 (`_execute_run`), 287 (dispatch), 234 (endpoint) plus `ralph_mode` named as non-interactive precedent; `[ours]` narrowed to the trigger/queue division of responsibility, which does remain ours | **done** |
| `archetypes/01-workspace-agent.md` | The `FilesystemMiddleware` tool list includes `delete` — **correct**; the list in `systems/deepagents.md` was the incomplete one (missing `delete`) | Add `delete` to the tool list in `systems/deepagents.md` | **done** |
| `recipes/03_subagents.py` docstring | "returns its final `messages` as a compact `ToolMessage`" — loose in the same way as the correction in `systems/deepagents.md` | Replaced with "the last non-empty `AIMessage` text, or the JSON-serialised `structured_response`" | **done** |
| `archetypes/03-general-task-agent.md:99` | Names `recursion_limit` as the only vanilla bound; `ModelCallLimitMiddleware` and `ToolCallLimitMiddleware` unmentioned | Add both (D-03 still stands; its reasoning strengthens) | **done** |

All five rows above are complete (a follow-up fix wave, 2026-08-23) — all
of them accuracy rather than structure. No KB pattern needs **removing** —
every `no`/`variant` in the table has a written reason, whether in a D-xx
entry or in its row's Notes column.

## `[ours]` roster

Built with this command, run from the repo root:

```bash
grep -rn '\[ours\]' references/ --include='*.md'
```

The result is **79 lines** at the latest count, in three groups:

- **56** outside `references/deepagents/` — these are the real claims,
  listed in full in the table below. (The first audit produced 53; two
  were withdrawn when D-01 proved not to be a deviation, then five were
  added: lines 54, 55, and 56-58.)
- **10** in `references/deepagents/per-archetype.md` — all **pointers**
  to D-xx entries in this file, not new claims.
- **13** in this file itself — all meta (section titles, explanations,
  the conclusion, and the `grep` command above).

These numbers must be rechecked whenever the KB changes: the `grep` above
must return exactly the set this roster lists.

The `#` column is a stable index from the first audit, not a running
count — rows marked `—` are claims **withdrawn** in fix round 1 that no
longer appear in the `grep`, so numbers 1 and 17 are deliberately empty.

| # | Location | Core claim | Divergence |
|---|---|---|---|
| — | `archetypes/01-workspace-agent.md` | Archetype 01 without subagents | D-01 — **withdrawn**, false premise; now `[code]` |
| 2 | `archetypes/02-generative-builder.md:98` | A gate only on publish/deploy | D-02 |
| 3 | `archetypes/03-general-task-agent.md:99` | A repeated tool-call guard | D-03 |
| 4 | `archetypes/04-research-agent.md:95` | Citation provenance validation | D-04 |
| 5 | `archetypes/05-in-app-copilot.md:95` | `undo_*` tools instead of `interrupt_on` | D-05 |
| 6 | `archetypes/06-workflow-agent.md:82` | Trigger/queue responsibility divided outside `deepagents` | D-06 (narrowed; the "always interactive" claim withdrawn) |
| 7 | `archetypes/06-workflow-agent.md:102` | `thread_id` from an idempotency key | D-06b |
| 8 | `archetypes/06-workflow-agent.md:114` | A kill switch outside the library | D-06c |
| 9 | `archetypes/07-computer-use-agent.md:100` | Verification through prompt convention | D-07 |
| 10 | `archetypes/README.md:54` | Deployment separated from the archetype taxonomy | taxonomy, not `deepagents` |
| 11 | `systems/INDEX.md:93` | Meta: why the `[ours]` label exists | meta |
| 12-16 | `scaffolds/_base.md:56,77,160,450,493` | The `Orchestrator` protocol; `namespace` from the application `Scope` rather than `rt.server_info.user.identity`; `AsyncConnectionPool`; inline turn execution in the SSE generator | **:160 → D-08 (highest risk)**; the rest is application architecture, outside `deepagents` |
| — | `scaffolds/deltas/01-workspace-agent.md` | Derived from D-01 | **withdrawn**, now `[code]` |
| 18-19 | `scaffolds/deltas/02-generative-builder.md:25,37` | Derived from #2 | D-02 |
| 20 | `scaffolds/deltas/03-general-task-agent.md:22` | Derived from #3 | D-03 |
| 21 | `scaffolds/deltas/04-research-agent.md:44` | Derived from #4 | D-04 |
| 22 | `scaffolds/deltas/05-in-app-copilot.md:34` | Derived from #5 | D-05 |
| 23-25 | `scaffolds/deltas/06-workflow-agent.md:14,24,49` | Derived from #6, #7, #8 | D-06, D-06b, D-06c |
| 26 | `scaffolds/deltas/07-computer-use-agent.md:29` | Derived from #9 | D-07 |
| 27 | `concepts/artifacts-and-canvas.md:88` | Artifact versions use a monotonic integer, not a timestamp | outside `deepagents` |
| 28-29 | `concepts/evaluation.md:37,66` | Evaluating the full trajectory; "golden transcript" | outside `deepagents` |
| 30 | `concepts/guardrails.md:31` | The six-point guardrail framework from the project spec | outside `deepagents` |
| 31-37 | `concepts/skill-composition.md:34,96,167,190,199,210,218` | A skill manifest resolution layer **before** `deepagents`; intent/expression separation | alongside `SkillsMiddleware`, not replacing it |
| 38-40 | `concepts/multilingual.md:58,160,223` | Language-locked points in the intent/expression pipeline | outside `deepagents` |
| 41-45 | `concepts/persistence-schema.md:37,294,337,342,351` | A local `users` table; RLS without subqueries; naming; the `user_id`→`tenant_id` migration path | outside `deepagents` |
| 46-48 | `concepts/policy-as-data.md:159,169,181` | A policy-as-data schema on top of what is already data-shaped in `deepagents` | explicitly states which part is **not** `[ours]` — the correct writing model |
| 49 | `concepts/queueing-and-backpressure.md:68` | The queue schema | outside `deepagents` |
| 50 | `concepts/resource-profiling.md:95` | Phase colocation vs splitting per bound | outside `deepagents` |
| 51 | `concepts/sandboxing.md:140` | Sandbox policy is not forced by the Daytona SDK | related to D-17 |
| 52 | `concepts/serving-topology.md:167` | Monolith first, split later | outside `deepagents` |
| 53 | `concepts/streaming-protocol.md:142` | Stream granularity per unit | outside `deepagents` |
| 54 | `concepts/guardrails.md:94` | Fail-deferred must be paired with a timeout plus an on-expiry policy (vanilla: an unbounded `await`, OpenWorker `inbox.py:362-371`) | outside `deepagents` |
| 56-58 | `scaffolds/skills/README.md:18,132,170` | Fenced-block syntax for tagged output (`table`/`chart` JSON, `mermaid`, `math`), its JSON schemas, and the inline→artifact thresholds of ~50 rows / ~200 points (vanilla: `response_format`, which forces the **whole** reply into one schema'd object — unable to express prose with zero to n heterogeneous insertions) | outside `deepagents`; alongside `SkillsMiddleware`, not replacing it |
| 55 | `concepts/isolation-and-scoping.md:121` | An RLS catalogue audit isn't enough; isolation evidence must be a cross-user query as a non-superuser application role (vanilla: check `relrowsecurity`/`relforcerowsecurity` and declare it sufficient) | outside `deepagents` |

How to read this roster: of the 51 claims, **12** genuinely concern how
`deepagents` is used (archetypes 02-07, `_base.md:56,77,160`,
`sandboxing.md:129`) and are recorded in the divergence log.
The rest are application architecture decisions in the layer **above**
`deepagents` — not deviations from the library, and not something that can
be audited against maintainer examples.

What most needs revisiting as the library matures, in order:
**D-08** (`namespace` for per-user isolation — the highest failure cost,
and it fails silently), **D-15** (`HarnessProfile` still beta),
**D-16/D-17** (a CLI schema and a partner package that can change),
then **D-01/D-06** (two vanilla claims this audit found inaccurate).

## Sources

Repos cloned and `grep`ed directly (not summarised):

- `langchain-ai/deepagents-quickstarts`, commit `31f9a02` (2026-01-23),
  `git clone --depth 1`. **Archived.** Contents: `README.md` (the moved
  notice), `deep_research/` (`agent.py`,
  `research_agent/{prompts,tools}.py`, `research_agent.ipynb`,
  `pyproject.toml` with `deepagents>=0.2.6`).
- `langchain-ai/deepagents`, commit `23b83ad` (2026-08-21),
  `git clone --depth 1`. Read: all of `examples/` (14 examples, 10
  `create_deep_agent` calls), `libs/code/deepagents_code/agent.py`,
  `libs/cli/deepagents_cli/deploy/project.py`,
  `libs/cli/tests/unit_tests/deploy/test_project.py`,
  `libs/partners/daytona/{README.md,langchain_daytona/sandbox.py}`.

Installed packages `[code]` (`deepagents==0.7.8`, `langchain==1.3.16`) in
`references/recipes/.venv/lib/python3.13/site-packages/` — the full file
list is in [`api-reference.md`](api-reference.md) §Sources.

The audit commands that were run are recorded in
`.superpowers/sdd/2026-08-23-agent-harness-kb/task-11-report.md`.

## Conclusion

The question at the head of this file: **is the way this KB uses
`deepagents` reasonable, or an arbitrary modification that happens to
work?**

**Reasonable.** 27 patterns audited. Against the living maintainer
examples (`deepagents/examples/`): 14 match, 4 variant, 9 absent. Against
the official CLI (`libs/code/`): 17 match, 3 variant, 6 absent, 1 not
applicable. Nineteen divergence log entries were written; **every**
`no`/`variant` row has a written reason, and **zero patterns were removed**
for deviating without one. Not a single place was found where this KB
writes custom code at a layer that already has an extension point — the
worry that prompted this audit.

What was unreasonable turned up in the opposite direction: **two of this
KB's own "vanilla" claims proved false** (D-01 and D-06), both making
maintainer behaviour look more uniform than it is. Both have been fixed in
their source files.

This conclusion carries the three limits stated at the head of the file:
`deepagents-quickstarts` is archived, making comparison against it nearly
meaningless; `deepagents` is still young, so parts of its surface have no
community practice; and twelve of the 51 `[ours]` claims are our
judgement, not canon. What most needs revisiting as the library matures is
listed at the end of §Roster.
