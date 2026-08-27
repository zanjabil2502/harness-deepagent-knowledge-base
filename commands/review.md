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

Then cover all four audit layers — a review that stops at structure passes a
project whose gate never fires and whose turn cannot be resumed:

4. **Layer 2 — HITL** (checks H-1..H-9): the gate criterion, granularity, a
   durable checkpointer behind it, the timeout policy, whether decisions are
   recorded as data, attended ↔ unattended, and **H-9, the one most often
   missed** — routes that bypass the gate entirely (PTC and subagents
   dispatched from code, `references/concepts/code-orchestration.md`).
5. **Layer 3 — flow** (F-1..F-9): trace one turn from admission to drain,
   naming the file that owns each hop. A hop nobody owns is where turns die.
6. **Layer 4 — best process / technical / implementation**, graded
   separately. Every "best" verdict must cite a KB section that states the
   practice; where none does, write **"no KB opinion"** rather than your
   preference.

Throughout, the six guardrail points (`references/concepts/guardrails.md`) and
the six anti-patterns (`references/deepagents/extension-points.md`) stay the
highest-yield structural checks.

A deviation from the KB **with a written reason** is not a finding; record it
under "Reasoned deviations". Every finding needs a concrete failure and a
`file:line` in the reviewed project. End with what you did **not** read —
an unverified area silently omitted reads as an area found clean.
