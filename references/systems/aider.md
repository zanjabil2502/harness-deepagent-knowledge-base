# Aider

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. `Aider-AI/aider`, a Python CLI, single-user, with no multi-tenant
backend. Chosen as the **context engineering** exemplar (a PageRank-based repo
map) per the T2 candidates in spec §10.

## Archetype

A pure **Workspace Agent (01)** — a local CLI, blast radius = the git repo's
working directory, artifacts = edits to existing files (not creating from
scratch), granular human control (`confirm_ask` per risky action: shell
commands, new files, commits). `[code]` — `aider/coders/base_coder.py` (see
axis 6).

## 1. Loop shape

**Not** classic ReAct tool calling. Aider has historically used a
"**reflection**" pattern: one user turn produces a `run_one()` that sends a
message, then checks `self.reflected_message` — if the LLM/harness produced
automatic feedback (a failing lint, a failing test, a file the model mentioned
that isn't in the chat yet), that message is **re-injected as a new turn**
with no user input, bounded by `max_reflections = 3`:

```python
while message:
    self.reflected_message = None
    list(self.send_message(message))
    if not self.reflected_message:
        break
    if self.num_reflections >= self.max_reflections:
        self.io.tool_warning(f"Only {self.max_reflections} reflections allowed, stopping.")
        return
    self.num_reflections += 1
    message = self.reflected_message
```

`[code]` — `aider/coders/base_coder.py` lines 100-101, 924-944. Who decides it
stops: **the harness**, through the `max_reflections` count, not a model
calling a "done" tool — a different philosophy from `deepagents`/OpenHands,
which leave the stopping moment to a model tool call and install limits only as
a safety net. The sources of reflection: the linter (lines 1604-1606), the test
runner (1620-1622), a file the model mentioned but which isn't in the chat
(1563-1566), and errors while applying an edit (2315, 2327). `[code]` — the
lines cited in `base_coder.py`.

## 2. Context

Two different mechanisms, **not** both active by default:

- **`RepoMap`** (`aider/repomap.py`) — a compact representation of the whole
  repo through *tags* (functions/classes/symbols extracted via
  tree-sitter/ctags-style), assembled into a graph then weighted with
  **PageRank** (`networkx.pagerank(G, weight="weight", **pers_args)` —
  `pers_args` can personalise the ranking towards files currently active in
  the chat), then trimmed to a token budget (`map_tokens`) through
  `get_ranked_tags_map`. This is a "context = a relevance-weighted map of code
  structure" pattern, not RAG embeddings and not filesystem-as-memory. `[code]`
  — `aider/repomap.py` lines 42, 365-388, 522-530, 576-710
  (`get_ranked_tags`, `render_tree`, the pagerank usage).
- **`ChatSummary`** (`aider/history.py`) — chat history compaction through a
  separate summarising LLM (`summarize`, `summarize_real` with a recursive
  `depth` for large chunks, `summarize_all`). Called explicitly when
  `edit_format` changes mid-session (see axis 7,
  `Coder.create(summarize_from_coder=True)`), not triggered automatically by a
  per-turn token threshold like `deepagents`' `SummarizationMiddleware`.
  `[code]` — `aider/history.py` lines 7, 27, 33, 98;
  `aider/coders/base_coder.py` lines 125-165 (the
  `from_coder.summarizer.summarize_all` call).

## 3. Tool surface

**No model tool-calling API at all** on the main edit path — Aider asks the LLM
to write **structured edit blocks inside an ordinary text response** (the
format depending on `edit_format`: a unified diff, a whole file, a
search/replace block, or an XML-like patch), then Aider **parses** that text
itself on the client side (`aider/coders/search_replace.py`, `patch_coder.py`,
`editblock_coder.py`). This contrasts entirely with
`deepagents`/OpenHands/LibreChat, which use the provider's tool-calling API.
Shell commands likewise appear as text blocks (a ```bash fenced block, not a
tool call), processed through `handle_shell_commands` (axis 6). `[code]` — the
filenames `aider/coders/{search_replace,patch_coder,editblock_coder}.py`,
`aider/coders/base_coder.py` lines 2440-2480 (parsing and executing shell
commands from text).

## 4. Delegation

There is explicit two-model delegation through **`ArchitectCoder`**: the
`--architect` mode separates the planning model (answering in prose, not
editing directly) from the editor model. `ArchitectCoder.reply_completed()` —
once the architect's response is finished and (unless
`auto_accept_architect=True`) `confirm_ask("Edit the files?")` is approved —
creates a **new `Coder` instance** (`editor_coder =
Coder.create(main_model=editor_model,
edit_format=self.main_model.editor_edit_format, ...)`) and runs it
synchronously: `editor_coder.run(with_message=content, preproc=False)`. The
editor model can differ from the architect model (`main_model.editor_model` —
the combination of an expensive model for planning plus a cheap/fast one for
editing is an explicitly supported pattern). `[code]` —
`aider/coders/architect_coder.py` lines 1-40.

**The result returning to the caller**: not a `ToolMessage` — the architect
calls `self.move_back_cur_messages("I made those changes to the files.")` once
`editor_coder` finishes, injecting one fixed summary message (not the editor's
working transcript) into the architect's history, plus absorbing the editor's
`total_cost` and `aider_commit_hashes` into the architect's state. `[code]` —
`aider/coders/architect_coder.py` lines 41-44 (outside the excerpt cited above,
confirmed through the `move_back_cur_messages` method name).

## 5. State & resume

`done_messages` (finished history, already committed to the chat history) vs
`cur_messages` (the running turn) — two separate buffers rather than one flat
transcript. When `Coder.create()` inherits from `from_coder` (used both in
architect→editor delegation and in an ordinary `edit_format` switch),
`done_messages`/`cur_messages`/`aider_commit_hashes`/`total_cost` are passed
through explicitly. `[code]` — `aider/coders/base_coder.py` lines 125-175
(`create`).

There is no formal checkpointer/state store (unlike LangGraph in
LibreChat/`deepagents`) — persistence across terminal sessions is the **chat
history in the `.aider.chat.history.md` file** plus a **git commit** per edit
(`auto_commits=True` by default) as a durable record a human can re-read
through `git log` rather than through a resume API. `[code]` —
`aider/coders/base_coder.py` lines 308-309, 409-413 (the `auto_commits`,
`dirty_commits` defaults of `True`).

## 6. Safety gate

A different philosophy from `deepagents`/OpenHands: **file edits are applied
automatically then committed straight to git** (rather than requiring approval
before execution) — reversibility comes from git history rather than from an
approval pause. `check_for_dirty_commit`/`dirty_commit` commit uncommitted
changes before Aider overwrites a file, so Aider's diff can always be separated
from the human's earlier diff. `[code]` — `aider/coders/base_coder.py` lines
2175-2238, 2291, 2411-2414.

**Shell commands** are the only action requiring explicit confirmation before
execution, and they are deliberately **fail-closed**:
`self.io.confirm_ask(prompt, subject="\n".join(commands),
explicit_yes_required=True, group=group, allow_never=True)` —
`explicit_yes_required=True` means a bare "Enter" doesn't automatically answer
yes (unlike other `confirm_ask` calls in the codebase, which accept Enter as
yes). `allow_never=True` offers a "don't ask again" option for the session.
`[code]` — `aider/coders/base_coder.py` lines 2449-2461. Creating a new file is
gated too: `confirm_ask("Create new file?", subject=path)`. `[code]` — line
2207.

There is no code execution sandbox — shell commands run directly in the host
process through `run_cmd()` (a subprocess), with no extra isolation; the only
mitigation is the approval gate above. `[code]` —
`aider/coders/base_coder.py` line 2465 (the `run_cmd` call).

## 7. Capability routing & policy

**Static configuration, neither a classifier nor runtime model judgement.**
Aider's main "capability" choice — which `edit_format` is used (determining the
concrete `Coder` class: `EditBlockCoder`, `WholeFileCoder`, `PatchCoder`, etc.,
each with its own prompt and parser) — is decided in `Coder.create()` through
an explicit priority order: an explicit `edit_format` argument →
`from_coder.edit_format` (when switching) → `main_model.edit_format` (the
per-model default, e.g. certain models defaulting to `"diff"` and others to
`"whole"`). This decision is made **once per session/switch**, by
code/configuration rather than by a model assessing the task at runtime, and it
is not a trained classifier. `[code]` — `aider/coders/base_coder.py` lines
125-152 (`Coder.create`).

The one "role-based" delegation (`ArchitectCoder` → editor, axis 4) is likewise
chosen statically through the `--architect` flag before the session starts, not
re-decided each turn. This contrasts with
`references/concepts/skill-composition.md` and the `SkillsMiddleware` pattern
in `deepagents`/OpenHands (per-turn routing from descriptions) — Aider has no
such dynamic routing mechanism in the source read. `[inferred]` — from the
absence of any classifier/skill-registry module in `aider/coders/` or the
`aider/` root.

## Sources

The `Aider-AI/aider` repo was shallow-cloned (`git clone --depth 1`) on
2026-08-23 and read directly as files:

- `aider/coders/base_coder.py` — lines 100-175 (`max_reflections`,
  `Coder.create`), 300-415 (the `auto_commits`/`dirty_commits` defaults),
  866-944 (`run`, `run_one`, the reflection loop), 976, 1187, 1415, 1563-1622
  (`confirm_ask` for lint/test/file mentions), 1772, 2175-2238
  (`check_for_dirty_commit`, `dirty_commit`), 2291, 2315, 2327, 2376-2414,
  2440-2485 (`handle_shell_commands`, the shell `confirm_ask`,
  `explicit_yes_required`)
- `aider/coders/architect_coder.py` — in full (the `ArchitectCoder` class,
  `reply_completed`, the delegation to `editor_coder`)
- `aider/repomap.py` — lines 42, 67, 103, 177-260 (`load_tags_cache`,
  `save_tags_cache`, `tags_cache_error`), 365-388, 522-530 (the
  `networkx.pagerank` usage), 576-710 (`get_ranked_tags_map`, `render_tree`)
- `aider/history.py` — in full (the `ChatSummary` class, its `summarize`,
  `summarize_real`, `summarize_all` methods)
- `aider/coders/__init__.py`, the listing of `aider/coders/*.py` — to confirm
  the family of `Coder` classes per `edit_format` (`editblock_coder.py`,
  `patch_coder.py`, `search_replace.py`, etc.)

An honesty note: the edit block parsers themselves
(`search_replace.py`/`patch_coder.py`) weren't read in detail — the claims
here are limited to "text parsing, not a tool-calling API", confirmed from the
file structure and `base_coder.py`'s docstrings rather than from reading the
parsing algorithm line by line.
