# Skill composition

## Problem

A new skill resembling an old one is usually born through copy-paste:
duplicate the whole `SKILL.md`, change a few lines, deploy. That is a DRY
violation that rots silently — once the base skill (`retrieval`, say) is
improved (a new tool added, the PII policy tightened), none of its
copy-pasted descendants receive that improvement unless someone remembers to
repeat the same change in every copy by hand. The more vertical skills there
are (a research skill for the legal domain, the medical domain, the
financial domain — all variants of one generic research skill), the larger
the delta to be synchronised by hand, and the more often that delta is
forgotten.

The second problem, independent of the first: skill routing triggered by
natural language phrases ("if the user says 'legal research', use this
skill") is silently locked to one language. A genuinely multilingual system
(this project's assumption, see spec §8.6) has users writing the same
request dozens of different ways across languages — "riset hukum", "legal
research", "nghubungke masalah hukum" — and if skill matching depends on
specific phrases (or even literal translations of specific phrases), that
skill silently fails to trigger for every untested language, with no visible
error — the user simply gets a generic answer instead of the specialised
skill that should have run. This isn't a bug that appears in logs; it is a
bug invisible until someone in the under-covered language reports it.

## Pattern

### Base → derived through a declarative manifest, not copy-paste

A derived skill is written as a **delta** from the base skill, expressed
through a declarative manifest — composition, not text duplication. The
normative manifest from this project's spec §8.5 `[ours]`:

```yaml
id: legal-research
extends: retrieval
intents: [research.legal]        # a neutral code, not a language phrase
locales: [id, en]
tools:    [+citation_check, -web_write]
policies: [+require_citation, +pii_redact]
precedence: derived_wins
```

`extends: retrieval` means this manifest **doesn't** redefine the whole
`retrieval` skill — it inherits its base tools/policies/instructions and
then states the delta: `tools: [+citation_check, -web_write]` adds one tool
and removes another from the base set; `policies: [+require_citation,
+pii_redact]` switches on two extra policies (the data shape of a policy
itself is in [`policy-as-data.md`](policy-as-data.md), not repeated here).
When `retrieval` is improved in future (e.g. a new tool added to its base
set), `legal-research` and every other `retrieval` descendant inherit that
improvement untouched — because they store a delta, not a full copy.

### Resolution = explicit composition, not concatenated paragraphs

The fundamental difference from a skill built as one large block of prose
(base + derived merged into one long system prompt): manifest resolution is
a set operation traceable step by step, not the model reading paragraphs
top to bottom and concluding for itself which one wins.

The concrete resolution order:

1. Load the base manifest (`retrieval`) and the derived manifest
   (`legal-research`).
2. Merge `tools`: start from the base tool set, add every `+`-prefixed
   entry, remove every `-`-prefixed entry. The result is one explicit set —
   printable, diffable across versions.
3. Merge `policies` with the same operation.
4. For **conflicting** fields (base and derived both declaring different
   values for the same field, rather than merely adding/removing set items)
   — the winner is determined by `precedence`, read from the manifest
   itself, not from who was "written last" in some merged text.
   `precedence: derived_wins` means the derived value beats the base value
   on conflicting fields; `base_wins` is the reverse.

The `precedence` field may deliberately differ per field class — one global
value for the whole manifest isn't required. Concretely: `legal-research`
may set `precedence: derived_wins` for `tools` (a derived skill knows its
domain better regarding which tools are relevant) while still honouring
`base_wins` specifically for security-class policies (`pii_redact` must not
be removable by any derived skill, even one declaring `policies:
[-pii_redact]`) — that decision must itself be explicit at the policy
definition level (`policy-as-data.md` marks such a policy non-removable),
not silently assumed from the manifest's global `precedence`. The point
isn't which value is correct, but that the decision **exists as a readable
field** rather than being implied by writing order — precisely the inverse
of the "implicit precedence" ailment named in
[`policy-as-data.md`](policy-as-data.md) §Problem.

### `intents` uses neutral codes, not language phrases

`intents: [research.legal]` isn't an arbitrary naming style — it is where
the intent/expression separation (spec §8.6) `[ours]` enters the manifest
schema. The flow: user input (in any language) is classified first into a
neutral intent code, and **only then** is that code used to find a matching
skill through the manifest's `intents` field — skill lookup from that point
on is language-free, purely string matching on a code (`research.legal` ==
`research.legal`, identically for a user writing Indonesian, English, or
anything else triggering the same intent classification).

Vanilla, and what we diverge from: if `intents` holds language phrases ("the
matching intent: 'riset hukum'/'legal research'") or — worse — if skill
routing is left relying purely on the model's judgement reading the
`description` (`deepagents`' native `SkillsMiddleware` mechanism, see `## In
deepagents` below), then that skill's language coverage is bound to how
completely the manifest's author wrote phrase variants in each supported
language — and the team writing the manifest, as `evaluation.md` §The
multilingual eval obligation notes, almost always writes in one language
(their own) first. A neutral code breaks that dependency: adding a new
language means extending the intent classifier (one place, outside the
manifest schema) so it can map that language's phrases to codes that
**already exist** — the skill manifests themselves are never touched, and
never need rewriting per language. The `locales: [id, en]` field in the
manifest is not a routing mechanism — it is metadata for another layer (e.g.
output/message template localisation per spec §8.6), separate from `intents`
which determines *whether* this skill is selected at all.

## Trade-offs

- **A declarative manifest (delta + explicit resolution) vs a fully
  standalone skill (no `extends`)** — a manifest avoids duplication and
  inherits improvements automatically, but adds a layer of indirection:
  understanding `legal-research`'s final behaviour means reading two files
  (base + derived) and running the resolution mentally or actually, rather
  than reading one complete `SKILL.md`. A standalone skill is easier to read
  alone but returns to the duplication problem as soon as a second similar
  skill exists.
- **Neutral intent codes vs natural language descriptions for routing** —
  neutral codes decouple language coverage from skill count (one extended
  intent classifier covers every skill at once), at a cost: an intent
  classifier maintained separately (§8.6) and an agreed code taxonomy (who
  may add a new `research.legal`, and when it should instead be a sub-code
  of an existing one). Natural language descriptions (the native
  `SkillsMiddleware` mechanism) need no separate taxonomy — the model reads
  the description and decides — but inherit exactly the language coverage
  gap named above, and their routing decisions can't be tested
  deterministically (two model calls can pick different skills for
  identical descriptions).
- **Uniform `precedence` per manifest vs per field** — uniform is simpler to
  reason about (one rule, one place) but forces a compromise: if a derived
  skill needs to win on most fields but lose on one security field, a global
  `precedence` can't express that without an extra mechanism (the
  non-removable policy noted above). Per-field is more expressive but adds
  surface to inspect during manifest review — a wrongly set per-field
  precedence is harder to spot at a glance than one global `precedence:
  derived_wins` line.

## In deepagents

`deepagents`' `SkillsMiddleware` implements Anthropic's Agent Skills pattern
with *progressive disclosure*: metadata (`name`/`description` from
`SKILL.md`'s YAML frontmatter) is loaded into the system prompt up front,
and the full content is loaded when the model selects it. `[code]` cited
from `../systems/deepagents.md` §7. The frontmatter the `SkillsMiddleware`
parser actually reads is only `name`, `description`, `allowed-tools`,
`compatibility`, `metadata` (a free `dict[str,str]`, not schema-validated
further), and `license` — there is **no** `extends`, `precedence`,
`intents`, `locales`, or `tools: [+/-]`/`policies: [+/-]` field this
middleware understands. `[code]` `deepagents/middleware/skills.py` (the
frontmatter parsing function, the `SkillMetadata` class), the same research
venv as `../systems/deepagents.md` (`deepagents==0.7.8`). So the whole §8.5
manifest schema — `extends`, `precedence`, `intents`, the `tools`/`policies`
deltas — is `[ours]`, a resolution layer running **before** `deepagents` is
called, not something `SkillsMiddleware` reads itself.

The mapping is concrete: the manifest resolution's output (the final `tools`
set, the final `policies` set already mapped to middleware through
[`policy-as-data.md`](policy-as-data.md)) becomes the **input** to
`create_deep_agent`/`SubAgent` construction — the final tool set goes into
the `tools=` parameter (or `excluded_tools` in `HarnessProfile` for removed
ones), the final policy set into `middleware=[...]` per each policy's
`enforcement.mechanism`, and the resolved `SKILL.md` content (base + the
derived narrative delta) becomes the actual skill content installed through
`skills=[...]` into `SkillsMiddleware`. `[code]` `deepagents/graph.py` (the
`tools`, `middleware`, `skills` parameters of `create_deep_agent`, cited
from `../systems/deepagents.md` §Surface API).

For same-named skills from different sources (e.g. a `user` skill
overriding a `base` skill of the same name), `SkillsMiddleware` already has
its own ordering rule — the source loaded last wins (base→user→project→team
layering, determined by the `skills=[...]` order the application supplies).
`[code]` cited from `../systems/deepagents.md` §7. This is **not** the
manifest `extends`/`precedence` mechanism above — it is a total override
based on list order (the second skill replaces the first entirely, not a
delta composition), so an application wanting genuine base→derived
composition (rather than total override) must have finished the `[ours]`
manifest resolution **before** its result enters `skills=[...]` —
`SkillsMiddleware` itself knows nothing about `extends`.

Skill routing in `deepagents` is entirely **prose + model judgement** — the
model picks a skill from the `description` visible in the system prompt;
there is no built-in intent classifier. `[inferred]` cited from
`../systems/deepagents.md` §7 (concluded from the absence of any classifier
module in the source read in Task 3). The manifest's `intents` field
`[ours]` is therefore a lookup key for an **additional** routing layer
outside `deepagents` — an intent classifier (§8.6) the application must
build itself, mapping raw input to a neutral code, with that code then
selecting which manifest's resolution is passed to `skills=[...]`. Without
that extra layer, `deepagents` still works (the model still reads
`description`), but multilingual coverage again depends on how completely
`description` is written in each language — exactly the problem neutral
`intents` codes are designed to avoid.

## Sources

- `[ours]` This project's internal design spec §8.5 — a working document
  **not shipped in the repo**, so this is a provenance note rather than a
  link — the normative manifest
  (`id`/`extends`/`intents`/`locales`/`tools`/`policies`/`precedence`),
  quoted verbatim in `## Pattern`. Vanilla: there is no industry standard
  for a base→derived skill manifest schema that we know of from source —
  this is a project design decision, not a pattern copied from
  `deepagents`/Anthropic Agent Skills (see `## In deepagents` for what is
  genuinely native).
- `[ours]` This project's spec §8.6 — the intent/expression separation
  (`input → neutral intent code → policy/skill lookup → execution → render
  in the user's locale`), the basis for the neutral `intents` code argument
  in `## Pattern`.
- `[code]` [`policy-as-data.md`](policy-as-data.md) — the data shape of one
  policy (`id`/`applies_to`/`rule`/`enforcement`) referenced by the
  manifest's `policies` field; written in the same task, not re-proposed
  here.
- `[code]` [`evaluation.md`](evaluation.md) §The multilingual eval
  obligation — the basis for the "teams write in one language first" claim
  in `## Pattern`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §7
  (`SkillsMiddleware`, source layering, the absence of an intent
  classifier), §Surface API (`create_deep_agent(tools=, middleware=,
  skills=)`) — a tier-1 reference verified in Task 3.
- `[code]` `deepagents/middleware/skills.py` (package `deepagents==0.7.8`,
  read from `references/recipes/.venv/lib/python3.13/site-packages/`, the
  same venv used by `../systems/deepagents.md`) — the full list of parsed
  frontmatter fields (`name`, `description`, `allowed-tools`,
  `compatibility`, `metadata`, `license`), the basis for the "there is no
  `extends`/`precedence`/`intents` field" claim in `## In deepagents`.
