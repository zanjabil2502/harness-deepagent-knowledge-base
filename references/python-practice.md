# Python practice for a harness

How to write the Python this KB tells you to write. Cross-cutting: it applies
to the scaffold ([`scaffolds/_base.md`](scaffolds/_base.md)), to the custom
tools and middleware a blueprint calls for, and to every refactor
[`deepagents/extension-points.md`](deepagents/extension-points.md) points at.

Everything here is grounded in one of three places: the `deepagents` source
this KB already reads, CPython's own documentation, or this repo's own code.
Where none of those states a practice, this file says so instead of filling
the gap with taste.

## Problem

Generic Python advice optimises for the wrong thing inside an agent harness.
A harness turn spends most of its wall clock waiting on a network socket
(`concepts/resource-profiling.md`: the LLM call is roughly 75% of a turn and
uses almost no CPU), so the costs that decide whether it survives production
are, in order: tokens sent, checkpoint bytes written, connections held, and
only then CPU. Advice tuned for CPU-bound scripts inverts that ranking.

Two failure shapes follow, and both are common in code an LLM wrote:

1. **A blocking call inside an async path.** One synchronous `requests.get`
   or `time.sleep` in a middleware stalls every other turn sharing that
   process, because they share one event loop. The symptom is throughput
   collapse under concurrency, not an error.
2. **An abstraction layer over something that already has one.** A wrapper
   class around a tool, a bespoke retry loop, a home-grown storage module.
   `extension-points.md` catalogues this at the harness level; at the language
   level it is the same instinct reaching for a class where a function, a
   `dataclass`, or a stdlib module would do.

## Pattern

### 1. Type the boundaries, not everything

Type where values cross between components, because that is where a mistake
is expensive and where a reader needs the contract. Inside a function body,
annotations mostly add noise.

The four shapes, and when each is right:

| Shape | Use it for | Verified in `deepagents` |
|---|---|---|
| `TypedDict` | a spec that travels as a plain dict and must stay JSON-shaped | `FileInfo`, `GrepMatch`, `FileData` (`backends/protocol.py:120,150,178`), `MemoryStateUpdate` (`middleware/memory.py:97`) |
| `@dataclass(frozen=True)` | a value object passed between layers, never mutated in place | the profile classes (`profiles/harness/harness_profiles.py:82,191,482`) |
| `Literal[...]` | a closed set of strings that is not worth an `Enum` | `FileType` (`backends/utils.py:27`), `ToolScope` (`middleware/_fs_interrupt.py:31`), `GraderVerdict` (`middleware/rubric.py:64`) |
| `typing.Protocol` | a seam you own, where implementers should not have to inherit | `Orchestrator` in `scaffolds/_base.md` |

`[code]` for the middle three, read from the installed `deepagents==0.7.8`.

**A correction worth knowing, because the name misleads.** `BackendProtocol`
is **not** a `typing.Protocol`. It is declared `class BackendProtocol(abc.ABC)`
with `# noqa: B024`, the lint suppression for an ABC that has no abstract
methods (`backends/protocol.py:378`), and `SandboxBackendProtocol` extends it
(`:840`). There is no `typing.Protocol` anywhere in the package. `[code]`

That choice has a consequence you can see in the source: because the base
ships concrete default methods, a subclass inherits them silently, so
"does this backend support delete?" cannot be answered by `hasattr`. It is
answered by comparing the bound method to the base's:
`type(backend).delete is not BackendProtocol.delete` (`:939-954`). `[code]`

So the rule is not "always use `Protocol`". It is:

- **`typing.Protocol`** when you define a seam and want anything
  structurally compatible to satisfy it without importing your base. That is
  the `Orchestrator` case: the route depends on the contract, and the
  implementation swaps from in-process to a network client without touching
  the route.
- **`abc.ABC`** when you ship default behaviour that implementers inherit.
  Then accept the consequence: capability detection compares methods, and
  `hasattr` will lie.

### 2. Async correctness before async speed

The harness is IO-bound by construction, so concurrency comes from **not
blocking**, not from adding threads.

**When a blocking call is unavoidable, hand it to a thread rather than
building your own pool.** This is the SDK's own dominant idiom:
`asyncio.to_thread` appears **12 times** in `deepagents`, more than every
other `asyncio.*` call combined (`wait_for` 3, `gather` 3, `timeout` 2).
`[code]`

```python
# A blocking library call inside an async tool: hand it off, keep the loop free.
result = await asyncio.to_thread(blocking_client.fetch, url)
```

**Bound every wait.** An unbounded `await` on something a human or a remote
service controls is how a run holds an orchestrator slot forever;
`concepts/guardrails.md` §The third failure mode documents exactly that shape
in OpenWorker. `asyncio.wait_for` is the stdlib answer, and
`scaffolds/_base.md` uses it for drain:

```python
await asyncio.wait_for(self._empty.wait(), timeout=timeout)
```

**Open expensive resources once, in the lifespan, not per request.** Pools for
Postgres and the checkpointer, an `httpx.AsyncClient` for a remote
orchestrator. `scaffolds/_base.md` states the rule for the checkpointer
("used across requests, NOT created anew per turn") and pairs every resource
with an explicit close at shutdown. A resource opened per request is both a
latency cost and a leak waiting for the first exception path.

**`contextlib.asynccontextmanager` is how a resource states its own
lifecycle.** `build_checkpointer` and `db_session` in the scaffold are both
that shape, so the caller cannot forget the teardown half.

### 3. Efficiency where it actually pays

Rank the costs before optimising anything:

| Rank | Cost | Where it is decided |
|---|---|---|
| 1 | Tokens per call | what enters the context: `concepts/context-engineering.md` |
| 2 | Checkpoint bytes per step | state shape and its reducer |
| 3 | Connections and processes | pools, per-turn construction |
| 4 | CPU in your own Python | almost never the bottleneck |

**What a real optimisation looks like at rank 2:** `DeepAgentState.messages`
uses `DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)`, which
turns checkpoint growth from O(N squared) into O(N) across a long session
(`graph.py:70-73`). `[code]` That is an algorithmic change to how state is
written, and it pays on every step of every long turn. No amount of tightening
a loop in a tool function compares.

**What a wasted optimisation looks like at rank 4:** micro-optimising a
function that then awaits a model for fifteen seconds. Measure first, per
phase, using the span method in `concepts/resource-profiling.md` §Measuring
phase dominance: a phase with a large share of wall clock but little CPU is
IO-bound, and the fix is concurrency, not speed.

The one rank-4 case that does matter: **work done per turn that could be done
once.** Building the agent, compiling a graph, or reading a file on every turn
is CPU paid per request in a component designed to hold hundreds of them.

### 4. Stdlib first

The working set for harness code, and what each replaces:

| Module | Use | Replaces |
|---|---|---|
| `dataclasses` | value objects, `frozen=True` for ones that cross layers | a hand-written class with `__init__` and `__eq__` |
| `typing` | `TypedDict`, `Literal`, `Protocol`, `Callable` | untyped dicts at boundaries |
| `contextlib` | `asynccontextmanager`, `suppress` | try/finally repeated at every call site |
| `asyncio` | `to_thread`, `wait_for`, `gather`, `Event` | a bespoke thread pool or a polling loop |
| `pathlib` | every path join, read, write | `os.path` string surgery |
| `functools` | `lru_cache`, `partial` | a hand-rolled memo dict |
| `collections` | `defaultdict`, `deque` | dict-of-lists boilerplate |
| `hashlib` | content hashes, idempotency keys | a pip install for a checksum |
| `json`, `re`, `subprocess` | serialisation, patterns, process calls | heavier wrappers |

Two pieces of evidence that this is not merely a preference:

- **This repo's own tooling is stdlib-only.** `tools/check_kb.py`,
  `build_glossary.py`, and `fetch_upstream_docs.py` import nothing beyond
  `collections`, `concurrent.futures`, `pathlib`, `hashlib`, `json`, `re`,
  `subprocess`, `sys`, and `urllib`. That is why the README can promise
  "Python 3.10+, standard library only. No `pip install`."
- **`deepagents` itself keeps a small required surface.** Its metadata
  declares seven required dependencies, of which only `packaging` and
  `wcmatch` are outside the LangChain family; video, quickjs, and AWS support
  are all optional extras rather than baseline weight. `[code]`

The rule that follows: **a new dependency has to name what the stdlib cannot
do.** "It is more convenient" is not that. Every dependency is a version to
track, a supply chain to trust, and a container layer to ship.

### 5. Refactoring moves

`extension-points.md` states the hard rule at the harness level: do not write
custom code where an official hook exists. These are the same instinct one
level down, in the language.

| Move | Do it when | Instead of |
|---|---|---|
| Delete the layer | the SDK already exposes the parameter | improving your wrapper |
| Extract a `Protocol` | two implementations must be swappable | a base class others must inherit |
| Class becomes a function | the class holds no state between calls | keeping a class with one method |
| Pass a parameter | behaviour varies along one axis | subclassing to vary it |
| Hoist to lifespan | the work is identical for every turn | recomputing per request |
| Split the seam, not the file | one module does two jobs at different rates | splitting by line count |

**Behaviour-preserving means the diff is boring.** One finding, one change.
A refactor that also renames, reformats, and reorders is unreviewable, and its
review is where a real regression hides.

**Verify by construction, the cheapest real check.** The four scripts in
`references/recipes/` build a real agent and print a summary without ever
calling a model. Construction alone proves that every API name, signature, and
parameter exists, because a wrong parameter raises immediately. Adopt the same
gate for a refactor: if the thing still constructs and its one runnable check
passes, the change is at least type-correct and import-correct.

Be honest about that method's limit: it cannot detect a stale value that is
never exercised. A model id that no longer exists passes construction happily,
because nothing calls it.

## Trade-offs

- **Strict typing vs velocity.** Types at every boundary make refactors safe
  and reviews fast; types everywhere, including local variables and private
  helpers, mostly add churn. The boundary rule above is the middle: annotate
  what crosses, leave the inside alone.
- **`typing.Protocol` vs `abc.ABC`.** `Protocol` keeps implementers free of
  your import and is right for a seam. `ABC` lets you ship defaults, at the
  price of inheritance coupling and capability detection that cannot use
  `hasattr`. `deepagents` chose `ABC` for its backends; this KB chose
  `Protocol` for the orchestrator seam. Both are correct for their purpose.
- **Stdlib vs a library.** Stdlib means no version to track and no supply
  chain to trust, at the price of writing the twenty lines yourself. A library
  wins when the problem is genuinely hard (parsing, crypto, HTTP/2) and loses
  when it is a convenience wrapper over something already present.
- **Async everywhere vs sync simplicity.** A sync harness is easier to read
  and debug, and it caps concurrency at your thread count. For an IO-bound
  agent serving many users, async is not an optimisation but the architecture;
  for a single-user CLI it is overhead. `concepts/serving-topology.md` decides
  which one you are.
- **`frozen=True` vs a mutable dict.** Frozen value objects make accidental
  mutation impossible and are hashable; they also mean building a new object
  to change one field. For values crossing layers, that constraint is the
  point.

## In deepagents

If you extend the SDK, matching its idioms costs nothing and makes your code
read as part of it:

- Specs that travel as dicts are `TypedDict`, not classes
  (`SubAgent`, `CompiledSubAgent`, `AsyncSubAgent`).
- Closed string sets are `Literal`, not `Enum` (`FsToolName`, `ToolScope`).
- Profiles are `@dataclass(frozen=True)`.
- Backends extend `BackendProtocol`, an `abc.ABC` with concrete defaults, so
  override exactly the methods you mean to change and remember that a
  capability check compares methods rather than asking `hasattr`.
- Blocking work goes to `asyncio.to_thread`.
- Middleware hooks are the extension surface; a wrapper around a tool function
  is `extension-points.md` anti-pattern #2.

One thing the SDK does **not** state, so neither does this file: there is no
documented style guide, line length, or formatter configuration in
`deepagents`. Where your project needs one, that is your decision to make and
to write down, not something this KB has an opinion on.

## Sources

- `[code]` `deepagents==0.7.8`, read from
  `references/recipes/.venv/lib/python3.13/site-packages/deepagents/`:
  `backends/protocol.py:120,150,178,378,840,939-954` (the `TypedDict` specs,
  `BackendProtocol(abc.ABC)` with `# noqa: B024`, the `delete` capability
  check), `backends/utils.py:27`, `middleware/_fs_interrupt.py:31`,
  `middleware/rubric.py:64` (the `Literal` sets), `middleware/memory.py:97`,
  `profiles/harness/harness_profiles.py:82,191,482` (frozen dataclasses),
  `graph.py:70-73` (`DeltaChannel`, the O(N squared) to O(N) reducer). The
  `asyncio.to_thread` count of 12 versus `wait_for` 3, `gather` 3, `timeout` 2
  is a grep over the same tree; the absence of `typing.Protocol` was confirmed
  the same way.
- `[code]` `deepagents-0.7.8.dist-info/METADATA`, the `Requires-Dist` lines:
  seven required dependencies, of which only `packaging` and `wcmatch` sit
  outside LangChain, with video, quickjs, and AWS as extras.
- `[code]` This repo: `tools/check_kb.py`, `tools/build_glossary.py`,
  `tools/fetch_upstream_docs.py` (stdlib-only imports),
  `references/recipes/0{1,2,3,4}_*.py` (verification by construction),
  `references/scaffolds/_base.md` (the `Orchestrator` Protocol,
  `asynccontextmanager` resources, `asyncio.wait_for` drain).
- `[code]` [`concepts/resource-profiling.md`](concepts/resource-profiling.md)
  for the phase cost ranking, and
  [`concepts/context-engineering.md`](concepts/context-engineering.md) for why
  tokens outrank CPU. Cited, not restated.
- `[code]` [`deepagents/extension-points.md`](deepagents/extension-points.md)
  §The hard rule and §Anti-patterns, which the refactoring moves mirror one
  level down.
