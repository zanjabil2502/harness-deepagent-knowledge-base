# MCP (Model Context Protocol)

## Problem

Before MCP, every (agent harness, external data source/tool) pair needed a
custom integration: different code to connect agent X to Google Drive, agent
X to an internal Postgres, agent Y to Google Drive again (a duplicate
integration because the harness differs) — the combinations grow N×M, and
each integration carries its own implicit assumptions about connection
lifecycle, authentication, and tool description shape. MCP standardises the
protocol side: one MCP server for Google Drive works with any agent harness
that has an MCP client, with no per-pair integration.

The second problem, which becomes an explicit warning for this file: **the
MCP specification and what a given client implements are not the same
thing.** The spec defines optional capabilities (`sampling`, `elicitation`,
`roots` on the client side) that a server may try to use — but client
support for those optional capabilities is highly uneven across the real
ecosystem. "Supports MCP" tells you nothing about which capabilities
actually work in a given client; that has to be checked per client, not
assumed from nominal spec compliance.

## Pattern

### MCP as an interop standard, not an implementation

MCP defines a JSON-RPC protocol between a **client** (part of the agent
harness) and a **server** (a process/endpoint exposing
tools/resources/prompts) — not a library or a single product. An MCP server
exposes three main capability categories: `tools` (functions the model can
call), `resources` (readable content, e.g. files/database rows), `prompts`
(ready-made prompt templates). `[docs]` — the MCP Specification, cited via
WebFetch from
`modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle`.

### Server lifecycle: init → operation → shutdown

Three mandatory phases, in normative order:

1. **Initialization** — the client **MUST** begin with an `initialize`
   request carrying the protocol versions it supports, its client
   capabilities (`roots`/`sampling`/`elicitation`), and its implementation
   info. The server replies with its own capabilities
   (`tools`/`resources`/`prompts`/`logging`/`completions`) plus
   implementation info. The client then **MUST** send an `initialized`
   notification before normal operation begins. The client **SHOULD NOT**
   send other requests (besides ping) before the server answers
   `initialize`; the server **SHOULD NOT** send other requests (besides
   ping/logging) before receiving `initialized`. `[docs]` — quoted directly
   from the spec (*"The client MUST initiate this phase by sending an
   `initialize` request"*, *"the client MUST send an `initialized`
   notification"*).
2. **Version & capability negotiation** — the client sends the protocol
   versions it supports (ideally the latest it knows); the server replies
   with the same version if supported, or another version it does support
   otherwise. The capabilities negotiated in this phase bound what **may**
   be used during the Operation phase — using a capability that wasn't
   successfully negotiated is a protocol violation, not merely suboptimal.
   `[docs]`
3. **Operation** — normal exchange (`tools/list`, `tools/call`,
   `resources/read`, etc.), bounded by the negotiated capabilities.
4. **Shutdown** — for the `stdio` transport: the client closes the server
   process's input stream, waits for the server to exit, sends `SIGTERM` if
   it doesn't exit in reasonable time, and `SIGKILL` as a last resort. For
   HTTP transports: shutdown = closing the relevant HTTP connection.
   `[docs]`

### Transport: `stdio` vs HTTP (`streamable_http`/`sse`)

| Transport | Suited to | Authentication |
|---|---|---|
| `stdio` | A local MCP server, run as a subprocess on the same machine as the client (e.g. a local developer tool) | Does **not** use MCP's OAuth spec — credentials come from the process environment `[docs]` |
| `streamable_http` / `sse` | A remote MCP server (a third-party SaaS, an internal service on a different network) | OAuth 2.1 per request, see §Per-user configuration |

`[docs]` — the MCP Authorization spec: *"Implementations using an STDIO
transport SHOULD NOT follow this specification, and instead retrieve
credentials from the environment."*

### Per-user configuration

For a multi-user deployment (this project's assumption), one remote MCP
server is often shared by many users while **its access credentials are
per user** (e.g. a Google Drive MCP server representing each user's own
Drive account, not one shared account). The protocol mechanism that closes
this is OAuth 2.1 at the HTTP transport level, **not** static server-level
configuration:

- Every MCP request carries `Authorization: Bearer <access-token>` — the
  token **MUST** be included on every HTTP request, even within the same
  logical session (there is no "log in once, the token is implicit for
  subsequent requests" at the transport level). `[docs]` — the MCP
  Authorization spec §Token Requirements.
- The token **MUST** be validated by the server against its own audience
  (the token's audience claim must name that MCP server, through RFC 8707's
  `resource` parameter) — the server **MUST reject** a token that is valid
  but issued for a different resource. `[docs]`
- **Token passthrough is explicitly forbidden**: if the MCP server itself
  calls another upstream API, it **must not** forward the token it received
  from the MCP client to that upstream API — it has to be its own OAuth
  client upstream with a separate token. This is a concrete instantiation
  of the *confused deputy* already named in [`security.md`](security.md)
  (§Problem: an agent using one service identity's full authority for all
  users rather than authority narrowed to the user and the action being
  requested) — that file owns the general confused-deputy/narrow-token-scope
  pattern; the MCP Authorization spec is this protocol's specific case,
  enforcing it as **mandatory** rather than as optional good practice.
  `[docs]` — *"MCP server MUST NOT pass through the token it received from
  the MCP client"*.
- Practically: per-user credentials (user A's own Drive OAuth token, not a
  server-wide one) live as part of the same **scope object** already used
  by [`isolation-and-scoping.md`](isolation-and-scoping.md) for other data
  — the per-user MCP connection configuration resolves from the same
  `(user_id)`/`(tenant_id, user_id)`, not through a separate mechanism.

### Real clients implement a subset of the spec

Client-side capabilities declared optional in the spec (`roots` — the server
can ask for the list of directories it may access; `sampling` — the server
can ask the client to run an LLM call on the server's behalf; `elicitation`
— the server can ask the user for extra input mid-interaction) have uneven
support across real clients. `[inferred]` — a widely observed general
pattern of the MCP ecosystem (optional protocol capabilities are rarely
implemented uniformly across clients); the specific claim "client X doesn't
support capability Y" was not verified in this task for any client beyond
`deepagents`/`langchain` (see `## In deepagents`; no
`sampling`/`roots`/`elicitation` support was found in the installed
packages). The design consequence: **do not** build a product feature
depending on an MCP server being able to use `sampling`/`elicitation`
against the client without verifying that the production client in use
actually implements it — the failure is silent (the server politely declares
that capability during negotiation, its request is sent, but a client that
doesn't implement it may respond with an error or ignore it depending on the
implementation, which is not something guaranteed to be uniform across
clients).

## Trade-offs

- **MCP vs a custom integration per source** — MCP avoids the N×M
  duplication above and brings an ecosystem of ready-made servers, at a
  cost: an extra protocol layer (JSON-RPC, capability negotiation,
  lifecycle) for a case that really needs one simple API call — a direct
  custom tool (a `@tool` written once) remains cheaper for a one-off
  internal integration no other harness will ever use.
- **`stdio` vs remote HTTP** — `stdio` is simple (no network server needed,
  credentials from the environment) but bound to one machine/process,
  unsuited to a server shared by many agent instances or many users; remote
  HTTP scales correctly for multi-user (one MCP server serving many clients
  with per-user tokens) at the cost of an operational server whose uptime
  must be maintained and an extra security surface (the OAuth flow, token
  audience validation).
- **Trusting negotiated capabilities vs explicitly verifying against the
  production client** — trusting the protocol negotiation (if the server
  requests `sampling` and the client "supports MCP", assume it works) is
  simpler to develop but brittle at precisely the point named in §Pattern
  above; explicit verification (testing optional capabilities against the
  real production client before depending on them) costs more development
  time but closes the "the name is right, the capability isn't there"
  defect class, the most expensive kind to discover late.

## In deepagents

No native MCP integration was found in the `deepagents==0.7.8` or
`langchain==1.3.16`/`langgraph==1.2.11` installed for this task — there is no
`langchain-mcp-adapters` package and no `mcp` module of any kind in
`references/recipes/.venv/lib/python3.13/site-packages/`. `[code]` —
verified by `ls`ing the site-packages directory; nothing matching `*mcp*`
belongs to the MCP ecosystem.

The integration route available through the `langchain` ecosystem (a
separate package, **not** installed or verified directly in this task's
venv, cited `[docs]` from the official README):

- **`MultiServerMCPClient`** (the `langchain-mcp-adapters` package) —
  configured through a dict mapping server names to connection parameters
  (`command`/`args`/`transport: "stdio"`, or `url`/`transport: "http"`).
  Calling `await client.get_tools()` returns tool objects usable directly as
  the `tools=[...]` argument of `create_agent(...)` — the same usage shape
  as `tools=[...]` on `create_deep_agent(...)`, so mechanically MCP tools
  arrive through the same "additive custom tool" route described in
  [`tool-design.md`](tool-design.md) §In deepagents; there is no MCP-specific
  integration path in `deepagents` itself.
- Per-connection runtime headers (e.g. `"headers": {"Authorization":
  "Bearer TOKEN"}`) are the concrete route for §Per-user configuration above
  — the per-user token is injected into the MCP connection configuration,
  not hardcoded at server level.
- `handle_tool_errors` (default `True`) controls whether errors from an MCP
  tool call are caught and returned as an error `ToolMessage` (so the model
  can retry) or allowed to propagate as an exception.

Because none of this was verified directly against this task's
installation, the details above are labelled `[docs]` (the
`langchain-ai/langchain-mcp-adapters` README, cited via WebFetch from
`raw.githubusercontent.com/langchain-ai/langchain-mcp-adapters/main/README.md`)
— not `[code]` read from source, consistent with how
`../systems/deepagents.md` §Sources marks packages not installed in this
environment (`deepagents-cli`/`langchain_daytona`).

## Sources

- `[docs]` MCP Specification 2025-06-18, §Basic/Lifecycle — cited via
  WebFetch from
  `modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle`, for
  the `initialize`/`initialized` order, version & capability negotiation,
  and per-transport shutdown.
- `[docs]` MCP Specification 2025-06-18, §Basic/Authorization — cited via
  WebFetch from
  `modelcontextprotocol.io/specification/2025-06-18/basic/authorization`,
  for the OAuth 2.1 flow, the mandatory `Authorization: Bearer` header,
  token audience validation (RFC 8707), the token passthrough prohibition,
  and the `stdio` exception (credentials from the environment).
- `[docs]` The `langchain-ai/langchain-mcp-adapters` README — cited via
  WebFetch from
  `raw.githubusercontent.com/langchain-ai/langchain-mcp-adapters/main/README.md`,
  for `MultiServerMCPClient`, `load_mcp_tools`, the supported transports,
  and per-connection header configuration.
- `[code]` Verified by `ls`ing the contents of
  `references/recipes/.venv/lib/python3.13/site-packages/` — no MCP package
  is installed in this task's `deepagents==0.7.8` venv.
- `[code]` [`tool-design.md`](tool-design.md) §In deepagents — the basis
  for the claim that "MCP tools arrive through the same additive
  `tools=[...]` route".
- `[code]` [`security.md`](security.md) §Problem — the basis for the general
  confused-deputy pattern, not repeated in this file.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — the
  basis for the per-user scope object pattern, cited for §Per-user
  configuration.
