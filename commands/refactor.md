---
description: Apply harness fixes - move custom code onto official deepagents extension points
argument-hint: [a finding id from /review, or the area to fix]
---

Invoke the `agent-harness-kb` skill, then apply fixes for:
$ARGUMENTS

This is the step `/review` deliberately does not take. It **edits code**, so
it starts from findings rather than from suspicion.

1. If a review report exists, work from its findings, most severe first. If
   not, run the `/review` procedure first and show the findings **before**
   changing anything.
2. For each fix, read `references/deepagents/extension-points.md` §The hard
   rule and its six anti-patterns. The fix is almost always "delete the custom
   layer, pass the parameter/hook that already exists" - not "write a better
   custom layer".
3. Before touching middleware order, read
   `references/deepagents/middleware.md` §Stack order and §Dangerous
   interactions. Composition is an onion; a fix in the wrong slot silently
   changes what gets filtered.
4. For the language-level move, read `references/python-practice.md`
   §Refactoring moves: delete the layer rather than improve the wrapper,
   extract a `Protocol` rather than a base class, turn a stateless class into
   a function, pass a parameter rather than subclass, hoist per-turn work into
   the lifespan. Behaviour-preserving means the diff is boring: no renaming,
   reformatting, or reordering riding along.
5. Preserve behaviour that was a **reasoned deviation**. If the project stated
   a reason for diverging, do not "fix" it into conformance - raise it with
   the user instead.
6. After each fix state what the reviewed code did before, what it does now,
   and which KB section justifies the change. Verify by construction where you
   can: if it still imports and constructs, the change is at least
   type-correct and import-correct.

Do not bundle unrelated cleanups into a harness fix. One finding, one change.
