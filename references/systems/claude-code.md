# Claude Code

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**, but **treated differently from the eight other files in this
grid**: Claude Code is a closed-source product - there is no public repo to
read. Every claim in this file is labelled `[docs]` (quoted directly from
`docs.claude.com`, fetched through `curl` to the raw `.md` URLs rather than
through a summary) or `[inferred]` (concluded from product behaviour/indirect
documentation). **There are no `[code]` claims in this file** - if source needs
reading for a comparable pattern, see `deepagents.md` (T1) or
`openhands.md`/`letta.md` in this grid, which implement equivalent mechanisms
openly.

This file has a specific job in the KB: to be the **primary axis 7 example**
for the "prose + model judgement" *capability routing* pattern - including that
pattern's weaknesses, argued in full in
`references/concepts/policy-as-data.md` and
`references/concepts/skill-composition.md`. This file cites that argument
rather than repeating it.

## Archetype

A **Workspace Agent (01)** - a local CLI, broad bash/file tools, a granular
permission gate, and aggressive compaction are archetype consequences matching
`archetypes/01-workspace-agent.md`'s description exactly. `[docs]` - the
command/tool structure documented at `docs.claude.com/en/docs/claude-code/*`
(permissions, hooks, subagents, skills - all cited in `## Sources`).

## 1. Loop shape

Not verified from source (closed). From the public documentation: a standard
ReAct loop (read/write files, run shell, call tools, repeat until the model
stops calling tools) - this behaviour is **not** documented explicitly as a
loop diagram on any page read, only implied by how `hooks.md` describes the
`PreToolUse`/`PostToolUse` cycle per tool call. `[inferred]`.

## 2. Context

**Auto-compaction** is documented explicitly with a concrete interaction with
skills (see axis 7): *"Auto-compaction carries invoked skills forward within a
token budget. When the conversation is summarized to free context, Claude Code
re-attaches the most recent invocation of each skill after the summary, keeping
the first 5,000 tokens of each. Re-attached skills share a combined budget of
25,000 tokens... older skills can be dropped entirely after compaction if you
have invoked many in one session."* `[docs]` -
`docs.claude.com/en/docs/claude-code/skills.md` line ~503 (quoted exactly).

This is a concrete instance of the compaction-vs-fidelity trade-off discussed
in `references/concepts/context-engineering.md`: a summary isn't complete
storage - a skill dropped from the compaction budget must be **invoked again**
explicitly for its full content to return; it doesn't recover automatically.
`[docs]` - the same quotation.

## 3. Tool surface

The complete list isn't verified from source. From the documentation: the
built-in `general-purpose` subagent gets "every tool available to subagents" (a
broad surface), while the built-in `Explore`/`Plan` subagents are deliberately
restricted to read-only ("Write and Edit are denied") - a tool surface pattern
that **differs per role** rather than one flat tool set for every context.
`[docs]` - `docs.claude.com/en/docs/claude-code/sub-agents.md` (the "Built-in
subagents" table).

## 4. Delegation

Subagents are the primary delegation mechanism, documented with three built-ins
(`Explore`, `Plan`, `general-purpose`) plus several helpers
(`statusline-setup`, `claude-code-guide`, a `claude` catch-all), and custom
subagents through Markdown+frontmatter files in `.claude/agents/` (project) or
`~/.claude/agents/` (user). An explicit claim from the docs: *"Each subagent
runs in its own context window with a custom system prompt, specific tool
access, and independent permissions"* - full context isolation, not merely an
extra prompt in the same context. `[docs]` -
`docs.claude.com/en/docs/claude-code/sub-agents.md`.

**The result returning to the caller**: *"The subagent summarizes its results
and returns them to your main conversation when it finishes"* - a summary, not
a full working transcript, the same philosophy as the compact `ToolMessage`
pattern in `deepagents`/OpenHands. `[docs]` - the same page, line ~717.

Which subagent gets called for a given task is **pure model judgement** over
the `description`: *"Claude uses each subagent's description to decide when to
delegate tasks. When you create a subagent, write a clear description so Claude
knows when to use it."* - the same pattern and the same weakness discussed in
axis 7 below, since the mechanism is identical to skill routing. `[docs]` -
`docs.claude.com/en/docs/claude-code/sub-agents.md`.

## 5. State & resume

The checkpoint/resume mechanism isn't verified from source. The documentation
pages read mention related capabilities but weren't read in detail in this task
(`background agents`, `agent-view`, `cross-session messaging`, `agent teams` -
referenced as separate features in `sub-agents.md`, their contents
unverified). `[inferred]` for the mechanism's details; `[docs]` only for those
features' existence (their names & cross-references, from
`docs.claude.com/en/docs/claude-code/sub-agents.md` line ~13, the Note box).

## 6. Safety gate

**Six documented permission modes**, a spectrum from strictest to loosest:

| Mode | Behaviour |
|---|---|
| `default` ("Manual") | Prompts for permission on each tool's first use |
| `acceptEdits` | Auto-accepts file edits + common filesystem commands (`mkdir`, `touch`, `mv`, `cp`) within the working directory |
| `plan` | Read-only for exploration; read-only-classified commands may run when `auto` mode is active |
| `auto` | Auto-approves tool calls, **with a model-based background safety check** verifying that actions align with the request |
| `dontAsk` | Auto-**denies** tools unless already allowed through `/permissions`/`permissions.allow` - `AskUserQuestion` and MCP tools marked `requiresUserInteraction` are still refused even when allowed |
| `bypassPermissions` | Skips every prompt except *"actions no mode auto-approves"* - the documentation warns explicitly: use only in an isolated environment (a container/VM) |

`[docs]` - `docs.claude.com/en/docs/claude-code/permissions.md` lines 74-91
(the mode table, the `bypassPermissions` warning quoted exactly).

The `auto` mode is interesting as an architectural contrast: its gate is **not**
a deterministic rule like OpenHands' `ConfirmRisky` or Letta's
`FsSandboxPolicy` - it is model-as-judge (*"background safety checks that
verify actions align with your request"*), which per the §Tiered taxonomy in
`references/concepts/guardrails.md` is the **most expensive and least
deterministic** check tier, used here as the primary gate of the
second-loosest mode rather than as a cheap first layer. `[docs]` + `[inferred]`
analysis from the pattern comparison.

**Hooks** are a **deterministic** enforcement mechanism distinct from
permission modes: an external script (shell/PowerShell) receives JSON on stdin
on a `PreToolUse`/`PostToolUse` event and returns
`{"hookSpecificOutput": {"permissionDecision": "deny"/...}}` to block a tool
call - code outside the model's control, exactly the "policy as data"
definition argued in `references/concepts/policy-as-data.md` (*"if a rule is
code-verifiable, that rule must not live in the prompt"*). The official
documentation even explicitly recommends hooks as the fallback when prose
instructions fail: *"If a skill seems to stop influencing behavior after the
first response... use hooks to enforce behavior deterministically."* -
Anthropic's own acknowledgement that description-based routing (axis 7) is
**not** deterministic and that hooks are the way out for cases needing
certainty. `[docs]` - `docs.claude.com/en/docs/claude-code/hooks.md` (the
`block-rm.sh`/`.ps1` examples, the `PreToolUse` → matcher → `if` → handler →
`permissionDecision` flow);
`docs.claude.com/en/docs/claude-code/skills.md` line ~505 (the hook
recommendation quotation).

## 7. Capability routing & policy

**Pure prose + model judgement - this KB's canonical example of the pattern,
and where its weakness is most concretely visible through real numbers from
the official documentation.**

The mechanism: each skill (`SKILL.md`, the open Agent Skills format) has a
`description` field (and an optional `when_to_use`) in its YAML frontmatter.
*"Claude uses this to decide when to apply the skill... Put the key use case
first: the combined `description` and `when_to_use` text is truncated at
**1,536 characters** in the skill listing to reduce context usage."* This is
the same *progressive disclosure* pattern as `deepagents`'
`SkillsMiddleware`: metadata (name + description, trimmed to a fixed character
budget) is loaded into the initial listing, with the full `SKILL.md` content
loaded only when the model chooses to invoke it. `[docs]` -
`docs.claude.com/en/docs/claude-code/skills.md` lines 323-324 (quoted exactly,
including the 1,536 figure).

**Weakness 1 - instruction dilution, with real numbers**: the skill listing
budget is shared among every loaded skill (`skillListingBudgetFraction`,
defaulting to a small fraction of the context; the alternative configuration:
`SLASH_COMMAND_TOOL_CHAR_BUDGET`, `skillListingMaxDescChars`). The more skills
installed, the fewer description characters available per skill before
truncation - exactly the "the 47th rule weakens the salience of 1-46"
mechanism argued in `references/concepts/policy-as-data.md` §Problem, except
here it isn't a metaphor: there is a real character count being cut
(`skillListingMaxDescChars`, defaulting to 1,536 combined across `description`
+ `when_to_use`) and an explicit configuration mechanism for *reducing*
dilution (marking low-priority skills as `"name-only"` in `skillOverrides` so
other skills get more budget). That this mitigation feature **exists** proves
Anthropic's own team recognises dilution as a real problem, not a hypothetical
one. `[docs]` - `docs.claude.com/en/docs/claude-code/skills.md` line ~1041
(the `skillListingBudgetFraction`, `skillOverrides`, `skillListingMaxDescChars`
quotation).

**Weakness 2 - language coupling**: no neutral code mechanism
(`intents: [research.legal]`) was found in the Skills documentation read -
matching a `description` to a user request runs purely through the model
reading the description text in whatever language it was written. The
consequence is explained in `references/concepts/skill-composition.md`
§`intents` uses neutral codes: a skill's language coverage is bound to how
completely its `SKILL.md` author wrote phrase variants in each supported
language - adding a new language means rewriting or extending the
`description` of every relevant skill, not extending one central classifier.
Claude Code has no intent classification layer separate from skill selection
itself (routing = one step: the model reads the description → the model
decides) - exactly the "native `SkillsMiddleware`" mechanism that
`skill-composition.md` §Trade-offs contrasts with this KB's neutral code
approach. `[inferred]` - from the absence of any separate classifier/intent
mechanism in `skills.md`; `[docs]` for the underlying mechanism
(description-only routing).

**The contrast with other systems in the grid**: OpenHands
(`skills/trigger.py`, see `openhands.md`) puts part of the routing decision in
deterministic code (`KeywordTrigger`/`PathTrigger`, matched through the
`_keyword_matches`/`path_matches_glob` functions) - skill triggering isn't
100% model judgement. `deepagents` and Letta (`letta.md`) are both purely
model judgement like Claude Code. LiteLLM (`litellm.md`) does no skill routing
at all - its routing (model/deployment) is entirely algorithmic through
`routing_strategy`. Claude Code, along with `deepagents` and Letta, sits at
the "leave it all to model judgement" extreme of the axis 7 spectrum - easy to
extend (a new skill = a new file, with no central taxonomy/registry to
maintain) but not deterministically testable and prone to dilution as the
skill count grows, exactly the trade-off recorded in `skill-composition.md`
§Trade-offs. `[inferred]` - a synthesis across this grid's files, not a new
claim about one system.

## Sources

Every quotation was fetched with `curl -sL` from the raw `.md` version of the
official documentation (`docs.claude.com`) rather than through HTML rendering
or a third-party summary, on 2026-08-23:

- `docs.claude.com/en/docs/claude-code/sub-agents.md` (1054+ relevant lines,
  mostly read) - the "Built-in subagents" section (the
  `Explore`/`Plan`/`general-purpose`/`Other` table), "Quickstart: create your
  first subagent", the quotations *"Each subagent runs in its own context
  window..."*, *"The subagent summarizes its results..."*, *"Claude uses each
  subagent's description to decide..."*
- `docs.claude.com/en/docs/claude-code/skills.md` (1054 lines, mostly read) -
  lines 69-110 (the quickstart, the frontmatter example), lines 133-165
  (nested-directory tiered skills), lines 322-328 (the frontmatter field
  table: `description`, `when_to_use`, `user-invocable`), lines 458-511
  (`disable-model-invocation`, `allowed-tools`, trust boundaries), lines
  501-505 (auto-compaction + skills, the hook recommendation), line 1041 (the
  listing budget, `skillOverrides`, `skillListingMaxDescChars`)
- `docs.claude.com/en/docs/claude-code/permissions.md` (592 lines, mostly
  read) - lines 74-92 (the six permission mode table, the
  `bypassPermissions` warning)
- `docs.claude.com/en/docs/claude-code/hooks.md` (3526 lines, partially read:
  ~150 lines around the `PreToolUse` examples) - the hook resolution flow, the
  `block-rm.sh`/`.ps1` examples, the
  `hookSpecificOutput.permissionDecision` format

An explicit honesty note (repeated from this file's opening): **no source file
was read for this system** - Claude Code is closed source. All the axes above
are labelled `[docs]` (verbatim quotations of official documentation) or
`[inferred]` (conclusions marked explicitly as conclusions rather than cited as
verified fact). Documentation sections not read (`agent-view`,
`cross-session-messaging`, `agent-teams`, the `context-window` visualisation,
the full `permission-modes` detail page, the full `settings-reference`) are
referenced only by name through cross-links on the pages read; their contents
were **not** verified - no claim is made about them.
