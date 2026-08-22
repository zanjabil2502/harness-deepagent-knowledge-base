# Desain: Agent Harness Engineering Knowledge Base

- **Tanggal:** 2026-08-23
- **Status:** Draft — menunggu review
- **Repo:** `base-deep-agent`

---

## 1. Masalah

Setiap kali membangun harness agent atau project berbasis AI Assistant, keputusan
arsitektural yang sama diulang dari nol: bentuk loop, cara mengelola konteks,
di mana state disimpan, bagaimana dilayani multi-user, guardrail apa yang dipasang.
Hasilnya tidak konsisten dan jarang production-grade.

Pengetahuan yang dibutuhkan terpencar di dokumentasi library, source code puluhan
repo, dan perilaku produk closed-source yang tidak terdokumentasi.

## 2. Tujuan

Satu knowledge base yang, diberi deskripsi project apa pun (goal, output, journey,
constraint, atau bentuk lain), mampu menghasilkan:

1. **Klasifikasi arketipe** — ini AI Assistant jenis apa
2. **Harness Blueprint** — keputusan arsitektural konkret di 7 sumbu
3. **Scaffold** — struktur project production-grade yang siap dikoding

KB ini dikonsumsi sebagai **Claude Code Skill**: `SKILL.md` tipis sebagai router
dan prosedur, `references/` sebagai kedalaman yang dimuat sesuai kebutuhan.

## 3. Non-tujuan

- Bukan template repo yang di-`cp -r`. Scaffold disimpan sebagai spesifikasi +
  snippet terverifikasi, karena template repo membusuk (pin versi basi, dependency
  drift) dan memaksa satu bentuk padahal tiap blueprint berbeda.
- Bukan tutorial deepagents. Dokumentasi resmi sudah ada; KB ini mengisi lapisan
  keputusan yang tidak dibahas dokumentasi.
- Bukan katalog semua harness yang pernah ada. Cakupan dibatasi lewat kerangka
  (lihat §6, §7), bukan lewat daftar.
- Tidak mengejar multi-tenant penuh di iterasi pertama (lihat asumsi §13, A4).

## 4. Prinsip desain

| Prinsip | Konsekuensi |
|---|---|
| **Cakupan ditentukan kerangka, bukan daftar** | Grid sumbu wajib penuh; menambah entri tidak mengubah struktur |
| **Kejujuran sumber** | Tiap klaim dilabeli `[code]` / `[docs]` / `[inferred]` |
| **DRY** | `_base` + delta, bukan N boilerplate lengkap |
| **Jahitan dipotong lebih dulu** | Modular monolith yang siap dipecah, bukan microservice prematur |
| **Kebijakan bukan prosa** | Aturan yang bisa diverifikasi kode tidak boleh hidup di prompt |
| **Netral bahasa** | Routing dan policy tidak menyentuh string bahasa |

## 5. Struktur

```
.                                 (root repo = root skill, siap di-symlink ke ~/.claude/skills/)
├── SKILL.md                      router tipis + prosedur diagnostik
└── references/
    ├── archetypes/
    │   ├── README.md             6 sumbu pembeda, 7 arketipe, matriks hibrida
    │   ├── 01-workspace-agent.md
    │   ├── 02-generative-builder.md
    │   ├── 03-general-task-agent.md
    │   ├── 04-research-agent.md
    │   ├── 05-in-app-copilot.md
    │   ├── 06-workflow-agent.md
    │   └── 07-computer-use-agent.md
    ├── concepts/                 5 bidang, wajib penuh (§7)
    ├── systems/
    │   ├── _template.md          grid 7 sumbu
    │   ├── INDEX.md              tier T3
    │   └── *.md                  tier T1/T2
    ├── scaffolds/
    │   ├── _base.md              struktur production-grade, arketipe-agnostik
    │   ├── serving.md            topologi deployment (lintas arketipe)
    │   └── deltas/01..07.md      selisih per arketipe
    ├── blueprint-template.md
    └── recipes/                  kode deepagents yang jalan
```

**Tiap file arketipe wajib ditutup section "Bangun ini pakai deepagents"** —
konfigurasi, middleware, dan backend konkret. Ini jembatan yang menyatukan
lapisan peta dengan lapisan kendaraan.

## 6. Taksonomi arketipe

### 6.1 Sumbu pembeda

| Sumbu | Pertanyaan |
|---|---|
| Blast radius | Menyentuh apa? mesin user / sandbox / data SaaS / dunia luar |
| Artefak | Output-nya apa? edit yang ada / bikin baru / jawaban / aksi di sistem lain |
| Horizon | Sekali jalan / satu sesi / hidup di background |
| Kendali manusia | Approve tiap langkah / review di akhir / tanpa manusia |
| Permukaan domain | General atau vertikal |
| Antarmuka | CLI / IDE / kanvas / chat / API tertanam |

Potongan utama: **artefak × blast radius**.

### 6.2 Tujuh arketipe

| # | Arketipe | Contoh | Konsekuensi harness |
|---|---|---|---|
| 1 | Workspace Agent | Claude Code, Cursor, Aider, OpenHands | Permission gate, tool bash luas, compaction agresif, resume |
| 2 | Generative Builder | Figma Make, v0, Lovable, Bolt | Sandbox, state = 1 artefak, iterasi cepat, persistence pendek |
| 3 | General Task Agent | Abacus DeepAgent, Manus | Planning eksplisit, subagent, filesystem-as-memory, horizon panjang |
| 4 | Research/Analyst | Deep Research, Perplexity, Elicit | Loop search→read→synthesize, budget token, wajib provenance |
| 5 | In-App Copilot | Notion AI, Figma AI, Agentforce | Tool = API produk, horizon pendek, undo/rollback kritis |
| 6 | Workflow Agent | Zapier/n8n agents, cron agent | Tanpa human-in-loop → retry, idempotency, observability, kill switch |
| 7 | Computer-Use Agent | Operator, browser agent | Loop lihat→klik→verifikasi, tool sempit tapi dalam, paling rapuh |

Hibrida normal dan dicatat eksplisit (Cursor = 1+5, Manus = 3+7).

### 6.3 Dimensi deployment (ortogonal)

Arketipe menjawab "ini asisten macam apa". Dimensi deployment menjawab "dilayani
bagaimana" — dan keduanya independen. Workspace Agent bisa berupa CLI lokal atau
layanan multi-user di K8s. Dimensi ini tinggal di `concepts/` bidang Runtime,
bukan di taksonomi arketipe.

## 7. Kerangka `concepts/` — 5 bidang wajib penuh

Cakupan ditentukan bidang, bukan oleh topik yang kebetulan terpikirkan.

### Bidang 1 — Cognition
`agent-loop.md`, `planning.md`, `delegation.md`, `context-engineering.md`
(termasuk trade-off compaction vs prompt caching), `memory.md`,
`policy-as-data.md`, `skill-composition.md`

### Bidang 2 — Interface
`tool-design.md`, `mcp.md`, `streaming-protocol.md` (termasuk reattach),
`human-in-the-loop.md`, `structured-output.md`, `multilingual.md`

### Bidang 3 — Data
`session-state.md`, `persistence-schema.md`, `artifacts-and-canvas.md`,
`retention-and-deletion.md`

### Bidang 4 — Runtime
`serving-topology.md`, `resource-profiling.md`, `isolation-and-scoping.md`,
`sandboxing.md`, `queueing-and-backpressure.md`, `scaling.md`

### Bidang 5 — Assurance
`observability.md`, `evaluation.md`, `cost-control.md`, `guardrails.md`,
`security.md`, `replay-and-forensics.md`

**Aturan:** tiap bidang wajib punya minimal satu reference implementation `[code]`.
Topik yang tidak menemukan repo terbaca ditandai lemah — jujur, bukan dikarang.

## 8. Keputusan teknis yang sudah dikunci

### 8.1 Lima lapis state (Bidang Data)

Garis batas: **BE punya kebenaran, AI punya proyeksi.** Heuristik — kalau bisa
dihitung ulang, boleh ephemeral di sisi AI; kalau tidak, wajib durable di BE.

| Lapis | Store | Lifetime | Pemilik |
|---|---|---|---|
| Transcript | Postgres append-only | permanen | BE |
| Model context | dihitung, cache Redis | 1 call | Harness |
| Run state | Checkpointer (Postgres) | 1 run, resumable | Harness |
| Memory | Postgres + vector | lintas sesi | BE + AI |
| Artefak | S3/GCS + row metadata | permanen, berversi | BE |

Aturan turunan:
- Transcript adalah **tree**, bukan list (edit pesan → bercabang)
- Checkpointer **bukan** database produk — jangan bangun fitur daftar chat di atasnya
- Artefak **by reference** — transcript menyimpan `artifact_id + version`, context
  menyimpan handle + ringkasan, byte-nya di object store
- Tool call & hasilnya adalah row transcript kelas satu
- Compaction dicatat sebagai event yang menunjuk pesan yang digantikan
- Idempotency key per turn
- Retention cascade wajib menyapu vector index dan trace store

### 8.2 Isolasi & scoping (Bidang Runtime)

Default: **multi-user** (`user_id`), bukan multi-tenant. Namun `user_id` tidak
pernah di-hardcode — semua akses data lewat **scope object** yang hari ini berisi
`(user_id)` dan nanti `(tenant_id, user_id)`.

Penegakan di **Postgres RLS**, bukan `WHERE` manual per query. Alasan: satu query
lupa filter = kebocoran antar user, dan itu pasti terjadi di codebase yang hidup.

### 8.3 Serving & resource (Bidang Runtime)

Satu turn agent adalah workload campuran: LLM call = IO-bound, context assembly =
memory-bound, code exec = CPU-bound + butuh isolasi, embedding = GPU-bound.
Satu pod memaksa scaling di dimensi terburuk.

| Komponen | Bound | Sinyal HPA |
|---|---|---|
| Gateway / SSE | IO | koneksi aktif |
| Orchestrator | IO dominan | **in-flight turns**, bukan RPS |
| Tool executor | CPU + mem | queue depth, CPU |
| Retrieval / embedding | GPU atau CPU | batch queue, GPU util |
| State store | IO/disk | bukan pod |

**`_base` = modular monolith dengan jahitan sudah dipotong.** Satu deployable,
tapi orchestrator / executor / retrieval terpisah di balik interface, sehingga
pecah jadi microservice = ganti binding + manifest, bukan rewrite.

### 8.4 Guardrail (Bidang Assurance)

Enam titik penegakan:

| # | Titik | Isi |
|---|---|---|
| 1 | Input | PII redaction, deteksi injection & jailbreak, batas topik, moderasi, abuse check |
| 2 | Retrieval/context | **Filter otorisasi** (paling sering bocor di RAG multi-user), penandaan konten tak-dipercaya, provenance |
| 3 | Tool/aksi | Allowlist per peran, validasi argumen, penyempitan scope token, gerbang approval, batas sandbox, dry-run |
| 4 | Output | Validasi schema, moderasi, cek kebocoran PII, groundedness, wajib sitasi, scan secret di kode generated |
| 5 | Loop | Max step, max kedalaman subagent, budget token/biaya, timeout, deteksi oscillation & no-progress, kill switch |
| 6 | Sistem | Pin versi model, kebijakan fallback, audit log tiap keputusan gerbang |

Aturan turunan:
- Tiap guardrail wajib menyatakan **kebijakan + titik penegakan + mode kegagalan**.
  Fail-open untuk moderasi, fail-closed untuk otorisasi. Jika tidak diputuskan,
  defaultnya menjadi kebetulan.
- Bertingkat: cek deterministik murah dulu, model-based hanya jika perlu
- Guardrail punya false-positive rate → masuk eval harness, diukur
- Kebijakan tidak boleh hanya di prompt. Prompt bisa dibujuk, middleware tidak.
- Di deepagents, guardrail memetakan 1:1 ke **middleware**

### 8.5 Policy as data & skill turunan (Bidang Cognition)

Aturan yang bisa diverifikasi kode → policy deklaratif (YAML/DB) + ditegakkan
middleware. Prompt hanya untuk yang butuh judgment bahasa alami.

Alasan: prosa-sebagai-aturan menderita dilusi (aturan ke-47 melemahkan 1–46),
presedensi implisit (yang menang adalah yang ditulis belakangan), dan tidak terlihat
saat runtime.

Skill punya model dasar → turunan lewat manifest deklaratif:

```yaml
id: legal-research
extends: retrieval
intents: [research.legal]        # kode netral, bukan frasa bahasa
locales: [id, en]
tools:    [+citation_check, -web_write]
policies: [+require_citation, +pii_redact]
precedence: derived_wins
```

Resolusi = komposisi dengan presedensi eksplisit, bukan sambung paragraf.

### 8.6 Multilingual (Bidang Interface)

Pisahkan **intent** dari **ekspresi**:

```
input (bahasa apa pun) → klasifikasi intent → kode netral (`deploy.request`)
  → lookup policy/skill by kode   [nol bahasa di sini]
  → eksekusi → render output di locale user
```

Titik yang terkunci bahasa dan wajib ditangani: trigger skill, regex guardrail
(NIK/NPWP ≠ SSN), deteksi injection, **eval golden test**, dan kalibrasi budget
token (bahasa non-Latin memakan token lebih banyak per kata).

Locale adalah konteks kelas satu di session, bukan tebakan per turn. Yang
dilokalkan: leksikon guardrail, few-shot, template output, pesan error. Instruksi
sistem tidak perlu diterjemahkan.

## 9. Grid `systems/` — 7 sumbu

| # | Sumbu | Pertanyaan |
|---|---|---|
| 1 | Loop shape | ReAct / plan-execute / loop-until-done? siapa yang memutuskan berhenti? |
| 2 | Context | compaction, summarization, filesystem-as-memory? |
| 3 | Tool surface | banyak tool sempit atau sedikit tool luas? kenapa? |
| 4 | Delegation | subagent atau flat? bagaimana hasil kembali? |
| 5 | State & resume | todo, scratchpad, checkpoint, resume? |
| 6 | Safety gate | kapan minta izin? apa yang di-sandbox? |
| 7 | **Capability routing & policy** | bagaimana memutuskan skill/mode mana yang dipakai — prosa + judgment model, manifest deklaratif, atau classifier? |

Multilingual **bukan** sumbu, melainkan kolom catatan di INDEX — ketiadaan desain
multilingual di sebuah sistem itu sendiri temuan.

## 10. Tier kedalaman & sumber

| Tier | Isi | Jumlah |
|---|---|---|
| T1 — bedah dalam | `deepagents`: API, middleware, backend, subagent, state | 1 |
| T2 — grid 7 sumbu | 1–2 sistem eksemplar per arketipe + referensi infrastruktur | ~12 |
| T3 — indeks | nama + arketipe + 1 baris ciri khas | tak terbatas |

Kandidat T2 (final saat penulisan, tergantung keterbacaan source):

| Keperluan | Repo |
|---|---|
| Multi-user BE, transcript, branching | LibreChat, Open WebUI, Onyx |
| Artefak / canvas | Vercel `ai-chatbot`, assistant-ui |
| Server + sandbox runtime | **OpenHands** |
| Memory lintas sesi | Letta, Mem0, Zep |
| Kuota & rate-limit per user | **LiteLLM** |
| Isolasi eksekusi kode | E2B, Daytona, microsandbox |
| Tracing & atribusi biaya | Langfuse, Phoenix, OpenLLMetry |
| Serving GPU-bound | vLLM, SGLang, Ray Serve, KEDA |
| Context engineering | Aider, SWE-agent, Cline |
| Platform workflow | Dify, n8n |
| Computer-use | browser-use, Stagehand |

Label sumber: **`[code]`** (dibaca dari source) > **`[docs]`** (dokumentasi resmi)
> **`[inferred]`** (disimpulkan dari perilaku produk closed). Mayoritas harus `[code]`.

## 11. Prosedur diagnostik (isi `SKILL.md`)

```
deskripsi project (bentuk apa pun)
   ↓ isi 6 sumbu pembeda
Arketipe (bisa hibrida)
   ↓ archetypes/NN-*.md
Batasan harness yang dipaksa arketipe
   ↓ cek silang concepts/ + systems/
HARNESS BLUEPRINT
   ├─ loop shape / context / tool surface / delegation
   ├─ state & resume        (§8.1)
   ├─ guardrail             (§8.4)
   ├─ deployment & resource (§8.3)
   ├─ isolation & scoping   (§8.2)
   └─ config deepagents
   ↓ scaffolds/_base + delta + serving
   ↓ gerbang wajib: checklist production-readiness
PROJECT PRODUCTION-GRADE
```

Blueprint yang dihasilkan tiap project disimpan dan kelak menjadi bahan T2/T3 —
KB memakan hasil kerja sendiri.

## 12. Checklist production-readiness (gerbang wajib scaffold)

| Syarat | Kegagalan yang dicegah |
|---|---|
| Tracing & observability | Agent gagal diam-diam, debugging jadi tebakan |
| Eval harness (termasuk multibahasa) | Ganti prompt = regresi senyap |
| Budget & cost guard | Loop liar membakar biaya semalam |
| Retry, timeout, idempotency | Tool call gagal itu normal, bukan pengecualian |
| Context overflow policy | Diputuskan di awal, bukan saat meledak |
| Secrets & config management | Key tersebar di kode |
| Human gate + audit log | Aksi destruktif tanpa jejak |
| Prompt & policy versioning | Tidak bisa rollback |
| Kill switch & sandbox | Blast radius tidak terbatas |

## 13. Asumsi (ditandai eksplisit, siap dikoreksi)

| # | Asumsi | Dampak jika salah |
|---|---|---|
| A1 | Target deploy: cloud **dan** on-prem | Isi `serving.md` dan `scaffolds/_base` |
| A2 | Menggunakan API key milik operator, kuota per user; BYOK sebagai opsi | Isi `isolation-and-scoping.md`, `cost-control.md` |
| A3 | Stack BE: Python + FastAPI (menyambung deepagents) | Bentuk seluruh `scaffolds/` |
| A4 | Multi-user (`user_id`), multi-tenant sebagai jalur migrasi | §8.2 |
| A5 | Scope bahasa KB: Python; `deepagentsjs` hanya disebut di INDEX | Tidak ada file TS |

## 14. Rencana penulisan

Ditulis bertahap, tiap batch bisa dipakai sebelum batch berikutnya selesai:

1. **Fondasi** — `SKILL.md`, `archetypes/README.md` + 7 file arketipe,
   `systems/_template.md`, `blueprint-template.md`
2. **Kendaraan** — `systems/deepagents.md` (T1) + `recipes/`
3. **Bidang Data & Runtime** — concept files (jawaban paling langsung atas
   concern BE↔AI dan serving)
4. **Bidang Assurance & Cognition** — guardrails, eval, policy-as-data,
   skill-composition, multilingual
5. **Bidang Interface** + sisa `systems/` T2 + `INDEX.md` T3
6. **Scaffolds** — `_base.md`, `serving.md`, `deltas/`

## 15. Risiko

| Risiko | Mitigasi |
|---|---|
| Riset `systems/` melebar tanpa batas | Grid 7 sumbu + tier T3 sebagai penampung murah |
| Klaim tentang produk closed jadi tebakan | Label `[inferred]` wajib, mayoritas harus `[code]` |
| KB membusuk seiring versi deepagents | T1 menyebut versi yang diverifikasi; sisanya konseptual |
| SKILL.md membengkak → boros token | SKILL.md hanya router + prosedur; kedalaman di `references/` |
| Scaffold hasil generate tidak jalan | Wajib diverifikasi sampai hijau tiap kali, bukan diasumsikan |
