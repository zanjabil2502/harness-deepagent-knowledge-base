# browser-use

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. `browser-use/browser-use`, a Python library for agents
controlling a browser through CDP (screenshots + DOM). Chosen as the
**computer-use** exemplar per the T2 candidates in spec §10.

## Archetype

A pure **Computer-Use Agent (07)**: a look→click→verify loop, narrow but deep
tools (26 registered actions, see axis 3), and the most fragile of all against
untrusted page content (see axis 6, `sensitive_data`). `[code]` —
`browser_use/tools/service.py` (the `@self.registry.action(...)` count
confirmed through `grep -c` = 26).

## 1. Loop shape

Loop-until-done with **two independent limits**, not one: `max_steps` (default
**500**, passed to `Agent.run(max_steps=500)`) and `max_failures` (default
**5**, counted as `consecutive_failures` — **consecutive** failures, not
total). If `consecutive_failures >= max_failures`, the loop stops entirely (not
merely forcing `done`): *"Stopping due to {max_failures} consecutive
failures"*. `[code]` — `browser_use/agent/service.py` line 171
(`max_failures: int = 5`), 2508 (`max_steps: int = 500`), 2603-2617 (`while
self.state.n_steps <= max_steps`, the `consecutive_failures` check).

One turn (`Agent.step()`) is **three explicit phases**: `_prepare_context`
(take a screenshot + a browser state summary — *"Always take screenshots for
all steps"*, plus a dedicated `wait_if_captcha_solving()` pause before the
context is prepared) → `_get_next_action` (call the LLM) → `_execute_actions` →
`_post_process`, wrapped in a single `try/except`/`finally`
(`_handle_step_error`/`_finalize`) so one failed step doesn't contaminate the
next step's state. `[code]` — `browser_use/agent/service.py` lines 1029-1090
(`step()`, the start of `_prepare_context`).

When `max_steps` is reached, the harness does **not** let the model call
another tool: *"You reached max_steps - this is your last step. Your only tool
available is the 'done' tool. No other tool is available."* — enforced through
prompt injection on the final step, plus a budget warning
(`budget_ratio = steps_used / max_steps`) injected into the prompt before the
limit is reached. `[code]` — `browser_use/agent/service.py` lines 1542-1566.

## 2. Context

No message-history condenser/summariser was found in `agent/service.py`.
Instead, long-running working state is moved into a **virtual filesystem**
(`browser_use/filesystem/file_system.py`) — the agent writes and reads files
(e.g. progress notes, extraction results) through filesystem tools rather than
keeping everything in message history. That module also blocks binary
extensions (`UNSUPPORTED_BINARY_EXTENSIONS` — png/jpg/mp4/zip/exe/dll/etc.)
from being written through the file-write tool, restricting the filesystem
tools to text content. `[code]` — `browser_use/filesystem/file_system.py` lines
1-40.

## 3. Tool surface

**Few tools, narrow but deep** — exactly the pattern archetype 07 predicts:
`Tools.registry` (`browser_use/tools/service.py`) registers **26** actions
through the `@self.registry.action("<description>")` decorator, among them
`go_back`, `wait` (wait N seconds), and `find_text`/scroll-to-text (confirmed
through the `find_text` function name and the description *"Scroll to
text."*) — other actions (click-by-index, input-text, content extraction) are
in the same module but not all their function names were verified through grep.
`[code]` — `browser_use/tools/service.py` (the `@self.registry.action(` count
through `grep -c` = 26; grep without the `@self.` anchor returns 27 because it
also counts the generic public wrapper `self.registry.action(description,
**kwargs)` at line 2097, which is an external registration path rather than a
built-in action registration; 3 function names confirmed directly: `go_back`,
`wait`, `find_text`).

## 4. Delegation

No subagent/task-tool mechanism was found in `agent/service.py` (4166 lines,
partially read) — a flat architecture: one `Agent` controlling one
`browser_session`. `[inferred]` — from the absence of any subagent/delegation
import in the portion of the file read.

## 5. State & resume

`filesystem/file_system.py` (axis 2) doubles as scratchpad state.
`AgentHistory` (`self.history.save_to_file(file_path,
sensitive_data=self.sensitive_data)`) — the step history can be saved to a
file, with `sensitive_data` **filtered during serialisation** (no claim is
made about whether it is fully censored or merely marked — only that the
parameter is passed through). `[code]` — `browser_use/agent/service.py` line
3918.

`browser_use/sandbox/sandbox.py` — a separate isolation module (its name
confirmed through a listing, its contents unread) shows there is a path to
running a browser session in an isolated sandbox/cloud rather than only a local
browser — consistent with the "outside world" blast radius (this agent touches
the public web, making process/browser isolation important). `[code]` (the
listing) / `[inferred]` (its exact isolation scope).

## 6. Safety gate

There is no per-action approval gate (clicks/scrolls/navigation run
automatically with no human pause) — the primary mitigation is
**domain-scoped `sensitive_data`** plus **an explicit warning when a dangerous
configuration is detected at startup**:

```
⚠️ Agent(sensitive_data=••••••••) was provided but Browser(allowed_domains=[...])
is not locked down! ⚠️
☠️ If the agent visits a malicious website and encounters a prompt-injection
attack, your sensitive_data may be exposed!
```

Credentials in `sensitive_data` can be a per-domain dict
(`has_domain_specific_credentials = any(isinstance(v, dict) for v in
self.sensitive_data.values())`); if a domain pattern in `sensitive_data` isn't
covered by any pattern in `Browser(allowed_domains=[...])`, the harness warns
again separately. This is not a gate that blocks execution (the agent still
runs after the warning) — purely a fail-open log message, but one that
explicitly names the attack class (prompt injection from page content →
credential exfiltration) relevant to `references/concepts/security.md` and
`guardrails.md`. `[code]` — `browser_use/agent/service.py` lines 150, 385,
532-577.

## 7. Capability routing & policy

**There is no internal routing between modes/skills** — browser-use does one
thing (control a browser) and has no skill/subagent system for a model to
choose from. What is interesting: browser-use **wraps itself** as an Anthropic
skill format (SKILL.md) to be **consumed** by other harnesses —
`browser_use/skills/browser_use.py` produces the skill text (`skill_text`) with
install metadata (`"openclaw": {"requires": {"bins": ["browser-use"]},
"install": [{"kind": "uv", "package": "browser-use", ...}]}`) synced into a
`SKILL.md` file through the `scripts/sync_browser_harness_skill.py` script. So
capability routing for browser-use happens **in the calling harness** (e.g.
deepagents/Claude Code/OpenHands choosing when to load the "Browser Use" skill
through model judgement over that skill's description), not inside browser-use
itself. `[code]` — `browser_use/skills/browser_use.py` lines 1-30 (the
docstring + `OPENCLAW_METADATA_LINES`), `browser_use/skills/__init__.py`.

## Sources

The `browser-use/browser-use` repo was shallow-cloned (`git clone --depth 1`)
on 2026-08-23 and read directly as files:

- `browser_use/agent/service.py` (4166 lines total — **not** read in full) —
  the lines cited: 133 (the `Agent` class), 150, 171, 385 (the
  `sensitive_data`, `max_failures` parameters), 397, 532-577 (the domain-lock
  warning), 786, 1029-1090 (`step()`, the three phases), 1291, 1542-1582 (the
  `max_steps` budget warning & force-done), 2183-2248 (`take_step`),
  2444-2471, 2506-2627 (`run()`, the main loop, the `consecutive_failures`
  limit), 3918 (`history.save_to_file`), 4066-4073
- `browser_use/filesystem/file_system.py` — lines 1-40
  (`UNSUPPORTED_BINARY_EXTENSIONS`, the imports)
- `browser_use/tools/service.py` — the `@self.registry.action(` decorator
  count through `grep -c` = 26 (grep without the `@self.` anchor returns 27
  because it also counts the generic public wrapper
  `self.registry.action(description, **kwargs)` at line 2097); the `go_back`,
  `wait`, `find_text` function names confirmed through `grep -A1`
- `browser_use/skills/__init__.py`, `browser_use/skills/browser_use.py` —
  lines 1-30
- A directory listing (file/folder names, contents unread):
  `browser_use/sandbox/sandbox.py`, `browser_use/controller/`,
  `browser_use/mcp/`, `browser_use/beta/`, `browser_use/actor/`

An honesty note: `agent/service.py` is a 4166-line file, mostly unread — the
claims in this file are limited to the lines actually cited. The complete list
of 26 actions in `tools/service.py` was **not** verified one by one (only 3
function names were confirmed); the "narrow but deep tools" claim rests on the
total count (26) and the visible naming pattern rather than an audit of each
action's function. `browser_use/sandbox/sandbox.py` is mentioned through a
listing only; its exact isolation mechanism wasn't verified.
