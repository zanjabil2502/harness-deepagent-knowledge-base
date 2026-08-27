# Sandboxing

## Problem

The `execute` tool - code written by an LLM, run as a real shell command -
is the most dangerous tool surface in any harness. Unlike typed/schema'd
tools (read a file, call a specific API) whose arguments can be validated
before execution, a shell command's content can be anything the model
decides to write, and validating "is this command safe" is in general
undecidable. The question to answer isn't "how do we prevent dangerous
commands" (not guaranteeable in general) but **"if that command is
dangerous, how far can the damage spread?"** - that is the blast radius,
and the answer is purely a function of the isolation layers wrapping the
execution.

The concrete dangers an isolation layer must answer: reading/writing files
outside the intended scope (including another session's or tenant's files
if execution shares a host), unrestricted outbound network access (data
exfiltration, attacks on other internal systems), unbounded resource
consumption (a fork bomb, an infinite loop consuming the host's CPU/memory),
and - most often overlooked - access to credentials/sockets that happen to
live in the same process/container (the Docker socket, the application's API
key environment variables, the host filesystem outside the workspace).

## Pattern

### The blast radius spectrum

| Isolation layer | What is bounded when the code is malicious/buggy | Cold start | Example |
|---|---|---|---|
| No isolation (a subprocess in the host process) | Nothing - the code has the full access of the process running it | Zero (it runs immediately) | `deepagents`' built-in `LocalShellBackend` (see `## In deepagents`) |
| A container (namespaces + cgroups) | Filesystem/processes isolated from the host **if** configured correctly; network and resource limits are **optional**, not automatic | Seconds (once the image is pulled) | The OpenHands docker runtime - one container per task |
| A microVM (an isolated kernel per sandbox) | Its own kernel, not just namespaces - the blast radius doesn't reach the host even under a classic container escape | Longer than a plain container, though providers offer pause/resume to cut it | E2B, Daytona (default mode) |
| A dedicated VM/host | Full physical isolation, including from other tenants' sandboxes on the same infrastructure | The longest, or paid for as always-on capacity | Daytona VM sandboxes (explicit Linux/Windows VMs) |

The table's rows rise in **isolation guarantee** and fall in **latency +
cost**. No row is universally right - the choice depends on who writes the
code being executed (a trusted developer in a Workspace Agent, vs an
anonymous user of a public product) and how expensive it is if the blast
radius is misjudged.

### OpenHands: a container per task, but optional resource limits

OpenHands spawns a separate Docker container per task, with the agent's code
running inside a sandbox isolated from the host controller `[docs]`. But
**resource isolation** (CPU/memory) inside it is optional, not the default:
PR `All-Hands-AI/OpenHands#6616` added a `memory_limit` option to
`SandboxConfig` and mapped it to Docker's `mem_limit` parameter at container
start - before that PR (and if the option isn't set), *"the container will
have access to all available system memory"* `[code]` - cited from that
PR's diff (`openhands/core/config/sandbox_config.py`,
`openhands/runtime/impl/docker/docker_runtime.py`). A container without an
explicit `mem_limit` is filesystem/process isolation, not resource
isolation - malicious code can still exhaust the host's entire memory.

A second detail that widens the blast radius if unnoticed: OpenHands'
`entrypoint.sh` sets up **Docker-out-of-Docker (DooD)** - mounting the
host's Docker socket into the container and adding the container user to the
group with access to that socket `[docs]`. This is a pattern that looks like
"a container, therefore isolated" while that container in fact holds the
ability to control **sibling** containers on the same host through the same
socket - if the code in that sandbox is itself malicious, DooD is the way
out of the container boundary that was supposed to contain it. It is a
concrete example of the defect class this whole KB guards against: the name
"container isolation" doesn't automatically mean the isolation capability
you imagine - the actual configuration has to be checked.

> **Repo note (2026-08-23):** `All-Hands-AI/OpenHands` now redirects to
> `OpenHands/OpenHands`, whose contents have been replaced entirely by
> "Agent Canvas"; the original coding agent moved to the separate repo
> `OpenHands/software-agent-sdk`. The paths
> `openhands/core/config/sandbox_config.py` and
> `openhands/runtime/impl/docker/docker_runtime.py` cited above no longer
> exist in the current repo structure - the claims still hold for the cited
> commit `db37f350` / PR `#6616` (a historical snapshot, not a path
> traceable today). See [`../systems/openhands.md`](../systems/openhands.md)
> for this repo pivot in full.

### E2B and Daytona: microVMs, two different resource-sizing models

Both are microVM-class isolation per sandbox - a separate kernel, not just
namespaces in the host kernel - but how resource sizes are determined
differs, and that is a real ops trade-off:

- **E2B** - resources (CPU/memory) are fixed at the **template/image**
  level at build time (`e2b.toml`), not as a per-`create()` parameter in the
  Python SDK. `[code]` - `e2b/sandbox/main.py` (`class SandboxBase`):
  `default_sandbox_timeout = 300` (5 minutes) as the default; the
  `create(template=None, timeout=None, metadata=None, ..., lifecycle=...)`
  parameters `[code]` `e2b/sandbox_sync/main.py` include no direct
  `cpu`/`memory` parameter - the resource envelope is fixed once the
  template is chosen. Lifecycle: `lifecycle.on_timeout` can be `"kill"` or
  `"pause"`; pausing with `keep_memory=False` drops in-memory state and
  preserves only the filesystem - resuming from that state **cold-boots
  again** from disk rather than continuing from a memory snapshot `[docs]`
  (cited from the E2B lifecycle documentation via WebFetch).
- **Daytona** - resources are set **per create call**, through a
  `Resources(cpu, memory, disk, gpu, gpu_type)` object `[code]` -
  `daytona/common/sandbox.py` (`class Resources`, attributes
  `cpu: int | None`, `memory: int | None` in GiB, `disk: int | None` in
  GiB, `gpu`/`gpu_type`). Its lifecycle is also more granular:
  `auto_stop_interval` (15 minutes by default, 0 = disabled),
  `auto_pause_interval` (60 minutes by default for sandbox classes
  supporting pause, mutually exclusive with `auto_stop_interval`),
  `auto_archive_interval` (7 days by default), `auto_delete_interval`
  (disabled by default), and `ttl_minutes` as a hard wall-clock limit from
  creation - `[code]` `daytona/common/daytona.py` (`class
  CreateSandboxBaseParams`, `class CreateSandboxFromImageParams`).

Status note: as of mid-2026, Daytona is no longer self-hostable - its
production codebase moved to a closed-source repo; the `daytona` package
(the Python client) cited above remains open and is what these claims were
verified against, but the server-side isolation guarantees (exactly how
those microVMs are implemented) can no longer be read from public source
`[inferred]` - server-side behaviour is concluded from public documentation,
not read from its implementation.

## Trade-offs

- **A container per session (OpenHands) vs a microVM per sandbox
  (E2B/Daytona) vs no isolation (the deepagents default)** - no isolation
  is the cheapest and fastest (zero cold start) but the blast radius is the
  entire process/host running it; defensible only when the executed code
  comes from a trusted operator (e.g. a local single-tenant Workspace
  Agent). Containers are relatively cheap and fast, but their guarantee
  depends entirely on configuration (explicit resource limits, no DooD) -
  with a loose configuration, "container" is a name, not a guarantee.
  MicroVMs give the strongest guarantee still affordable for public
  multi-tenant use, at the cost of a higher cold start and a dependency on
  a third-party provider (and for Daytona as of 2026, a dependency on a
  closed-source service rather than self-hosting).
- **Resources fixed at build time (E2B) vs call time (Daytona)** -
  build-time is operationally simpler (one image, predictable capacity for
  planning) but can't be right-sized per task - a lightweight `pip list`
  call gets exactly the same resource envelope as a heavy container
  build. Call-time (Daytona's
  `Resources(...)`) is more flexible but adds a surface that must be
  validated: if the `cpu`/`memory` values come from arguments influenced by
  model output or user input, they must be ceiling-capped on the
  application side before being passed to the SDK - `[ours]`, not something
  the Daytona SDK enforces itself (the SDK accepts any type-valid value);
  vanilla is passing whatever the caller asks for straight through to the
  Daytona API, and we chose to add ceiling validation on the application
  side because a resource argument influenced by model generation is an
  abuse surface (repeatedly asking for `cpu=64`) that must not be trusted
  as-is.
- **Pure cold start vs a warm pool** - discussed further in `scaling.md`,
  relevant here because `on_timeout: "pause"` (E2B) and
  `auto_pause_interval` (Daytona) exist precisely to cut cold-start cost
  through resume rather than creating from scratch - both provide the
  primitive; the decision to use it for a warm pool belongs to the scaling
  layer.

## In deepagents

`execute` in `deepagents` runs only through a backend implementing
`SandboxBackendProtocol` - and that protocol itself guarantees **no**
isolation; it is only an interface contract (§Filesystem backend of
`../systems/deepagents.md`). Real isolation depends entirely on the backend
implementation installed:

| Backend | Execution isolation |
|---|---|
| `LocalShellBackend` (built in) | None - `subprocess.run(shell=True)` in the same process/host, with no validation of command content beyond a non-empty check; `virtual_mode` only restricts file operations (`read_file`/`write_file`/etc.), **not** `execute()`. Explicitly labelled *"not the default; it must be explicitly provided by the user"* in `deepagents`' `THREAT_MODEL.md`. `[code]` - [`../systems/deepagents.md`](../systems/deepagents.md) §6 (quoting `THREAT_MODEL.md` directly). |
| `LangSmithSandbox` | Isolation follows LangSmith's managed sandbox guarantees rather than the host process - the only `SandboxBackendProtocol` implementation besides `LocalShellBackend`/`FilesystemBackend` named explicitly in the source. `[code]` - `deepagents/backends/langsmith.py`. |
| A custom backend (e.g. an E2B/Daytona wrapper) | `deepagents` provides **no** built-in E2B/Daytona backend - using microVM isolation means implementing `SandboxBackendProtocol` yourself around the E2B/Daytona SDK (create the sandbox, send the command, return the result per the protocol contract). `[code]`+`[inferred]` - concluded from the backend list in §Filesystem backend, which names neither. |

The direct implication: which row of the "blast radius spectrum" table above
applies to a `deepagents`-based project is determined purely by which
backend is injected into `create_deep_agent(backend=...)` - not something
`deepagents` decides by default, beyond offering `LocalShellBackend` as the
loosest option (and not as the default unless explicitly requested).

## Sources

- `[docs]` OpenHands - the runtime/sandbox architecture (a container per
  task, isolated from the host controller), cited via WebFetch from
  `docs.openhands.dev/openhands/usage/architecture/runtime`.
- `[code]` OpenHands `openhands/core/config/sandbox_config.py`,
  `openhands/runtime/impl/docker/docker_runtime.py` - the `memory_limit`
  field and its mapping to Docker's `mem_limit`, read through the diff of
  PR `All-Hands-AI/OpenHands#6616` via WebFetch.
- `[docs]` OpenHands `containers/app/entrypoint.sh` - the
  Docker-out-of-Docker pattern (mounting the host Docker socket, adding the
  user to the socket-access group), cited via DeepWiki
  (`deepwiki.com/All-Hands-AI/OpenHands/3.1-docker-runtime`), which quotes
  `containers/app/entrypoint.sh#L31-L58` at commit `db37f350`.
- `[code]` The E2B Python SDK, package `e2b` version 2.45.1 from PyPI,
  downloaded and read directly: `e2b/sandbox/main.py` (`class SandboxBase`,
  `default_sandbox_timeout = 300`), `e2b/sandbox_sync/main.py` (the
  `create(template, timeout, metadata, ..., lifecycle)` signature).
- `[docs]` E2B - the semantics of `lifecycle.on_timeout`
  (`"kill"`/`"pause"`) and `keep_memory` on pause/resume, cited via
  WebFetch from the E2B sandbox lifecycle documentation.
- `[code]` The Daytona Python SDK, package `daytona` version 0.205.1 from
  PyPI, downloaded and read directly: `daytona/common/sandbox.py` (`class
  Resources`: `cpu`, `memory`, `disk`, `gpu`, `gpu_type`),
  `daytona/common/daytona.py` (`class CreateSandboxBaseParams`:
  `auto_stop_interval`, `auto_pause_interval`, `auto_archive_interval`,
  `auto_delete_interval`, `ttl_minutes`; `class
  CreateSandboxFromImageParams`: `resources: Resources | None`).
- `[inferred]` Daytona's self-hosting status (production going closed-source
  as of mid-2026) - concluded from third-party documentation/analysis cited
  via WebSearch, not verified directly from a Daytona announcement.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §6,
  §Filesystem backend - a tier-1 reference verified in Task 3, cited
  without re-reading the source.
