---
description: Audit an existing agent project against the KB and report findings — reports only, never edits
argument-hint: [path to the project, or leave empty for the current repo]
---

Invoke the `agent-harness-kb` skill, then run its **reviewing** mode over:
$ARGUMENTS

Follow `references/review-template.md` exactly — it is the output contract.

**This command reports. It does not edit.** Do not fix anything you find, not
even a one-line change that looks obvious. The fix is `/refactor`, and the
user asks for it separately.

The order matters — read the code before deciding what it should have done:

1. **Observe** every `create_deep_agent(...)`/`create_agent(...)` call site and
   record what is passed *and what is absent*.
2. **Derive the archetype as built** from the 6 axes in the code, not from the
   project's README. A gap between the claimed and the built archetype is
   usually the most valuable finding.
3. Compare against that archetype's demands
   (`references/deepagents/per-archetype.md`).
4. Audit the **six guardrail points** (`references/concepts/guardrails.md`) —
   an unstated failure mode is a finding even when today's behaviour is fine.
5. Audit the **six anti-patterns**
   (`references/deepagents/extension-points.md`) — the highest-yield checks.

A deviation from the KB **with a written reason** is not a finding; record it
under "Reasoned deviations". Every finding needs a concrete failure and a
`file:line` in the reviewed project. End with what you did **not** read —
an unverified area silently omitted reads as an area found clean.
