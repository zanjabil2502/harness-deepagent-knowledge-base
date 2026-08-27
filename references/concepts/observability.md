# Observability

## Problem

Agents fail silently far more often than they fail loudly. A tool call
that fails and is swallowed by a `try/except` that shouldn't exist, a
model that picks the wrong tool yet still produces a plausible-sounding
answer, a loop that widens to 20 steps when 3 would do - all of them
return HTTP 200 and text that looks reasonable. Without per-step
visibility, "debugging" becomes reading the whole transcript and guessing
which step actually went wrong, because nothing marked that specific step
as anomalous when it happened.

The second problem: a trace not tagged with `user_id` is useless for
per-user investigation. "User X reported Y" cannot be answered by
filtering traces to that user if the tag was never applied when the trace
was recorded - much like a query without `WHERE user_id` in
`isolation-and-scoping.md`, except that here the consequence isn't a data
leak (traces aren't product data) but the inability to answer "what
actually happened for this user" after the fact, including when an
incident investigation needs its scope (which users were affected) and
that cannot be reconstructed from untagged traces.

## Pattern

### A span per step, not one span per turn

One trace = one turn; inside it, **one span per graph step** - one model
call = one span (`LangfuseGeneration`), one tool call = one child span
(`LangfuseTool`), nested under the turn/agent span
(`LangfuseChain`/`LangfuseAgent`). `[code]` - span class names cited from
`langfuse/langchain/CallbackHandler.py` (Langfuse Python SDK 4.14.4,
installed via `pip install langfuse` in a separate research venv). This
nesting maps directly onto standard OpenTelemetry semantics (parent-child
spans), which underpins both libraries referenced in this task (Langfuse
and OpenLLMetry/Traceloop are both built on OTel). With a span per step,
time/tokens/cost/errors become attributable to a specific step rather than
only to a per-turn aggregate - this is what makes "which step failed"
answerable directly from the trace instead of by guessing.

### A `user_id` label on every trace

Neither Langfuse nor OpenLLMetry knows anything about the application's
scope model (`user_id` from `isolation-and-scoping.md`) natively - that
tag must be injected explicitly on every invoke, with a different
mechanism per library:

- **Langfuse** - through `config={"metadata": {"langfuse_user_id": ...,
  "langfuse_session_id": ...}}` passed into the LangChain runnable call;
  `CallbackHandler` reads those metadata keys and copies them into the
  span attributes `user_id`/`session_id`. `[code]` -
  `langfuse/langchain/CallbackHandler.py` lines ~496-504 (detecting
  `langfuse_session_id`/`langfuse_user_id` in metadata and writing them to
  `attributes["session_id"]`/`attributes["user_id"]`).
- **OpenLLMetry/Traceloop** - through an explicit call to
  `traceloop.sdk.tracing.set_association_properties({"user_id": ...,
  "session_id": ...})` before the invoke; this attaches to the OTel
  context (`attach(set_value("association_properties", properties))`) so
  every span created afterwards automatically receives the attribute
  `traceloop.association.properties.user_id`. `[code]` -
  `traceloop/sdk/tracing/tracing.py`, the functions
  `set_association_properties` and
  `_set_association_properties_attributes` (package
  `opentelemetry-instrumentation-langchain`==0.62.3, released alongside
  `traceloop-sdk`).

The two mechanisms differ in shape but share exactly the discipline of
`SET LOCAL app.current_user_id` at the RLS layer
(`isolation-and-scoping.md`): it must be applied on **every** invoke, not
once at process start, and a trace that forgot the tag isn't wrong - it is
merely useless for per-user filtering, exactly as a query without
`WHERE user_id` isn't syntactically wrong, merely unsafe for scoping. The
tag's source must be the same scope object already established in
`isolation-and-scoping.md` (`(user_id,)` → `(tenant_id, user_id)`) rather
than derived again at the observability layer - one place changes during a
tenant migration, not two.

## Trade-offs

- **Langfuse (a dedicated LLM observability product with ready-made
  UI+eval+prompt management) vs OpenLLMetry/OTel-native (vendor-neutral,
  exporting to any OTel backend - Honeycomb, Datadog, Jaeger, Grafana
  Tempo, including self-hosted)** - Langfuse gives an LLM-specific UI
  (token/cost breakdowns, session views) out of the box at the cost of one
  more dedicated backend/dependency to run and pay for; OpenLLMetry gives
  spans over the standard OTel protocol so they can be pointed at an
  existing observability stack (including on-prem, relevant to assumption
  A1 cloud-and-on-prem) at the cost of assembling LLM-specific views
  yourself. The two aren't technically exclusive at the wire level
  (Langfuse is itself built on OTel `[code]`, visible from the
  `opentelemetry.trace`/`context` imports in `CallbackHandler.py`), but
  running both at once doubles overhead with no added benefit - pick one
  per project based on cloud-vs-on-prem and whether an OTel stack already
  exists.
- **Span-per-step granularity vs coarse span-per-turn** - fine-grained is
  exactly what answers "which step failed", but multiplies span volume
  (cost on a hosted tracing backend at high traffic, more noise for the
  human tracing through). Mitigation: sample successful runs with no error
  and no guardrail triggered, and always keep full detail for runs that
  errored or triggered a guardrail (a guardrail event recorded in the
  trace, from `guardrails.md`, is a "full retention required" signal, not
  merely an extra note).

## In deepagents

`deepagents` emits no tracing of its own - there is not a single mention
of OTel/spans/traces in the source read in Task 3
(`../systems/deepagents.md` has no such section), consistent with the
"the calling application owns truth" pattern already recurring in
`session-state.md`/`isolation-and-scoping.md`. `[inferred]` - inferred
from finding no tracing module in the `deepagents` source dissected in
Task 3. Tracing is attached entirely at the LangChain layer:

- Langfuse's `CallbackHandler` is a standard `BaseCallbackHandler`
  (`langchain_core.callbacks`) passed through
  `config={"callbacks": [...]}` at invoke time - the same generic
  mechanism that captures model and tool calls (including the `task` tool
  from `SubAgentMiddleware` and the background tools from
  `AsyncSubAgentMiddleware`) as nested chain/tool spans automatically,
  with no `deepagents`-specific integration code - callbacks fire at the
  LangChain/LangGraph graph node level, which `deepagents` merely
  assembles rather than replaces. `[code]` - cited from
  `../systems/deepagents.md` §Built-in middleware for the
  `SubAgentMiddleware`/`AsyncSubAgentMiddleware` list.
- The `user_id` tag is applied at the same invoke point where the
  application already passes `config={"configurable": {"thread_id": ...}}`
  for the checkpointer (`session-state.md`, `persistence-schema.md`) -
  extending that same config dict with `metadata` (Langfuse) or calling
  `set_association_properties` (OpenLLMetry) before the invoke;
  `deepagents` itself neither reads nor cares about that metadata, passing
  it through unchanged to the LangChain runnable engine.
- **Propagation to subagents** - Langfuse's `CallbackHandler` keeps an
  explicit run hierarchy (`_RunState.parent_run_id`/`root_run_id`,
  `_RootRunState.run_ids`) `[code]` -
  `langfuse/langchain/CallbackHandler.py` - which means spans from a
  subagent (the `task` tool, `SubAgentMiddleware`) automatically inherit
  the `user_id` tag applied at the top-level invoke, with no extra
  per-subagent code, as long as the top-level config/metadata carries it.
  Without understanding this, it is easy to assume each subagent must be
  tagged manually.

## Sources

- `[code]` `langfuse/langchain/CallbackHandler.py` (Langfuse Python SDK
  4.14.4, `pip install langfuse` in a separate research venv) - the span
  classes (`LangfuseGeneration`/`LangfuseTool`/`LangfuseChain`/
  `LangfuseAgent`), parsing of `langfuse_user_id`/`langfuse_session_id`
  from metadata, `_RunState`/`_RootRunState` for parent-child run
  hierarchy, and the `opentelemetry.trace`/`context` imports proving
  Langfuse is built on OTel.
- `[code]` `traceloop/sdk/tracing/tracing.py` and
  `opentelemetry/instrumentation/langchain/callback_handler.py`
  (`opentelemetry-instrumentation-langchain`==0.62.3, released alongside
  `traceloop-sdk`; `pip install traceloop-sdk opentelemetry-instrumentation`
  in a separate research venv) - the functions
  `set_association_properties`, `_set_association_properties_attributes`,
  and the OTel context attach mechanism.
- `[code]`/`[inferred]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Built-in middleware - no tracing module was found in the `deepagents`
  source dissected in Task 3; `SubAgentMiddleware`/`AsyncSubAgentMiddleware`
  are cited to explain the `task`/background tool spans.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) - the
  `user_id`/scope object model that is the source of the tag's value,
  cited without proposing a new model.
- `[code]` [`persistence-schema.md`](persistence-schema.md),
  [`session-state.md`](session-state.md) - the
  `config={"configurable": {"thread_id": ...}}` convention marking the
  same invoke point where the `user_id` tag is applied.
- `[code]` [`guardrails.md`](guardrails.md) - the basis for the "a trace
  with a guardrail event requires full retention" rule in §Trade-offs.
