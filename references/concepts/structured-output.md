# Structured output

## Problem

Model output is free text by default — if the application needs a specific
shape (JSON with required fields, an enum of valid values, types the code
behind it can use directly), that shape has to be enforced somewhere. The
easiest place to install it — an instruction in the prompt ("reply in JSON
format with fields `x`, `y`, `z`") — is only **advisory**, for exactly the
reason [`guardrails.md`](guardrails.md) §Policy must not live only in the
prompt rejects the prompt as the sole enforcement layer: the model can omit
a field, get a type wrong, or add a preamble before the JSON ("Sure, here's
the result:") that makes a naive JSON parser fail outright. This failure
usually surfaces only in the code layer that assumed the output was already
valid — a `json.loads()` blowing up, or worse, not blowing up but returning
a structure that is quietly the wrong shape and passes on to the next layer.

Second problem: once a schema is enforced **and** there is a retry mechanism
for failures, the retry itself needs an explicit decision — unbounded retry
for a systematic failure (a schema the model structurally cannot satisfy,
e.g. mutually contradictory fields) burns money without end; zero retries
turn one transient failure (a formatting slip from sampling noise) directly
into an error propagated to the user, when a second attempt would very
likely have succeeded.

## Pattern

### Two schema enforcement routes: provider-native vs synthetic tool call

- **Native/provider-side** — the model provider has a built-in structured
  output mode (constrained decoding/JSON mode) guaranteeing schema-conformant
  output at the token generation level itself, rather than validating
  afterwards. The strictest option (structurally incapable of producing
  invalid JSON), but not every provider/model supports it, and different
  providers use different mechanisms (not portable across providers without
  an abstraction layer).
- **A synthetic tool call** — the schema is registered as a fabricated
  "tool" (not a real tool with side effects); the model "calls" that tool
  with arguments shaped like the requested schema, and those arguments are
  parsed and validated like ordinary tool arguments (see `tool-design.md`
  §Strict vs loose schemas). Portable across providers (using the existing
  tool-calling mechanism rather than a provider-specific feature), but
  schema validity is only known **after** generation completes, not
  guaranteed during it — which is where retry (below) matters, because a
  validation failure on this route is an ordinary occurrence, not a rare
  case.

These two routes aren't an exclusive project-level choice — production
systems usually select automatically: use native if the active
model/provider supports it (stricter, no retry needed for shape failures),
fall back to a synthetic tool call otherwise (portable, but needing retry).
See `## In deepagents` for the concrete form of that automatic selection.

### Retry as part of the schema contract, not a separate wrapper

A schema validation failure must have an explicit answer for three things,
just like a guardrail (`guardrails.md` §Pattern: "every guardrail must state
three things") — **which schema/validator**, **how many retries**, **what
happens when retries are exhausted**:

- **The retry signal must go back to the model as actionable feedback**,
  not merely "try again" with no context — the validation error message
  (which field is missing or wrongly typed) is sent back as part of the
  conversation history so the second attempt has information the first
  didn't. A blind retry (repeating the identical prompt) merely hopes
  sampling noise happens to produce the right shape this time — sometimes it
  works, but it can't be relied on as a strategy.
- **Retries have an explicit upper bound** — for the same reason
  `guardrails.md` point 5 (Loop) requires an explicit
  `max_iterations`/limit to stop a systematic failure burning money without
  end: a failure persisting to the retry limit means the problem isn't
  transient noise but structural (the schema can't be satisfied from the
  available context) — more retries don't solve a structural problem.
- **A failure after retries are exhausted must have a defined way out** —
  the same pattern as `guardrails.md` point 4 (Output, `RubricMiddleware`
  on reaching `max_iterations`: *"send the best available answer with a
  'rubric not met' flag... don't leave the turn hanging forever"*). For
  structured output: an explicit choice between (a) returning a structured
  error to the caller (the application knows this turn failed validation and
  can show the user a message) or (b) returning the raw unvalidated output
  with an explicit "schema not met" flag for a more tolerant caller — **not**
  a silent default of passing unvalidated output on as if valid, which moves
  the failure to the next code layer, the one least prepared to handle it
  (because it assumes validation already happened).

### Its relationship with output guardrails — two distinct layers, don't merge them

[`guardrails.md`](guardrails.md) point 4 (Output) lists **"Schema
validation, groundedness, citations required"** (plus PII leakage and
secret scanning on separate rows), all enforced by `RubricMiddleware`. The
phrase "schema validation" on that row is **not** the mechanism this file
describes — two files have "schema validation" in their scope and the
boundary must be explicit rather than left to the reader: `guardrails.md`'s
`RubricMiddleware` is a **self-eval rubric criterion** scoring output that
is **already well-formed** (part of quality assessment alongside
groundedness/citations — e.g. "are all the required fields relevant and
meaningfully filled", not "is the JSON valid"); this file owns **whether
the output is well-formed at all** — the question that must be answered YES
first, at a layer before any rubric can evaluate anything, through
`response_format`/`ToolStrategy`/`ProviderStrategy` (see `## In
deepagents`). The ordering is therefore not merely advisable but structural:
output failing shape validation (e.g. `amount` isn't a number, or
`ToolStrategy` couldn't parse it at all) has no structure for
`RubricMiddleware` to score — this file's schema validation runs **first**
(retrying until the shape is valid or giving up through the defined way out
above), and `guardrails.md` point 4's rubric runs **after**, over output
already known to be correctly shaped. These two layers **must not be
merged** into one large validator — shape failures and policy/quality
failures need different retry strategies and failure modes (see
`guardrails.md` §Pattern: "every guardrail must state three things" applies
separately to each layer, not once to both combined).

## Trade-offs

- **Provider-native vs synthetic tool call** — covered in §Pattern; in
  brief: native is stricter (guaranteed at generation level) but not
  portable and not universally supported; a synthetic tool call is portable
  and works on any model that already supports tool calling, but its
  validity is known afterwards (needing retry) and it costs slightly more
  (one synthetic tool-call round vs direct generation).
- **Strict validation (raise on every schema deviation) vs loose validation
  (accept a superset, ignore extra fields)** — strict guarantees the exact
  contract with the schema (safe for downstream code assuming the exact
  shape) but is brittle against minor deviations that are actually harmless
  (an extra unused field); loose tolerates minor noise but can let through a
  deviation that actually matters (a typo'd field name that should count as
  "required field missing" rather than "extra field ignored").
- **Automatic retry (within one turn, transparent to the user) vs visible
  explicit retry (the user knows a retry happened)** — automatic gives a
  smooth UX (the user never sees a transient failure) but hides a signal
  useful for observability (how often the schema fails on the first attempt
  is a prompt/model health metric — see
  `evaluation.md`/`observability.md`); visible retry (a separate log/span
  per attempt) preserves that signal but needs explicit instrumentation so
  "transparent retry" doesn't become "retry nobody ever measured".

## In deepagents

`response_format` on
`create_deep_agent(...)`/`langchain.agents.create_agent(...)` is the
built-in route for all of §Pattern above:

- **Three strategies**, exactly the two routes of §Pattern plus one
  automatic mode: `ToolStrategy` (the synthetic tool call — the schema is
  registered as a fabricated tool whose arguments are parsed and validated
  through Pydantic's `TypeAdapter`), `ProviderStrategy` (native — using the
  provider's built-in structured output mode), `AutoStrategy` (chosen
  automatically based on the active model's support — the private helper
  `_supports_provider_strategy` checks the model profile, with explicit
  exceptions for models that can't do tool calling and native structured
  output at the same time). `[code]` —
  `langchain/agents/structured_output.py`, the `ToolStrategy`,
  `ProviderStrategy`, `AutoStrategy` classes; `langchain/agents/factory.py`,
  the provider-native structured output support check.
- **Retry is the explicit `handle_errors` parameter on `ToolStrategy`**,
  exactly the §Pattern contract: `True` (the default) catches every
  validation error with a default message template sent back to the model; a
  custom `str` message; `type[Exception]`/`tuple[type[Exception], ...]`
  catches only certain error classes; `Callable[[Exception], str]` is a
  custom function producing the error message from the exception; `False` =
  **no** retry, the exception propagates. This is **exactly** "the retry
  signal goes back to the model as actionable feedback" from §Pattern — the
  message `handle_errors` produces enters as `ToolMessage` content, not a
  blind retry. `[code]` — `langchain/agents/structured_output.py`, the
  `ToolStrategy` class, the `handle_errors` field/parameter.
- **A concrete warning**: if the registered `schema` is a raw JSON Schema
  `dict` (rather than a Pydantic model/`dataclass`/`TypedDict`), the tool
  call arguments are **returned as-is without validation** — `handle_errors`
  becomes *"effectively inert"* in that case, because there is no validation
  that can fail to trigger the retry. This is the same defect class this
  task's instructions name generally: a correct parameter name
  (`response_format=`, `handle_errors=True`) doesn't automatically mean the
  capability (validation + retry) is actually active — it depends on the
  shape of the schema registered. `[code]` — quoting the
  `ToolStrategy.handle_errors` docstring directly: *"Raw JSON schema dicts
  are not validated... `handle_errors` is effectively inert for dict
  schemas. To get validation and automatic retries, express the schema as a
  Pydantic model, dataclass, or TypedDict instead."*
- **There is no built-in retry ceiling in `handle_errors` itself** — that
  parameter governs *whether* and *how* an error is handled per attempt, not
  how many attempts are allowed; a structural attempt limit has to come from
  another mechanism already mapped in `guardrails.md` point 5
  (`ModelCallLimitMiddleware`) or `RubricMiddleware` (`max_iterations`, if
  structured output is combined with self-eval iteration) — not re-proposed
  here. `[inferred]` — concluded from the `ToolStrategy.__init__` signature
  cited above: that class has no retry-count parameter.
- **The result is stored in `state["structured_response"]`**, separate from
  `messages` — if `has_structured_output=True` but the model fails to
  produce a valid structured response (after retries are exhausted, or with
  `handle_errors=False` and an error not fatal to the whole run),
  `structured_response` is explicitly set to `None` rather than left holding
  a stale/undefined value — the defined way out §Pattern requires (a caller
  can check for `None` explicitly instead of assuming the field is always
  populated). `[code]` — `langchain/agents/factory.py`, the comments and
  logic around handling `has_structured_output`/`state["structured_response"]`.

## Sources

- `[code]` `langchain/agents/structured_output.py` — read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langchain/agents/structured_output.py`;
  the `ToolStrategy` class (`handle_errors`, the JSON Schema dict warning
  docstring), `ProviderStrategy`, `AutoStrategy`, `ResponseFormat` (a union
  type),
  `StructuredOutputError`/`MultipleStructuredOutputsError`/`StructuredOutputValidationError`.
- `[code]` `langchain/agents/factory.py` — read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langchain/agents/factory.py`;
  the `response_format` parameter of `create_agent(...)`, the
  provider-native structured output support check, the
  `state["structured_response"]` handling.
- `[code]` [`guardrails.md`](guardrails.md) §Pattern ("every guardrail must
  state three things"), point 4 (Output, `RubricMiddleware`), point 5 (Loop,
  retry/iteration limits) — the basis for the retry and defined-way-out
  framework this file applies to structured output; the guardrail mechanism
  detail isn't repeated.
- `[code]` [`tool-design.md`](tool-design.md) §Strict vs loose schemas — the
  basis for the tool argument validation analogy on the synthetic tool call
  route.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) — the
  `response_format` surface API on `create_deep_agent`, cited for parameter
  consistency with `langchain.agents.create_agent`.
