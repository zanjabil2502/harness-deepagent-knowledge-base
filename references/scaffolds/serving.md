# Serving topology — lintas arketipe

Ditulis **sekali**, berlaku untuk ketujuh arketipe: topologi deployment
ditentukan oleh **tool apa yang dipasang ke agent**, bukan oleh identitas
arketipenya. Dua project yang sama-sama "Workflow Agent" bisa butuh topologi
berbeda total kalau satu punya tool `execute` dan yang lain cuma tool API
pihak-ketiga sempit — dan dua arketipe berbeda (Workspace Agent, Generative
Builder) bisa butuh topologi yang **sama** kalau keduanya sama-sama punya
`execute`. Mengelompokkan topologi per arketipe di `deltas/*.md` akan
menduplikasi keputusan yang sama tujuh kali dan tetap salah begitu ada
project yang mencampur tool lintas kategori — makanya file ini berdiri
sendiri, bukan section di tiap delta.

Baseline deployment (`_base.md`) dan tabel komponen→bound→sinyal HPA sudah
dipatok penuh di [`../concepts/serving-topology.md`](../concepts/serving-topology.md)
dan [`../concepts/scaling.md`](../concepts/scaling.md) — **tidak diulang di
sini**. File ini menjawab satu pertanyaan yang belum dijawab keduanya:
untuk *project konkret* dengan tool surface tertentu, komponen mana dari
tabel itu yang sungguh perlu dipisah dari orchestrator lebih dulu, dan apa
persisnya yang berubah saat pemisahan itu terjadi.

## Tool surface menentukan komponen yang perlu dipisah

`serving-topology.md` mendaftar lima komponen (Gateway/SSE, Orchestrator,
Tool executor, Retrieval/embedding, State store). Semua project mulai dari
`_base` — modular monolith, kelima "komponen" itu kolokasi di satu
deployable. Kolom kanan tabel berikut adalah komponen mana yang **realistis
jadi kandidat pisah pertama** kalau beban tumbuh, ditentukan murni dari tool
apa yang dipasang di tiap arketipe (dikutip dari `## Bangun ini pakai
deepagents`/`## Posisi di 6 sumbu` tiap file arketipe) — bukan dari nama
arketipenya:

| Arketipe | Tool surface (ringkas) | Kandidat pisah pertama |
|---|---|---|
| 01 Workspace Agent | `execute` (bash luas), lewat `LocalShellBackend`/backend sandbox — lihat `deltas/01-workspace-agent.md` | **Tool executor** — `execute` adalah fase CPU-bound (`resource-profiling.md`); tanpa isolasi tambahan blast radius = mesin host (`sandboxing.md`) |
| 02 Generative Builder | `execute` di sandbox milik sendiri (`DaytonaSandbox`/setara) | **Tool executor** — sama alasan seperti 01, tapi backend sudah microVM sejak `_base` delta-nya (biaya sandbox dominan lebih awal) |
| 03 General Task Agent | Campuran: `execute` **dan/atau** tool retrieval, tergantung subagent yang didelegasikan | **Tool executor DAN/ATAU Retrieval** — ditentukan tool nyata yang dipasang tiap subagent, bukan aturan tetap untuk arketipe ini |
| 04 Research/Analyst | `web_search`/retrieval, `think_tool` — tidak ada `execute` sama sekali | **Retrieval/embedding** saja — tidak pernah butuh Tool executor terpisah karena tidak ada tool CPU-bound |
| 05 In-App Copilot | Tool sempit ke API produk tuan rumah, tanpa `execute`, tanpa retrieval mandiri | **Tidak ada** — orchestrator saja cukup; tidak ada tool CPU/GPU-bound yang layak dipisah |
| 06 Workflow Agent | Tool API pihak ketiga, kadang `execute` tergantung workflow konkret | Sama seperti baris 03 — ditentukan tool nyata, "workflow" bukan sinyal topologi |
| 07 Computer-Use Agent | click/type/screenshot lewat backend automasi browser (Playwright/CDP), idealnya di sandbox | **Tool executor** — browser automation CPU/memory-bound sama seperti `execute`, alasan isolasi sama (`sandboxing.md`) |

Konsekuensi langsung: **05 In-App Copilot tidak pernah butuh Tool
executor/Retrieval terpisah** berapa pun skalanya — bukan karena arketipe
itu "kecil", tapi karena tool surface-nya secara struktural tidak pernah
punya kandidat CPU/GPU-bound untuk dipisah. Sebaliknya, dua project "06
Workflow Agent" bisa berakhir di topologi yang sama sekali berbeda kalau
satu memasang `execute` dan satu tidak — baris tabel untuk 06 memang sengaja
tidak memberi jawaban tunggal.

## Migrasi modular monolith → microservice

`_base.md` sudah menulis tiga jahitan (`Orchestrator` Protocol, tool
executor lewat `SandboxBackendProtocol`, retrieval lewat `StoreBackend`)
supaya migrasi ini adalah **ganti binding + manifest**, bukan rewrite
(`serving-topology.md` §Modular monolith dengan jahitan dipotong). Konkretnya:

### Yang berubah: binding

Hari ini `app/api/deps.py`'s `build_orchestrator(model, checkpointer)`
mengembalikan `DeepAgentsOrchestrator(...)` (in-process, `_base.md` §Binding).
Begitu Tool executor (atau orchestrator itu sendiri) dipisah jadi service
sendiri, satu-satunya yang berubah adalah **isi fungsi itu** — implementasi
baru yang **memenuhi Protocol yang sama**:

```python
"""RemoteOrchestratorClient -- binding pengganti DeepAgentsOrchestrator SAAT
tool executor/orchestrator dipisah jadi service sendiri. Implementasi
Protocol Orchestrator yang SAMA (orchestrator/interface.py) -- return value
build_orchestrator() (app/api/deps.py) diganti ke ini; main.py dan
routes/turns.py tidak berubah satu baris pun.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.orchestrator.interface import Scope, TurnEvent


class RemoteOrchestratorClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base_url = base_url
        self._client = client

    async def run_turn(
        self, scope: Scope, turn_id: str, thread_id: str, user_input: str
    ) -> AsyncIterator[TurnEvent]:
        # Scope diteruskan eksplisit di payload -- BUKAN ambient state --
        # syarat 4 modular monolith (serving-topology.md): begitu jadi
        # network call sungguhan, otorisasi harus ikut eksplisit.
        payload = {
            "user_id": scope.user_id,
            "turn_id": turn_id,
            "thread_id": thread_id,
            "message": user_input,
        }
        async with self._client.stream(
            "POST", f"{self._base_url}/internal/turns", json=payload
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line.removeprefix("data: "))
                yield TurnEvent(**data)
```

`app/api/routes/turns.py` **tidak berubah satu baris pun** — ia menerima
`orchestrator: Orchestrator = Depends(get_orchestrator)` (`_base.md`
§Binding) dan memanggil `orchestrator.run_turn(...)` lewat Protocol, tidak
pernah tahu (atau perlu tahu) apakah implementasinya lokal atau network
call. `main.py` juga tidak berubah — pemanggilnya tetap
`build_orchestrator(model, checkpointer)`, cuma isi fungsi itu di
`deps.py` yang beda. Ini persis syarat 1 modular monolith
(`serving-topology.md`): panggilan lintas komponen lewat interface
eksplisit, bukan pemanggilan langsung. Catatan jujur: `model`/`checkpointer`
yang diteruskan ke `build_orchestrator` jadi parameter yang tidak dipakai
`RemoteOrchestratorClient` — dua parameter mati yang sengaja dibiarkan
alih-alih mengubah signature, supaya `main.py` benar-benar nol-baris-ubah;
kalau itu mengganggu, membersihkan signature-nya tetap migrasi satu file
yang sama (`deps.py`), bukan penyebaran ke file lain.

### Yang berubah: manifest

`k8s/deployment.yaml` (`_base.md`) yang tadinya satu Deployment pecah jadi
dua, masing-masing dengan sinyal scaling sendiri dari `scaling.md`:

| | Sebelum (`_base.md`) | Sesudah (dipisah) |
|---|---|---|
| Deployment | Satu (`harness-orchestrator`), replicas tetap | Dua: `harness-orchestrator` (in-flight turns) + `harness-tool-executor` (queue depth/CPU, `scaling.md` §Konfigurasi konkret per komponen) |
| Service | Satu | Dua — `harness-tool-executor` jadi tujuan network call `RemoteOrchestratorClient`/backend baru di atas |
| Scaling | Tidak ada HPA/KEDA di `_base.md` (sengaja, lihat `_base.md` §Manifest K8s dasar) | KEDA `ScaledObject` terpisah per Deployment, trigger `prometheus` masing-masing atas gauge/queue-depth miliknya sendiri — konfigurasi konkretnya `scaling.md`, tidak diulang di sini |
| Node pool | Homogen | Kalau komponen yang dipisah GPU-bound (Retrieval), tambah taint+toleration+nodeAffinity (`scaling.md` §Node pool GPU) |

### Yang TIDAK berubah: logika

- Skema DDL (`persistence-schema.md`) dan RLS — sama persis, `db/session.py`
  tidak berubah.
- Kontrak `SandboxBackendProtocol`/`StoreBackend` yang dipakai
  `FilesystemMiddleware` di dalam `deepagents` — sama persis, backend
  implementasinya (lokal vs microVM eksternal) sudah selalu berupa binding
  yang bisa diganti sejak `_base`, migrasi ini tidak mengubah kontraknya.
- Skema event streaming (`streaming-protocol.md`) dan kontrak reattach —
  `TurnEvent` yang di-yield `Orchestrator.run_turn(...)` bentuknya sama
  baik yang men-generate-nya proses lokal atau service jarak jauh yang
  mem-forward SSE upstream (lihat `RemoteOrchestratorClient` di atas —
  ia mem-parse ulang event dari service lain jadi `TurnEvent` yang sama,
  bukan skema baru).
- Guardrail dan safety gate — titik penegakan (`guardrails.md`) tetap
  hidup di `middleware=[...]`/`interrupt_on=` saat `create_deep_agent(...)`
  dipanggil; pindah proses tidak memindahkan *di mana* guardrail dievaluasi.

## Sumber

- `[code]` [`../concepts/serving-topology.md`](../concepts/serving-topology.md)
  — tabel komponen→bound→sinyal HPA, empat syarat modular monolith, dan
  argumen in-flight-turns vs RPS; tidak diulang di sini.
- `[code]` [`../concepts/scaling.md`](../concepts/scaling.md) — konfigurasi
  KEDA/taint konkret yang dirujuk di tabel migrasi manifest, tidak diulang.
- `[code]` [`../concepts/resource-profiling.md`](../concepts/resource-profiling.md)
  — dasar "Tool executor = kandidat pisah pertama begitu ada `execute`",
  argumen lima fase/empat bound.
- `[code]` [`../concepts/sandboxing.md`](../concepts/sandboxing.md) — dasar
  kenapa `execute`/browser automation butuh isolasi tambahan begitu
  dipisah, bukan cuma alasan performa.
- `[code]` `../archetypes/01..07-*.md` §Bangun ini pakai deepagents/§Posisi
  di 6 sumbu — sumber tool surface tiap baris tabel §Tool surface
  menentukan komponen di atas, dikutip tanpa membaca ulang.
- `[code]` `_base.md` — `Orchestrator` Protocol dan tiga jahitan yang jadi
  dasar §Migrasi di file ini.
