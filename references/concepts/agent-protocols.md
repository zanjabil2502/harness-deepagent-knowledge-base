# Agent protocols (ACP, A2A) — the harness as an endpoint

## Problem

Almost every harness decision is made with one caller in mind: a human,
through a UI we built ourselves. As soon as **someone else** calls the agent
— a code editor, another agent, a scheduler — four things that were implicit
become contracts that have to be stated:

- **Identity** — who is asking, and on whose authority. In our own UI the
  answer comes from the login session. In a protocol, nothing carries it
  unless we install it.
- **Session continuity** — what groups turns into one conversation. Each
  protocol has its own identifier, and almost always **two**, not one: one
  for the conversation, one for the request. Mapping them wrongly onto the
  internal `thread_id` either fragments history or mixes it between callers.
- **Gates** — where approval happens, and **what approval shape the caller
  can render**. This is the most frequently missed: the harness may install
  exactly the right pause, but if the caller has no way to display it, that
  pause is a deadlock rather than a gate.
- **The capability surface** — who decides which tools exist. In some
  protocols the answer isn't the agent's author but the **client**.

Getting these four wrong isn't a bug caught in testing. A protocol freezes
its shape, so a mistaken decision can't be patched later without breaking
compatibility with everything already connected.

The second problem is quieter: **an endpoint that exists by default.** A
platform enabling a protocol surface by default makes "who may call this
agent" a decision nobody ever took.

## Pattern

### Three directions, not three protocols

What distinguishes these protocols isn't their features but **where the call
arrow points**. Once the direction is clear, the remaining decisions follow:

| | The agent **consumes** | The agent **is driven** | The agent **is called** |
|---|---|---|---|
| Example | MCP | ACP | A2A |
| Counterpart | a tool server | a human's editor/IDE | another agent (a machine) |
| Usual transport | stdio / HTTP | **stdio**, a subprocess of the editor | HTTP, JSON-RPC |
| Identity | ours, to the server | the human running the editor | **none built in** |
| Session | the server connection | the editor session, one process | a conversation id + a task id |
| Gate | we install it | rendered by the editor, in a limited shape | no human gate |
| Who chooses tools | the agent's author | **partly the client** | the agent's author |

[`mcp.md`](mcp.md) already covers the first column. The other two are this
file's subject, and both invert assumptions the first column relies on.

### Identity doesn't come from the protocol

None of the three carries an end-user identity as part of the protocol. The
consequence differs per direction:

- **Driven by an editor** — the agent process is run by the human
  themselves, on their machine, with their access rights. Identity is
  implicit and correct, but that also means its blast radius is that
  person's blast radius: no layer restricts the agent more narrowly than its
  user unless we install one.
- **Called by another agent** — there is no human at all. All that arrives
  is an HTTP request. Authentication, authorisation, and attribution
  **must** be built at the transport layer, and "on whose behalf is this
  agent acting" has no built-in answer. For a `user_id`-based multi-user
  pattern, this means an agent-to-agent endpoint must not inherit the
  authorisation path used by the UI — it needs its own.

### Continuity is always two identifiers

Agent protocols distinguish the **conversation** from the **request**, while
the harness usually has one concept (`thread_id`). The mapping has to be
decided deliberately: the conversation id → `thread_id`, the request id →
one run within that thread. Equating them makes every request a new
conversation (history lost) or makes every caller share one thread (history
mixed — and on a multi-user system that is a data leak, not merely a display
mess).

The party starting a conversation usually **omits** its id on the first
request and receives a server-generated one, returning it on every
subsequent turn. So the server holds authority over the id and the client is
responsible for carrying it — two roles that must be clear before anyone
writes code.

### Gates are bounded by what the caller can render

This is the most important inversion. Normally the harness decides its
approval shape. When driven by a protocol, **the protocol decides**, and the
harness must adapt.

Editor protocols generally recognise only a fixed decision set — approve,
reject, edit — bound to a single tool call. A free-form pause ("the agent
asks something and waits for a prose answer") has no representation. The
design consequence: **every stopping point must take the shape of structured
approval over a tool call**, not a dialogue. If a flow genuinely needs to
ask, that has to become a schema'd tool rather than a free `interrupt`.

In the agent-to-agent direction, conversely, there is no human at all. Every
gate must be automatic — policy, limits, validation — because nobody is
going to press a button.

### The capability surface can come from the caller

In editor integrations, the client commonly injects its own tool servers when
opening a session. So the effective tool list = the tools we registered
**plus** whatever the editor brings, and the agent's author doesn't control
the second part. Every piece of reasoning about tool surfaces in
[`tool-design.md`](tool-design.md) and about exclusion in
[`../deepagents/middleware.md`](../deepagents/middleware.md) applies to a set
only known at runtime.

### Capability advertisement is disclosure

The agent-to-agent direction usually includes a discovery mechanism: a public
document naming the agent, its description, and a **list of its
capabilities** so others know how to call it. That is its purpose — but it
also means the harness's internal structure becomes metadata retrievable by
anyone who can reach the endpoint. A skill name referencing an internal
system, or a description leaking a business process, is published there too.

### A default endpoint is a decision nobody took

If a platform enables a protocol surface by default, the first gate isn't
approval but **whether that endpoint exists at all**. This enters
[`guardrails.md`](guardrails.md)'s inventory as an enforcement point of its
own with a **fail-open** failure mode: nothing is wrong, nothing errors, only
a surface left open because nobody closed it.

## Trade-offs

- **One process per session vs one server for many sessions.** The
  subprocess model (an editor running the agent as a child process, talking
  over stdio) gives the strongest isolation available for free: each session
  has its own memory, no shared state, no network surface. Its cost: nothing
  survives the process unless deliberately made to, no horizontal scaling,
  and no place for centralised policy. The HTTP server model is its opposite
  on every axis — including on isolation, which becomes our problem.
- **Continuity owned by the protocol vs owned by us.** Using the protocol's
  session id directly as a storage key is simplest and immediately wrong on
  a multi-user system: that id comes from the client, so it identifies the
  conversation, not its owner. Mapping it to an internal id adds a table and
  a step, but separates "who" from "which conversation" — the same
  separation [`isolation-and-scoping.md`](isolation-and-scoping.md) demands.
- **Interop vs the subset actually installed.** The same warning as
  `mcp.md` §"Real clients implement a subset of the spec": supporting a
  protocol doesn't mean every client supports every feature of it. The
  features the harness uses must be limited to the intersection target
  clients genuinely render, and that is learned by trying, not by reading
  the specification.
- **Being callable vs the attack surface.** An agent-to-agent endpoint is
  the most direct way to turn an agent into a reusable component, and
  equally the most direct way to expose its entire capability set to
  anything that can send HTTP. The value is real; the decision must be
  deliberate.

## In deepagents

**Both live outside the `deepagents` package, and they are different in
kind.** ACP is a companion package wrapping an agent; A2A isn't a library
feature at all but an endpoint belonging to the deployment server.

### ACP — `deepagents-acp`

A separate package, `deepagents-acp`, latest version **0.0.10** — a 0.0.x
number to be read at face value. Its dependencies:
`agent-client-protocol>=0.10.1` and **`deepagents` with no version bound at
all** (`[code]` — the `deepagents-acp` 0.0.10 PyPI metadata). With no
constraint, resolution can pull any deepagents version; in a test venv it
pulled 0.7.9 while this KB pins 0.7.8. Pin it yourself if used seriously.

Its usage shape: `AgentServerACP(agent)` then `await run_agent(server)`,
running over **stdio** as a subprocess launched by the editor. `[docs]` —
`../upstream/deepagents-docs/acp.md` lines 32, 54-55. The clients named:
Zed, JetBrains, VS Code through an extension, Neovim. `[docs]` — `acp.md`
lines 226-229.

What isn't readable from the documentation, and shapes the design:

- **The agent may be a factory, and that isn't a detail.**
  `AgentServerACP` accepts a `CompiledStateGraph` **or** a
  `Callable[[AgentSessionContext], CompiledStateGraph]`, where
  `AgentSessionContext` carries `cwd`, `mode`, and `model`. This is the only
  route to building a different harness per editor session — a different
  working directory, a different permission posture, a different model. The
  `modes=` and `models=` parameters are **only valid when the agent is a
  factory**; passing them with a compiled graph raises `ValueError`.
  `[code]` — `deepagents_acp/server.py:156-206`.
- **The permission posture is a session option a human changes from the
  editor UI**, not a configuration constant: modes are rendered as a
  selector described as "Controls how the agent requests permission".
  `[code]` — `server.py:222-257`. This is
  [`policy-as-data.md`](policy-as-data.md) surfacing in the interface.
- **ACP rejects free-form `interrupt()`.** If the agent raises an interrupt
  whose value isn't a `dict` with `action_requests`, the server raises
  `RequestError(-32600)` with a message calling it an "ACP limitation… ACP
  only supports human-in-the-loop permission prompts with a fixed set of
  decisions (approve/reject/edit)". `[code]` — `server.py:972-994`. This is
  the concrete form of §"Gates are bounded by what the caller can render":
  `HumanInTheLoopMiddleware`-style HITL works, free dialogue doesn't.
- **"Always allow" is granular per command type, and only for the process's
  lifetime.** The approval options offered: `allow_once`, `reject_once`, and
  `approve_always` which — for the `execute` tool — remembers the **command
  type** extracted from the command rather than the exact command. That
  memory lives in `_allowed_command_types[session_id]`, a dict in process
  memory. `[code]` — `server.py:214-216, 1150-1215`. So an "always allow
  `git`" decision is lost when the editor closes the agent, and is never
  stored anywhere auditable.
- **`write_todos` is auto-approved** when it is an update to an existing
  plan, and the plan is rendered into the editor's plan panel. `[code]` —
  `server.py:489-541, 1118-1120, 1160-1170`.
- **Durable sessions are opt-in, not the default.** `load_sessions=False` by
  default; enabling it advertises `session/load` to clients and **requires a
  checkpointer surviving a server restart** — while every documentation
  example uses `MemorySaver()`. `[code]` — `server.py:169-192, 286-302`;
  `[docs]` — `acp.md` lines 40, 51.
- **All session state lives in process memory**: `_session_cwds`,
  `_session_mcp_servers`, `_session_modes`, `_session_models`,
  `_session_plans`, `_allowed_command_types` — all plain dicts keyed by
  `session_id`. `[code]` — `server.py:207-216`. Consistent with the
  one-process-per-editor model, and not movable to a multi-process topology
  without replacing this layer.
- **The client injects its own MCP servers** through
  `new_session(mcp_servers=...)`. `[code]` — `server.py:304-315`. The
  effective tool surface is therefore known only once the session opens.
- One concurrency subtlety the source records: the checkpoint underlying an
  update **may not be visible** until the stream iterator closes, so reading
  state inside the iterator can return a stale pre-interrupt snapshot.
  `[code]` — `server.py:996-1000`.

### A2A — not deepagents, but Agent Server

The A2A page under the deepagents section is really a LangSmith document (its
source is `src/langsmith/server-a2a.mdx`). What implements the protocol is
**Agent Server / `langgraph-api>=0.4.21`**, at the `/a2a/{assistant_id}`
endpoint. `[docs]` — `../upstream/deepagents-docs/a2a.md` lines 9-11, 35,
445.

- **The endpoint is on by default.** Turning it off means writing
  `{"http": {"disable_a2a": true}}` in `langgraph.json`. `[docs]` —
  `a2a.md` lines 426-435. This is §"A default endpoint is a decision nobody
  took" in concrete form: deploy with Agent Server and the agent is callable
  by other agents unless someone deliberately closes it.
- **Capability discovery is public**:
  `GET /.well-known/agent-card.json?assistant_id={id}` returns the name,
  description, **skill list**, input/output modes, and endpoint URL.
  `[docs]` — `a2a.md` lines 23-29. That card's contents are disclosure;
  treat skill naming as public-facing text.
- **Three methods**: `message/send`, `message/stream` (SSE), `tasks/get`.
  `[docs]` — `a2a.md` lines 17-19.
- **Two identifiers, exactly the §Pattern shape**: `contextId` groups the
  conversation, `taskId` marks each request. The first request omits both
  and the server generates them; subsequent turns must carry them back. The
  server maps `contextId` → `thread_id`. `[docs]` — `a2a.md` lines 57-64,
  270-272.
- **A state shape requirement**: the agent must have a `messages` key in its
  state to be compatible with A2A "text parts". `[docs]` — `a2a.md` line 55.
- One placement trap named explicitly: `thread_id` goes in the JSON-RPC
  payload's **top-level** `metadata`, not inside `params`. `[docs]` —
  `a2a.md` line 368.

Worth noting about the page's quality: its code example uses a raw
`StateGraph` with `gpt-3.5-turbo` and direct OpenAI calls — **no
`create_deep_agent` anywhere**. `[docs]` — `a2a.md` lines 68-152. So the page
shows how to make an A2A-compatible LangGraph graph, not how to expose a deep
agent; most of the rest is about unifying traces across agents in LangSmith.

## Sources

- `[code]` `deepagents-acp==0.0.10` — `deepagents_acp/server.py`, read from
  a separate venv (not `../recipes/.venv`, which was deliberately left
  untouched). To reproduce:
  `uv venv acpv && VIRTUAL_ENV=acpv uv pip install "deepagents-acp==0.0.10"`,
  then read `acpv/lib/python3.*/site-packages/deepagents_acp/server.py`.
- `[code]` The `deepagents-acp` 0.0.10 PyPI metadata
  (`https://pypi.org/pypi/deepagents-acp/json`, fetched as raw JSON) —
  `requires_dist` lists `deepagents` with no version bound, the basis for
  the pinning warning in §In deepagents. Real resolution in the test venv
  pulled `deepagents` 0.7.9.
- `[docs]` [`../upstream/deepagents-docs/acp.md`](../upstream/deepagents-docs/acp.md)
  — a verbatim snapshot; the stdio mode, usage shape, client list, and
  `MemorySaver` in every example.
- `[docs]` [`../upstream/deepagents-docs/a2a.md`](../upstream/deepagents-docs/a2a.md)
  — a verbatim snapshot; the entire A2A section is sourced here, including
  `disable_a2a`, the agent card, `contextId`/`taskId`, and the `messages`
  key requirement.
- `[code]` [`mcp.md`](mcp.md) §Pattern, §Trade-offs — the consumption
  direction and the "real clients implement a subset of the spec" warning,
  generalised to the other two directions in this file; referenced without
  being rewritten.
- There are no `[inferred]` claims in this file: every technical point has a
  source citation or a snapshot line reference.
