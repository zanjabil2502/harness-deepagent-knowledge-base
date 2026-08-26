# Guardrails

## Problem

"Guardrail" almost always shrinks to one thing: a content filter on output —
usually one moderation call before the answer goes to the user. That covers
one of the six points where policy can (and will) be violated inside an
agent loop. A product that feels it "has guardrails" because it installed one
moderation classifier on output is still breached through: prompt injection
arriving in a tool result (not in a user message, so it never passes the
input filter), retrieval returning another user's documents (nothing is
wrong with the "output" — the text is valid, only its owner is wrong), a
destructive tool called without approval, or a loop running 4000 steps
before anyone notices the cost. The right classifier name (Llama Guard, NeMo
Guardrails, etc.) installed at the wrong point is still breached at the other
five — the right product name is no evidence of sufficient coverage.

The second problem is subtler: a guardrail installed without **deciding**
what happens when it fails (a classifier error, a timeout, a dependency
down) inherits its behaviour from however that error happens to be handled
in code — usually a `try/except` that swallows it and continues (accidental
fail-open) or one that lets the exception propagate and stops the request
(accidental fail-closed). Both defaults are right for some guardrails and
fatally wrong for others, and the code can't tell the difference unless its
author decides explicitly per guardrail.

## Pattern

### Six enforcement points, each guardrail declaring three things

This six-point framework is `[ours]` — following this project's spec §8.4,
consistent with NeMo Guardrails' "rails" taxonomy which independently
arrives at something similar: *input rails* (pre-LLM), *dialog rails*
(conversation flow), *retrieval rails* (validating retrieved content),
*execution/tool rails* (before/after a tool call), *output rails* (post-LLM)
`[docs]`. Vanilla in the industry: guardrails are sold and installed as one
point — usually "output moderation", sometimes plus input — sufficient for a
single-turn chatbot with no tools. We diverge by adding two points no
single-turn taxonomy needs: **Loop** (multi-step controls: cost, time,
oscillation) and **System** (model versions, fallbacks, auditing across gate
decisions) — neither exists in non-agentic products because there are no
"many steps" or "many gate decisions" to control or audit.

Each row below is one concrete guardrail, not one point — and **every
guardrail must state three things**: the policy, the enforcement point, the
failure mode. The failure modes are deliberately not uniform:

| # | Point | Policy (example) | Enforcement point | Failure mode |
|---|---|---|---|---|
| 1 | Input | Content moderation (violence/harassment/abuse) | Before the turn enters state, the `before_model` hook | **Fail-open** — a classifier error → log + continue. Holding the whole product hostage to one failed check costs more than letting one turn through unmoderated |
| 1 | Input | PII redaction (emails, card numbers in user messages) | `before_model`, `PIIMiddleware(apply_to_input=True)` | Mixed per type: `strategy="block"` (fail-closed) for high-risk PII (card numbers), `strategy="redact"` (fail-open, continuing with a masked version) for low-risk PII (emails) |
| 1 | Input | Injection & jailbreak detection, topic bounds | `before_model`, a custom classifier (Llama Guard / a NeMo input rail) | Fail-closed on a high score (`can_jump_to=["end"]`, the turn stops) — a false positive here only rejects one turn, far cheaper than a false negative letting a jailbreak through |
| 2 | Retrieval/context | **Authorisation filtering** — retrieval results scoped to the active `user_id` (§8.2) | Inside the retrieval tool's implementation, before the query executes — not filtering the results afterwards | **Fail-closed** — an error in the scope layer (e.g. `current_user_id` never set) means zero rows, not the whole index. This is the most frequent leak in multi-user RAG because it looks like "just a search", exactly the `isolation-and-scoping.md` argument |
| 2 | Retrieval/context | Untrusted content tagging + provenance | When retrieval/tool result content is written to state, before it enters the model context | Fail-open for tagging (always tag, never block content) — the label is what tells the model (and other guardrails at the Output point) that this content must not be treated as instructions. See `security.md` for why this is the primary defence against prompt injection through tool results |
| 3 | Tool/action | A per-role tool allowlist | `excluded_tools` (`HarnessProfile`) → `_ToolExclusionMiddleware` | **Fail-closed** — an unlisted tool is never visible to the model at all, rather than visible then refused when called (a failure the model doesn't see = no attempt to re-persuade) |
| 3 | Tool/action | Tool argument validation | The tool schema (Pydantic `args_schema`) before the handler is called | Fail-closed — arguments failing validation never reach the tool function |
| 3 | Tool/action | An approval gate for destructive actions, token scope narrowing | `interrupt_on=`/`permissions=[...,mode="interrupt"]` → `HumanInTheLoopMiddleware` | Fail-closed — the run stops awaiting approval; an approval timeout defaults to *deny*, not to continue |
| 4 | Output | Schema validation, groundedness, citations required | `RubricMiddleware` (iterating until the rubric passes or `max_iterations`) | Fail-open on reaching `max_iterations` — send the best available answer with a "rubric not met" flag to the observability layer; don't leave the turn hanging forever |
| 4 | Output | Checking for PII leakage in the answer | `after_model`, `PIIMiddleware(apply_to_output=True)` | The same mixed pattern as input PII — `hash`/`mask` for pseudonymous data that must stay useful, `block` for data classes that must never leave |
| 4 | Output | Secret scanning in generated code (API keys, private keys, `sk-…`/`AKIA…` patterns) | Before `write_file`/`edit_file` commits to disk, or `after_model` on code blocks | **Fail-closed** — a secret pattern match blocks the write; write-then-warn means the secret is already on disk (and possibly already in git) before anyone reads the warning |
| 5 | Loop | Max tool calls per run/thread | `ToolCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior=)` | `exit_behavior` **is** the explicit failure mode declaration: `"error"` = fail-closed (raise), `"end"` = controlled fail-open (close the turn with state as-is), `"continue"` (the library default) = it doesn't stop at all — choosing the default without reading its documentation means this guardrail does nothing |
| 5 | Loop | Token/cost budget per run, kill switch | `ModelCallLimitMiddleware` + app-level cost accumulation (`cost-control.md`) | Fail-closed at run level (stop that run), fail-open at user level (the user can still start a new run — an exhausted budget isn't a permanent ban) |
| 5 | Loop | Oscillation & no-progress detection | A custom `after_model` — comparing consecutive tool-call hashes / state progress | Fail-open with a warning up to N repetitions, then fail-closed (stop the run) — one repetition is normal (a legitimate retry), many identical repetitions signal being stuck |
| 6 | System | Pinning the model version | An explicit `model` parameter to `create_deep_agent(model=...)`, not a floating alias (`"latest"`) | Implicitly fail-closed — an unknown model/alias fails at agent construction rather than quietly resolving to another version at runtime |
| 6 | System | Model fallback policy | `ModelFallbackMiddleware(primary, *fallbacks)` | **Fail-open by design** (its purpose is availability) — but it must be paired with an audit log per gate decision (which model actually answered), or "an answer from a weaker fallback" becomes untraceable |

### The third failure mode: fail-deferred

The table above uses two modes — fail-open and fail-closed. There is a third,
and it only makes sense when the gate is **human approval** and no human is
waiting: **don't allow, don't refuse, suspend**.

OpenWorker implements it as an approver swapped per session mode. An
unattended session uses `inbox_approver`, whose docstring states its own
behaviour — *"routes a permission request to the Inbox and suspends until
resolved"*. `[code]` `andrewyng/openworker` @ `141d02a`,
`coworker/inbox.py:387-406`; the `await store.wait(item.id)` at `:362-371`
has **no timeout**. See
[`../systems/openworker.md`](../systems/openworker.md) §6.

What makes it more than a polite fail-closed: the request is **durable and
idempotent**. An inbox item stores its `tool_call_id` and its creation is
idempotent over `(session_id, tool_call_id)` (`inbox.py:77,142`), so a
process dying while waiting loses its coroutine but not its request — a
re-run raises the same prompt rather than a duplicate. `[code]`

**Its cost is honest and must not be hidden**: a suspended run holds
resources indefinitely. In a single-operator desktop product that is
acceptable — there is one run, belonging to the person who will come back.
**In a multi-user service it is a resource leak**, and a scheduled run
waiting for approval is a normal occurrence, not an exception.

So fail-deferred may only be used here when paired with two things OpenWorker
doesn't need: `[ours]`

1. **A timeout on the wait**, not a bare `await` — so the run doesn't hang
   forever. Vanilla is the unbounded `await` at `inbox.py:362-371`; we
   diverge because one hanging run in a multi-user service holds an
   orchestrator slot the HPA counts
   ([`serving-topology.md`](serving-topology.md) §the in-flight turns
   signal).
2. **An explicit policy when the timeout expires** — falling to fail-closed
   (cancel the run, record why) or to a controlled fail-open. Choosing "let
   it hang" is choosing a failure mode without stating it, which the
   three-things rule above forbids.

The queue of waiting requests has backpressure of its own; see
[`queueing-and-backpressure.md`](queueing-and-backpressure.md).

### Tiered: deterministic first, model-based only when needed

Model-based guardrails (Llama Guard, NeMo's self-check rails, Guardrails AI's
LLM-based validators) multiply cost and latency on **every call passing that
point** — not just the violating ones. One model-based guardrail at the Input
point means every turn, including the 99% that are safe, now waits for an
extra LLM round trip before the main turn starts. The tiers, cheap to
expensive:

1. **Purely deterministic** — schemas (Pydantic `args_schema`), regexes, a
   tool name allowlist. Presidio partly belongs here: its regex/checksum
   recognisers (e.g. Luhn validation for card numbers) run with no model at
   all. `[docs]`
2. **Deterministic + cheap NER** — the full Presidio Analyzer combines regex
   recognisers with NER models (spaCy/Transformers/Stanza, pluggable) plus a
   lemma-based `ContextAwareEnhancer` to raise confidence from surrounding
   context — more expensive than pure regex but far cheaper than one
   generative LLM call, and it catches PII classes regex cannot (people's
   names, addresses). `[docs]`
3. **A small model/dedicated classifier** — Llama Guard: an 8B fine-tuned
   model inferenced once to produce a safe/unsafe verdict plus a category (a
   14-category taxonomy aligned with MLCommons: violence, child
   exploitation, privacy, hate speech, etc., supporting both input and
   output). Still one model call, but a small model on a narrow task
   (classification, not free generation) — cheaper than the product's main
   model but not free. `[docs]`
4. **A full generative LLM as the guardrail** — NeMo Guardrails' self-check
   rails or Guardrails AI's LLM-based validators asking a model to judge or
   rewrite the answer. The most expensive, used only for what can't be
   checked deterministically or by a small classifier: groundedness against
   retrieved documents, nuanced policy compliance irreducible to patterns.
   `[docs]`

The default order: try tier 1 first; go up one tier only when the previous
proves insufficient for that risk class — not installing tier 4 everywhere
because it is "the most accurate".

### A guardrail has a false-positive rate — put it in the eval harness

A guardrail installed and never measured is a liability, not a control: every
detector (regex, NER, classifier) has a precision/recall trade-off, and
without real numbers its threshold is a guess. A guardrail that fails closed
too aggressively on legitimate requests (e.g. moderation wrongly blocking
non-English text, PII redaction wrongly flagging an ordinary reference number
as a card) is a UX incident nobody will ever discover unless somebody
measures it. Every guardrail's precision/recall must be an eval harness
metric rather than merely "installed" — see [`evaluation.md`](evaluation.md)
§Guardrails as measurable objects.

### Policy must not live only in the prompt

A rule in the system prompt ("never leak another user's data", "always ask
for confirmation before deleting") is **advisory** — the model can be
persuaded to ignore it, and the most frequent persuader isn't an honest user
in the opening message but text in a tool result disguised as an instruction
(see [`security.md`](security.md) §Prompt injection through tool results, the
number one multi-step security issue). Real enforcement lives in code running
outside the model's control — middleware reading, changing, or blocking state
before or after the model is called. The prompt remains useful for guiding
the model's *default* behaviour, but is never the only layer for anything
whose failure is expensive.

## Trade-offs

- **Fail-closed everywhere vs fail-open everywhere** — uniform fail-closed is
  maximally safe but makes every guardrail a single point of failure for the
  whole product (guardrail down = product down); uniform fail-open is
  maximally available but makes guardrails decorative as soon as their
  infrastructure fails or is under load. The decision must be per guardrail
  based on the asymmetry of harm: a silent, invisible data leak (fail-closed)
  vs an annoying, visible blocked chat (fail-open) — the table above is that
  rule applied, not a new rule.
- **Tiering vs one LLM classifier checking everything** — one generic LLM
  checker is simpler to reason about (one code path, one place to tune) but
  adds a full model round trip to *every* turn without exception; tiering is
  cheaper on average but adds code surface (each tier = a separate path
  needing tests) and an explicit "when to go up a tier" decision that can be
  set wrongly.
- **A centralised guardrail framework (NeMo Guardrails/Guardrails AI as the
  rail orchestrator) vs point libraries wired together yourself** (Presidio
  for PII + Llama Guard for content + custom regexes for secrets, each called
  from middleware we write) — a framework provides a configuration/rail
  language reusable across projects at the cost of an extra dependency and a
  runtime whose semantics we don't fully control running inside our loop;
  wiring point libraries fits `deepagents`/`langchain`'s "guardrail =
  middleware" model better (each library becomes one call inside a hook we
  wrote) at the cost of repeating the plumbing (hook wiring, exit behaviour,
  logging) manually per guardrail, with no shared abstraction.

## In deepagents

None of NeMo Guardrails, Guardrails AI, Llama Guard, or Presidio has a native
integration into `deepagents`/`langchain` — all four are standalone libraries
that must be called manually from inside custom `AgentMiddleware`. What
**maps 1:1 to middleware** is the enforcement point, not the classifier
library:

| Point (from the table above) | `deepagents`/`langchain` middleware/mechanism | Source |
|---|---|---|
| 1. Input — PII | `langchain.agents.middleware.PIIMiddleware(pii_type, strategy=, apply_to_input=True)`, the `before_model` hook | `[code]` `langchain/agents/middleware/pii.py` (langchain 1.3.16, the same version cited by `deepagents.md`) |
| 1. Input — injection/jailbreak/topic/moderation/abuse | No built-in middleware; write a custom `AgentMiddleware` with a `before_model` hook calling a classifier (Llama Guard / a NeMo input rail / a Guardrails AI validator) inside it, with `@hook_config(can_jump_to=["end"])` to cut the turn on a positive | `[code]` the `before_model`/`hook_config` hooks exist in `langchain/agents/middleware/types.py`; `[inferred]` no built-in classifier module — concluded from the absence of any such import in `langchain/agents/middleware/` or `deepagents/middleware/` |
| 2. Retrieval/context — authorisation, provenance | No generic middleware; enforcement lives **inside** the custom retrieval tool's implementation (an RLS-scoped query, see `isolation-and-scoping.md`), or through the `wrap_tool_call(request, handler)` hook intercepting the request before the tool handler runs | `[code]` `wrap_tool_call` — `langchain/agents/middleware/types.py` |
| 3. Tool/action — a per-role allowlist | `excluded_tools` (`HarnessProfile`/`ProviderProfile`) → `_ToolExclusionMiddleware` | `[code]` cited from `../systems/deepagents.md` §7, §Built-in middleware |
| 3. Tool/action — argument validation | Each `BaseTool`'s Pydantic `args_schema`, validated by the LangChain framework before the handler is called | `[docs]` |
| 3. Tool/action — approval gate, scope narrowing | `interrupt_on=`/`permissions=[FilesystemPermission(mode="interrupt")]` → `HumanInTheLoopMiddleware` | `[code]` cited from `../systems/deepagents.md` §6 |
| 3. Tool/action — sandbox bounds | A backend implementing `SandboxBackendProtocol` (not `LocalShellBackend` without additional sandboxing — optional, must be installed explicitly, and **not** a `deepagents` default (the default is `StateBackend`, see `../systems/deepagents.md` §Filesystem backend); once `LocalShellBackend` is chosen, the `THREAT_MODEL.md` finding about unvalidated commands applies) | `[code]`/`[docs]` cited from `../systems/deepagents.md` §6, §Filesystem backend |
| 3. Tool/action — dry run | No built-in mechanism; `permissions=[..., mode="deny"]` refuses execution without side effects but that is a permanent block, not a "try without effects" mode repeatable as a real execution — a genuine dry run (the tool returning a simulated result with no side effects) has to be written inside the tool implementation itself | `[inferred]` no dry-run parameter/mode found in the `FilesystemPermission`/`interrupt_on` read in Task 3 |
| 4. Output — schema, groundedness, citations | `RubricMiddleware` (deepagents; iterating against a rubric until it passes or `max_iterations`; not a default) | `[code]` cited from `../systems/deepagents.md` §Built-in middleware (`deepagents/middleware/rubric.py`) |
| 4. Output — PII, secret scanning | `PIIMiddleware(apply_to_output=True, apply_to_tool_results=True)` for PII; secret scanning = a custom `after_model` or pre-write hook (nothing built in) | `[code]` `langchain/agents/middleware/pii.py` |
| 5. Loop — step limits, budget, kill switch | `ToolCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior=)`, `ModelCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior=)`; `cancel_async_task` (`AsyncSubAgentMiddleware`) as a background task kill switch | `[code]` `langchain/agents/middleware/tool_call_limit.py`, `model_call_limit.py`; `AsyncSubAgentMiddleware` cited from `../systems/deepagents.md` §Built-in middleware |
| 6. System — pinning models, fallback | An explicit `model` parameter to `create_deep_agent(model=...)`; `ModelFallbackMiddleware(primary_model, *fallback_models)`, the `wrap_model_call` hook | `[code]` `langchain/agents/middleware/model_fallback.py` |
| 6. System — a gate audit log | No built-in audit table; the per-step state checkpoint (the application-injected `checkpointer`) is the closest trail available for free — see [`replay-and-forensics.md`](replay-and-forensics.md) for its limits as an audit log | `[code]` cited from `persistence-schema.md` §checkpointer, `../systems/deepagents.md` §5 |

**A concrete warning for point 5 (Loop)**: `deepagents` raises LangGraph's
`recursion_limit` from 25 (the default) to **9999**
(`.with_config({"recursion_limit": 9_999, ...})`, installed automatically in
`create_deep_agent`) — this is **not** a loop guardrail, it is a safety net
so a legitimately long task isn't cut off by a `GraphRecursionError` at
LangGraph's much smaller default. `[code]` — cited from
`../systems/deepagents.md` §1 (`deepagents/graph.py` lines 935-944). The
consequence: unless `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` are
installed explicitly, the `deepagents` default effectively has **no**
practical step limit — 9999 steps is a budget that can burn significant money
before stopping on its own. Point 5's guardrails must be installed
explicitly, not assumed to come free with `deepagents`.

Every `langchain.agents.middleware.*` middleware in the table above
(`PIIMiddleware`, `ToolCallLimitMiddleware`, `ModelCallLimitMiddleware`,
`ModelFallbackMiddleware`) does not belong to `deepagents` — like
`TodoListMiddleware`, already marked in `../systems/deepagents.md` as "not
`deepagents`'", it is imported from `langchain.agents.middleware` and
injected manually through `create_deep_agent(middleware=[...])`, entering no
built-in stack.

## Sources

- `[docs]` NeMo Guardrails — NVIDIA's official documentation
  (`docs.nvidia.com/nemo/guardrails`), the five rail types taxonomy
  (input/dialog/retrieval/execution/output).
- `[docs]` Guardrails AI — `guardrailsai.com/docs`, Guards/validators as
  Input+Output Guards, Hub validators for risk detection/mitigation.
- `[docs]` Llama Guard 3 — `huggingface.co/meta-llama/Llama-Guard-3-8B`, a
  fine-tuned content safety classification model, its 14-category taxonomy
  aligned with MLCommons, supporting both input and output, model-based
  (requiring inference).
- `[docs]` Presidio — `presidio.dataprivacystack.org/analyzer/`, the hybrid
  regex+NER Analyzer (`ContextAwareEnhancer`), the Anonymizer's
  redact/hash/encrypt strategies.
- `[code]` `langchain/agents/middleware/pii.py` (langchain 1.3.16, installed
  through `pip install langchain==1.3.16` in a separate research venv) —
  `PIIMiddleware`, the
  `apply_to_input`/`apply_to_output`/`apply_to_tool_results` parameters, the
  `block`/`redact`/`mask`/`hash` strategies, the `before_model` hook.
- `[code]` `langchain/agents/middleware/tool_call_limit.py` —
  `ToolCallLimitMiddleware`, `thread_limit`/`run_limit`/`exit_behavior`
  (`"continue"`/`"error"`/`"end"`).
- `[code]` `langchain/agents/middleware/model_call_limit.py` —
  `ModelCallLimitMiddleware`, the same parameters, the
  `before_model`/`after_model` hooks with `can_jump_to=["end"]`.
- `[code]` `langchain/agents/middleware/model_fallback.py` —
  `ModelFallbackMiddleware`, `wrap_model_call`, sequential retry into
  fallback models when the primary errors.
- `[code]` `langchain/agents/middleware/types.py` — the complete
  `AgentMiddleware` hook set
  (`before_agent`/`before_model`/`wrap_model_call`/`after_model`/`wrap_tool_call`/`after_agent`),
  the basis for every point→middleware mapping above.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §1
  (recursion_limit 9999), §6 (Safety gate —
  `interrupt_on`/`permissions`/sandbox), §7
  (`HarnessProfile`/`excluded_tools`), §Built-in middleware
  (`RubricMiddleware`, `AsyncSubAgentMiddleware`, `TodoListMiddleware` as the
  "not deepagents'" precedent) — a tier-1 reference verified in Task 3, cited
  without re-reading the `deepagents` source in this task.
- `[code]` [`persistence-schema.md`](persistence-schema.md) §checkpointer —
  the basis for the "per-step state checkpoints as the closest free audit
  trail" claim in §6 System.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — the basis
  for the `user_id`/RLS scope model referenced at point 2
  (Retrieval/context), not re-proposed in this file.
