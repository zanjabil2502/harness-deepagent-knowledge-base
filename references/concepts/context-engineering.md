# Context engineering

## Problem

A context window filled with tool call history, search results, and old
messages looks like a single problem with an obvious solution: compaction —
summarise the old messages into something shorter, send fewer tokens per
call. That instinct is right for one cost axis (tokens per request) and
wrong for another that almost nobody writes down: **compaction breaks the
prompt prefix cache**, and once the prefix changes, the saving from sending
fewer tokens can be dwarfed by the lost cache-hit discount on *every*
subsequent call until that cache would have expired anyway.

The mechanism, quoted directly from Anthropic's official documentation
`[docs]`: the cache is formed as a **cumulative hierarchy** — `tools` →
`system` → `messages`. Each breakpoint (`cache_control`) writes a hash of
the entire prefix up to that point; the system writes **no** entry for
earlier positions. "Changes at each level invalidate that level and all
subsequent levels" — because the hash is cumulative, **changing any block at
or before a breakpoint produces a different hash on the next request**, and
the backwards cache lookup (a 20-block lookback window) finds no old entry
for that new hash. So one summary rewriting messages mid-history doesn't just
shorten `messages` — it shifts the prefix identity at that point and
onwards, making the *entire* tail after it (including anything already
cached there) a cache miss.

The cost of that miss is concrete and compounding, not merely "slightly more
expensive": per the same documentation, cache-written tokens are charged at
**1.25×** the base price (5-minute TTL) or **2×** (1-hour TTL), while a
cache hit costs only **0.1×** — a 12.5× spread between "the prefix is still
valid" and "you just rewrote the prefix". In a multi-user service where many
consecutive turns depend on the same prefix (the system prompt + tool
definitions + a stable early history), one badly placed compaction decision
pays the full write-cache price repeatedly — once per turn — until that
content is stable long enough to be cached again. This is rarely written
down because the two metrics (tokens sent vs cache-hit rate) appear on
different lines of the bill and are seldom seen side by side.

## Pattern

### A cache-friendly context order: stable first, volatile last

Anthropic's cache hierarchy (`tools` → `system` → `messages`) `[docs]` isn't
an implementation detail to be ignored — it **is** the context ordering rule:
put what changes least often first (tool definitions, static system
instructions, a document/repo map skeleton stable across turns), and what
changes most often last (the latest conversation turn, the tool result just
returned). Breakpoints go at the end of the last stable block — **not** at
the end of a block that changes every request. Anthropic's own documentation
gives the most common mistake: placing a breakpoint in a block containing a
per-request timestamp, producing a total cache miss every time because the
hash is always new; the fix is moving the breakpoint to the last stable block
**before** the changing content `[docs]`.

### Compaction isn't the first step — structural techniques are cheaper when available

Before rewriting history, three techniques reduce context growth without
ever touching an already-stable prefix:

- **Shape tool output at the source rather than summarising it later** —
  SWE-agent's *Agent-Computer Interface* principle: its built-in file viewer
  shows 100 lines per turn (rather than `cat`ing a whole file), and its
  directory search commands are deliberately terse — just the list of
  matching files, with no context per match, because the SWE-agent team
  found the more verbose version "too confusing for the model" as well as
  more token-hungry. `[code]` `docs/background/aci.md`, repo
  `SWE-agent/SWE-agent` (read via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/docs/background/aci.md`).
  The consequence: tool results entering the context are small from the
  start, so they never need summarising later — the problem is prevented
  upstream rather than cleaned up downstream.
- **Evict, don't rewrite** — `deepagents`' `FilesystemMiddleware` moves
  large tool results (>20000 tokens) into a file in the backend once they
  cross that threshold, leaving a head/tail preview plus a path reference in
  the original message's position (`TOO_LARGE_TOOL_MSG`). `[code]` cited
  from `../systems/deepagents.md` §2. This is a different mechanism from
  compaction even though the effect is likewise "fewer tokens": eviction
  happens to a **newly added** message (at the volatile end, before any
  breakpoint has marked it) rather than rewriting old messages already part
  of a cached prefix.
- **Recompute the context each turn from the source rather than
  accumulating then trimming** — Aider's repo map builds a graph of symbol
  definitions/references across files, weighting identifiers mentioned in
  the chat and long names higher (`mul *= 10`) along with currently open
  files (`mul *= 50`), then runs `networkx.pagerank` to rank which files are
  most relevant to include. `[code]` `aider/repomap.py` lines 480-511
  (weights), 365-380 (pagerank), repo `Aider-AI/aider`. Output size is kept
  within the token budget through a binary search over how many tags to
  include (`get_ranked_tags_map_uncached`, lines 629-703) `[code]`
  `aider/repomap.py`. This pattern avoids the "when to compact" question
  entirely for that part of the context — the repo map is recomputed each
  time rather than written once and summarised later.

### If compaction is unavoidable, keep message boundaries valid

Compaction cutting through the middle of a `tool_use`/`tool_result` pair
makes the provider reject the request (half a pair is orphaned). Cline
enforces this explicitly: a "safe" cut point exists only at a text-type user
message or at an assistant message (because its `tool_use` and the result
stay on the same side of the cut); a user message containing only a
`tool_result` is **never** a safe cut point, because its paired `tool_use`
is in the preceding assistant message and would be folded into the summary,
orphaning the `tool_result`. `[code]`
`sdk/packages/core/src/extensions/context/compaction-shared.ts` lines
317-325, repo `cline/cline`. `deepagents` handles the same problem class
differently — not by preventing unsafe cuts but by patching afterwards:
`PatchToolCallsMiddleware` inserts a synthetic `ToolMessage` for tool calls
left dangling by compaction/interrupts, keeping history valid for the next
model call. `[code]` cited from `../systems/deepagents.md` §2.

Cline also distinguishes **when** compaction triggers from **how much** it
trims: it triggers at 90% of the usable input budget
(`COMPACTION_TRIGGER_RATIO = 0.9`), targets a drop to 70%
(`DEFAULT_TARGET_RATIO = 0.7`), and always preserves the most recent 20000
tokens verbatim (`DEFAULT_PRESERVE_RECENT_TOKENS`), excluded from the fold.
`[code]` `sdk/packages/core/src/extensions/context/compaction-shared.ts`
lines 12-21. That "leave a large verbatim tail" pattern aligns with the
cache-friendly ordering rule above — but it **doesn't solve** invalidation:
the folded portion sits in the *middle* of the prefix, and per the hierarchy
mechanism above, rewriting the middle still shifts the hash of every
breakpoint at and after that point. Leaving the tail verbatim reduces how
much has to be re-written into cache after compaction (the tail doesn't need
rewriting), but doesn't make the compaction itself cache-neutral.

## Trade-offs

- **Compaction vs letting the cache hits run** — compare two numbers before
  deciding: (a) the tokens saved by summarising, times the base token price,
  versus (b) the full cache-write price (1.25×/2× base, not 0.1×) for the
  whole prefix that now has to be rewritten, times how many more turns are
  expected within the TTL before that cache would have expired naturally. If
  the session will continue for many turns inside the TTL window, losing the
  cache hits on all of them is usually more expensive than one compaction's
  token saving. Compaction is clearly a win only when: (i) the context
  window genuinely approaches a hard limit (no choice), or (ii) the session
  is about to go quiet for a long time anyway (the cache would expire on its
  own, so no cache hits are lost by rewriting it early).
- **Structural techniques (ACI, eviction, a recomputed repo map) vs generic
  compaction** — structural prevents growth at the source and never touches
  a stable prefix, but needs design work per tool/content type up front (a
  viewer window, an eviction threshold, a ranking graph) and isn't generic —
  every new tool needs its own thinking. Generic compaction (summarise
  whatever is old) works for any content with no special design, but always
  pays the cache cost above, and is reactive (it runs only once the context
  is already full rather than preventing that).
- **A breakpoint at the end of a large (rarely changing) block vs one
  further back (near the latest content)** — a breakpoint marking a large,
  stable block (the system prompt + tool definitions, as
  `AnthropicPromptCachingMiddleware` chooses — marking only the **last
  block** of the system message and the **last tool**, one trailing
  breakpoint for the whole tool set `[code]`
  `langchain_anthropic/middleware/prompt_caching.py` lines 232-262, repo
  `langchain-ai/langchain`) gives a high cache-hit rate because it rarely
  invalidates, but if something in that block **must** change (e.g. memory
  content injected into the system prompt), that entire large block
  invalidates at once. A breakpoint placed closer to the volatile end bounds
  the invalidation blast radius but leaves less content genuinely cached at
  any moment.

## In deepagents

`AnthropicPromptCachingMiddleware` (from `langchain-anthropic`, injected
automatically by `deepagents` through `append_prompt_caching_middleware`)
implements exactly the "stable first" rule above: it marks the **last
content block** of the system message and the **last tool** in the tool list
with `cache_control`, not every message — because tools are defined as one
contiguous block, one trailing breakpoint on the last tool already caches
the whole tool set. `[code]`
`langchain_anthropic/middleware/prompt_caching.py` lines 42-56, 122-151,
232-262 (installed as a dependency of `deepagents==0.7.8`,
`langchain-anthropic==1.6.1`, the same research venv as
`../systems/deepagents.md`).

A precision correction to what `../systems/deepagents.md` §2 says about this
ordering: re-read directly from `deepagents/graph.py` for this task, the
list construction order is `append_prompt_caching_middleware(deepagent_middleware)`
(line 860) **first**, with `MemoryMiddleware` appended afterwards (lines
861-865) if `memory` is set — the reverse of the "memory installed before
the prompt-caching tail" framing inferred from `../systems/deepagents.md`'s
prose. `[code]` `deepagents/graph.py` lines 860-865.

The actual mechanism keeping memory updates from breaking the prefix cache
isn't that inter-middleware ordering — `MemoryMiddleware` has its own
`add_cache_control: bool = False` parameter (`deepagents` sets `True`
specifically for the main stack's instance), and its `wrap_model_call`
(through `modify_request`, the internal method it calls on its first line)
marks the **last block** of the system message (after its own content is
inserted) with `cache_control` when that flag is on and `request.model` is a
`ChatAnthropic` — independently of whether `AnthropicPromptCachingMiddleware`
runs before or after it in the list. `[code]`
`deepagents/middleware/memory.py` line 193 (the `add_cache_control`
parameter), 342-374 (`modify_request`, marking the last block), 380, 394
(`wrap_model_call` calling `modify_request`); invoked with
`add_cache_control=True` in `deepagents/graph.py` lines 861-866. The source
comment at `deepagents/graph.py` lines 856-858 gives a different reason for
the **harness profile vs memory** ordering (not caching vs memory): a
profile's extra middleware is inserted between the core middleware and
memory deliberately "so that memory updates (which change the system
prompt) don't invalidate the prefix cache" of the profile's content — the
"stable first, volatile last" pattern from `## Pattern` above, applied to
the profile's position relative to memory, not to
`AnthropicPromptCachingMiddleware`'s position relative to memory as
`../systems/deepagents.md` originally claimed before correction. `[code]`
`deepagents/graph.py` lines 856-858 (the source comment, quoted as-is).
This detail was also used to fix `../systems/deepagents.md` §2 directly (the
`AnthropicPromptCachingMiddleware` paragraph) in this task — not merely
noted here, because that file is a tier-1 reference other tasks read as
authoritative.

The other side of the coin: `SummarizationMiddleware` (also a default,
always installed) works by rewriting a `messages` segment once tokens exceed
a threshold computed from the model profile
(`compute_summarization_defaults`). `[code]` cited from
`../systems/deepagents.md` §2. Per the cache hierarchy above, that rewrite
**always** shifts the `messages`-level hash at that point — and `deepagents`
does nothing by default to hold `SummarizationMiddleware`'s trigger until a
cache-neutral point (e.g. compacting only just before the context window is
exhausted rather than at an earlier threshold) — *when* that threshold is
reached relative to the cache TTL cycle is left entirely to the calling
application through the model parameters it uses. `[inferred]` — concluded
from the absence of any parameter in
`create_summarization_middleware`/`compute_summarization_defaults` aware of
the current cache TTL status; this isn't a bug claim, only the observation
that the two mechanisms (`SummarizationMiddleware` and
`AnthropicPromptCachingMiddleware`) run independently without informing each
other.

`FilesystemMiddleware` (evicting large tool results, see `## Pattern` above)
is the available mitigation that **doesn't** pay this cost, because it works
on a newly added message before any breakpoint has marked it — consequently,
raising eviction aggressiveness (lowering
`tool_token_limit_before_evict`) is a cheaper lever for restraining context
growth before `SummarizationMiddleware` triggers at all, compared with
relying on compaction as the only valve.

## Sources

- `[docs]` Anthropic —
  `platform.claude.com/docs/en/build-with-claude/prompt-caching`, the
  `tools`→`system`→`messages` cache hierarchy, the cumulative per-breakpoint
  hash mechanism, the 20-block lookback window, the 4 explicit breakpoint
  limit, the 5-minute/1-hour TTLs, the pricing multipliers (write 1.25×/2×,
  read 0.1×), and the example mistake of a breakpoint on content that
  changes every request.
- `[code]` `langchain_anthropic/middleware/prompt_caching.py` (package
  `langchain-anthropic==1.6.1`, read from
  `references/recipes/.venv/lib/python3.13/site-packages/`, the same venv
  used by `../systems/deepagents.md`) — `AnthropicPromptCachingMiddleware`,
  `_tag_system_message`, `_tag_tools`.
- `[code]` `deepagents/middleware/_prompt_caching.py` (same venv) —
  `append_prompt_caching_middleware`, its unconditional automatic
  installation.
- `[code]` `deepagents/middleware/memory.py` lines 193, 342-374, 380, 394
  (same venv) — the `add_cache_control` parameter; `modify_request` (called
  by `wrap_model_call`) marking the system message's last block itself,
  independently of `AnthropicPromptCachingMiddleware`.
- `[code]` `deepagents/graph.py` lines 856-866 (same venv, re-read directly
  for this task) — the main middleware list construction order
  (`append_prompt_caching_middleware` before `MemoryMiddleware` is
  appended), and the source comment on the profile vs memory middleware
  position; the basis for the precision correction to
  `../systems/deepagents.md` §2 (fixed directly in this task, see `## In
  deepagents`).
- `[code]` `docs/background/aci.md`, repo `SWE-agent/SWE-agent`, read via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/docs/background/aci.md`
  — the ACI design principles: the linter gate, the 100-line file viewer,
  terse search.
- `[code]` `tools/search/config.yaml`, repo `SWE-agent/SWE-agent`, read via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/tools/search/config.yaml`
  — the search command signatures referenced in `## Pattern`.
- `[code]` `aider/repomap.py`, repo `Aider-AI/aider`, read via
  `raw.githubusercontent.com/Aider-AI/aider/main/aider/repomap.py` — the
  personalisation weights (lines 480-511), `get_ranked_tags` +
  `nx.pagerank` (lines 365-380, 519-529), and the token budget binary search
  in `get_ranked_tags_map_uncached` (lines 629-703).
- `[code]` `sdk/packages/core/src/extensions/context/compaction-shared.ts`,
  repo `cline/cline`, read via
  `raw.githubusercontent.com/cline/cline/main/sdk/packages/core/src/extensions/context/compaction-shared.ts`
  — the `COMPACTION_TRIGGER_RATIO`/`DEFAULT_TARGET_RATIO`/`DEFAULT_PRESERVE_RECENT_TOKENS`
  constants (lines 12-21) and the safe cut-point rules (lines 317-325).
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2
  Context (`SummarizationMiddleware`, `FilesystemMiddleware`,
  `AnthropicPromptCachingMiddleware`, the tail stack order, the reasoning
  for memory-before-caching) — a tier-1 reference verified in Task 3, cited
  without re-reading the `deepagents/graph.py` source in this task except
  for `_prompt_caching.py` and
  `langchain_anthropic/middleware/prompt_caching.py`, which were re-read
  directly for it.
