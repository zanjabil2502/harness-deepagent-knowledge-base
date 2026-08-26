# Policy as data

## Problem

`guardrails.md` §Policy must not live only in the prompt already settles the
**enforcement** argument: a rule in a system prompt is advisory, the model
can be persuaded to ignore it (most often through text in a tool result
posing as an instruction), so real enforcement has to live in code running
outside the model's control. This file doesn't repeat that argument — it
adds a different, standalone one that holds **even if the model complies
100% of the time**: how a rule is **represented** determines whether it can
be managed at all, regardless of whether the model obeys it.

Imagine a perfectly compliant model — never persuaded, never confused.
Prose-as-rules still has three structural ailments that are purely about
representation:

1. **Dilution** — the 47th rule in a system prompt weakens the salience of
   rules 1–46. Not because the model "forgets", but because no natural
   language mechanism guarantees an even weighting of attention across 47
   competing imperative sentences, and the prompt's author has no way to
   check which rule lost that competition before an incident proves it.
2. **Implicit precedence** — when two rules conflict ("always ask for
   confirmation before deleting" vs "if the user says 'just do it', stop
   asking"), the winner is usually whichever was written last in the
   prompt, not whichever was deliberately most important. No author
   designed that — it is a side effect of writing order, and it changes
   silently every time someone adds a new sentence in the wrong place.
3. **Invisible at runtime** — prose has no identity. There is no way to
   answer "which rules were active this turn", "which rule changed last
   week", or "show me every case where rule X should have applied" without
   manually re-reading paragraph after paragraph. A rule with no identity
   cannot be tested in CI, cannot be diffed in code review, and cannot have
   its precision/recall measured as `evaluation.md` §Guardrails as
   measurable objects demands — because there is no object to measure, only
   text.

Those three are why `guardrails.md` requires every guardrail to
"state three things: the policy, the enforcement point, the failure
mode" as explicit structure rather than free sentences — this file
generalises that structure into a single rule holding across all
policies, not just guardrails: **if a rule is code-verifiable, that
rule must not live in the prompt.** The prompt is reserved purely
for what needs natural-language judgement — tone, how an answer is
composed, decisions with no computable right/wrong definition.

## Pattern

### The distinguishing test: code-verifiable, or needing judgement?

The distinguishing question isn't "is this rule important" (every rule
someone writes feels important) but: **given a concrete input and output,
can a deterministic function decide pass/fail without calling a model?**
Which tool names a given role may call — verifiable (set membership). A
citation format required in any answer claiming facts — verifiable (a
schema/regex check). "Answer empathetically" — not verifiable; no function
scores empathy without the model itself becoming the checker (and once it is
model-as-judge, that is a tier 3-4 guardrail in `guardrails.md` §Tiered, no
longer "policy as data"). Verifiable rules move into data + middleware;
rules that aren't stay in the prompt — and are labelled explicitly as that
decision, rather than left mixed into the same block of prose.

### The data shape: one policy = one object with an identity

One verifiable policy is represented as one record, not one sentence inside
a paragraph. A concrete example — the policy "an answer containing factual
claims must include a citation", one of the `policies` list referenced by
the skill manifest in [`skill-composition.md`](skill-composition.md):

```yaml
id: require_citation
version: 3
applies_to: output
rule:
  type: schema_check
  condition: "claims_factual == true implies citations.length >= 1"
enforcement:
  point: output          # federated to point 4 (`guardrails.md` §Six points)
  mechanism: RubricMiddleware
  failure_mode: fail-open-with-flag   # exhaust max_iterations, send + flag "rubric not met"
owner: trust-and-safety
updated_at: 2026-08-20
```

What makes this different from a prose sentence isn't its content
(the content could be stated in one sentence too) — it is the
**structure**: `id` gives a referenceable identity (from a skill
manifest, from a golden test, from an eval dashboard), `version` +
`updated_at` give a diffable trail, `applies_to`/`enforcement.point`
answer "where is this enforced" directly without reading middleware
code, and `enforcement.failure_mode` forces the explicit decision
that `guardrails.md` §Second problem shows is often skipped until an
accidental `try/except` default decides it. Those last three fields
directly invert the three ailments in `## Problem`: `id` counters
invisibility (it can be queried), `version`/`updated_at` counter
implicit precedence (the order of change is recorded, not implied by
sentence position), and existing as a separate record (rather than
one of 47 sentences) counters dilution — the policy engine processes
each record independently; there is no "47th sentence" weakening the
others because there is no linear reading order the model traverses
to reach it.

### The enforcement point: middleware reads the data, it doesn't memorise it

Policy-as-data is useless if the middleware enforcing it repeats the
logic as separate hardcoded code per `id` — that merely moves
dilution from the prompt into the source (47 `if` blocks weakening
each other instead of 47 sentences). The correct pattern: a generic
middleware reads the policy record as configuration rather than
hardcoding its content. For `require_citation` above,
`enforcement.mechanism: RubricMiddleware` means that record **is**
the parameter injected into the rubric that `RubricMiddleware`
evaluates — changing the policy means changing a YAML line and
redeploying config, not changing middleware code. For a structurally
simpler policy — "the `delete_file` tool may only be called by the
`admin` role" — the data shape is a row in a per-role allowlist
table, and enforcement is `excluded_tools` (`HarnessProfile`) read
by `_ToolExclusionMiddleware` (`../systems/deepagents.md` §7, re-
cited in `guardrails.md` point 3) — the same middleware, with no
code change, enforces a different tool set for a different role
because the data differs, not because a different code branch does.

## Trade-offs

- **A generic policy engine (reading data, one middleware for many
  policies) vs hardcoded code per rule** — a generic engine gives
  identity/versioning/queryability free for each new policy (just add a
  record), but needs an up-front investment in an engine plus a schema
  expressive enough for the rule classes to come; with only two or three
  verifiable rules that won't grow, an `if` block directly in custom
  middleware is cheaper and needs no extra abstraction layer. The
  turning point isn't today's rule count but the rate of growth — if new
  policies arrive weekly, the engine pays for itself quickly; if it's
  static, it doesn't.
- **Policy granularity (many narrow records vs few broad ones)** — narrow
  policies (`require_citation`, `pii_redact` kept separate) recompose easily
  per skill (the `skill-composition.md` manifest can switch them on and off
  individually), but the record count grows and every interaction between
  policies (two policies touching the same output field) has to be thought
  through explicitly in the resolution layer. Broad policies (one
  "comprehensive output policy" record holding many sub-rules) are fewer to
  manage but revive dilution inside a single record — the problem this file
  avoids simply moves into a `rule` field that has become a paragraph again.
- **Static data (YAML in the repo, versioned with the code) vs data in a
  database changeable without a deploy** — YAML in the repo gives code
  review and rollback free through git (aligned with `guardrails.md`
  §Prompt & policy versioning in the spec's §12 gate checklist), but a
  policy change (e.g. raising a moderation threshold) needs a full
  deploy cycle. Policy in a DB allows fast changes without deploying
  (essential for an incident needing mitigation in minutes), but loses
  git's review/rollback trail unless rebuilt separately (its own audit
  table, its own approval flow) — an investment that is exactly the
  circular argument being avoided: if it isn't built explicitly, DB
  policy changes **also** become invisible at runtime.

## In deepagents

There is no built-in generic `deepagents` policy engine reading a YAML
schema like the example above — that is `[ours]`. Vanilla:
`deepagents`/`langchain` provide ready-made middleware whose parameters
are **already** structured data (not prose), but each middleware reads
its own data shape rather than one universal policy schema. We diverge
by proposing one schema (`id`/`applies_to`/`rule`/`enforcement`) mapping
onto different middlewares, because without that layer a team adding a
new policy must know each middleware's construction detail individually
instead of writing one record and referencing an existing
`enforcement.mechanism`.

What is **not** `[ours]` — already natively data-shaped in
`deepagents`/`langchain`, ready to be an `enforcement.mechanism` target:

| Verifiable policy class | Native data shape | Reading middleware |
|---|---|---|
| Which tools a given role may use | `excluded_tools` (a list of tool names) in `HarnessProfile` | `_ToolExclusionMiddleware` `[code]` cited from `../systems/deepagents.md` §7 |
| Which filesystem paths/operations are allowed/denied/need approval | `FilesystemPermission(operations=[...], paths=[...], mode=...)`, an ordered rule list, first match wins | `FilesystemMiddleware` `[code]` cited from `../systems/deepagents.md` §6 |
| Which PII types are blocked/redacted/masked/hashed, and on which side (input/output/tool result) | The `PIIMiddleware(pii_type=, strategy=, apply_to_*=)` parameters | `PIIMiddleware` `[code]` `langchain/agents/middleware/pii.py`, cited from `guardrails.md` |
| Tool-call/model-call limits per thread/run | `thread_limit=`/`run_limit=`/`exit_behavior=` | `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` `[code]` cited from `guardrails.md` |

These rows **already are** policy-as-data in this file's sense — those
middleware construction parameters are themselves data, not prose in a
system prompt. All the `[ours]` schema above adds is an
identity/version/lookup-by-id layer unifying these different rows under one
way of referencing them from a skill manifest (`skill-composition.md`),
because without it each policy still has to be referenced through a
different middleware parameter name rather than one consistent `id`.

For a policy with **no** ready-made middleware (e.g. `require_citation`
above, which needs evaluation against a rubric rather than a mere
membership/regex check) — `RubricMiddleware` (`../systems/deepagents.md`
§Built-in middleware, not a default) is the closest `enforcement.mechanism`
target: it accepts a rubric as application-injected state (data) and
iterates the answer against it until it passes or `max_iterations` is
reached. `[code]` cited from `../systems/deepagents.md` §Built-in middleware
(`deepagents/middleware/rubric.py`).

## Sources

- `[code]` [`guardrails.md`](guardrails.md) §Policy must not live only in
  the prompt, §Second problem (the failure mode nobody decided), the six
  enforcement points — the enforcement argument this file deliberately does
  **not** repeat, only references and generalises through the
  `enforcement`/`applies_to` fields.
- `[code]` [`evaluation.md`](evaluation.md) §Guardrails as measurable
  objects — the basis for the "without an identity, precision/recall cannot
  be measured" claim in the third ailment (§Problem).
- `[code]` [`skill-composition.md`](skill-composition.md) — the consumer of
  the policy `id` schema through the `policies: [+require_citation,
  +pii_redact]` manifest field in §8.5; written in the same task, not
  re-proposed here.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §6, §7,
  §Built-in middleware — `FilesystemPermission`,
  `HarnessProfile.excluded_tools`, `_ToolExclusionMiddleware`,
  `RubricMiddleware` — a tier-1 reference verified in Task 3, cited without
  re-reading the `deepagents` source in this task.
- `[code]` `langchain/agents/middleware/pii.py`, `tool_call_limit.py`,
  `model_call_limit.py` (langchain 1.3.16) — cited via `guardrails.md`, not
  re-read in this task.
