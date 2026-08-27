# Memory

## Problem

Cross-session memory differs from `session-state.md`'s "Run state" layer -
not merely "more durable state", but state that has to be **curated**
actively rather than accumulated raw. Four questions rarely answered
deliberately:

1. **Extraction** - what enters memory from the raw conversation?
   Everything said, or only facts judged important - and who or what makes
   that judgement?
2. **Conflict** - if a new fact contradicts an old one (the user once said
   X, now says not-X), are both stored (memory becoming silently
   internally inconsistent), or does one win - and if one wins, on what
   basis, and is that decision recorded?
3. **Update** - if the same fact recurs with fuller detail, is that a new
   entry (duplication) or an update to the old one?
4. **Deletion** - the least discussed: how is memory actually deleted,
   rather than merely "no longer shown"? `retention-and-deletion.md`
   already requires deletion across layers to be real and cascading; the
   memory layer is no exception.

The symptom of a system that doesn't answer these: memory that only ever
grows (endless ADD, never UPDATE/DELETE) turns into a pile of possibly
contradictory facts, and the conflict resolution problem is silently
shifted to whatever reads memory at query time - rather than resolved at
write time.

## Pattern

### Three different mechanisms for three different questions

The real memory system read for this file (Letta) separates three
mechanisms with different purposes, rather than one generic store:

- **Core/working memory** - a set of small, labelled blocks **always**
  present in the context, edited precisely through tools
  (`core_memory_append`, `core_memory_replace`, `memory_replace`,
  `memory_insert`, `rethink_memory`). It answers "what must always be
  remembered" (e.g. a `human` block holding core facts about the user).
  `[code]` `letta/functions/function_sets/base.py` lines 246-527, repo
  `letta-ai/letta` branch `archive`.
- **Archival/long-term memory** - large, unbounded, retrieved through
  semantic search, **not** always in the context (`archival_memory_insert`,
  `archival_memory_search`, supporting tags and date filters). It answers
  "what might need finding later" - facts that needn't always be present
  but must remain findable. `[code]`
  `letta/functions/function_sets/base.py` lines 164-245.
- **Recall/conversation search** - search over the raw transcript itself
  (`conversation_search`, hybrid text + semantic similarity), not over
  curated facts at all. It answers "what was actually said", different from
  the two above which answer "what was concluded to be important". `[code]`
  `letta/functions/function_sets/base.py` lines 87-163. This is the
  conceptual counterpart of the `messages`/`tool_calls` tables in
  [`persistence-schema.md`](persistence-schema.md) - the transcript as the
  source of truth, searched directly with no curation layer.

Merging all three into one generic store loses the very properties that
justify each existing: core memory needs always-in-context (expensive if
every fact is treated that way); archival needs not-always-in-context
(wasteful if every fact must appear each turn); recall needs to stay raw
(over-aggressive curation removes exactly the detail sought later).

### Extraction: who decides something is worth remembering

Two real mechanisms, two different actor models:

- **Model-driven, tool-based** (Letta) - the agent itself calls
  `core_memory_append`/`archival_memory_insert` as part of its own
  reasoning in the moment. Extraction **is** a tool call - explicit,
  auditable from the trajectory (`evaluation.md` can assert directly
  "was `core_memory_append` called in this case" as part of trajectory
  eval). `[code]` the same as above.
- **Pipeline-driven, LLM extraction as a batch step** (Mem0) - a separate
  LLM call (`ADDITIVE_EXTRACTION_PROMPT`) over the latest messages plus
  existing candidate memories produces a JSON list of candidate facts, run
  as its own phase (`_add_to_vector_store` Phase 2), not an act of the
  agent currently on task. `[code]` `mem0/memory/main.py` lines 913-968
  (Phase 2, the `self.llm.generate_response` call with `system_prompt =
  ADDITIVE_EXTRACTION_PROMPT`), repo `mem0ai/mem0`.

The actor judging "worth remembering" differs: the agent working on the
task, in the moment (Letta), vs a separate extraction process re-reading
the conversation afterwards (Mem0) - see `## Trade-offs` for the
consequences.

### Conflict and update: LLM judgement vs deterministic exact match

Mem0 **documents** a four-way conflict resolution pattern well known in the
agent memory literature: for each extracted fact,
`DEFAULT_UPDATE_MEMORY_PROMPT` asks the LLM to decide one of ADD (a new
fact), UPDATE (contradicting or stating the same thing more fully - the old
ID retained), DELETE (the old and new facts directly contradict), or NONE
(already present/irrelevant), complete with paired examples for each case.
`[code]` `mem0/configs/prompts.py` lines 176-322, repo `mem0ai/mem0`.

**An important finding that must be recorded honestly**: this prompt is
**not** called on the `_add_to_vector_store` path in the version read today
(`mem0/memory/main.py`, verified by searching for
`DEFAULT_UPDATE_MEMORY_PROMPT`/`get_update_memory_messages` in that file -
zero matches). The pipeline actually running today is purely additive with
MD5 content-hash dedup (`mem_hash in existing_hashes or mem_hash in
seen_hashes` → skip, otherwise always `event: "ADD"`) - there is no
automatic UPDATE/DELETE decision against existing memories when a new fact
is written. `[code]` `mem0/memory/main.py` lines 1010-1039 (Phases 4-5,
hash dedup), 1160-1168 (`returned_memories` always `"event": "ADD"`). The
UPDATE/DELETE that genuinely exists in the API is an explicit **by-ID**
call: `update(memory_id, text=...)` and `delete(memory_id)`, triggered by
the calling application rather than decided automatically by the memory
system when writing a new fact. `[code]` `mem0/memory/main.py` lines
1815-1866 (`update`), 1869-1889 (`delete`). The per-fact ADD/UPDATE/
DELETE/NONE pattern remains a real, fully documented example of **how**
LLM-judgement-based conflict resolution can be designed - but citing it as
"this is how Mem0 resolves conflicts today" would be wrong without this
note.

Letta takes the opposite route for conflict in core memory:
**deterministic, not judgement**. `core_memory_replace(label, old_content,
new_content)` requires `old_content` to match the block's current content
**exactly** - if not found, the function raises `ValueError` rather than
guessing the caller's intent. `[code]`
`letta/functions/function_sets/base.py` lines 263-281. Conflict here isn't
"resolved" by judgement - it is caught as a hard failure forcing the caller
(the model itself, mid-reasoning) to re-read the block's content and try
again with a correct match. For a reorganisation/dedup genuinely needing
the whole block rewritten (rather than one string replaced), the route is
explicit and separate: `rethink_memory`/`memory_rethink` rewrites the
**entire** block at once, its documentation requiring it to integrate new
information while discarding what is stale or inconsistent - a full rewrite
operation, not a partial patch. `[code]`
`letta/functions/function_sets/base.py` lines 283-310, 488-519.

### Deletion: an explicit act, not "no longer shown"

Consistent with `retention-and-deletion.md`: both systems read treat
deletion as its own code path rather than a side effect of something else.
Mem0: `delete(memory_id)`/`delete_all(user_id=..., agent_id=...,
run_id=...)` are first-class API calls. `[code]` `mem0/memory/main.py`
lines 1869-1926. Letta: the `memory` tool supports an explicit `"delete"`
sub-command on a given block path, and `core_memory_replace` with
`new_content=""` is the equivalent route for core memory. `[code]`
`letta/functions/function_sets/base.py` lines 10-69 (the `memory` tool
docstring, the `delete` sub-command), 263-281 (`core_memory_replace`, the
comment "To delete memories, use an empty string"). Neither system treats
"no longer retrieved" as deletion - both have a delete operation that
genuinely removes the record.

## Trade-offs

- **Model-driven vs pipeline-driven extraction** - model-driven is
  auditable as a specific act in the trajectory and happens exactly when
  the agent on task judges something worth storing, but its memory quality
  is bound to what that agent happens to notice while doing something else
  (not its main focus), and it adds tool-call overhead to whichever turn
  extraction occurs in. A separate pipeline can process the whole
  conversation with full hindsight and can use a smaller/cheaper model
  dedicated to extraction, but is a separate system to build and maintain
  and has a lag (a gap between something being said and becoming reusable
  memory).
- **LLM-judgement conflict resolution vs deterministic exact match** - LLM
  judgement can recognise a semantically identical restatement ("likes
  cheese pizza" = "loves cheese pizza") and act like a human editor, but
  its decisions are a black box each time (not reproducible, requiring a
  model call per batch of facts) and can be wrong (producing a DELETE for
  something that doesn't actually contradict). Deterministic exact match is
  100% predictable and free (no extra model call), but brittle - the caller
  must know the old string exactly or the operation fails, and it can't
  recognise a paraphrase as "the same fact" the way LLM judgement can.
- **Always-on conflict resolution vs deferring to explicit by-ID calls**
  (the pattern actually verified on Mem0's current path) - deferring is far
  simpler to build (no need to resolve conflicts against the existing
  memory store on every write) and avoids the LLM judgement cost/risk
  above, but shifts the conflict detection problem onto whoever reads
  memory later - near-duplicate or even contradictory facts can coexist
  silently, unless the application builds its own reconciliation on top.

## In deepagents

`deepagents` does **not** ship a curated cross-session memory system like
Letta's or Mem0's - `MemoryMiddleware` only loads the contents of an
`AGENTS.md` file into the system prompt once at session start
(`memory=["./AGENTS.md", ...]`): static context injected once, not
extraction/conflict/update/deletion of discrete facts. `[code]` cited from
`../systems/deepagents.md` §2. `StoreBackend(namespace=...)` provides
durable cross-thread storage through LangGraph's `BaseStore` - but it is a
generic backend for the filesystem tool surface
(`read_file`/`write_file`/`edit_file`), not a memory-specific pipeline with
extraction/conflict mechanisms of its own. `[code]` cited from
`../systems/deepagents.md` §Filesystem backend. `CompositeBackend` even has
a documentation-example convention routing the `/memories/` path prefix to
`StoreBackend` - but that remains a filesystem naming convention, not a
built-in memory curation mechanism. `[code]`/`[docs]` cited from
`../systems/deepagents.md` §Filesystem backend
(`docs.langchain.com/oss/python/deepagents/backends`).

A project needing Letta/Mem0-style memory has to build it on top of
`deepagents` - either as custom tools writing to `StoreBackend` (the
model-driven pattern, like Letta: explicit tools the agent calls), or by
calling an external memory service (Letta/Mem0 themselves) as a tool.
`[inferred]` concluded from the absence of any fact
extraction/conflict/dedup module in the `deepagents/middleware/` read in
Task 3 and in this task. The "Memory" layer in
[`session-state.md`](session-state.md)'s five-layer table (§8.1) - Postgres
+ vector, cross-session, owned by BE+AI - is the architectural place this
project reserves for that custom build; `deepagents` itself doesn't fill
that layer.

## Sources

- `[code]` `letta/functions/function_sets/base.py` (repo `letta-ai/letta`,
  branch `archive` - the branch holding the Letta V1 server source; `main`
  is now a landing page pointing to `letta-ai/letta-code`, confirmed
  through that repo's `README.md`), read via
  `raw.githubusercontent.com/letta-ai/letta/archive/letta/functions/function_sets/base.py`
  - `core_memory_append`/`core_memory_replace`/`rethink_memory` (lines
  246-323), `memory_replace`/`memory_insert`/`memory_rethink` (lines
  330-527), `archival_memory_insert`/`archival_memory_search` (lines
  164-245), `conversation_search` (lines 87-163), the `memory` tool's
  `delete` sub-command (lines 10-69).
- `[code]` `mem0/memory/main.py` (repo `mem0ai/mem0`, branch `main`), read
  via `raw.githubusercontent.com/mem0ai/mem0/main/mem0/memory/main.py` -
  `_add_to_vector_store` Phase 2 extraction (lines 913-968), Phases 4-5
  hash dedup (lines 1010-1039), `returned_memories` always `"ADD"` (lines
  1160-1168), the explicit by-ID `update`/`delete` (lines 1815-1889).
- `[code]` `mem0/configs/prompts.py` (repo `mem0ai/mem0`), read via
  `raw.githubusercontent.com/mem0ai/mem0/main/mem0/configs/prompts.py` -
  `DEFAULT_UPDATE_MEMORY_PROMPT` (lines 176-322, the ADD/UPDATE/DELETE/NONE
  pattern documented in full with examples, cited with the note that it is
  unused on `main.py`'s current path), `ADDITIVE_EXTRACTION_PROMPT` (line
  468+, genuinely used).
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2
  (`MemoryMiddleware`), §Filesystem backend (`StoreBackend`,
  `CompositeBackend`) - a tier-1 reference verified in Task 3.
- `[code]` [`session-state.md`](session-state.md) §Five layers (§8.1) - the
  Memory layer (Postgres + vector, BE+AI) as the architectural home for a
  custom build on top of `deepagents`; not re-proposed here.
- `[code]` [`persistence-schema.md`](persistence-schema.md) - the
  conceptual counterpart `messages`/`tool_calls` tables, referenced to
  distinguish recall/transcript from curated memory.
- `[code]` [`retention-and-deletion.md`](retention-and-deletion.md) - the
  basis for the "deletion must be real, not merely no longer shown"
  requirement applied to the memory layer here.
- `[code]` [`evaluation.md`](evaluation.md) - the basis for the claim that
  model-driven extraction can be scored through trajectory eval.
