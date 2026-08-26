# Evaluation

## Problem

An eval that only scores "does the final answer match" (the classic QA
shape: one input, one output, one score) misses most of the failures
possible in an agent loop. An agent can arrive at a correct final answer by
the wrong route — calling a destructive tool that should have required
approval and then undoing it, reading files outside the permitted scope and
not using them in the answer, or spending 40 steps on a task that should
take 3 — and all of that **passes** an eval that only inspects the final
text, because the metric never looks at what happened in between.
Regressions of this kind (a worsening path, an unchanged final answer) stay
invisible until a real incident — an approval gate that "happens to" always
pass in eval because the eval never checks whether the gate was actually
invoked.

Second problem: golden tests written in only one language (usually the
language of the team writing them) make regressions in **other languages**
entirely invisible, not merely less visible. A prompt change, a model swap,
or a shifted guardrail threshold that improves behaviour in one language can
break another completely with no signal in CI — the team's first signal is a
user report, and the user who reports first is usually not the one speaking
the eval suite's majority language.

Third problem, federated directly from `guardrails.md`: a guardrail
installed without ever measuring its precision/recall is a vendor claim
unverified in your own product domain — this file is where that claim gets
verified.

## Pattern

### Trajectory-based eval, not just the final answer

The unit being scored is the full **trajectory** — the sequence of (model
call, tool call + arguments, tool result, guardrail decision) across one
run — not just the final answer string. `[ours]` — vanilla is classic NLP
eval: one (input, expected output) pair, scored by exact match or
similarity. We diverge because whether an agent's answer is right depends on
the route taken (which tools were called, whether the approval gate actually
fired, how many steps were used) — an identical final output can come from a
safe trajectory or a dangerous one, and only the trajectory tells them
apart.

Concrete metrics beyond "the answer is correct":

- **Tool-call accuracy** — which tools were called and with what arguments,
  against what the case required.
- **Step efficiency** — step count against the reasonable range for that
  task class (the "the loop keeps getting longer" regression shows up here
  before it becomes a real cost problem — see `cost-control.md`).
- **Guardrail trigger accuracy** — whether the approval gate/block actually
  fired on the cases that required it, and **didn't** fire on the cases that
  should pass (see the subsection below).

Two ways to score a trajectory, tiered like guardrails themselves
(`guardrails.md`): **deterministic assertions** (the exact expected tool call
sequence) are cheap and reproducible, suited to workflow-shaped tasks with
genuinely one route; **LLM-as-judge** scores the full trajectory against a
rubric, used for open-ended tasks with more than one correct route — and that
judge is itself guardrail-shaped (it has an FP/FN rate and needs periodic
calibration against a human-scored sample), not absolute truth.

### Golden transcripts + a replay harness

A **golden transcript** `[ours]` — a tuple of (initial input, expected
trajectory range, expected final state, tags `{language, guardrail_ids}`)
versioned alongside the prompt/tool code, not filed separately as a QA
document. Vanilla: a classic golden set stores only (input, expected
output) — we add the trajectory range and the tags because both are exactly
what the file's other two demands (trajectory and multilingual) need in
order to be queried/aggregated along those dimensions rather than read one
case at a time.

The **replay harness** re-runs the same input against the **current** agent
build (not replaying recorded output) and diffs the resulting trajectory
against the golden expectation. So results aren't flaky because the outside
world moved (a search API a tool calls returning different results between
runs), external tool responses are **recorded and frozen** when the golden
transcript is created — the only thing allowed to vary run to run is the
model's decisions, not the environment it acts on. This differs in purpose
from [`replay-and-forensics.md`](replay-and-forensics.md): replay there
reconstructs **one real production run** (a variable world, a single event)
for incident investigation; replay here re-runs the agent against a **frozen
world** to detect regressions before release. Golden transcript material can
come from real production transcripts that are "promoted" — the
`messages`/`tool_calls` tables (`persistence-schema.md`) are the raw
material, with tool results frozen at promotion time.

### Guardrails as measurable objects

Federated directly from `guardrails.md` §A guardrail has a false-positive
rate: each guardrail (of the six points) needs its own labelled dataset —
known-positive examples that **must** fire it, known-negative examples that
**must not** — with precision/recall/F1 measured every time the threshold,
classifier model, or guardrail version changes, not once at installation.
The same trajectory harness treats guardrail decisions as first-class
trajectory events, so one golden transcript can express both failure
directions at once: "guardrail X should **not** fire here" (catching
over-blocking, false positives) matters as much as "guardrail Y should fire
here" (catching under-blocking, false negatives) — both directions belong in
the golden set, not just the positive cases.

### The multilingual eval obligation

This is not a nice-to-have or something added after a production incident
proves the gap — for a product whose user base isn't monolingual, the golden
set **must** cover the real language mix production sees from the first
golden set onward, not just the language of the team writing the code. A
single-language golden test is structurally blind to regressions in other
languages — not less sensitive, entirely blind: a prompt/model/guardrail
threshold change that breaks Indonesian while English stays fine produces
**zero** signal in an English-only suite, because that suite never runs a
case that could fail that way.

The concrete reason this isn't speculation: model-based guardrails
(`guardrails.md` §Tiered) trained predominantly on English corpora perform
unevenly across languages — even Llama Guard, which explicitly claims
support for 8 languages `[docs]` (cited in `guardrails.md` §Sources), still
needs its precision/recall measured **per language**; "supports 8 languages"
is not evidence of uniform performance across all eight — which is exactly
why §Guardrails as measurable objects above and the multilingual obligation
here are the same demand, not two separate ones: a golden set without
language labels cannot answer "in which languages is this guardrail
accurate".

## Trade-offs

- **LLM-as-judge vs deterministic assertions for trajectory scoring** — a
  judge handles open-ended trajectories whose assertions are expensive to
  hand-write, at a cost: the judge itself becomes a guardrail-shaped problem
  (an FP/FN rate, periodic calibration, one model call per eval becoming the
  eval's own cost). Deterministic assertions are free and reproducible but
  only correct for tasks with genuinely one right route (the Workflow Agent
  archetype), and brittle for anything with more than one valid path.
- **Frozen tool responses vs live calls to external services during replay**
  — frozen means deterministic, cheap, fast, safe to run in CI on every PR;
  live catches real integration drift (an API contract changing) but is
  flaky, expensive, slow, and cannot separate "the agent regressed" from
  "the external service changed". Default: frozen as the primary CI gate,
  with a separate, less frequent live-integration suite for the drift class
  the frozen version can't catch.
- **Golden set language coverage vs cost** — each additional language
  multiplies the suite's size and needs a reviewer fluent in it to write and
  validate the examples — that cost is real, but not a reason to defer: the
  lazy failure is leaving a language "for later" and getting the signal only
  after the damage has happened in production.

## In deepagents

`RubricMiddleware` (cited from `guardrails.md`/`../systems/deepagents.md`
§Built-in middleware) is the *in-band* runtime analogue — it iterates an
answer against a rubric during a run in progress — but is **not** the eval
harness itself: it has no notion of a golden dataset, replay, or
precision/recall aggregation across many recorded cases, and only operates
on the currently active turn. `[code]` — cited from
`../systems/deepagents.md` §Built-in middleware
(`deepagents/middleware/rubric.py`). The eval harness is therefore a system
**outside** `deepagents`: something that repeatedly invokes the same
compiled graph (`create_deep_agent(...)`, exactly the graph serving real
requests) with fixed initial state/messages and a controlled environment
(mocked backends/tools) — not something `deepagents` provides.

One detail that must be accounted for when diffing replay trajectories:
`SummarizationMiddleware` compacts old messages based on a threshold
computed automatically from the model profile
(`compute_summarization_defaults`, based on `max_input_tokens`) — swapping
the model under test (e.g. evaluating a new model) can change **when**
compaction happens for identical input, even when the answer's content
doesn't change. `[code]` — cited from `../systems/deepagents.md` §2
Context. A golden trajectory diff must therefore tolerate a different
compaction shape (the number/position of summary messages) rather than
byte-diffing raw messages — or the replay harness pins the model profile
whose thresholds are in use, depending on the case under test (a prompt
regression and a model-swap regression are two different evals).

## Sources

- `[code]` [`guardrails.md`](guardrails.md) — §A guardrail has a
  false-positive rate (federated directly into this file), the six-point
  table, and the Llama Guard language-support claim re-cited in §The
  multilingual eval obligation.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — the
  `messages`/`tool_calls` tables, the raw material for golden transcripts
  promoted from real production transcripts.
- `[code]` [`replay-and-forensics.md`](replay-and-forensics.md) —
  referenced to distinguish replay-for-regression (this file) from
  replay-for-forensics (that one), written in the same task, not
  re-proposed.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §Built-in
  middleware (`RubricMiddleware`), §2 Context (`SummarizationMiddleware`,
  `compute_summarization_defaults`) — a tier-1 reference verified in Task 3,
  cited without re-reading the `deepagents` source in this task.
