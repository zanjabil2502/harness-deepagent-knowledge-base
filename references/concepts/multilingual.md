# Multilingual

## Problem

Multilingual is usually reduced to "translate the UI" — button strings and
labels are translated, and the team considers the system multilingual. That
covers one surface of an agent loop with many points quietly assuming one
language (and almost always English): guardrail regexes validated against US
identity formats, injection detection classifiers trained predominantly on
English corpora, golden tests written in only one language, and token budget
calculations quietly assuming a Latin-language tokens-per-word ratio. Each of
these fails **silently** — no error, only worse behaviour for users in the
under-covered language, discovered only after a user reports it.

The second problem, independent of the first: if routing/policy hangs on
natural language *phrases* ("if the user says X, do Y"), every new language
means rewriting every surface hanging on those phrases.
[`skill-composition.md`](skill-composition.md) §Problem already names the
narrow version of this for skill triggering; this file widens it to the full
pipeline (spec §8.6): the problem isn't only which skill is triggered but
*every* decision point along the loop that happens to read the user's
language text rather than an already-neutralised code.

This project's assumption (multi-user, cloud + on-prem) makes a
cross-language user base the **default** case, not an edge case patched
later. Spec §9 stresses this another way: multilingual isn't one of the 7
`systems/` axes, it is a notes column in the INDEX — the **absence** of
multilingual design in a system is itself a finding worth recording, not a
safe default.

## Pattern

### The pipeline: separate intent from expression (spec §8.6)

```
input (any language)
   │
   ▼
[1] intent classification       — a model/classifier reads the text as-is
   │                               (any language, even mixed)
   ▼
[2] a neutral code (e.g. "deploy.request", "research.legal")
   │                               ── zero languages from this point on ──
   ▼
[3] policy/skill lookup BY CODE  — string matching, not phrase matching
   │                               (see skill-composition.md §`intents`
   │                               uses neutral codes)
   ▼
[4] execution                    — tools operate on structured values/codes,
   │                               never on raw language text
   ▼
[5] render output in the user's locale — localisation happens ONCE, at the end
```

The crucial point: the line between [2] and [3] is the "zero language" line
— once the user's text has become an intent code, no policy/routing decision
in the remainder of the pipeline may read language text again. This is
`[ours]` — following this project's spec §8.6 literally; vanilla (and what
we diverge from) is the single-layer pipeline common in chatbot products: a
system prompt holding routing instructions in natural language ("if the user
asks for X, call tool Y"), with the model reading instructions + user
messages in the same language throughout — language leaks into every
decision because there is never an explicit cut point. We diverge because
that vanilla means testing *every* policy decision against *every* supported
language to know whether routing is still correct — test cost multiplying by
language count at points that should not care about language at all.

The intent code mechanism's details and the skill manifest (`intents: [...]`,
`extends`/`precedence` resolution) are **owned entirely by
[`skill-composition.md`](skill-composition.md)** — this file doesn't repeat
them, only places them as one node ([3]) in a larger pipeline. The policy
data shape that lookup [3] targets is owned by
[`policy-as-data.md`](policy-as-data.md).

### Locale is first-class session context, not a per-turn guess

The locale (the user's output rendering language preference — `id`, `en`,
etc.) is **set once** when the session/conversation is created (from the user
profile, the `Accept-Language` header, or an explicit choice), then **carried
as part of the session context** rather than re-inferred from each incoming
message.

The reason isn't stylistic preference: two different signal sources are
easily conflated if the locale is re-guessed per turn —

- **The message's language** — whichever language the user happened to use
  in one particular turn. The pipeline's input (stage [1] above) must handle
  this as-is, including mixed languages within one message.
- **The rendering locale** — the language the user *expects* the system to
  reply in, display error messages in, and so on.

If the locale is re-guessed from the last message's language, one English
sentence in the middle of an Indonesian conversation (e.g. the user pasting
an English error log) can silently switch the system's next reply's language
— a bug that looks like a "smart feature" but is really an unstable locale.
A persisted session field for the locale breaks that dependency: individual
message languages remain free to vary (handled by the intent classifier),
but the rendering locale doesn't change unless the user changes it
explicitly.

Schema-wise, this means the locale deserves a column in the
session/conversation layer owned by
[`persistence-schema.md`](persistence-schema.md) (e.g. `conversations.locale`,
or `users.locale` as a default overridable per conversation) — that file
doesn't yet declare this column in its DDL; it is an addition this file
recommends, not a correction to the existing schema.

### What is localised, and what isn't (spec §8.6)

| Localised | Not localised |
|---|---|
| Guardrail lexicons (regexes, moderation word lists) | Core system/prompt instructions |
| Few-shot examples | Intent code names, tool names, data schemas |
| Output templates (date/currency formats, greetings) | Policy/skill manifest schemas |
| User-facing error messages | Internal logs, observability traces |

System instructions **need no translation** — a direct consequence of the
pipeline above: the same model reads one system prompt (in whatever language
it is written, usually the team's) and can still classify intent from input
in any language and render output in the requested locale, because
routing/policy instructions have been moved into neutral codes rather than
living as prose the model must "understand" in the same language as the
user. What **must** be localised is the surface that directly reads from or
is shown to the user: guardrail lexicons, few-shots, output templates, error
messages.

### The table of language-locked points

Each row is an enforcement/decision point that behaves differently per
language unless handled explicitly. The "Owner" column names the file
holding that point's technical detail — this file doesn't repeat it, only
stresses the multilingual angle.

| # | Point | Why it is language-locked | Detail owner |
|---|---|---|---|
| 1 | Skill triggering | The skill description underpinning the model's judgement (`SkillsMiddleware`), or `intents` phrases written in one language, fails to match an equivalent expression in another — see `## In deepagents` for why `deepagents`' own built-in mechanism is purely model judgement over text, not codes | [`skill-composition.md`](skill-composition.md) §`intents` uses neutral codes |
| 2 | Guardrail regexes | National identity formats differ in structure, not just length — Indonesia's NIK (16 digits: province+regency/city+district codes+date of birth+sequence) and NPWP (the format `XX.XXX.XXX.X-XXX.XXX`, 15 digits in the old form / 16 digits in the new NIK-integrated form) are **not** a US SSN (`XXX-XX-XXXX`, 9 digits). `[inferred]` — the NIK/NPWP formats here are general knowledge, not verified against official Ditjen Dukcapil/Ditjen Pajak documents in this task; what matters is the structural point (a different format, not merely a different length, so an SSN regex doesn't automatically cover it), not the exact digits. A regex validated only against the SSN pattern will false-negative entirely against NIK/NPWP (never matching, therefore never redacting data that genuinely is PII) and can incidentally false-positive (9 random digits inside a 16-digit NIK can coincidentally match another irrelevant pattern). Content moderation lists/lexicons are also overwhelmingly English — abuse/violence keywords curated for English don't automatically cover their equivalents in other languages | [`guardrails.md`](guardrails.md) points 1 & 4 (PII, moderation) — that file owns the enforcement mechanisms (`PIIMiddleware`, etc.); this file adds the requirement: per-language/per-country lexicons and regexes must be explicit, not one generic set that happens to have been written for one country |
| 3 | Injection & jailbreak detection | Security classifiers (Llama Guard and peers, see `guardrails.md` §Tiered) are trained predominantly on English corpora; an injection payload written in another language, or *code-switched* mid-sentence, has lower recall on the same model — not because the model "doesn't understand" that language, but because the training data distribution for *this specific security task* skews English `[inferred]` (a general pattern in cross-language security model performance; the specific "Llama Guard supports 8 languages" claim is in `guardrails.md`, which claims no per-language accuracy for this attack class) | [`security.md`](security.md) §Prompt injection, [`guardrails.md`](guardrails.md) point 1 |
| 4 | Golden-test eval | A single-language golden set is entirely blind (not merely less sensitive) to regressions in other languages — a change breaking Indonesian while English stays fine produces zero signal in an English-only suite | [`evaluation.md`](evaluation.md) §The multilingual eval obligation — owned in full there, cited here as one table row because it is the **measurement** instrument for every other row in this table (points 1-3 and 5 all need a language-labelled golden set to know whether they genuinely work across languages) |
| 5 | Token budget calibration | Non-Latin/non-space-separated languages (Javanese script, Han, Thai, etc.) and agglutinative languages consume far more tokens per word/character than space-separated Latin ones — a BPE tokenizer fitted predominantly on English corpora splits non-English words into more subword tokens. Thresholds calibrated from English examples (`SummarizationMiddleware`'s compaction limit, `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` computed from per-turn token estimates, see `cost-control.md` and `context-engineering.md`) trigger compaction/truncation sooner for conversations in other languages at an equivalent *word* count — the user's experience differs in quality purely because of the language they use, not the conversation's content | Not owned by another file in this KB — new ground; `context-engineering.md`/`cost-control.md` own the compaction/limit mechanisms, and this file adds the requirement: those thresholds must be calibrated (or measured) per language actually used in production, not inherited from defaults computed on an English example corpus |

## Trade-offs

- **Intent classification + language detection in one model call vs two
  separate steps** — one combined call is cheaper (one round trip) but mixes
  two different failure modes into one signal: if the result is wrong, it
  isn't immediately clear whether the intent code or the detected language
  was wrong, complicating per-language debugging from golden set eval (point
  4 above). Two separate steps can be diagnosed independently (measuring
  language detection accuracy and intent classification accuracy separately)
  at the cost of doubled latency/tokens on every turn.
- **A locale persisted once in the session vs re-inferred each turn** —
  persisted is stable and cheap (one lookup, not a classification per turn)
  but needs an explicit mechanism for the user to change it (it doesn't
  automatically follow when the user deliberately switches language for the
  rest of the session); automatic re-inference adapts to that change but is
  prone to flip-flopping from one mixed-language sentence as described above
  — this project chooses persisted, judging rendering-locale flip-flop more
  disruptive than the small friction of "change the locale in settings".
- **Localising the whole system prompt per locale vs localising only
  lexicons/templates/errors (the spec §8.6 decision)** `[ours]` — vanilla in
  many multilingual products: the system prompt is fully translated into
  every supported locale, one file per language. That is easy to reason
  about (one prompt = one language, consistent) but costs a multiple of the
  locale count for every prompt change (a new skill, a new policy → rewrite
  N translations and keep them in sync — exactly the duplication ailment
  named in `skill-composition.md` §Problem, only at the prompt layer rather
  than the skill layer), and a translated prompt's instruction-following
  quality isn't guaranteed equal to the original's. We diverge: the system
  prompt stays single (the pipeline has already separated language from
  decisions, see `## Pattern`), and only surfaces genuinely written to be
  read or seen by users are localised — so the multiple of locale count
  applies to those surfaces alone, not the whole prompt.

## In deepagents

`deepagents` has no built-in language/locale mechanism at all — no `locale`
parameter, no intent classifier, no automatic translation. What is relevant
among the existing primitives:

- **`SkillsMiddleware` is purely model judgement over description text**
  (see [`../systems/deepagents.md`](../systems/deepagents.md) §7) — there is
  no built-in code classifier mapping intents to skills. This is exactly
  point 1 of the table above: if a team relies on `deepagents`' built-in
  mechanism as-is (skill descriptions written in one language, the model
  judging the match directly from the user's text), its language coverage is
  bound to how completely those descriptions name cross-language variants.
  The zero-language pipeline in `## Pattern` (intent classification → code →
  manifest `intents` lookup, `skill-composition.md`) has to be built **in
  front of** `SkillsMiddleware` as an additional application layer —
  `deepagents` doesn't provide it. `[code]` — cited from
  `../systems/deepagents.md` §7 (`deepagents/middleware/skills.py`).
- **`context_schema` + `Runtime[ContextT]`** is the concrete primitive best
  suited to "locale as first-class session context, not a per-turn guess":
  `create_deep_agent(..., context_schema=Context)` defines *"immutable
  run-scoped context"* — a dataclass/`TypedDict` set once when the run
  starts (e.g. `Context(user_id=..., locale=...)`) and read through
  `runtime.context.locale` from any middleware/tool throughout the run,
  needing no recomputation. This isn't a built-in locale mechanism —
  `deepagents`/`langgraph` know nothing about "locale"; the fields are
  purely what the application defines — but its shape (immutable,
  run-scoped, read through `Runtime`) is exactly the contract §Locale above
  needs. `[code]` — `deepagents/graph.py` lines 282, 543 (the
  `context_schema` parameter's docstring: *"Schema class that defines
  immutable run-scoped context"*), `langgraph/runtime.py`'s `Runtime` class
  (*"This class is injected into graph nodes and middleware... `context`,
  `store`, `stream_writer`..."*). The same use of `Runtime` for a similar
  per-user field already appears in
  `StoreBackend(namespace=lambda rt: (rt.server_info.user.identity,))` cited
  from `../systems/deepagents.md` §Filesystem backend — evidence that
  `Runtime.context`/`Runtime.server_info` is indeed the route used for
  per-session data like this, not a new suggestion inconsistent with
  existing `deepagents` patterns.
- No built-in middleware calibrates token thresholds
  (`compute_summarization_defaults` in `SummarizationMiddleware`, see
  `../systems/deepagents.md` §2) per language — the computation is purely
  based on the model profile's `max_input_tokens`, unaware of the language
  of the content being counted. `[inferred]` — concluded from the absence of
  any language parameter in the
  `create_summarization_middleware`/`compute_summarization_defaults`
  signatures cited in `../systems/deepagents.md` §2; per-language
  calibration (point 5 of the table above) must be done by the application
  through real per-locale token measurement, not provided automatically by
  the middleware.

## Sources

- `[ours]` This project's spec §8.6 — the intent/expression pipeline, the
  language-locked points table, and the "locale is first-class, not a
  per-turn guess" rule are this project's design decisions, cited and
  extended in this file.
- `[code]` [`skill-composition.md`](skill-composition.md) §`intents` uses
  neutral codes, §Base → derived through a declarative manifest — cited for
  pipeline node [3], details not repeated.
- `[code]` [`evaluation.md`](evaluation.md) §The multilingual eval
  obligation — cited for table point 4, details not repeated.
- `[code]` [`guardrails.md`](guardrails.md) points 1 & 4 (PII, moderation),
  §Tiered (Llama Guard's 8-language support) — cited for table points 2 & 3.
- `[code]` [`security.md`](security.md) §Prompt injection — cited for table
  point 3.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — cited for the
  proposed locale column in the session layer; that DDL itself is unchanged
  by this file.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2, §7,
  §Filesystem backend — a verified tier-1 reference, cited directly without
  re-reading the `deepagents` source in this task.
- `[code]` `deepagents/graph.py` lines 282, 543 — read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/deepagents/graph.py`
  to verify the `context_schema` parameter's docstring.
- `[code]` `langgraph/runtime.py` — read directly from
  `references/recipes/.venv/lib/python3.13/site-packages/langgraph/runtime.py`
  to verify the `Runtime` class contract (run-scoped, immutable `context`).
