# 4. Research/Analyst

## Definition

An agent that runs a search → read → synthesize loop to produce a written
answer that **must carry citations**, with an explicit token/time budget
because a single research topic can trigger dozens of searches. Delegation
is commonly used to parallelise sub-topics, but the goal remains one
synthesised document at the end, not actions in other systems.

Boundaries against neighbours: differs from **General Task Agent** (03)
because its output artifact is always a written answer/report with
provenance rather than a free mix of files and actions; differs from
**In-App Copilot** (05) because it isn't bound to one product/API — its
sources are the open web and documents; differs from **Workflow Agent**
(06) because its horizon is a single research session, not an endlessly
repeating process.

## Position on the 6 axes

| Axis | Value |
|---|---|
| Blast radius | The outside world (web search, document retrieval), read-only |
| Artifact | A written answer/report with citations |
| Horizon | One research session (can be long, but ends in one report) |
| Human control | Review the final result; rarely approve each search |
| Domain surface | General or vertical (legal, financial, academic) |
| Interface | Chat, with a sources/citations panel |

## Harness consequences

1. **Loop shape: an explicit search → read → synthesize**, not free-form
   ReAct — each iteration must make clear which phase is running so the
   budget can be allocated per phase rather than consumed entirely by one.
2. **A hard token/iteration budget per sub-research** — without a limit one
   sub-topic can drain the whole allowance before other topics are
   processed; an explicit cap forces breadth-first coverage.
3. **Provenance attached to every claim** rather than added afterwards — if
   citations are bolted on after synthesis is complete, claims and their
   sources easily stop corresponding 1:1.
4. **Delegation for parallelising sub-topics**, with subagent results as a
   summary plus a source list (not raw search transcripts) so the main
   synthesiser's context doesn't drown in search detail.

## Example systems

- **deep_research (deepagents)** `[code]` — the official example defines a
  `research_sub_agent` with the `tavily_search` and `think_tool` tools, and
  bounds the scope through `max_concurrent_research_units = 3` and
  `max_researcher_iterations = 3` at the orchestrator level. This is a
  readable implementation of the archetype, not merely a description of
  behaviour. Source: `examples/deep_research/research_agent.ipynb`
  (langchain-ai/deepagents).
- **Perplexity** `[inferred]` — from product behaviour: answers always come
  with a numbered source list that can be traced back to search results.
- **OpenAI Deep Research** `[inferred]` — from product behaviour: long
  research sessions (minutes to hours) that emit one structured report
  with citations at the end, not an instant answer.
- **Elicit** `[inferred]` — from product behaviour: focused on academic
  literature, with answers linked to specific papers per claim.

## Common pitfalls

1. **Hallucinated citations** — the model names a source that was never
   actually fetched in the retrieval step, because nothing enforces that
   every citation must point at a real tool call result in the transcript.
2. **The budget is consumed by one "interesting" sub-topic** — without a
   per-subagent iteration cap, research widens uncontrollably into one
   branch and other topics from the original brief are never touched.
3. **Low-quality sources aren't filtered** — a naive search→read loop
   treats every search result as equal, so a speculative blog post and
   official documentation carry the same citation weight.
4. **Final synthesis loses the trail back to the originating search** — if
   subagent summaries don't carry source metadata, the main synthesiser
   has to guess or invent citations while assembling the final report.

## Building this with deepagents

- **Delegation**: the research subagent is defined as a dict
  `{"name": "research-agent", "description": "...", "system_prompt": ...,
  "tools": [web_search_tool, think_tool]}` and invoked through the `task`
  tool that `SubAgentMiddleware` provides. `[code]` — source:
  `examples/deep_research/research_agent.ipynb`.
- **Budget/loop limit**: explicit orchestrator-level caps such as
  `max_concurrent_research_units` and `max_researcher_iterations` —
  controlled in the code that calls the subagents, not a built-in
  `create_deep_agent` parameter. `[code]` — same source.
- **Tool surface**: narrow search tools (`web_search`) plus a `think_tool`
  that forces a reflection step before searching again — not a broad bash
  tool like a Workspace Agent, because this archetype's blast radius is
  read-only against the outside world. `[code]`.
- **Provenance/output**: `response_format` on `create_deep_agent` to force
  a structured output schema (e.g. a list of claims plus citations) rather
  than free text — the parameter exists in `create_deep_agent`'s
  signature. `[code]` — source: `graph.py`. `[ours]` We add a post-hoc
  validation that matches every citation in `response_format` against
  `web_search` tool-call results in the transcript; vanilla
  `response_format` only validates the schema's shape, not that its
  contents actually came from a real tool call — and that gap is exactly
  what lets hallucinated citations (pitfall #1) through unless patched.

## Sources

- deepagents `examples/deep_research/research_agent.ipynb`, `graph.py` —
  `[code]` — Context7 `/langchain-ai/deepagents`,
  https://github.com/langchain-ai/deepagents
- Perplexity, OpenAI Deep Research, Elicit — `[inferred]` — closed-source
  product behaviour.
