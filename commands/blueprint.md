---
description: Turn a project description into an archetype classification and a filled Harness Blueprint
argument-hint: [project description — goals, output, constraints, in any shape]
---

Invoke the `agent-harness-kb` skill, then run its **building** mode for:
$ARGUMENTS

Follow the diagnostic procedure in `SKILL.md` in order:

1. Fill the **6 discriminating axes** from the description. Ask about the axes
   the description leaves genuinely open — blast radius and human control are
   the two that most often go unstated and most change the outcome.
2. Classify the **archetype** (hybrids are normal, record both). Read that
   archetype's `## Harness consequences` and `## Common pitfalls`.
3. Cross-check the relevant `references/concepts/` files and
   `references/systems/INDEX.md`.
4. Copy `references/blueprint-template.md` and fill it: the 7 axes, the 5
   state layers, the 6 guardrail points, deployment, isolation & scoping, the
   `deepagents` config. Every guardrail row needs policy + enforcement point +
   **failure mode** — a blank failure mode is not finished.
5. Then read `references/deepagents/per-archetype.md` for that archetype's
   correct construction, and `extension-points.md` before writing any custom
   code.

To go deeper on one axis afterwards, stay in this mode — re-read that axis's
concept file and refine the blueprint row rather than starting a new document.
The scaffold (`references/scaffolds/_base.md` + the archetype delta) comes
after the blueprint is filled, never before.
