# Harness Review template

The output contract of **reviewing** mode. Copy this file per review and fill
it in. Where [`blueprint-template.md`](blueprint-template.md) is the contract
for designing a harness that doesn't exist yet, this is the contract for
judging one that already does.

**This mode reports; it does not edit.** No finding here is applied to the
reviewed codebase. Fixing is a separate step the user asks for explicitly,
because a review that silently rewrites code destroys the one thing a review
is for - an independent reading of what the code actually does.

## The procedure: the diagnostic run backwards

Building goes description → archetype → decisions → code. Reviewing goes the
other way, and the order matters: **read what the code does before deciding
what it should have done**, or the review turns into a search for evidence
supporting an archetype guessed up front.

1. **Observe.** Find every `create_deep_agent(...)`/`create_agent(...)` call
   site and record, per call, what is actually passed: `model`, `tools`,
   `middleware`, `subagents`, `backend`, `interrupt_on`, `permissions`,
   `checkpointer`, `store`, `response_format`. Record absences too - a
   parameter not passed is a decision that was made by default.
2. **Derive the archetype as built.** Fill in the 6 axes from the code, not
   from the README's claims. Blast radius comes from the backend and the tool
   surface; horizon from the checkpointer and the loop's caller; human control
   from `interrupt_on`/`permissions`. A gap between the archetype the project
   *claims* and the one its code *builds* is itself a finding, usually the
   most valuable one.
3. **Compare against that archetype's constraints** -
   [`archetypes/NN-*.md`](archetypes/) §Harness consequences and §Common
   pitfalls, then [`deepagents/per-archetype.md`](deepagents/per-archetype.md)
   for the construction that archetype demands.
4. **Audit the six guardrail points** - [`concepts/guardrails.md`](concepts/guardrails.md).
   For each point: is there a policy, an enforcement point, and a **stated**
   failure mode? An unstated failure mode is a finding even when the code
   happens to behave correctly today.
5. **Audit against the six anti-patterns** -
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
| Custom code at a layer that has an official hook | **Yes** - extension-points §Anti-patterns |
| A guardrail point with no stated failure mode | **Yes** - the default becomes an accident |
| A deviation from the KB **with** a written reason | No - record it as "deviation, reasoned" |
| A deviation with no reason anywhere in the repo | **Yes** - undecided, not decided |
| A pattern the KB has no opinion on | No - say so plainly, don't invent one |
| Style, naming, formatting | No - out of scope; this is a harness review |

## Severity

Severity is about **what breaks and how visibly**, not about how much code the
fix touches:

| Level | Meaning | Example |
|---|---|---|
| **critical** | Silent data exposure across users, or an irreversible action with no gate | `StoreBackend` with no `namespace`; `LocalShellBackend` with no approval gate |
| **high** | A guardrail believed to exist that doesn't fire | `interrupt_on` set with no `checkpointer`; PTC allowlist bypassing tool exclusion |
| **medium** | Correct today, brittle by construction | Custom `while` loop bounding steps instead of the limit middleware |
| **low** | Works and is decided, but diverges from idiomatic construction | Subclassing built-in middleware where a parameter exists |

A finding whose consequence you cannot state concretely is not yet a finding -
either work out the failure it produces, or drop it.

## Depth: the four audit layers

A review that only checks structure passes a project whose gate never fires
and whose turn cannot be resumed. Cover all four, in this order - each later
layer only means something once the earlier one is established.

| Layer | Question | Primary sources |
|---|---|---|
| 1. Structure | Which harness decisions were made, and do they match the archetype? | `archetypes/`, `deepagents/per-archetype.md` |
| 2. HITL | Where does a human actually stop this, and is that decision recorded? | `concepts/human-in-the-loop.md`, `concepts/guardrails.md` point 3 |
| 3. Flow | Follow one turn end to end - does it survive a drop, a retry, a deploy? | `deepagents/lifecycle.md`, `concepts/streaming-protocol.md`, `concepts/queueing-and-backpressure.md`, `concepts/session-state.md` |
| 4. Best practice | Process, technical, implementation - each graded against a stated KB section | `deepagents/best-practices.md`, `deepagents/extension-points.md`, `blueprint-template.md` |

### Layer 2 - the HITL audit

The gate is the part most often present in configuration and absent in
behaviour. Check the mechanism, then check whether anything is written down
when a human decides.

| # | Check | A finding when |
|---|---|---|
| H-1 | Is the gate criterion derived from **reversibility × blast radius**, or is it an ad-hoc list of tool names? | A name list - it silently fails for every tool added later |
| H-2 | Granularity: does the gate distinguish operations *within* one tool (`execute ls` vs a recursive delete)? | One flag covers a broad tool, so safe calls are gated and dangerous ones are not distinguished |
| H-3 | Is `interrupt_on` paired with a **durable** checkpointer (not `MemorySaver`) when approval is asynchronous? | A gate exists with nowhere to store the pause point - it cannot resume |
| H-4 | Is the approval **timeout policy** stated, and does it default to *deny*? | Unstated - an irreversible action proceeds because a timer expired |
| H-5 | Are decisions recorded as data: **who / when / what was decided / the pre-edit arguments**? | A `'success'` after a gate is indistinguishable from a `'success'` with no gate |
| H-6 | Attended ↔ unattended: is the approver swapped per session mode, and is there reconciliation on resume? | Scheduled runs prompt into a void, or a returning operator never learns what was approved for them |
| H-7 | Are pauses **structured approvals over a tool call**, not free-form dialogue? | A free-form `interrupt()` cannot be rendered by an editor protocol client - the pause becomes a deadlock |
| H-8 | Does `allowed_decisions` include `"edit"` without an `args_schema`? | Humans edit arguments with no shape guidance |
| H-9 | Is a gated tool reachable through a path that bypasses the gate - code orchestration (PTC), a subagent dispatched from code, or an unlisted tool? | The policy is in the config and its enforcement is never invoked |

H-9 is the check most often missed: `concepts/code-orchestration.md` documents
two routes that bypass `interrupt_on` entirely. A gate audited only at the
tool-call layer will read as green while both routes are wide open.

### Layer 3 - the flow audit

Trace **one turn** from arrival to completion, naming the file that handles
each hop. A hop nobody owns is where turns are lost.

| # | Hop | A finding when |
|---|---|---|
| F-1 | **Admission** - is there an idempotency key per turn, unique per user? | A network retry creates a second turn with duplicate side effects |
| F-2 | **Loop stop** - who decides it stops, and is "finished" distinguishable from "budget exhausted"? | One boolean covers both, so a truncated answer ships as a final one |
| F-3 | **Step bound** - is there a real limit, or only the inherited `recursion_limit=9999`? | No practical ceiling; cost is bounded only by 9999 steps |
| F-4 | **Tool results** - are large results evicted rather than left to grow the context? | Context growth is handled only by compaction, paying the prefix-cache cost every time |
| F-5 | **Streaming** - is the event schema stable, and are events durable per unit (not per token)? | A dropped connection loses the turn's visible progress permanently |
| F-6 | **Reattach** - can a reconnecting client learn a turn is still running, and that a gate is waiting? | A waiting approval disappears from view; the turn stalls with nobody knowing |
| F-7 | **Resume** - is `thread_id` derived deliberately, and does the checkpointer survive a restart? | Retries fork new runs, or resume is impossible after a deploy |
| F-8 | **Drain** - does a rolling deploy wait for in-flight turns, or is resume the only safety net? | Turns die mid-flight on every deploy, silently |
| F-9 | **Cancellation** - can a running turn be stopped, and are background tasks stopped with it? | A kill switch exists for the loop but orphans its async subagents |

### Layer 4 - three grades of "best"

Grade each separately; they fail independently. A technically idiomatic
codebase built with no blueprint still has a process failure, and vice versa.

| Grade | What it asks | Graded against |
|---|---|---|
| **Best process** | Were the harness decisions made *before* the code? Does every guardrail state policy + point + failure mode? Is there an eval harness, prompt/policy versioning, and a release gate? | `blueprint-template.md`, `concepts/evaluation.md`, `concepts/guardrails.md` |
| **Best technical** | Is custom code sitting where an official hook exists? Is middleware order correct given onion composition? Do the documentation-stated practices hold? Is the Python itself sound: boundaries typed, the event loop never blocked, expensive resources opened once, stdlib before dependency? | `deepagents/extension-points.md`, `deepagents/middleware.md`, `deepagents/best-practices.md`, `python-practice.md` |
| **Best implementation** | Is the construction the one this archetype demands? Are API signatures read from source rather than remembered? Are the parameters real? | `deepagents/per-archetype.md`, `deepagents/api-reference.md`, `deepagents/graph/` |

**The rule that keeps this from becoming opinion:** a "best" verdict must cite
a KB section that *states* the practice. Where no section states it, the
correct verdict is **"the KB has no opinion here"** - recorded as such, not
filled with the reviewer's preference. It mirrors the discipline the KB's own
source labels enforce: a claim without a stated basis is not a claim, it is a
habit.

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

### HITL (layer 2)

| # | Check | Verdict | Evidence (`file:line`) |
|---|---|---|---|
| H-1 | Criterion: reversibility × blast radius | | |
| H-2 | Per-operation granularity | | |
| H-3 | Durable checkpointer behind the gate | | |
| H-4 | Timeout policy, default-deny | | |
| H-5 | Decisions recorded as data | | |
| H-6 | Attended ↔ unattended + reconciliation | | |
| H-7 | Structured approval, not free-form | | |
| H-8 | `allowed_decisions` + `args_schema` | | |
| H-9 | Bypass routes (PTC / code-dispatched subagents) | | |

### Flow (layer 3)

| # | Hop | Who handles it (`file:line`) | Verdict |
|---|---|---|---|
| F-1 | Admission + idempotency | | |
| F-2 | Loop stop vs budget stop | | |
| F-3 | Step bound | | |
| F-4 | Tool result eviction | | |
| F-5 | Streaming schema + durability | | |
| F-6 | Reattach (incl. a waiting gate) | | |
| F-7 | Resume + `thread_id` derivation | | |
| F-8 | Drain on deploy | | |
| F-9 | Cancellation + background tasks | | |

### Best practice (layer 4)

| Grade | Verdict | Basis cited | Notes |
|---|---|---|---|
| Best process | | | |
| Best technical | | | |
| Best implementation | | | |

Where the KB states no practice, write **"no KB opinion"** rather than a
preference.

### Findings

One block per finding, most severe first:

```
F-01  [critical|high|medium|low]  <one-line claim>
Where:      <path/to/file.py:NN>  (in the reviewed project)
Evidence:   <what the code does, quoted or summarised>
Why:        <the concrete failure this produces>
KB says:    <references/... file + section>
Direction:  <where the fix would go - NOT applied>
```

### Reasoned deviations (not findings)

Divergences from the KB that the project decided deliberately and documented.
Listing them protects the next reviewer from re-raising them.

| Divergence | Their stated reason | Where it is written |
|---|---|---|
| | | |

### Out of scope / not verified

State plainly what this review did not cover - files not read, behaviour not
executed, claims taken from the project's own documentation rather than its
source. An unverified area silently omitted reads as an area found clean.

## Sources

- [`blueprint-template.md`](blueprint-template.md) - the 7 axes, the 6
  guardrail points, and the 6 discriminating axes reused here as audit rows.
- [`deepagents/conformance.md`](deepagents/conformance.md) - the audit shape
  this template imitates: a pattern table plus a divergence log where every
  deviation names its reason.
- [`deepagents/extension-points.md`](deepagents/extension-points.md)
  §Anti-patterns - the six highest-yield checks for a `deepagents` codebase.
- [`concepts/guardrails.md`](concepts/guardrails.md) - the six enforcement
  points and the rule that each states policy + point + failure mode.
- [`deepagents/per-archetype.md`](deepagents/per-archetype.md) - the correct
  construction per archetype, used as the comparison baseline.
