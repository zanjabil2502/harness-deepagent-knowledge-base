# Harness Review template

The output contract of **reviewing** mode. Copy this file per review and fill
it in. Where [`blueprint-template.md`](blueprint-template.md) is the contract
for designing a harness that doesn't exist yet, this is the contract for
judging one that already does.

**This mode reports; it does not edit.** No finding here is applied to the
reviewed codebase. Fixing is a separate step the user asks for explicitly,
because a review that silently rewrites code destroys the one thing a review
is for — an independent reading of what the code actually does.

## The procedure: the diagnostic run backwards

Building goes description → archetype → decisions → code. Reviewing goes the
other way, and the order matters: **read what the code does before deciding
what it should have done**, or the review turns into a search for evidence
supporting an archetype guessed up front.

1. **Observe.** Find every `create_deep_agent(...)`/`create_agent(...)` call
   site and record, per call, what is actually passed: `model`, `tools`,
   `middleware`, `subagents`, `backend`, `interrupt_on`, `permissions`,
   `checkpointer`, `store`, `response_format`. Record absences too — a
   parameter not passed is a decision that was made by default.
2. **Derive the archetype as built.** Fill in the 6 axes from the code, not
   from the README's claims. Blast radius comes from the backend and the tool
   surface; horizon from the checkpointer and the loop's caller; human control
   from `interrupt_on`/`permissions`. A gap between the archetype the project
   *claims* and the one its code *builds* is itself a finding, usually the
   most valuable one.
3. **Compare against that archetype's constraints** —
   [`archetypes/NN-*.md`](archetypes/) §Harness consequences and §Common
   pitfalls, then [`deepagents/per-archetype.md`](deepagents/per-archetype.md)
   for the construction that archetype demands.
4. **Audit the six guardrail points** — [`concepts/guardrails.md`](concepts/guardrails.md).
   For each point: is there a policy, an enforcement point, and a **stated**
   failure mode? An unstated failure mode is a finding even when the code
   happens to behave correctly today.
5. **Audit against the six anti-patterns** —
   [`deepagents/extension-points.md`](deepagents/extension-points.md)
   §Anti-patterns. These are the highest-yield checks in a `deepagents`
   codebase because each one is custom code sitting where an official hook
   already exists.
6. **Report** using the skeleton below.

## What counts as a finding

A divergence from this KB is **not** automatically a finding. The KB audits
itself the same way in [`deepagents/conformance.md`](deepagents/conformance.md):
a deviation with a written reason is a legitimate engineering decision, and
what is defective is a deviation nobody decided.

| Situation | Finding? |
|---|---|
| Custom code at a layer that has an official hook | **Yes** — extension-points §Anti-patterns |
| A guardrail point with no stated failure mode | **Yes** — the default becomes an accident |
| A deviation from the KB **with** a written reason | No — record it as "deviation, reasoned" |
| A deviation with no reason anywhere in the repo | **Yes** — undecided, not decided |
| A pattern the KB has no opinion on | No — say so plainly, don't invent one |
| Style, naming, formatting | No — out of scope; this is a harness review |

## Severity

Severity is about **what breaks and how visibly**, not about how much code the
fix touches:

| Level | Meaning | Example |
|---|---|---|
| **critical** | Silent data exposure across users, or an irreversible action with no gate | `StoreBackend` with no `namespace`; `LocalShellBackend` with no approval gate |
| **high** | A guardrail believed to exist that doesn't fire | `interrupt_on` set with no `checkpointer`; PTC allowlist bypassing tool exclusion |
| **medium** | Correct today, brittle by construction | Custom `while` loop bounding steps instead of the limit middleware |
| **low** | Works and is decided, but diverges from idiomatic construction | Subclassing built-in middleware where a parameter exists |

A finding whose consequence you cannot state concretely is not yet a finding —
either work out the failure it produces, or drop it.

## Report skeleton

### Summary

- **Project:**
- **Reviewed at:** commit/date
- **Read:** which files/paths were actually opened (and which were not)
- **Archetype claimed:**
- **Archetype as built:**
- **Verdict in one sentence:**

### The 6 axes as built

| Axis | Value in the code | Evidence (`file:line`) |
|---|---|---|
| Blast radius | | |
| Artifact | | |
| Horizon | | |
| Human control | | |
| Domain surface | | |
| Interface | | |

### The 7 harness axes vs the archetype's demands

| # | Axis | What the code does | What the archetype demands | Verdict |
|---|---|---|---|---|
| 1 | Loop shape | | | ok / finding / reasoned deviation |
| 2 | Context | | | |
| 3 | Tool surface | | | |
| 4 | Delegation | | | |
| 5 | State & resume | | | |
| 6 | Safety gate | | | |
| 7 | Capability routing & policy | | | |

### The six guardrail points

| # | Point | Policy | Enforcement point | Failure mode stated? |
|---|---|---|---|---|
| 1 | Input | | | |
| 2 | Retrieval/context | | | |
| 3 | Tool/action | | | |
| 4 | Output | | | |
| 5 | Loop | | | |
| 6 | System | | | |

### Findings

One block per finding, most severe first:

```
F-01  [critical|high|medium|low]  <one-line claim>
Where:      <path/to/file.py:NN>  (in the reviewed project)
Evidence:   <what the code does, quoted or summarised>
Why:        <the concrete failure this produces>
KB says:    <references/... file + section>
Direction:  <where the fix would go — NOT applied>
```

### Reasoned deviations (not findings)

Divergences from the KB that the project decided deliberately and documented.
Listing them protects the next reviewer from re-raising them.

| Divergence | Their stated reason | Where it is written |
|---|---|---|
| | | |

### Out of scope / not verified

State plainly what this review did not cover — files not read, behaviour not
executed, claims taken from the project's own documentation rather than its
source. An unverified area silently omitted reads as an area found clean.

## Sources

- [`blueprint-template.md`](blueprint-template.md) — the 7 axes, the 6
  guardrail points, and the 6 discriminating axes reused here as audit rows.
- [`deepagents/conformance.md`](deepagents/conformance.md) — the audit shape
  this template imitates: a pattern table plus a divergence log where every
  deviation names its reason.
- [`deepagents/extension-points.md`](deepagents/extension-points.md)
  §Anti-patterns — the six highest-yield checks for a `deepagents` codebase.
- [`concepts/guardrails.md`](concepts/guardrails.md) — the six enforcement
  points and the rule that each states policy + point + failure mode.
- [`deepagents/per-archetype.md`](deepagents/per-archetype.md) — the correct
  construction per archetype, used as the comparison baseline.
