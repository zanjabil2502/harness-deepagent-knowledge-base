# Scaffold dasar (`_base`)

Spesifikasi + snippet terverifikasi untuk struktur project production-grade
yang **arketipe-agnostik** — bukan template repo untuk `cp -r`
(desain §3 spec internal proyek, tidak ikut di-repo).
Ketujuh file di `deltas/` masing-masing **hanya** menuliskan selisihnya
terhadap file ini — baca `_base.md` dulu, delta tidak mengulang isinya.

Asumsi mengikuti kendala global KB ini: multi-user (`user_id`) hari ini,
multi-tenant sebagai jalur migrasi; cloud dan on-prem; Python + FastAPI;
Postgres.

## Pohon direktori

```
app/
├── main.py                         # App factory + lifespan (startup/shutdown)
├── config.py                       # Konfigurasi env (lihat §Config & secrets)
├── api/
│   ├── deps.py                     # build_orchestrator()/get_orchestrator() -- satu titik binding
│   ├── middleware/
│   │   └── scope.py                # ScopeMiddleware -- user_id dari auth -> Scope
│   └── routes/
│       ├── health.py               # /healthz, /readyz
│       └── turns.py                # POST /turns, GET /turns/{id}/events (SSE)
├── orchestrator/
│   ├── interface.py                # Protocol Orchestrator, Scope, TurnEvent
│   └── deepagents_orchestrator.py  # Implementasi default: bungkus create_deep_agent
├── db/
│   ├── session.py                  # Pool app-data + SET LOCAL app.current_user_id (RLS)
│   └── checkpointer.py             # Factory checkpointer eksternal (Postgres)
├── observability/
│   └── otel.py                     # Tracer + label enduser.id
└── lifecycle/
    └── drain.py                    # Gauge in-flight turn + graceful drain
Dockerfile
k8s/
├── deployment.yaml
└── service.yaml
pyproject.toml
uv.lock
```

Tidak ada folder `executor/`/`retrieval/` terpisah — alasannya di section
berikutnya: dua dari tiga jahitan itu sudah disediakan `deepagents` sendiri,
membuat direktori baru untuk mengulangnya adalah duplikasi, bukan struktur.

## Batas modul: orchestrator / executor / retrieval di balik interface

`serving-topology.md` §Modular monolith dengan jahitan dipotong menuntut
empat syarat supaya klaim "pisah nanti tinggal ganti binding" benar-benar
berlaku. `_base` memenuhi keempatnya lewat tiga batas berikut:

| Batas | Interface | Siapa yang menyediakan |
|---|---|---|
| **Orchestrator** | `Orchestrator` (Protocol, `orchestrator/interface.py`) | `_base` sendiri — `deepagents` **tidak** menyediakan seam ini (lihat kutipan `[ours]` di kode di bawah) |
| **Tool executor** | `SandboxBackendProtocol` | Sudah disediakan `deepagents` — dipasang lewat parameter `backend=` |
| **Retrieval / state durable** | `StoreBackend`/`CompositeBackend` (`namespace=...`) | Sudah disediakan `deepagents` — dipasang lewat parameter `backend=` |

`[code]` — dua baris terakhir dikutip `../systems/deepagents.md` §Backend
filesystem dan `../concepts/serving-topology.md` §Di deepagents: hanya
`StoreBackend`, `CompositeBackend`, dan `ContextHubBackend` yang punya *hook*
scoping eksplisit; `StateBackend`/`FilesystemBackend`/`LocalShellBackend`
tidak. `_base` tidak menulis ulang kontrak backend `deepagents` sebagai
interface baru — itu duplikasi definisi yang sudah ada. Yang `_base` tulis
sendiri cuma seam **Orchestrator**, karena itulah satu-satunya dari ketiga
jahitan yang `deepagents` sengaja tidak putuskan untuknya (lihat
`## Di deepagents` `resource-profiling.md`/`serving-topology.md`: "ke mana
pun graph di-invoke adalah keputusan aplikasi sepenuhnya").

```python
"""Orchestrator interface -- seam antara API layer dan graph deepagents.

deepagents TIDAK menyediakan seam ini: ke mana pun graph di-invoke (satu
proses FastAPI, satu Job Kubernetes, satu worker antrean) adalah keputusan
aplikasi sepenuhnya di luar deepagents (concepts/serving-topology.md, ##
Di deepagents). Protocol ini [ours] mengisi kekosongan itu -- vanilla-nya
route handler memanggil create_deep_agent()/.astream() langsung; kita
menyimpang supaya route (app/api/routes/turns.py) memanggil orchestrator
lewat kontrak eksplisit, bukan mengimpor modul deepagents langsung -- syarat
1 "modular monolith dengan jahitan dipotong" (serving-topology.md §8.3).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Scope:
    """Scope object literal dari isolation-and-scoping.md -- (user_id,) hari
    ini, (tenant_id, user_id) setelah migrasi multi-tenant. Semua panggilan
    lintas interface di file ini membawa Scope eksplisit sebagai parameter,
    bukan ambient state (thread-local/proses) -- syarat 4 modular monolith."""

    user_id: str


@dataclass(frozen=True)
class TurnEvent:
    """Amplop event persis skema streaming-protocol.md -- dataclass murni,
    serializable ke JSON tanpa transformasi (syarat 2 modular monolith)."""

    event_id: str
    turn_id: str
    type: str
    data: dict[str, Any]
    ts: str


class Orchestrator(Protocol):
    """Kontrak orchestrator. Implementasi konkret ada di
    deepagents_orchestrator.py; app/api/routes/turns.py hanya bergantung pada
    Protocol ini lewat Depends(get_orchestrator) -- mengganti implementasi
    (proses lokal hari ini, network call ke service terpisah nanti, lihat
    serving.md §Migrasi) berarti ganti body build_orchestrator() di satu
    titik (app/api/deps.py), bukan menulis ulang routes.
    """

    async def run_turn(
        self, scope: Scope, turn_id: str, thread_id: str, user_input: str
    ) -> AsyncIterator[TurnEvent]:
        """Jalankan satu turn, yield TurnEvent progresif.

        thread_id = conversations.id (persistence-schema.md), diteruskan
        sebagai LangGraph thread_id ke checkpointer -- konvensi yang sama
        yang sudah dipatok isolation-and-scoping.md §Di deepagents.
        """
        ...
```

Implementasi default membungkus `create_deep_agent` — inilah baseline aman
tiap delta arketipe mulai dari sini dan **mengganti** parameter
`create_deep_agent(...)`-nya, bukan menulis ulang kelas:

```python
"""Implementasi Orchestrator (Protocol) yang membungkus create_deep_agent.

Tool executor dan Retrieval/state durable TIDAK dapat interface baru di sini
-- keduanya sudah punya seam resmi dari deepagents sendiri
(SandboxBackendProtocol, StoreBackend/CompositeBackend), dipakai apa adanya
lewat parameter backend= di bawah. Membuat interface baru untuk itu akan
mengulang yang sudah ada -- lihat serving-topology.md ## Di deepagents.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend

from app.orchestrator.interface import Orchestrator, Scope, TurnEvent


def _build_backend(scope: Scope) -> StoreBackend:
    # Namespace per-user, hook resmi StoreBackend (isolation-and-scoping.md,
    # systems/deepagents.md §Backend filesystem). Closure atas scope
    # (bukan rt.server_info.user.identity dari contoh dokumentasi) [ours]
    # -- contoh dokumentasi mengasumsikan LangGraph Platform yang mengisi
    # server_info dari auth context bawaannya; kita self-host FastAPI
    # sendiri tanpa runtime itu, jadi user_id ditutup lewat closure saat
    # agent dirakit per turn (pola yang sama dengan recipes/04_custom_backend.py,
    # sudah diverifikasi Task 3), bukan dibaca dari field runtime yang tidak
    # kita punya.
    return StoreBackend(namespace=lambda _rt, uid=scope.user_id: (uid,))


class DeepAgentsOrchestrator:
    """Implementasi default Orchestrator untuk _base -- baseline aman: tanpa
    tools kustom, tanpa subagents, tanpa interrupt_on. Tiap delta arketipe
    menambah/mengganti parameter create_deep_agent(...) di sini, tidak
    menulis ulang kelas ini."""

    def __init__(self, model, checkpointer) -> None:
        self._model = model
        self._checkpointer = checkpointer  # eksternal, disuntik -- lihat db/checkpointer.py

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

`_base` sengaja tidak memasang `tools=`, `subagents=`, `interrupt_on=`, atau
`memory=` — itu semua keputusan per-arketipe, lihat `deltas/01..07.md`.
Backend baseline (`StoreBackend`, tanpa `execute`) juga sengaja tidak
mendukung eksekusi kode — arketipe yang butuh `execute` (Workspace Agent,
Generative Builder, Computer-Use Agent) mengganti backend ini secara
eksplisit di delta masing-masing, bukan mewarisi kemampuan eksekusi kode
secara diam-diam dari baseline.

### Binding: `app/api/deps.py`

`Orchestrator` adalah Protocol — sesuatu harus memutuskan implementasi
konkret mana yang dipakai, dan route (`api/routes/turns.py`) harus
menerimanya lewat `Depends(...)`, bukan menjangkau `request.app.state`
langsung. `deps.py` adalah titik tunggal itu:

```python
"""Binding point -- satu-satunya file yang berubah saat migrasi modular
monolith -> microservice (serving.md §Yang berubah: binding). main.py
lifespan tetap merakit resource bersama (model, checkpointer); fungsi di
bawah ini adalah titik tunggal yang memutuskan implementasi Orchestrator
konkret mana yang dipakai.
"""
from __future__ import annotations

from fastapi import Request

from app.orchestrator.deepagents_orchestrator import DeepAgentsOrchestrator
from app.orchestrator.interface import Orchestrator


def build_orchestrator(model, checkpointer) -> Orchestrator:
    """Dipanggil sekali dari main.py lifespan. Migrasi ke service terpisah
    -- ganti isi fungsi ini untuk return RemoteOrchestratorClient(...)
    (lihat serving.md §Migrasi); pemanggilnya di main.py tidak berubah.
    """
    return DeepAgentsOrchestrator(model=model, checkpointer=checkpointer)


def get_orchestrator(request: Request) -> Orchestrator:
    """Dependency FastAPI -- routes memanggil ini lewat
    Depends(get_orchestrator), tidak pernah membaca request.app.state
    langsung."""
    return request.app.state.orchestrator
```

`main.py` lifespan memanggil `build_orchestrator(model, checkpointer)`
(bukan mengonstruksi `DeepAgentsOrchestrator(...)` langsung) dan menaruh
hasilnya di `app.state.orchestrator`; route mengambilnya lewat
`Depends(get_orchestrator)`. Migrasi ke service terpisah (`serving.md`
§Migrasi) berarti mengganti isi `build_orchestrator()` — satu fungsi, satu
file — bukan menelusuri `main.py`/`turns.py`.

## FastAPI async-first

Seluruh I/O (LLM call, checkpoint write, query Postgres) memakai `async`/
`await` — deepagents/langgraph sudah async-native (`.astream()`,
`AsyncPostgresSaver`), jadi handler sinkron di sini cuma akan memblokir
event loop untuk hal yang seharusnya IO-wait murni (persis argumen
`resource-profiling.md`: fase LLM call nyaris tidak memakai CPU, satu proses
async bisa menahan ratusan turn concurrent tanpa thread tambahan).

```python
"""FastAPI app factory + lifespan.

Startup: buka pool checkpointer + pool DB aplikasi, pasang OTel, rakit
Orchestrator sekali (dipakai lintas request lewat app.state, bukan
dikonstruksi ulang tiap request). Shutdown: drain in-flight turn sebelum
proses keluar -- lihat lifecycle/drain.py dan k8s/deployment.yaml
(preStop + terminationGracePeriodSeconds) untuk paruh K8s dari mekanisme
yang sama.
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

        yield  # <-- app melayani traffic di sini

        # Shutdown: readyz mulai 503 (draining=True di dalam wait_empty),
        # tunggu in-flight selesai. Timeout habis != error -- checkpointer
        # resumability adalah jaring pengaman (serving-topology.md).
        finished = await app.state.drain.wait_empty(timeout=DRAIN_TIMEOUT_S)
        if not finished:
            print(f"drain timeout {DRAIN_TIMEOUT_S}s tercapai, turn tersisa lanjut dari checkpoint")

    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(ScopeMiddleware)
    app.include_router(health.router)
    app.include_router(turns.router)
    return app


app = create_app()
```

## Scope middleware: `user_id` + RLS

Satu-satunya titik yang membaca identitas dari request — kode di bawahnya
menerima `Scope` sebagai parameter eksplisit, tidak pernah membaca ulang
header/token sendiri:

```python
"""ScopeMiddleware -- satu-satunya titik yang membaca identitas dari request.

Ekstrak user_id dari auth (placeholder header di bawah -- ganti dengan
verifikasi JWT/session nyata sesuai IdP project) dan taruh sebagai Scope()
eksplisit di request.state.scope. Kode di bawahnya (routes, orchestrator, DB
session) menerima Scope sebagai parameter, tidak pernah membaca ulang
header/token sendiri -- basis fail-closed RLS (isolation-and-scoping.md:
satu titik penegakan per lapis, bukan N titik yang bisa lupa satu-satu).
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
    # ponytail: placeholder -- header mentah, bukan verifikasi token. Ganti
    # dengan verifikasi JWT nyata (mis. python-jose terhadap JWKS IdP) atau
    # session cookie signed sebelum production; header x-user-id apa adanya
    # bisa dipalsukan siapa pun.
    return request.headers.get("x-user-id") or None
```

RLS Postgres (DDL sudah dieksekusi & diaudit — lihat
`../concepts/persistence-schema.md`, **tidak diubah di sini**) butuh
`SET LOCAL app.current_user_id` di **setiap** transaksi baru, bukan sekali
per koneksi pool:

```python
"""DB session per-request dengan RLS scope wajib di-set SEBELUM query apa pun
(persistence-schema.md, isolation-and-scoping.md). Pool aplikasi ini
TERPISAH dari pool checkpointer (db/checkpointer.py) -- skema dan siklus
migrasi berbeda, lihat persistence-schema.md 'Yang sengaja TIDAK
di-DDL-kan di sini'.
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
    """SET LOCAL berakhir otomatis di batas transaksi -- dipanggil ULANG di
    tiap transaksi baru, bukan sekali per koneksi (isolation-and-scoping.md,
    poin 'Connection pooling adalah vektor kebocoran baru yang harus dijaga
    eksplisit'). current_setting(..., true) di sisi policy RLS (sudah
    dipatok persistence-schema.md) yang membuat lupa SET LOCAL jatuh ke
    fail-closed (nol baris), bukan fail-open -- bukan sesuatu yang perlu
    diulang di sini.
    """
    assert _pool is not None, "init_pool() belum dipanggil (lihat app/main.py lifespan)"
    async with _pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.current_user_id = %s", (scope.user_id,))
            yield conn
```

Backend filesystem `deepagents` di-namespace per-`user_id` lewat
`_build_backend(scope)` di `deepagents_orchestrator.py` (lihat di atas) —
scope yang sama, dua penegakan berbeda (RLS Postgres untuk tabel aplikasi,
`StoreBackend.namespace` untuk file agent) yang keduanya berasal dari objek
`Scope` tunggal yang di-resolve `ScopeMiddleware`, bukan dua sumber
kebenaran yang bisa divergen.

## Checkpointer eksternal

```python
"""External checkpointer -- factory dipanggil sekali di app/main.py lifespan,
dipakai lintas request, TIDAK dibuat baru per turn.

[code] AsyncPostgresSaver menerima conn: AsyncConnection | AsyncConnectionPool
(langgraph-checkpoint-postgres==3.1.2, langgraph/checkpoint/postgres/_ainternal.py,
dibaca langsung dari paket PyPI). Skema checkpoints/writes MILIK library ini
-- persistence-schema.md sengaja tidak mendefinisikannya ulang; file ini
cuma membangun koneksinya.

[ours] AsyncConnectionPool dipakai di sini, BUKAN
AsyncPostgresSaver.from_conn_string(...) yang dicontohkan dokumentasi resmi
LangGraph (docs.langchain.com/oss/python/langgraph/checkpointers) --
from_conn_string membuka SATU AsyncConnection per context manager, cukup
untuk skrip/notebook tapi jadi bottleneck serial untuk server yang menahan
ratusan in-flight turn concurrent (resource-profiling.md: fase checkpoint
write IO-disk, terjadi tiap step graph). Pool membiarkan checkpoint write
turn yang berbeda jalan concurrent alih-alih antre di satu koneksi.
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
        await checkpointer.setup()  # idempotent -- no-op kalau tabel sudah ada
        yield checkpointer
```

## Turn admission & streaming

`POST /turns` menerima turn, `GET /turns/{turn_id}/events` mem-stream
event SSE dengan skema persis `../concepts/streaming-protocol.md` (tidak
diimplementasikan ulang di sini):

```python
"""POST /turns admisi turn baru; GET /turns/{turn_id}/events mem-stream event
SSE dari Orchestrator. Skema event dan kontrak reattach TIDAK diimplementasi
ulang di sini -- bentuknya persis streaming-protocol.md, file ini cuma
menyambungkan Orchestrator ke transport HTTP.

[ours] Eksekusi turn di sini terjadi INLINE di dalam generator SSE (event
loop async yang sama menjalankan koneksi), bukan queue-then-execute penuh
(worker pool terpisah menarik dari antrean, HTTP handler kembali segera
dengan turn_id -- queueing-and-backpressure.md). Ini baseline paling
sederhana yang masih benar untuk in-flight-turns sebagai gauge (drain.py
start_turn/end_turn tetap presisi), cukup untuk volume yang belum butuh
admission control eksplisit. Begitu antrean sungguh perlu (burst turn
melebihi kapasitas worker), ganti admisi di create_turn() untuk push ke
antrean nyata (Redis/RabbitMQ) dan pindahkan pemanggilan orchestrator ke
worker terpisah -- perubahan lokal di titik admisi, kontrak Orchestrator
Protocol dan skema event tidak berubah.
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
    # -- lihat persistence-schema.md UNIQUE(user_id, idempotency_key). Kalau
    # konflik (retry/duplicate submit), SELECT baris existing dan kembalikan
    # turn_id yang sama -- bukan turn baru.
    del scope  # dipakai db_session(scope) saat query nyata ditulis
    turn_id = str(uuid4())  # ponytail: placeholder, ganti hasil INSERT nyata
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

## Observability: OTel + label user

```python
"""OTel setup -- tracer provider + label user_id di span aktif.

`enduser.id` [docs] adalah atribut semantic convention resmi OpenTelemetry
untuk identitas pengguna per-span (opentelemetry.io/docs/specs/semconv/
general/attributes-registry/enduser/) -- dipakai apa adanya di sini, bukan
key kustom, supaya backend tracing manapun (Tempo/Jaeger/Honeycomb) bisa
memfilter/agregasi per user tanpa konvensi khusus proyek ini.
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
    """Dipanggil dari ScopeMiddleware setelah user_id diresolusi -- titik
    tunggal yang menambah label user ke span aktif, dipanggil di dalam
    request span yang sudah dibuka FastAPIInstrumentor."""
    span = trace.get_current_span()
    span.set_attribute("enduser.id", user_id)
```

## `/healthz` dan `/readyz`

```python
"""Liveness vs readiness -- dua kegagalan yang berbeda, dua endpoint terpisah.

/healthz: proses hidup. Tidak cek dependency eksternal -- DB down bukan
alasan K8s membunuh dan me-restart pod ini (restart tidak menyembuhkan DB
down, cuma membuang in-flight turn tanpa guna).
/readyz: siap menerima turn BARU. 503 begitu draining=True -- Service
berhenti mengirim traffic baru ke pod ini sementara in-flight turn tetap
diselesaikan (serving-topology.md, mitigasi rolling-deploy).
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
    # TODO project: tambahkan cek dependency kritikal (mis. SELECT 1 lewat
    # db/session.py pool) kalau produk butuh readyz gagal saat DB unreachable.
    return {"status": "ready"}
```

## Graceful drain

```python
"""Graceful drain -- gauge in-flight turn + tunggu kosong saat shutdown.

Menegakkan mitigasi rolling-deploy dari serving-topology.md: readiness probe
mati duluan (readyz 503 begitu draining), lalu tunggu in-flight selesai
sebelum proses keluar. Kalau drain_timeout habis sebelum semua turn selesai,
KITA TIDAK menunggu paksa -- checkpointer resumability (session-state.md,
db/checkpointer.py) adalah jaring pengaman: turn yang belum selesai bisa
dilanjut pod lain dari checkpoint terakhir.
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
            raise RuntimeError("server sedang drain, tidak menerima turn baru")
        self._count += 1
        self._empty.clear()

    def end_turn(self) -> None:
        self._count -= 1
        if self._count <= 0:
            self._count = 0
            self._empty.set()

    async def wait_empty(self, timeout: float) -> bool:
        """True kalau semua in-flight turn selesai sebelum timeout."""
        self.draining = True
        try:
            await asyncio.wait_for(self._empty.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False
```

Dipasang lengkap lewat tiga bagian yang saling mengunci — kalau salah satu
hilang, drain jadi janji kosong: (1) `lifecycle/drain.py` di atas menghitung
gauge in-flight turn, (2) `api/routes/turns.py` memanggil
`drain.start_turn()`/`end_turn()` mengurung eksekusi tiap turn, (3)
`main.py` lifespan memanggil `wait_empty()` saat shutdown **sebelum**
menutup pool, dan (4) `k8s/deployment.yaml` di bawah menyelaraskan
`terminationGracePeriodSeconds` dan `preStop` supaya Kubernetes benar-benar
memberi waktu untuk (1)-(3) berjalan sebelum mengirim `SIGKILL`.

## Dockerfile

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

# Liveness Docker-level saja (/healthz) -- BUKAN pengganti readinessProbe
# K8s (lihat k8s/deployment.yaml): HEALTHCHECK ini cuma dipakai `docker run`
# standalone/compose, orkestrator K8s mengabaikannya dan pakai probe sendiri.
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Manifest K8s dasar

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
      # > DRAIN_TIMEOUT_S (25s default, env di bawah) + margin preStop.
      # Turn yang masih jalan lewat batas ini mati bersama pod -- jaring
      # pengamannya checkpointer resumability, bukan grace period tak
      # terbatas (serving-topology.md).
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
                # Beri waktu endpoint controller mempropagasi pod ini keluar
                # dari Service (readyz sudah 503 sejak SIGTERM diterima)
                # SEBELUM koneksi baru sungguh berhenti masuk.
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

Manifest ini sengaja **tidak** memuat HPA/KEDA — sinyal scaling per
komponen (in-flight turns untuk orchestrator, queue depth untuk tool
executor, dst.) dan konfigurasi `ScaledObject` konkretnya adalah domain
`../concepts/scaling.md` dan `serving.md` (§Migrasi monolith → microservice),
bukan diulang di sini.

## Config & secrets

`app/config.py` (tidak dikutip penuh — bentuknya standar `pydantic-settings`
baca dari env var) memuat `APP_DATABASE_URL`, `CHECKPOINTER_DATABASE_URL`,
`DRAIN_TIMEOUT_S`, kredensial model. Nilai-nilai ini datang dari Kubernetes
`Secret` (lihat `env[].valueFrom.secretKeyRef` di manifest di atas), tidak
pernah di-hardcode atau commit ke repo — ini salah satu dari sembilan syarat
gerbang production-readiness di bawah, disebut di sini karena wiring-nya
memang hidup di `config.py`+manifest, tapi definisi lengkap syaratnya tetap
satu-satunya di `blueprint-template.md`.

## Guardrail: titik pemasangan, bukan daftar ulang

Enam titik penegakan dan tabel middleware konkretnya sudah dipatok penuh di
`../concepts/guardrails.md` — **tidak diulang di sini**. Yang perlu diketahui
scaffold ini cuma **di mana** tiap titik terpasang di pohon direktori di
atas:

| Titik (`guardrails.md`) | Terpasang di |
|---|---|
| 1. Input, 4. Output | Parameter `middleware=[...]` saat `create_deep_agent(...)` dipanggil di `deepagents_orchestrator.py` |
| 2. Retrieval/context | Di dalam implementasi tool retrieval kustom (tidak ada di `_base` — arketipe yang punya tool retrieval menambahkannya di delta) |
| 3. Tool/aksi | Parameter `interrupt_on=`/`permissions=` di `create_deep_agent(...)`, tool `undo_*`, atau validasi `args_schema` — beda per arketipe, lihat `deltas/*.md` |
| 5. Loop | `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` di `middleware=[...]` yang sama |
| 6. Sistem | Parameter `model=` eksplisit (sudah di `_base` — `ChatAnthropic(model_name="claude-sonnet-4-6")`, bukan alias mengambang) |

`_base` baseline hanya memasang titik 6 (pin model). Titik 1/3/4/5 kosong di
baseline secara sengaja — lihat `## Bangun ini pakai deepagents` tiap
arketipe (`../archetypes/*.md`) untuk keputusan konkret per delta.

## Gerbang production-readiness

Checklist 9 syarat ada **satu-satunya** di
[`../blueprint-template.md`](../blueprint-template.md#checklist-production-readiness)
— tidak disalin di sini supaya tidak ada dua salinan yang bisa saling
berbeda begitu spec §12 berubah. **Scaffold ini belum boleh dinyatakan
selesai sebelum seluruh sembilan item di sana tercentang.**
