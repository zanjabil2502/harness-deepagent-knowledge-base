---
description: Design an eval harness for an agent - trajectory scoring, golden transcripts, guardrail precision/recall
argument-hint: [the agent or behaviour to evaluate]
---

Invoke the `agent-harness-kb` skill, then design the eval harness for:
$ARGUMENTS

This is **building an eval harness for an agent**, not auditing a project's
design - that is `/review`. Keep the two apart; they share the word
"evaluation" and nothing else.

Read `references/concepts/evaluation.md` and follow its three demands:

1. **Score the trajectory, not just the final answer.** An identical answer
   can come from a safe path or a dangerous one; only the trajectory tells
   them apart. Define the concrete metrics: tool-call accuracy, step
   efficiency, guardrail trigger accuracy.
2. **Golden transcripts + a replay harness.** Freeze external tool responses
   so the only thing varying run to run is the model's decisions. Tag each
   case with `{language, guardrail_ids}`.
3. **Guardrails are measurable objects.** Each guardrail needs known-positive
   and known-negative cases; both directions belong in the golden set, and
   precision/recall gets re-measured whenever a threshold or model changes.

If the product is multilingual, `references/concepts/multilingual.md` §The
multilingual eval obligation is not optional - a single-language golden set is
structurally blind to regressions in every other language.
