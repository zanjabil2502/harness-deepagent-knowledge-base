# Template Harness Blueprint

Salin file ini per project. Isi tiap bagian — jangan hapus baris kerangka
yang sudah terisi dari framework KB, tambahkan keputusan spesifik project di
kolom yang disediakan.

## Ringkasan project

- **Nama:**
- **Deskripsi singkat:**
- **Domain (general/vertikal):**

## Arketipe

- **Arketipe utama:**
- **Arketipe sekunder (jika hibrida):**

| Sumbu | Nilai project ini |
|---|---|
| Blast radius | |
| Artefak | |
| Horizon | |
| Kendali manusia | |
| Permukaan domain | |
| Antarmuka | |

## 7 sumbu harness

Kolom terakhir adalah bacaan sebelum mengisi kolom keputusan — tanpa itu
sumbu diisi dari kebiasaan, bukan dari trade-off yang sudah dipetakan.

| # | Sumbu | Keputusan | Timbang dulu |
|---|---|---|---|
| 1 | Loop shape | | [`agent-loop`](concepts/agent-loop.md), [`planning`](concepts/planning.md) |
| 2 | Context | | [`context-engineering`](concepts/context-engineering.md), [`memory`](concepts/memory.md) |
| 3 | Tool surface | | [`tool-design`](concepts/tool-design.md), [`mcp`](concepts/mcp.md), [`structured-output`](concepts/structured-output.md) |
| 4 | Delegation | | [`delegation`](concepts/delegation.md), [`code-orchestration`](concepts/code-orchestration.md) — subagent dipilih model per giliran, atau di-dispatch dari kode? |
| 5 | State & resume | | [`session-state`](concepts/session-state.md), [`streaming-protocol`](concepts/streaming-protocol.md) |
| 6 | Safety gate | | [`human-in-the-loop`](concepts/human-in-the-loop.md), [`guardrails`](concepts/guardrails.md) — tiap titik: kebijakan + titik + mode kegagalan |
| 7 | Capability routing & policy | | [`policy-as-data`](concepts/policy-as-data.md), [`skill-composition`](concepts/skill-composition.md), [`multilingual`](concepts/multilingual.md) |

## Antarmuka & keluaran

| Pertanyaan | Keputusan | Timbang dulu |
|---|---|---|
| Siapa yang memanggil harness ini — UI sendiri, editor, atau agent lain? | | [`agent-protocols`](concepts/agent-protocols.md) |
| Keluaran selain prosa yang perlu dirender (tabel, chart, diagram, rumus)? | | [`scaffolds/skills/`](scaffolds/skills/README.md) |

## State & data

Lima lapis, garis batas: BE punya kebenaran, AI punya proyeksi.

| Lapis | Store | Lifetime | Pemilik | Keputusan project |
|---|---|---|---|---|
| Transcript | Postgres append-only | permanen | BE | |
| Model context | dihitung, cache Redis | 1 call | Harness | |
| Run state | Checkpointer (Postgres) | 1 run, resumable | Harness | |
| Memory | Postgres + vector | lintas sesi | BE + AI | |
| Artefak | S3/GCS + row metadata | permanen, berversi | BE | |

## Guardrail

Tiap titik wajib punya kebijakan + titik penegakan + mode kegagalan. Fail-open
untuk moderasi, fail-closed untuk otorisasi — kalau tidak diputuskan, defaultnya
jadi kebetulan.

| # | Titik | Kebijakan | Titik penegakan | Mode kegagalan |
|---|---|---|---|---|
| 1 | Input | | | |
| 2 | Retrieval/context | | | |
| 3 | Tool/aksi | | | |
| 4 | Output | | | |
| 5 | Loop | | | |
| 6 | Sistem | | | |

## Deployment & resource

Satu turn agent adalah workload campuran — jangan paksa satu pod untuk semua.

| Komponen | Bound | Sinyal HPA | Keputusan project |
|---|---|---|---|
| Gateway / SSE | IO | koneksi aktif | |
| Orchestrator | IO dominan | in-flight turns | |
| Tool executor | CPU + mem | queue depth, CPU | |
| Retrieval / embedding | GPU atau CPU | batch queue, GPU util | |
| State store | IO/disk | bukan pod | |

- **Topologi awal (monolith/split):**

## Isolation & scoping

- **Default:** multi-user (`user_id`), bukan multi-tenant kecuali dinyatakan lain.
- **Scope object project ini:**
- **Penegakan (RLS/lainnya):**

## Config deepagents

```yaml
# isi konfigurasi deepagents aktual: subagents, middleware, tools, checkpointer
```

## Checklist production-readiness

Gerbang wajib sebelum scaffold dianggap selesai. Ini satu-satunya salinan
checklist ini di KB — referensikan section ini dari file lain, jangan disalin.

- [ ] Tracing & observability
- [ ] Eval harness (termasuk multibahasa)
- [ ] Budget & cost guard
- [ ] Retry, timeout, idempotency
- [ ] Context overflow policy
- [ ] Secrets & config management
- [ ] Human gate + audit log
- [ ] Prompt & policy versioning
- [ ] Kill switch & sandbox
