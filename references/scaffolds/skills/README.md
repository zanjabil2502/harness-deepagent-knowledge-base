# Base skills: tagged output (table, chart, diagram, formula)

Four skills scaffolded as a **base set** into any project whose answers
sometimes need a shape other than prose. Their content is an emission
contract, not UI components: a skill tells the model **when** and **in what
shape** to emit; the application decides how to render it.

| Skill | Fence tag | Payload | Rendered by |
|---|---|---|---|
| [`tag-table/`](tag-table/SKILL.md) | ` ```table ` | JSON | the application's table component |
| [`tag-chart/`](tag-chart/SKILL.md) | ` ```chart ` | JSON | the application's chart library |
| [`tag-diagram/`](tag-diagram/SKILL.md) | ` ```mermaid ` | Mermaid source | a Mermaid renderer |
| [`tag-formula/`](tag-formula/SKILL.md) | ` ```math ` | LaTeX | KaTeX/MathJax |

## Why fenced blocks rather than XML tags

`[ours]` — This syntax decision is ours; `deepagents` has no built-in
convention for inline structured output. The vanilla alternative is
`response_format` on `create_deep_agent`, which forces the **whole reply**
into one schema'd object (see
[`../../concepts/structured-output.md`](../../concepts/structured-output.md)).
That is right for an endpoint whose output genuinely is one object, and wrong
for a conversational assistant: its answer is prose that **sometimes** inserts
a table, sometimes two diagrams, sometimes nothing at all. A single schema
can't express "prose with zero to n heterogeneous insertions" without turning
the entire reply into an array of blocks — which sacrifices text streaming and
makes the model write worse.

Three reasons for choosing fences (` ``` `) over XML-style tags:

- **Their boundaries already mean something in Markdown.** Every chat renderer
  already separates code blocks from prose. XML tags inside Markdown collide
  with HTML and can be stripped by a sanitizer.
- **They are detectable while streaming.** The opening line determines the
  block type before its content is complete, so the UI can immediately show
  the right placeholder. The handling details are in §Streaming.
- **One is already a de facto standard.** Mermaid is already tagged `mermaid`
  across the ecosystem. Renaming it to `diagram` would only break
  compatibility with existing renderers — so the skill is named `tag-diagram`
  while its fence tag stays `mermaid`.

## The emission contract

The flow has three steps, and the middle one must not be skipped:

```
the model emits a block  →  the app parses & validates  →  render / degrade
```

**Validation isn't optional.** Model output isn't trusted input, however clear
the skill is. JSON can be malformed, columns can mismatch rows, Mermaid can
fail to parse, LaTeX can be unterminated. An application feeding a block
straight to a rendering library delegates its error handling to that library,
which usually means an empty component with no explanation.

**Degradation must be visible, never silent.** A block failing validation is
rendered as an ordinary code block with one line explaining why. Discarding it
quietly is the most expensive failure: the user sees an answer that reads
complete while half its content is missing, and nobody knows — exactly the
failure mode [`../../concepts/guardrails.md`](../../concepts/guardrails.md)
forbids.

## Streaming

A block can't be rendered before its closing fence arrives. That is a direct
consequence, not an implementation detail:

- When the opening line appears, the UI already knows the block's **type**.
  Show a type-appropriate placeholder (a table skeleton, a chart box) and hold
  its content.
- While the content streams, don't try to parse it partially. Half a JSON
  document is always invalid; half a Mermaid diagram can be **valid but wrong**
  (an unclosed subgraph) — rendering then replacing makes the diagram flicker.
- A block that never closes (a cancelled turn, the model running out of
  tokens) must be closed by the application as a failed block rather than left
  hanging as an eternal placeholder.

The event shape and its reattach are in
[`../../concepts/streaming-protocol.md`](../../concepts/streaming-protocol.md).

## Security

Two of these four tags are executed by a rendering library in the browser, and
both have a surface beyond display:

- **Mermaid** recognises a `click` directive that can link out or invoke a
  callback, and some configurations allow HTML in labels. Run it with
  `securityLevel: "strict"` and reject blocks containing `click` unless that
  is genuinely wanted.
- **LaTeX** through KaTeX/MathJax has macros reaching beyond mathematics
  (`\href` the most obvious). Use an allowlisted macro set, bound expansion
  depth, and set a render timeout.

The JSON in `table`/`chart` is inert, but **its content is strings shown to
the user**. Column labels and captions can contain markup; escape them at
render time rather than trusting them because "it's only data".

All three belong to the same category: model-written content executed in the
user's browser. Treat it as untrusted input —
[`../../concepts/security.md`](../../concepts/security.md).

## Multilingual

There is one rule, and it separates two things easily conflated:

- **Machine keys are always language-neutral and stable** — `columns[].key`,
  `series[].key`, `type`, `v`. These are identifiers, not text.
- **Human-visible text follows the session's locale** — `label`, `caption`,
  `note`, diagram node labels.

The wrong practice, and a frequent one: using a localised label as a key
(`{"Pendapatan": 120}`). As soon as the locale changes, the same data can no
longer be matched against itself. The full explanation of intent/expression
separation is in
[`../../concepts/multilingual.md`](../../concepts/multilingual.md).

Each skill's frontmatter description is written in English because it is
matched by the model rather than read by the user — but it carries
cross-language trigger words so an Indonesian-language request still activates
it.

## When an insertion should become an artifact

An inline block is right for a result **read once inside the conversation**.
As soon as its output needs to persist, be versioned, be downloaded, or be
edited separately, it isn't an insertion any more but an artifact — stored
by-reference with the transcript holding only an `artifact_id` + a version
([`../../concepts/artifacts-and-canvas.md`](../../concepts/artifacts-and-canvas.md)).

The practical threshold all four skills use: a table above ~50 rows, or chart
data above ~200 points, is emitted as an artifact rather than inline.
`[ours]` — those numbers are our choice, not a `deepagents` limit (whose
built-in thresholds operate at another layer: tool result offloading at 20,000
tokens, see
[`../../deepagents/best-practices.md`](../../deepagents/best-practices.md)
§3). Retune them to the project's render width and token costs.

## Installing: a skill or memory?

All four are written as skills, and that choice's consequences deserve
attention. The upstream documentation recommends **memory for conventions that
are always relevant, skills for per-task capabilities**
([`../../deepagents/best-practices.md`](../../deepagents/best-practices.md)
§3, §5). Emitting a table is genuinely per-task — only when the answer demands
it — so a skill is the correct shape.

The cost is still real: each skill's frontmatter enters the system prompt
**every turn**, so these four skills add four descriptions to the baseline
permanently. If a project only ever uses one of them, install only that one.
If all four are used almost always and their descriptions become a burden,
merge them into one `tag-output` skill with four sections — the upstream
documentation itself recommends consolidation once descriptions start to
overlap.

Installation goes through `skills=` on `create_deep_agent`; the discovery and
activation mechanism is in
[`../../concepts/skill-composition.md`](../../concepts/skill-composition.md).

## Deriving other skills from these four

A derived skill **doesn't copy** the format; it references it. A quiz skill,
say, states when its result takes a table shape and names `tag-table` rather
than repeating its schema — as soon as the schema changes, a derived copy goes
stale with nobody noticing. The base→derived pattern through a declarative
manifest is in
[`../../concepts/skill-composition.md`](../../concepts/skill-composition.md)
§"Base → derived through a declarative manifest".

## Sources

- `[ours]` The tag syntax, the `table`/`chart` JSON schemas, the
  inline→artifact thresholds, and the degradation rules — our decisions; the
  vanilla alternative (`response_format` for the whole reply) is stated in
  §Why fenced blocks. Listed in the roster section of
  [`../../deepagents/conformance.md`](../../deepagents/conformance.md).
- `[docs]` [`../../deepagents/best-practices.md`](../../deepagents/best-practices.md)
  §3 (memory vs skills for always-relevant conventions; the 20,000-token
  offload threshold) and §5 (the frontmatter budget, consolidating overlapping
  skills) — the basis for §Installing and §When an insertion should become an
  artifact.
- `[code]` [`../../concepts/structured-output.md`](../../concepts/structured-output.md)
  §In deepagents — `response_format`'s behaviour, the basis for rejecting a
  single schema for a conversational reply; referenced without being
  rewritten.
