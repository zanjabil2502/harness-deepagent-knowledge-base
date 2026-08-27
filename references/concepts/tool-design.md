# Tool design

## Problem

An agent's tool surface usually grows organically: every new feature
"needs a new tool", until the model must choose among dozens or hundreds
of similar tool definitions on every turn. This isn't merely an aesthetic
problem with a long list - each extra tool enlarges the prompt (every
tool's schema and description is sent to the model on every call, see
[`context-engineering.md`](context-engineering.md)), enlarges the choice
space the model must judge per turn (more similar candidates = a greater
chance of picking the wrong one), and multiplies the points that
guardrails must cover (`per-role allowlist` in
[`guardrails.md`](guardrails.md) point 3 scales linearly with tool count).

The opposite direction - a few very broad tools (one `execute` tool that
can "do anything") - has the mirror problem: the model must construct
more complex, free-form arguments (arbitrary shell commands, arbitrary SQL
queries) for every call, argument validation becomes far harder (an
`args_schema` for "an arbitrary command string" validates essentially
nothing beyond "this is a string"), and the blast radius of one wrong
argument is far larger because the tool itself constrains nothing - the
constraint depends entirely on the argument content the model produces.
There is no single answer to "how many tools" - the right question is an
explicit trade-off between those two extremes for each class of capability
exposed.

## Pattern

### The granularity axis: many-narrow vs few-broad

| | Many narrow tools | Few broad tools |
|---|---|---|
| Example | `create_file`, `read_file`, `list_files`, `delete_file`, `move_file`, ... one tool per operation | `execute` (one name, running any shell command or code) |
| Argument validation | A narrow, specific schema per tool - `path`, `content` are type/format validated at the schema | Minimal/generic schema (`command: str`) - the real validation (if any) must happen inside the handler, not in the schema |
| Model choice burden | The model picks from a long list of similar tools; the more tools, the higher the chance of picking a similar-but-wrong one | The model needn't pick the right tool (there is only one), but must construct the right argument itself - the burden shifts from "choose correctly" to "compose correctly" |
| Blast radius of a mistake | Bounded by the tool's own shape - `delete_file` can only delete the one file named explicitly in its argument | Unbounded by the tool - `execute("rm -rf /")` is schema-valid and intent-wrong; guardrails/sandbox must close what the schema doesn't |
| Prompt cost | Every tool's schema+description is sent on every call - grows linearly with tool count | Stays small - one tool definition regardless of how broad its capability |
| Granular approval (HITL) | Possible per operation type (`interrupt_on={"delete_file": ...}` without disturbing `read_file`) - see [`human-in-the-loop.md`](human-in-the-loop.md) | Only per that broad tool's name - every `execute` call enters the same approval whether it contains a harmless `ls` or a destructive `rm -rf`; it can be narrowed with an `InterruptOnConfig.when` predicate over argument content, but that moves the operation distinction into application code (command parsing) rather than into the tool schema the model sees |

### A heuristic, not a fixed rule

The right granularity isn't a property of an individual tool but of the
**capability class** being exposed:

- **Split tools when the operations need different policies** - if
  `read_file` may be called freely but `delete_file` requires approval
  (`guardrails.md` point 3), the two **must** be separate tools; a single
  `file_op(action, path)` combining them forces the approval gate to read
  the `action` argument before knowing whether to stop - policy moves from
  declarative (the tool's name) to imperative (read the argument),
  precisely the disease that `guardrails.md` §Policy must not live only in
  the prompt rejects elsewhere.
- **Combine tools when the operation class genuinely needs legitimate
  breadth** - code execution is the canonical case: listing every possible
  execution operation as its own tool (`run_python`, `run_shell`,
  `run_node`, ...) doesn't close the space that is actually open (the code
  being run can still do anything in that language) - splitting merely
  lengthens the tool list without adding real safety. This is where "few
  broad tools" wins: one `execute` tool plus sandboxing/scoping at
  *runtime* (not in the schema) is honest enforcement about where the
  boundary truly lies.
- **A correct tool name with the wrong capability is the most expensive
  class of defect** - a tool called `read_file` that quietly also writes
  (because its implementation was merged with `write_file` behind one
  handler "to stay DRY") passes any review that only reads tool names in
  an allowlist. Tool granularity isn't only about count, but about a tool
  name **honestly reflecting** the scope of its capability - a role
  allowlist (`guardrails.md` point 3) is only as safe as this assumption.

## Trade-offs

- **Many narrow vs few broad tools** - covered in full in the §Pattern
  table; in short: narrow gives granular control (per-operation approval,
  strict validation) at the cost of a large tool surface and model choice
  burden; broad gives a small surface and flexibility (no need to enumerate
  every operation upfront) at the cost of moving validation and the
  approval gate into the handler/sandbox, no longer obtained free from the
  tool's shape.
- **Detailed vs terse tool descriptions** - detailed descriptions (usage
  examples, explicit constraints in the tool docstring) help the model pick
  correctly and fill arguments correctly, but add tokens sent on every call
  for a tool that may not be used that turn; terse descriptions are cheap
  but raise the chance of the model picking wrong among similar tools -
  the same trade-off as progressive disclosure for skills
  (`skill-composition.md`), just at the tool layer rather than the skill
  layer.
- **A strict schema (every field Pydantic-validated) vs a loose one (free
  `dict`/`str`)** - a strict schema rejects malformed arguments before the
  handler runs at all (fail-closed for free, see `guardrails.md` point 3
  "Tool argument validation"), but must be redefined whenever a field
  changes; a loose schema is flexible for tools whose arguments genuinely
  vary (`execute`) but moves the entire validation burden into the handler
  - and if it isn't written there explicitly, there is no validation at
  all.

## In deepagents

`deepagents` is itself a concrete instance of the "few broad tools, by
design" decision at its filesystem/execution surface - not merely theory:

- The built-in tools from `FilesystemMiddleware` - `ls`, `read_file`,
  `write_file`, `edit_file`, `glob`, `grep`, and `execute` - keep
  `execute` as **one name** even though its implementation changes
  entirely with the backend installed (`StateBackend` vs
  `LocalShellBackend` vs a third-party sandbox). The model never sees more
  than one execution tool no matter how differently it behaves underneath.
  `[code]` - cited from
  [`../systems/deepagents.md`](../systems/deepagents.md) §3
  (`deepagents/backends/protocol.py`).
- `execute` **only appears** when the backend implements
  `SandboxBackendProtocol` - for non-sandbox backends,
  `FilesystemMiddleware` filters it out entirely before it reaches the
  model (not a tool that exists and then refuses, a tool that is never
  seen). This is the same pattern as §Pattern above: breadth of capability
  (`execute` can run anything) is balanced not by splitting it into narrow
  tools, but by controlling **whether the tool exists at all** based on
  the installed backend. `[code]` - cited from
  `../systems/deepagents.md` §3, §6 (`THREAT_MODEL.md`: *"the execute tool
  is filtered out by FilesystemMiddleware when the backend does not
  implement SandboxBackendProtocol"*).
- `tools=[...]` on `create_deep_agent` is **additive** - custom tools
  registered by the application are always merged with the built-in
  filesystem/execution tools, never replacing them. This matters for an
  application's granularity decisions: adding a narrow domain tool (e.g.
  `send_invoice(customer_id, amount)`) does not automatically remove the
  built-in broad tool (`execute`) - if a team wants that broad tool
  unavailable to a given agent, the only official path is
  `HarnessProfile.excluded_tools`, not simply omitting it from `tools=`.
  `[code]` - cited from `../systems/deepagents.md` §3
  (`deepagents/graph.py` lines 331-339, 787-788).
- Granular per-tool approval (§Pattern, the "Granular approval (HITL)"
  row) maps directly onto
  `interrupt_on={"tool_name": True | InterruptOnConfig}` - per tool
  **name**, not per argument content. A direct consequence of
  granularity: one broad tool like `execute` given
  `interrupt_on={"execute": True}` halts **every** `execute` call for
  approval, including harmless read-only commands - splitting it into
  narrower tools (e.g. `execute_readonly` vs `execute_write`, where the
  backend can distinguish them) is the only way to get granular approval
  without reading argument content inside the gate itself. `[code]` -
  cited from [`../systems/deepagents.md`](../systems/deepagents.md) §6.

## Sources

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §3
  (Tool surface), §6 (Safety gate) - a tier-1 reference verified against
  `deepagents==0.7.8`, cited directly without re-reading the source in
  this task.
- `[code]` [`guardrails.md`](guardrails.md) point 3 (Tool/action) - the
  basis for the per-role allowlist and argument validation claims; not
  re-argued in this file.
- `[code]` [`context-engineering.md`](context-engineering.md) - the basis
  for the claim that prompt cost grows with tool count.
- `[code]` [`skill-composition.md`](skill-composition.md) - the basis for
  the progressive-disclosure analogy in the tool description trade-off.
- `[code]` [`human-in-the-loop.md`](human-in-the-loop.md) - the basis for
  the granular per-tool-name approval claim; its mechanism is not repeated
  here.
