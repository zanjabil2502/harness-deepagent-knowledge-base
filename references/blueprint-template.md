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

| # | Sumbu | Keputusan |
|---|---|---|
| 1 | Loop shape | |
| 2 | Context | |
| 3 | Tool surface | |
| 4 | Delegation | |
| 5 | State & resume | |
| 6 | Safety gate | |
| 7 | Capability routing & policy | |

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
