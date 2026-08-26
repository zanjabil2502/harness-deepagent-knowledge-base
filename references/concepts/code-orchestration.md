# Code orchestration (interpreters, PTC, dynamic subagents)

## Problem

One model turn produces one batch of tool calls, and that batch is **frozen
the moment it is emitted**. Nothing can loop, branch on a result, retry after
a failure, or feed one call's output into the next without a new model turn.
Three costs flow from this single fact, and all three are often mistaken for
separate problems:

- **Token cost.** Every intermediate result lands in the context, including
  results that only feed the next step and are never read by a human nor
  used by the model for anything but filtering. This is the same concern as
  `context-engineering.md`, but its source isn't a long history — it is
  orchestration forced through the context.
- **Coverage cost.** A model deciding how many calls to emit tends to take a
  **sample**, not a census. Ask it to process 300 items and what comes back
  is usually a dozen "representative" ones. The failure is silent: the
  output looks right, it just isn't complete.
- **Latency cost.** N sequential steps = N model turns, even though many of
  them need no reasoning at all (sorting, joining, parsing, counting,
  filtering).

Moving orchestration into code solves all three at once. But that is where
the real problem for a harness designer begins, and it isn't visible from the
list of benefits above: **every gate a harness builds is built at the tool
call.** Human approval, tool exclusion, per-call logging, rate budgets,
per-capability policy — all of them attach there because that used to be the
only place an agent touched the outside world. Code calling tools from
**inside an already-approved tool call** passes through none of those gates.

So this pattern trades model turns and tokens for **the loss of per-call
control**, and that trade is almost always invisible in configuration: what is
written is "enable the interpreter", while what changes is where the whole
system's capability boundary sits.

## Pattern

### An in-loop interpreter ≠ a sandbox against the environment

Two things that both "run code" but with different blast radii, gates, and
reasons to exist — conflating them gets both configured wrongly:

- **A sandbox** (`sandboxing.md`) — code that **acts on the environment**:
  shell commands, installing dependencies, running tests, editing OS files.
  Its blast radius is that environment; its isolation is a
  process/container.
- **An in-loop interpreter** — code that **composes tools, holds state, and
  decides what returns to the model**. By default it touches nothing:
  without an explicit bridge it can only compute and write to a console. Its
  blast radius is exactly as wide as the bridges installed, not as wide as
  its engine.

The practical consequence: an interpreter with no bridges is nearly inert
and needs no heavy gate. What needs gating are **the bridges**, one at a
time.

### Two capability bridges, two separate decisions

A useful interpreter always crosses its boundary through a bridge, and each
bridge is its own permission decision — not one "enable the interpreter"
switch:

- **The tool bridge (programmatic tool calling / PTC)** — some of the
  agent's tools are exposed as functions inside the code. Its allowlist is
  the permission boundary: what is listed can be called in a loop, in
  parallel, and repeatedly with no model turn in between. An expensive,
  destructive, or sensitive-system tool doesn't automatically belong there
  just because the agent may call it through the normal path — on the normal
  path it is called once per turn and visible; here it can be called
  hundreds of times inside one tool call.
- **The subagent bridge (dynamic subagents)** — code dispatches an
  already-configured subagent. This makes delegation a **program
  operation** rather than a per-turn model choice: fan-out over N items
  becomes a loop, verification becomes a second call to another subagent,
  and recursive flows (hold a working set in a variable, take a slice, call
  a subagent, synthesise) become possible without flooding the parent
  context. See [`delegation.md`](delegation.md) for the result contract and
  depth limits that still apply on this route.

The healthy default posture: both bridges **closed**, opened one at a time
with a written reason. A system that opens both wide "for flexibility" has
moved its entire capability surface inside one uninspected tool call.

### The "what returns to the model" contract

An interpreter's real job isn't running code but **deciding what the model
doesn't need to see**. Its contract must be explicit on three things: what
value counts as the result (the last expression? a returned value?), whether
console output comes back too, and at what size results are truncated.
Without truncation the pattern fails at its own purpose — code returning a
300-element array moves every intermediate result into the context, exactly
what it was meant to avoid.

### Interpreter state persistence is a third decision

Variables inside the interpreter can live for three spans, and the choice
determines far more than convenience:

- **per call** — each execution starts from nothing. Easiest to reason
  about, adding nothing to session state.
- **per turn** — variables survive between executions within one turn and
  are gone in the next. Enough for almost all orchestration.
- **per thread** — variables survive across turns. This moves the
  interpreter's memory **into session state**, and with it inherits every
  question in `session-state.md`: where is it stored, how large may it grow,
  what happens when a restore fails, and whose is it
  (`isolation-and-scoping.md` — interpreter memory leaking between users is
  a data leak, not merely a bug).

Easily missed: an interpreter memory snapshot restores **variables**, not
side effects. If the code inside already called a tool that changed the
outside world, restoring an old snapshot doesn't undo that change — it only
restores the record of it. State rollback ≠ effect rollback.

### The gate shifts from "every tool call" to "every code execution"

This is the most important consequence and the one most often discovered too
late. If orchestration moves into code, the only gate still lit is the gate
on the **code execution tool itself**. Three strategies exist, and the choice
must be explicit in the blueprint:

1. **Gate the code execution** — a human approves the *program*, not each
   call. Coarse but still one stopping point; it depends on the human
   genuinely reading the code, so it is only meaningful when the approved
   code is short and assessable.
2. **Gate inside what is delegated** — approval installed inside the
   subagent spec, so it stays lit even when dispatch comes from code.
   Applies to the subagent bridge, not the tool bridge.
3. **Close the bridge** — for a capability that genuinely must be approved
   per call, don't bring it into the interpreter at all; leave it on the
   normal tool call path.

In `guardrails.md`'s framework, a bridge open without one of those three is
a **fail-open** enforcement point: the policy is still written in the config,
its enforcement is never invoked.

## Trade-offs

- **Context economy & coverage vs per-call control.** The benefit is real
  and large (intermediate results stay out of the context, fan-out becomes a
  census rather than a sample, N model turns become one). The cost is real
  too: per-call approval, tool exclusion, and per-call auditing stop working
  inside the code. This isn't a patchable bug — the execution path genuinely
  differs. A system with a small blast radius (reading, computing,
  searching) gets nearly all the benefit without the cost; a system that
  writes, spends, or sends to third parties pays it in full.
- **Determinism vs a new failure surface.** Code removes model variance from
  mechanical steps but adds failure classes that didn't exist before:
  language runtime errors, timeouts, exhausted call budgets, oversized
  results. All of them return to the model as text it must read and
  interpret — so error message quality becomes part of prompt design, not
  just a runtime concern.
- **Cross-turn persistence vs state weight.** Convenient (the agent can
  continue long work without rebuilding it), but the memory snapshot becomes
  part of the session state written every turn. The question isn't "does it
  fit" but "does it belong in a checkpoint that is stored, replayed, and
  deleted under retention rules" (`retention-and-deletion.md`,
  `replay-and-forensics.md`).
- **A wide vs narrow allowlist.** Wide lets the model compose anything
  without coming back for permission; narrow forces some orchestration back
  through model turns. The right size isn't "how many tools" but "if this is
  called 200 times in one execution, what happens" — and that is a per-tool
  question, not a per-list one.
- **Observability.** Fan-out from inside code is invisible in the
  transcript: all that is recorded is one tool call containing a program and
  one result. Unless the runtime emits lifecycle events of its own, the UI
  and audit trail lose the entire structure of the work that actually
  happened (`observability.md`, `streaming-protocol.md`).

## In deepagents

This capability is **not in the `deepagents` package**. It lives in a
separate package, `langchain-quickjs`, which `deepagents==0.7.8` declares as
an extra: `Requires-Dist: langchain-quickjs>=0.3.5; extra == "quickjs"`
(`[code]` — `deepagents-0.7.8.dist-info/METADATA`). The upstream
documentation states the requirement as `langchain-quickjs>=0.2.0` (`[docs]`
— `../upstream/deepagents-docs/interpreters.md` line 18) — **looser than what
the package itself enforces**; follow the METADATA, not the documentation.
Its status is `@beta()` (`[code]` — `middleware.py:120`), so its lifecycle
behaviour can change between releases.

It enters through `middleware=[CodeInterpreterMiddleware(...)]`, meaning it
lands in the **user middleware slot** — between the base stack and the tail
stack ([`../deepagents/middleware.md`](../deepagents/middleware.md) §Stack
order). Every ordering consequence below flows from that position.

**The tool bridge (PTC)** — `ptc=` accepts a list of tool names or `BaseTool`
instances; `None` (the default) = closed. Tools are exposed as
`tools.<camelCase>(input) => Promise<string>` (`[code]` —
`_ptc.py:35,48-116`). The camelCase mapping itself is documented (`[docs]` —
`interpreters.md` line 184); the following three limits are not:

- A tool's name must map to a valid JavaScript identifier
  (`/^[A-Za-z_$][A-Za-z0-9_$]*$/`), or construction raises `ValueError`
  (`[code]` — `_ptc.py:134-144`). Relevant for MCP tool surfaces whose names
  often carry unusual prefixes/separators (`mcp.md`).
- `ptc=["task"]` is **rejected** with `ValueError` — the `task` tool is
  reserved because it is already available as the `task()` global, and the
  `tools.task` route would discard `responseSchema` (`[code]` —
  `_ptc.py:37-45,86-93`).
- The `max_ptc_calls` budget (256 by default) is counted per code execution;
  exceeding it raises host-side before the tool is called (`[code]` —
  `middleware.py:51,132-137`, `_repl.py:90-106`). `max_ptc_calls=None`
  disables the budget and opens an unbounded host-call DoS pattern — its
  docstring states this explicitly.

**The subagent bridge** — `subagents=True` (the default) installs the
`task()` global as soon as the agent has deepagents' `task` tool, detected
through the tool's name plus the presence of `description`+`subagent_type`
fields in its schema (`[code]` — `_subagent.py:165-173`). `task()` accepts
`description`, `subagentType`, and two fields **the documentation doesn't
fully cover**: `label` (for event labelling; `[code]` —
`_repl.py:539-566`) and `responseSchema`. `responseSchema` is installed as a
per-dispatch `AutoStrategy` whose result is `json.loads`ed before returning
to the code, with hard limits: ≤4096 serialised bytes, depth ≤5, ≤32 total
properties (`[code]` — `_subagent.py:33-40,209-213,275-307`). This is
`structured-output.md` applying inside the code loop rather than at the API
boundary.

**Gates** — this is the most important part to record. **Two** routes bypass
`interrupt_on`, and both are warned about in the source and the
documentation:

- PTC calls "do **not** go through the normal `ToolNode` path… `interrupt_on`
  / HITL approval workflows are not enforced per PTC-invoked tool call"
  (`[code]` — `middleware.py:179-183`, `_ptc.py:76-79`; `[docs]` —
  `interpreters.md` lines 282-284).
- `task()` dispatches "run inside an already-approved `eval` invocation and
  do not trigger parent-level `interrupt_on` / HITL approval per dispatch"
  (`[code]` — `middleware.py:158-163`; `[docs]` — `dynamic-subagents.md`
  lines 1278-1280). This second warning exists **only on the
  `dynamic-subagents` page** — the §Dynamic subagents summary on the
  `interpreters` page (lines 286-311) doesn't carry it, and the
  configuration table at line 564 mentions `subagents=False` only as a way
  to "require dispatch through the normal `task` tool" without linking it to
  approval. A reader who stops at the interpreters page misses it.

The three mitigations in §Pattern aren't this KB's invention — all three are
named in the `middleware.py:161-163` docstring: "Gate the `eval` tool itself,
add approval middleware inside subagent specs, or set `subagents=False`". The
documentation names only the first (`dynamic-subagents.md` line 1279). The
first works because `HumanInTheLoopMiddleware` sits in the tail stack and
fires on tool names in `interrupt_on`, while the `eval` tool is registered by
user middleware — so `interrupt_on={"eval": True}` gates the program
(`[inferred]` from `../deepagents/middleware.md` §Stack order +
`middleware.py:263`; not executed). The second works because `GraphInterrupt`
is deliberately **re-raised** unwrapped, so an interrupt from inside a
subagent propagates up through the bridge (`[code]` —
`_subagent.py:247-248`).

**Tool exclusion doesn't bind PTC.** `_ToolExclusionMiddleware` is appended
last, making it the **innermost** `wrap_model_call` layer, while
`CodeInterpreterMiddleware` as user middleware sits further out and reads
`request.tools` **before** exclusion runs (`[code]` —
`middleware.py:446,455-463`; the onion composition rule with `m[0]` outermost
verified in `../deepagents/middleware.md` §Dangerous interactions,
`langchain/agents/factory.py:349`). So a tool removed by
`HarnessProfile.excluded_tools` remains reachable through `tools.*` if its
name is in the PTC allowlist. `[inferred]` — assembled from the two `[code]`
facts above, not executed; if the profile and the PTC allowlist are
maintained by two different people, this is a hole that will show up in no
config review.

**Persistence** — `mode="thread"` (the default) / `"turn"` / `"call"`
(`[code]` — `middleware.py:81-95,211-224`). The snapshot is restored in
`before_agent` and written in `after_agent`, after which the REPL slot is
always evicted (`[code]` — `middleware.py:343-365,501-533`). Two things the
documentation doesn't mention:

- The snapshot is stored as a **binary patch chain**, not a full copy: the
  `_quickjs_snapshot_payload` field is a `PrivateStateAttr` annotated
  `DeltaChannel(replay_snapshot_chain)`, and the package pulls in `bsdiff4`
  as a dependency (`[code]` — `middleware.py:58-67`,
  `langchain_quickjs-0.3.5.dist-info/METADATA`). Being a `PrivateStateAttr`,
  it doesn't flow back to the parent through the subagent result contract
  ([`delegation.md`](delegation.md) §In deepagents) — but it **is** in the
  checkpoint.
- `max_snapshot_bytes` defaults to `memory_limit` = 64 MiB (`[code]` —
  `middleware.py:49,242-244`). That is a very high per-thread ceiling for
  something written into the checkpointer every turn; lower it deliberately
  rather than leaving the default.

Snapshot failures — on both restore and create — are caught,
`logger.warning`ed, and the payload set to `None` (`[code]` —
`middleware.py:358-364,524-530`). In `guardrails.md`'s taxonomy this is
**fail-open**: work continues with the interpreter's memory silently gone,
marked only by one log line.

**Per-user isolation requires `thread_id`.** The REPL is keyed by
`thread_id` from the LangGraph config; without one, a `session_<uuid8>`
fallback generated **once per middleware instance** is used (`[code]` —
`middleware.py:98-117,262`). The class docstring promises "globals from one
conversation cannot leak into another" (`middleware.py:122-125`) — that
promise holds **only** when `thread_id` is genuinely set. One
`CodeInterpreterMiddleware` instance reused across users without `thread_id`
shares one REPL, and user A's JS variables are readable by user B. This is
[`isolation-and-scoping.md`](isolation-and-scoping.md) §The prerequisite that
voids all of it in another form: a correct control, disabled by missing
configuration.

**Fan-out observability** exists and is useful: each dispatch emits `start` →
`complete`/`error` on LangGraph's `custom` stream, typed `"subagent"`, with a
per-dispatch `id`, an `eval_id` grouping one fan-out batch, `duration_ms`,
and `error` (`[code]` — `_subagent.py:30,55-134,221-271`). This is what makes
a live fan-out panel buildable (`streaming-protocol.md`). Worth noting:
`_emit_subagent_event` swallows every exception so observability can never
fail a dispatch (`[code]` — `_subagent.py:137-154`) — so a missing event
isn't a sign the subagent failed.

**Its trigger is partly an English keyword.** The documentation states that
the interpreter's system prompt treats the word **"workflow"** as a signal to
organise work through the interpreter and dispatch subagents from code, and
recommends it as "a deliberate lever you can pull to opt into dynamic
orchestration" (`[docs]` — `dynamic-subagents.md` line 145). For a
multilingual product this is exactly the problem
[`multilingual.md`](multilingual.md) discusses: a different execution path
chosen based on a word in one particular language, so an Indonesian-speaking
user asking for the same thing doesn't get the same behaviour. If dynamic
orchestration is genuinely wanted consistently, don't rely on this trigger —
state it in your own system prompt, or trigger it through request structure
rather than vocabulary.

**Two other documentation errors worth knowing before tuning:**

- `timeout` is described as "timeout limit in seconds for each `eval` call"
  (`[docs]` — `interpreters.md` line 558). The source: that is true only for
  the async path; on the **sync** path, `timeout` is used as a
  **cumulative** budget for the entire context (`[code]` —
  `_repl.py:401-405`). A long-lived sync agent will see all of its
  executions start timing out without a single program getting slower.
- The PTC prompt is cached by the **set of names** of exposed tools, not
  their identity. If a tool keeps the same name while its schema changes
  between turns, the model reads a stale signature — a source comment states
  that the consequence is the caller's to bear (`[code]` —
  `middleware.py:466-476`).

## Sources

- `[code]` `langchain_quickjs==0.3.5` — `middleware.py`, `_ptc.py`,
  `_subagent.py`, `_repl.py`. **Not** from the `../recipes/.venv` venv
  (deliberately left untouched so other packages' line citations don't
  shift); read from a separate venv. To reproduce:
  `uv venv qjs && VIRTUAL_ENV=qjs uv pip install "langchain-quickjs==0.3.5"`,
  then read `qjs/lib/python3.*/site-packages/langchain_quickjs/`.
- `[code]` `deepagents-0.7.8.dist-info/METADATA` (the
  `../recipes/.venv/lib/python3.13/site-packages/` venv) — the
  `Provides-Extra: quickjs` and `Requires-Dist: langchain-quickjs>=0.3.5;
  extra == "quickjs"` lines, the basis for the "the extra exists in 0.7.8"
  claim and for the contradiction with `>=0.2.0` in the documentation.
- `[docs]` [`../upstream/deepagents-docs/interpreters.md`](../upstream/deepagents-docs/interpreters.md)
  — a verbatim snapshot; used for claims about what the documentation
  **does** and **doesn't** state (the version requirement at line 18, the
  PTC warning at lines 282-284, the configuration table at lines 555-566).
- `[docs]` [`../upstream/deepagents-docs/dynamic-subagents.md`](../upstream/deepagents-docs/dynamic-subagents.md)
  — a verbatim snapshot; the `task()` input
  (`description`/`subagentType`/`responseSchema`, without `label`) and the
  six named orchestration patterns (classify-and-act, fan-out, adversarial
  verification, generate-and-filter, tournament, loop-until-done).
- `[code]` [`../deepagents/middleware.md`](../deepagents/middleware.md)
  §Stack order, §Dangerous interactions — the user middleware slot's
  position, the onion composition rule (`langchain/agents/factory.py:349`),
  and `_ToolExclusionMiddleware`'s position; used without re-reading
  `factory.py`.
- `[code]` [`delegation.md`](delegation.md) §In deepagents —
  `PrivateStateAttr` not flowing back into parent state; used to infer where
  `_quickjs_snapshot_payload` sits relative to the result contract.
- `[inferred]` Two claims are marked explicitly in the body and have not
  been executed: (a) `interrupt_on={"eval": True}` gates the program, (b)
  `HarnessProfile.excluded_tools` doesn't bind the PTC allowlist. Both are
  assembled from the `[code]` facts cited in place.
