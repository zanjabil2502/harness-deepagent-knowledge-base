# The base scaffold (`_base`)

A specification plus verified snippets for an **archetype-agnostic**
production-grade project structure - not a template repo to `cp -r`
(design §3 of the project's internal spec, which isn't shipped in the repo).
Each of the seven files in `deltas/` writes **only** its difference from this
file - read `_base.md` first; the deltas don't repeat its contents.

Its assumptions follow this KB's global constraints: multi-user (`user_id`)
today with multi-tenancy as a migration path; cloud and on-prem; Python +
FastAPI; Postgres.

## The directory tree

```
app/
├── main.py                         # The app factory + lifespan (startup/shutdown)
├── config.py                       # Env configuration (see §Config & secrets)
├── api/
│   ├── deps.py                     # build_orchestrator()/get_orchestrator() -- the single binding point
│   ├── middleware/
│   │   └── scope.py                # ScopeMiddleware -- user_id from auth -> Scope
│   └── routes/
│       ├── health.py               # /healthz, /readyz
│       └── turns.py                # POST /turns, GET /turns/{id}/events (SSE)
├── orchestrator/
│   ├── interface.py                # The Orchestrator Protocol, Scope, TurnEvent
│   └── deepagents_orchestrator.py  # The default implementation: wrapping create_deep_agent
├── db/
│   ├── session.py                  # The app-data pool + SET LOCAL app.current_user_id (RLS)
│   └── checkpointer.py             # The external checkpointer factory (Postgres)
├── observability/
│   └── otel.py                     # The tracer + the enduser.id label
└── lifecycle/
    └── drain.py                    # The in-flight turn gauge + graceful drain
Dockerfile
k8s/
├── deployment.yaml
└── service.yaml
pyproject.toml
uv.lock
```

There are no separate `executor/`/`retrieval/` folders - the reason is in the
next section: two of the three seams are already provided by `deepagents`
itself, so creating new directories to repeat them would be duplication, not
structure.

## Module boundaries: orchestrator / executor / retrieval behind interfaces

`serving-topology.md` §A modular monolith with the seams cut demands four
conditions for the "splitting later is just a binding change" claim to
genuinely hold. `_base` satisfies all four through the following three
boundaries:

| Boundary | Interface | Who provides it |
|---|---|---|
| **The orchestrator** | `Orchestrator` (a Protocol, `orchestrator/interface.py`) | `_base` itself - `deepagents` does **not** provide this seam (see the `[ours]` quotation in the code below) |
| **The tool executor** | `SandboxBackendProtocol` | Already provided by `deepagents` - installed through the `backend=` parameter |
| **Retrieval / durable state** | `StoreBackend`/`CompositeBackend` (`namespace=...`) | Already provided by `deepagents` - installed through the `backend=` parameter |

`[code]` - the last two rows are cited from `../systems/deepagents.md`
§Filesystem backend and `../concepts/serving-topology.md` §In deepagents: only
`StoreBackend`, `CompositeBackend`, and `ContextHubBackend` have an explicit
scoping *hook*; `StateBackend`/`FilesystemBackend`/`LocalShellBackend` don't.
`_base` doesn't rewrite `deepagents`' backend contract as a new interface -
that would duplicate an existing definition. The only seam `_base` writes
itself is the **Orchestrator**, because it is the only one of the three that
`deepagents` deliberately leaves undecided (see `## In deepagents` in
`resource-profiling.md`/`serving-topology.md`: "wherever that graph is invoked
is entirely an application decision").

```python
"""The Orchestrator interface -- the seam between the API layer and the
deepagents graph.

deepagents does NOT provide this seam: wherever the graph is invoked (one
FastAPI process, one Kubernetes Job, one queue worker) is entirely an
application decision outside deepagents (concepts/serving-topology.md, ## In
deepagents). This Protocol [ours] fills that gap -- vanilla has the route
handler call create_deep_agent()/.astream() directly; we diverge so the route
(app/api/routes/turns.py) calls the orchestrator through an explicit contract
rather than importing deepagents modules directly -- condition 1 of "a modular
monolith with the seams cut" (serving-topology.md §8.3).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Scope:
    """The literal scope object from isolation-and-scoping.md -- (user_id,)
    today, (tenant_id, user_id) after the multi-tenant migration. Every
    cross-interface call in this file carries Scope explicitly as a parameter
    rather than as ambient state (a thread-local/process global) -- condition
    4 of the modular monolith."""

    user_id: str


@dataclass(frozen=True)
class TurnEvent:
    """The event envelope, exactly the streaming-protocol.md schema -- a plain
    dataclass, JSON-serializable with no transformation (condition 2 of the
    modular monolith)."""

    event_id: str
    turn_id: str
    type: str
    data: dict[str, Any]
    ts: str


class Orchestrator(Protocol):
    """The orchestrator contract. The concrete implementation is in
    deepagents_orchestrator.py; app/api/routes/turns.py depends only on this
    Protocol through Depends(get_orchestrator) -- swapping the implementation
    (a local process today, a network call to a separate service later, see
    serving.md §Migrating) means changing build_orchestrator()'s body at one
    point (app/api/deps.py), not rewriting routes.
    """

    async def run_turn(
        self, scope: Scope, turn_id: str, thread_id: str, user_input: str
    ) -> AsyncIterator[TurnEvent]:
        """Run one turn, yielding TurnEvents progressively.

        thread_id = conversations.id (persistence-schema.md), passed as the
        LangGraph thread_id to the checkpointer -- the same convention
        isolation-and-scoping.md §In deepagents already pins down.
        """
        ...
```

The default implementation wraps `create_deep_agent` - this is the safe
baseline each archetype delta starts from and **replaces**
`create_deep_agent(...)` parameters in, rather than rewriting the class:

```python
"""The Orchestrator (Protocol) implementation wrapping create_deep_agent.

The tool executor and retrieval/durable state get NO new interface here --
both already have official seams from deepagents itself
(SandboxBackendProtocol, StoreBackend/CompositeBackend), used as-is through
the backend= parameter below. Creating new interfaces for them would repeat
what exists -- see serving-topology.md ## In deepagents.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend

from app.orchestrator.interface import Orchestrator, Scope, TurnEvent


def _build_backend(scope: Scope) -> StoreBackend:
    # A per-user namespace, StoreBackend's official hook
    # (isolation-and-scoping.md, systems/deepagents.md §Filesystem backend).
    # A closure over scope (rather than the documentation example's
    # rt.server_info.user.identity) [ours] -- the documentation example
    # assumes a LangGraph Platform filling server_info from its own auth
    # context; we self-host FastAPI without that runtime, so user_id is
    # closed over when the agent is assembled per turn (the same pattern as
    # recipes/04_custom_backend.py, verified in Task 3) rather than read from
    # a runtime field we don't have.
    return StoreBackend(namespace=lambda _rt, uid=scope.user_id: (uid,))


class DeepAgentsOrchestrator:
    """_base's default Orchestrator implementation -- a safe baseline: no
    custom tools, no subagents, no interrupt_on. Each archetype delta
    adds/replaces create_deep_agent(...) parameters here rather than rewriting
    this class."""

    def __init__(self, model, checkpointer) -> None:
        self._model = model
        self._checkpointer = checkpointer  # external, injected -- see db/checkpointer.py

    async def run_turn(
        self, scope: Scope, turn_id: str, thread_id: str, user_input: str
    ) -> AsyncIterator[TurnEvent]:
        agent = create_deep_agent(
            model=self._model,
            backend=_build_backend(scope),
            checkpointer=self._checkpointer,
        )
        config = {"configurable": {"thread_id": thread_id}}
        seq = 0
        async for chunk, _metadata in agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
            stream_mode="messages",
        ):
            seq += 1
            yield TurnEvent(
                event_id=f"{turn_id}-{seq}",
                turn_id=turn_id,
                type="message.delta",
                data={"text_delta": getattr(chunk, "content", "")},
                ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
```

`_base` deliberately installs no `tools=`, `subagents=`, `interrupt_on=`, or
`memory=` - those are all per-archetype decisions, see `deltas/01..07.md`.
The baseline backend (`StoreBackend`, with no `execute`) deliberately doesn't
support code execution either - an archetype needing `execute` (Workspace
Agent, Generative Builder, Computer-Use Agent) swaps this backend explicitly
in its own delta rather than silently inheriting code execution from the
baseline.

### The binding: `app/api/deps.py`

`Orchestrator` is a Protocol - something has to decide which concrete
implementation is used, and the route (`api/routes/turns.py`) must receive it
through `Depends(...)` rather than reaching into `request.app.state` directly.
`deps.py` is that single point:

```python
"""The binding point -- the only file that changes when migrating from a
modular monolith to microservices (serving.md §What changes: the binding).
main.py's lifespan still assembles the shared resources (the model, the
checkpointer); the function below is the single point deciding which concrete
Orchestrator implementation is used.
"""
from __future__ import annotations

from fastapi import Request

from app.orchestrator.deepagents_orchestrator import DeepAgentsOrchestrator
from app.orchestrator.interface import Orchestrator


def build_orchestrator(model, checkpointer) -> Orchestrator:
    """Called once from main.py's lifespan. To migrate to a separate service
    -- change this function's body to return RemoteOrchestratorClient(...)
    (see serving.md §Migrating); its caller in main.py doesn't change.
    """
    return DeepAgentsOrchestrator(model=model, checkpointer=checkpointer)


def get_orchestrator(request: Request) -> Orchestrator:
    """The FastAPI dependency -- routes call this through
    Depends(get_orchestrator) and never read request.app.state directly."""
    return request.app.state.orchestrator
```

`main.py`'s lifespan calls `build_orchestrator(model, checkpointer)` (rather
than constructing `DeepAgentsOrchestrator(...)` directly) and puts the result
in `app.state.orchestrator`; the route takes it through
`Depends(get_orchestrator)`. Migrating to a separate service (`serving.md`
§Migrating) means changing `build_orchestrator()`'s body - one function, one
file - not tracing through `main.py`/`turns.py`.

## FastAPI, async-first

All I/O (LLM calls, checkpoint writes, Postgres queries) uses
`async`/`await` - deepagents/langgraph are already async-native
(`.astream()`, `AsyncPostgresSaver`), so a synchronous handler here would
only block the event loop for something that should be pure IO-wait (exactly
`resource-profiling.md`'s argument: the LLM call phase barely uses CPU, and
one async process can hold hundreds of concurrent turns with no extra
threads).

```python
"""The FastAPI app factory + lifespan.

Startup: open the checkpointer pool + the application DB pool, install OTel,
assemble the Orchestrator once (used across requests through app.state rather
than reconstructed per request). Shutdown: drain in-flight turns before the
process exits -- see lifecycle/drain.py and k8s/deployment.yaml (preStop +
terminationGracePeriodSeconds) for the K8s half of the same mechanism.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_anthropic import ChatAnthropic

from app.api.deps import build_orchestrator
from app.api.middleware.scope import ScopeMiddleware
from app.api.routes import health, turns
from app.db.checkpointer import build_checkpointer
from app.db.session import close_pool, init_pool
from app.lifecycle.drain import DrainState
from app.observability.otel import setup_otel

DRAIN_TIMEOUT_S = float(os.environ.get("DRAIN_TIMEOUT_S", "25"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_otel(app)
    await init_pool(os.environ["APP_DATABASE_URL"])

    async with build_checkpointer(os.environ["CHECKPOINTER_DATABASE_URL"]) as checkpointer:
        model = ChatAnthropic(model_name="claude-sonnet-4-6")
        app.state.orchestrator = build_orchestrator(model, checkpointer)
        app.state.drain = DrainState()

        yield  # <-- the app serves traffic here

        # Shutdown: readyz starts returning 503 (draining=True inside
        # wait_empty), then we wait for in-flight turns. A timeout is not an
        # error -- checkpointer resumability is the safety net
        # (serving-topology.md).
        finished = await app.state.drain.wait_empty(timeout=DRAIN_TIMEOUT_S)
        if not finished:
            print(f"drain timeout {DRAIN_TIMEOUT_S}s reached; remaining turns continue from their checkpoint")

    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(ScopeMiddleware)
    app.include_router(health.router)
    app.include_router(turns.router)
    return app


app = create_app()
```

## The scope middleware: `user_id` + RLS

The only point reading identity from the request - everything below it
receives `Scope` as an explicit parameter and never re-reads a header/token
itself:

```python
"""ScopeMiddleware -- the only point reading identity from a request.

It extracts user_id from auth (a header placeholder below -- replace with real
JWT/session verification per the project's IdP) and places it as an explicit
Scope() in request.state.scope. Everything below it (routes, the orchestrator,
DB sessions) receives Scope as a parameter and never re-reads a header/token
itself -- the basis of fail-closed RLS (isolation-and-scoping.md: one
enforcement point per layer, not N points that can each be forgotten).
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.observability.otel import label_current_span_user
from app.orchestrator.interface import Scope

_UNSCOPED_PATHS = {"/healthz", "/readyz"}


class ScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _UNSCOPED_PATHS:
            return await call_next(request)

        user_id = _extract_user_id(request)
        if not user_id:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)

        request.state.scope = Scope(user_id=user_id)
        label_current_span_user(user_id)
        return await call_next(request)


def _extract_user_id(request: Request) -> str | None:
    # ponytail: a placeholder -- a raw header, not token verification. Replace
    # with real JWT verification (e.g. python-jose against the IdP's JWKS) or
    # a signed session cookie before production; a bare x-user-id header can
    # be forged by anyone.
    return request.headers.get("x-user-id") or None
```

Postgres RLS (its DDL already executed and audited - see
`../concepts/persistence-schema.md`, **unchanged here**) needs
`SET LOCAL app.current_user_id` in **every** new transaction, not once per
pooled connection:

```python
"""A per-request DB session with the RLS scope that MUST be set BEFORE any
query (persistence-schema.md, isolation-and-scoping.md). This application pool
is SEPARATE from the checkpointer pool (db/checkpointer.py) -- different
schemas and migration cycles, see persistence-schema.md 'Deliberately NOT
given DDL here'.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.orchestrator.interface import Scope

_pool: AsyncConnectionPool | None = None


async def init_pool(dsn: str) -> None:
    global _pool
    _pool = AsyncConnectionPool(conninfo=dsn, open=False)
    await _pool.open()


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


@asynccontextmanager
async def db_session(scope: Scope) -> AsyncIterator[AsyncConnection]:
    """SET LOCAL ends automatically at the transaction boundary -- so it is
    called AGAIN in every new transaction, not once per connection
    (isolation-and-scoping.md, the point 'Connection pooling is a new leak
    vector that must be guarded explicitly'). It is current_setting(..., true)
    on the RLS policy side (already pinned down in persistence-schema.md) that
    makes a forgotten SET LOCAL fail closed (zero rows) rather than open --
    not something that needs repeating here.
    """
    assert _pool is not None, "init_pool() hasn't been called (see app/main.py's lifespan)"
    async with _pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.current_user_id = %s", (scope.user_id,))
            yield conn
```

The `deepagents` filesystem backend is namespaced per `user_id` through
`_build_backend(scope)` in `deepagents_orchestrator.py` (above) - the same
scope with two different enforcements (Postgres RLS for application tables,
`StoreBackend.namespace` for agent files), both derived from the single
`Scope` object `ScopeMiddleware` resolves rather than from two sources of
truth that can diverge.

## The external checkpointer

```python
"""The external checkpointer -- a factory called once in app/main.py's
lifespan, used across requests, NOT created anew per turn.

[code] AsyncPostgresSaver accepts conn: AsyncConnection | AsyncConnectionPool
(langgraph-checkpoint-postgres==3.1.2,
langgraph/checkpoint/postgres/_ainternal.py, read directly from the PyPI
package). The checkpoints/writes schema BELONGS to that library --
persistence-schema.md deliberately doesn't redefine it; this file only builds
its connection.

[ours] An AsyncConnectionPool is used here, NOT the
AsyncPostgresSaver.from_conn_string(...) shown in LangGraph's official
documentation (docs.langchain.com/oss/python/langgraph/checkpointers) --
from_conn_string opens ONE AsyncConnection per context manager, fine for a
script/notebook but a serialising bottleneck for a server holding hundreds of
concurrent in-flight turns (resource-profiling.md: the checkpoint write phase
is disk IO, happening at every graph step). A pool lets different turns'
checkpoint writes run concurrently instead of queuing on one connection.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


@asynccontextmanager
async def build_checkpointer(dsn: str) -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncConnectionPool(
        conninfo=dsn,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        checkpointer = AsyncPostgresSaver(conn=pool)
        await checkpointer.setup()  # idempotent -- a no-op if the tables exist
        yield checkpointer
```

## Turn admission & streaming

`POST /turns` accepts a turn; `GET /turns/{turn_id}/events` streams SSE events
with exactly the `../concepts/streaming-protocol.md` schema (not reimplemented
here):

```python
"""POST /turns admits a new turn; GET /turns/{turn_id}/events streams the
Orchestrator's events as SSE. The event schema and the reattach contract are
NOT reimplemented here -- their shape is exactly streaming-protocol.md's; this
file only connects the Orchestrator to the HTTP transport.

[ours] Turn execution here happens INLINE inside the SSE generator (the same
async event loop running the connection), rather than full queue-then-execute
(a separate worker pool pulling from a queue, with the HTTP handler returning
immediately with a turn_id -- queueing-and-backpressure.md). This is the
simplest baseline still correct for in-flight-turns as a gauge (drain.py's
start_turn/end_turn stay precise), sufficient for volumes that don't yet need
explicit admission control. Once a queue is genuinely needed (turn bursts
exceeding worker capacity), change the admission in create_turn() to push onto
a real queue (Redis/RabbitMQ) and move the orchestrator call into a separate
worker -- a local change at the admission point; the Orchestrator Protocol
contract and the event schema don't change.
"""
from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_orchestrator
from app.orchestrator.interface import Orchestrator

router = APIRouter(prefix="/turns")


class CreateTurnRequest(BaseModel):
    conversation_id: str
    idempotency_key: str
    message: str


@router.post("")
async def create_turn(body: CreateTurnRequest, request: Request) -> dict:
    scope = request.state.scope
    # project: INSERT INTO turns (...) VALUES (...)
    #   ON CONFLICT (user_id, idempotency_key) DO NOTHING RETURNING id
    # -- see persistence-schema.md's UNIQUE(user_id, idempotency_key). On a
    # conflict (a retry/duplicate submit), SELECT the existing row and return
    # the same turn_id -- not a new turn.
    del scope  # used by db_session(scope) once the real query is written
    turn_id = str(uuid4())  # ponytail: a placeholder, replace with the real INSERT's result
    return {"turn_id": turn_id, "status": "pending"}


@router.get("/{turn_id}/events")
async def stream_turn(
    turn_id: str,
    thread_id: str,
    message: str,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    scope = request.state.scope
    drain = request.app.state.drain

    async def event_source():
        drain.start_turn()
        try:
            async for event in orchestrator.run_turn(scope, turn_id, thread_id, message):
                yield (
                    f"id: {event.event_id}\n"
                    f"event: {event.type}\n"
                    f"data: {json.dumps(event.data)}\n\n"
                )
        finally:
            drain.end_turn()

    return StreamingResponse(event_source(), media_type="text/event-stream")
```

## Observability: OTel + a user label

```python
"""The OTel setup -- a tracer provider + a user_id label on the active span.

`enduser.id` [docs] is OpenTelemetry's official semantic convention attribute
for per-span user identity (opentelemetry.io/docs/specs/semconv/
general/attributes-registry/enduser/) -- used as-is here rather than a custom
key, so any tracing backend (Tempo/Jaeger/Honeycomb) can filter/aggregate per
user with no convention specific to this project.
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_SERVICE_NAME = "harness-orchestrator"


def setup_otel(app) -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": _SERVICE_NAME}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)


def label_current_span_user(user_id: str) -> None:
    """Called from ScopeMiddleware once user_id is resolved -- the single
    point adding a user label to the active span, called inside the request
    span FastAPIInstrumentor already opened."""
    span = trace.get_current_span()
    span.set_attribute("enduser.id", user_id)
```

## `/healthz` and `/readyz`

```python
"""Liveness vs readiness -- two different failures, two separate endpoints.

/healthz: the process is alive. It doesn't check external dependencies -- a
DB being down is no reason for K8s to kill and restart this pod (a restart
doesn't heal a downed DB; it only discards in-flight turns pointlessly).
/readyz: ready to accept NEW turns. It returns 503 as soon as draining=True --
the Service stops sending new traffic to this pod while its in-flight turns
still finish (serving-topology.md, the rolling-deploy mitigation).
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict:
    drain = request.app.state.drain
    if drain.draining:
        response.status_code = 503
        return {"status": "draining"}
    # TODO project: add critical dependency checks (e.g. SELECT 1 through the
    # db/session.py pool) if the product needs readyz to fail when the DB is
    # unreachable.
    return {"status": "ready"}
```

## Graceful drain

```python
"""Graceful drain -- an in-flight turn gauge + waiting for empty at shutdown.

It enforces the rolling-deploy mitigation from serving-topology.md: the
readiness probe fails first (readyz 503 as soon as draining), then we wait for
in-flight turns to finish before the process exits. If drain_timeout expires
before every turn finishes, WE DON'T force a wait -- checkpointer resumability
(session-state.md, db/checkpointer.py) is the safety net: an unfinished turn
can continue on another pod from its last checkpoint.
"""
from __future__ import annotations

import asyncio


class DrainState:
    def __init__(self) -> None:
        self._count = 0
        self.draining = False
        self._empty = asyncio.Event()
        self._empty.set()

    def start_turn(self) -> None:
        if self.draining:
            raise RuntimeError("the server is draining and accepts no new turns")
        self._count += 1
        self._empty.clear()

    def end_turn(self) -> None:
        self._count -= 1
        if self._count <= 0:
            self._count = 0
            self._empty.set()

    async def wait_empty(self, timeout: float) -> bool:
        """True if every in-flight turn finished before the timeout."""
        self.draining = True
        try:
            await asyncio.wait_for(self._empty.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False
```

It is installed through four interlocking parts - if one is missing, the drain
is an empty promise: (1) `lifecycle/drain.py` above counts the in-flight turn
gauge, (2) `api/routes/turns.py` calls `drain.start_turn()`/`end_turn()`
around each turn's execution, (3) `main.py`'s lifespan calls `wait_empty()` at
shutdown **before** closing the pools, and (4) `k8s/deployment.yaml` below
aligns `terminationGracePeriodSeconds` and `preStop` so Kubernetes genuinely
gives (1)-(3) time to run before sending `SIGKILL`.

## The Dockerfile

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

FROM base AS builder
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base AS runtime
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY app/ ./app/
USER appuser
EXPOSE 8000

# A Docker-level liveness check only (/healthz) -- NOT a replacement for the
# K8s readinessProbe (see k8s/deployment.yaml): this HEALTHCHECK is only used
# by standalone `docker run`/compose; a K8s orchestrator ignores it and uses
# its own probes.
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## The basic K8s manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: harness-orchestrator
  labels:
    app: harness-orchestrator
spec:
  replicas: 2
  selector:
    matchLabels:
      app: harness-orchestrator
  template:
    metadata:
      labels:
        app: harness-orchestrator
    spec:
      # > DRAIN_TIMEOUT_S (25s by default, the env below) + the preStop
      # margin. A turn still running past this limit dies with its pod -- its
      # safety net is checkpointer resumability, not an unbounded grace period
      # (serving-topology.md).
      terminationGracePeriodSeconds: 60
      containers:
        - name: orchestrator
          image: registry.example.com/harness-orchestrator:latest
          ports:
            - containerPort: 8000
          env:
            - name: DRAIN_TIMEOUT_S
              value: "25"
            - name: APP_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: harness-db
                  key: app-url
            - name: CHECKPOINTER_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: harness-db
                  key: checkpointer-url
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8000
            periodSeconds: 5
            failureThreshold: 1
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            periodSeconds: 10
          lifecycle:
            preStop:
              exec:
                # Give the endpoint controller time to propagate this pod out
                # of the Service (readyz has returned 503 since SIGTERM was
                # received) BEFORE new connections genuinely stop arriving.
                command: ["sleep", "5"]
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              memory: "1Gi"
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: harness-orchestrator
spec:
  selector:
    app: harness-orchestrator
  ports:
    - port: 80
      targetPort: 8000
```

This manifest deliberately contains **no** HPA/KEDA - the per-component
scaling signals (in-flight turns for the orchestrator, queue depth for the
tool executor, etc.) and the concrete `ScaledObject` configuration belong to
`../concepts/scaling.md` and `serving.md` (§Migrating from a modular monolith
to microservices), not repeated here.

## Config & secrets

`app/config.py` (not quoted in full - its shape is a standard
`pydantic-settings` read from env vars) holds `APP_DATABASE_URL`,
`CHECKPOINTER_DATABASE_URL`, `DRAIN_TIMEOUT_S`, and the model credentials.
Those values come from a Kubernetes `Secret` (see `env[].valueFrom.secretKeyRef`
in the manifest above) and are never hardcoded or committed to the repo - this
is one of the nine production-readiness gate conditions below, mentioned here
because its wiring genuinely lives in `config.py` + the manifest, while the
condition's full definition stays solely in `blueprint-template.md`.

## Guardrails: the installation points, not a re-listing

The six enforcement points and their concrete middleware table are already
pinned down in full in `../concepts/guardrails.md` - **not repeated here**.
All this scaffold needs to know is **where** each point is installed in the
directory tree above:

| Point (`guardrails.md`) | Installed in |
|---|---|
| 1. Input, 4. Output | The `middleware=[...]` parameter when `create_deep_agent(...)` is called in `deepagents_orchestrator.py` |
| 2. Retrieval/context | Inside the custom retrieval tool's implementation (absent from `_base` - an archetype with retrieval tools adds it in its delta) |
| 3. Tool/action | The `interrupt_on=`/`permissions=` parameters of `create_deep_agent(...)`, an `undo_*` tool, or `args_schema` validation - differing per archetype, see `deltas/*.md` |
| 5. Loop | `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` in that same `middleware=[...]` |
| 6. System | An explicit `model=` parameter (already in `_base` - `ChatAnthropic(model_name="claude-sonnet-4-6")`, not a floating alias) |

The `_base` baseline installs only point 6 (pinning the model). Points
1/3/4/5 are deliberately empty in the baseline - see each archetype's
`## Building this with deepagents` (`../archetypes/*.md`) for the concrete
per-delta decisions.

## The production-readiness gate

The 9-condition checklist exists **solely** in
[`../blueprint-template.md`](../blueprint-template.md#production-readiness-checklist)
- not copied here, so there can never be two copies that diverge once spec
§12 changes. **This scaffold must not be declared finished until all nine
items there are ticked.**
