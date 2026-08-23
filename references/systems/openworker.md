# OpenWorker

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. Sumber dibaca dari `git clone --depth 1` repo `andrewyng/openworker`
pada commit `141d02a` (2026-08-22), 257 file Python / 75.493 baris. Repo berstatus
**open beta** menurut README-nya sendiri. `[code]`

## Arketipe

**General Task Agent (03)** sebagai inti, tapi hibrida **empat arah** — paling
banyak dari semua sistem di indeks ini. Artefaknya dokumen/spreadsheet/laporan
sebagai file jadi (**Generative Builder 02**), sekaligus bertindak di objek SaaS
lewat 25+ konektor (**In-App Copilot 05**), menyentuh terminal dan file lokal
(**Workspace Agent 01**), dan punya automation terjadwal yang berjalan tanpa
ditunggu (**Workflow Agent 06**).

Blast radius: mesin operator **plus** data SaaS yang dia sambungkan. Kendali
manusia: approval per aksi konsekuensial. Antarmuka: desktop GUI, mention Slack,
dan penjadwal. **Single-operator** — README menyebutnya eksplisit: *"designed for
a single operator"*. `[docs]` README

## 1. Loop shape

`TurnEngine` (`coworker/engine.py:65`) menjalankan `while True` (`:356`) dengan
pembatas iterasi di puncak loop (`:357`); saat terlampaui ia memancarkan status
`max_iterations_exceeded` (`:360`). Model yang memutuskan berhenti secara normal;
pembatas hanya jaring pengaman. `[code]`

Default efektifnya **150**, dari `config.max_iterations` (`coworker/config.py:34`)
yang dioper di `coworker/agent.py:508-510`. Angka `12` pada signature
`TurnEngine.__init__` (`engine.py:75`) hanya fallback konstruktor dan tidak
berlaku di jalur normal. `[code]`

## 2. Context

Auto-kompaksi dengan batas eksplisit. `CompactionState` (`coworker/compaction.py:86-94`)
menyimpan `boundary_index` yang menunjuk ke **daftar pesan kanonik**: pesan sebelum
batas diwakili blok terkompaksi di *outbound view*, pesan dari batas ke depan
dikirim verbatim. State-nya dipersist bersama sesi (`coworker/sessions.py:37-39`)
sehingga sesi yang dimuat ulang mempertahankan view terkompaksinya. `[code]`

Pemisahan kanonik/outbound ini setara dengan pemisahan transcript vs model context
di [`../concepts/session-state.md`](../concepts/session-state.md) — ditemukan
independen, dan di sini batasnya berupa satu indeks yang eksplisit.

## 3. Tool surface

Sedikit tool luas ditambah banyak konektor sempit. Terminal (`run_shell`) dan
operasi file lokal (`write_file`, `replace_in_file`, `apply_patch`,
`apply_unified_diff`) adalah tool bawaan yang risikonya ditetapkan by-name
(`coworker/risk.py:26-33`). `[code]` Di atasnya 25+ integrasi (GitHub, Slack, Jira,
Notion, Linear, HubSpot, Outlook, monday.com, Gmail, Google Calendar) plus apa pun
yang dapat dicapai lewat MCP. `[docs]` README

Biner eksternal dikelola sendiri: `coworker/toolchain.py` mengunduh, memverifikasi
hash (`_verify`, `:227`), dan me-resolve path (`resolve`, `:171`), dengan
`missing()`/`installable()` untuk menyatakan kebutuhan sebelum dipakai. `[code]`

## 4. Delegation

Satu bentuk delegasi: **explorer subagent** read-only
(`coworker/tools/subagent.py:79`, `build_explorer_engine` di `:42`). Docstring
tool-nya menyatakan kontraknya sendiri — riset broad read-only dengan *"its own
fresh context window"*, mengembalikan **hanya laporan akhir**, dan *"the
intermediate file reads never touch your context"*. Panggilan `explore` independen
berjalan paralel bila diminta bersamaan. `[code]`

Kontrak hasil ini persis pola yang dianjurkan
[`../concepts/delegation.md`](../concepts/delegation.md): subagent mengembalikan
ringkasan bersih, bukan transkrip.

## 5. State & resume

Sesi dipersist beserta state kompaksinya (`sessions.py:37-39`). Yang lebih menarik
adalah **durable resume untuk approval**: item inbox menyimpan `tool_call_id`
(`coworker/inbox.py:77`, `coworker/engine.py:55`) dan `add_approval` **idempoten
atas `(session_id, tool_call_id)`** (`inbox.py:142`) — komentarnya menyatakan *"a
durable resume re-raises the same prompt"*. Jadi bila proses mati saat menunggu
persetujuan, coroutine-nya hilang tetapi permintaannya bertahan, dan run yang
dijalankan ulang membangkitkan prompt yang sama alih-alih duplikat. `[code]`

Kunci idempotensi `(session_id, tool_call_id)` berbentuk sama dengan
`turns.idempotency_key` + `UNIQUE(user_id, idempotency_key)` di
[`../concepts/persistence-schema.md`](../concepts/persistence-schema.md).
Konvergensi independen pada bentuk yang sama.

## 6. Safety gate

Empat kelas risiko sebagai enum (`coworker/risk.py:18-23`): `READ` (tanpa efek
samping, selalu diizinkan), `WRITE_LOCAL` (path-scoped + mode-gated), `EXEC`
(mode-gated), dan `EXTERNAL` — yang komentarnya menyebut dirinya *"the unattended
Inbox hook"*. `is_consequential()` (`:56-58`) menyatakan aturannya: apa pun selain
`READ` masuk ke permission engine. `[code]`

Approver adalah **strategi yang ditukar per mode sesi**, bukan cabang di dalam
engine. Sesi unattended memakai `inbox_approver` (`coworker/inbox.py:387`) yang
docstring-nya menyatakan: *"routes a permission request to the Inbox and suspends
until resolved"* — `await store.wait(item.id)` (`:362-371`) **tanpa timeout**.
`ApprovalOutcome` (`engine.py:31-37`) punya lima nilai: `ONCE`, `ALWAYS_TOOL`,
`ALWAYS_COMMAND`, `READONLY_SESSION`, `DENY`. `[code]`

Saat operator kembali ke kendali attended, `reconcile_on_resume` (`inbox.py:374-380`)
memunculkan item yang masih pending secara inline **plus rekap apa yang dijawab
selama ia pergi**, dengan prinsip *"Single source of truth: every item already has
one authoritative resolution."* `[code]`

Lihat [`../concepts/guardrails.md`](../concepts/guardrails.md) §Mode kegagalan
ketiga untuk implikasi polanya, dan
[`../concepts/human-in-the-loop.md`](../concepts/human-in-the-loop.md) untuk
transisi attended/unattended.

## 7. Capability routing & policy

Risiko ditentukan **sebagai data, bukan prosa**, dengan presedensi eksplisit di
`classify()` (`risk.py:39-54`): override user-lokal menang, lalu tabel by-name
`_BASE` (`:29-33`), lalu metadata aisuite `requires_approval` → `EXTERNAL`, dan
default `READ`. Komentar sumbernya menyebut sendiri bahwa tabel itu adalah *"the
old WRITE_TOOLS / SHELL_TOOL, **as data**"*. `[code]`

Ini bentuk yang sama dengan yang dianjurkan
[`../concepts/policy-as-data.md`](../concepts/policy-as-data.md): aturan yang bisa
diverifikasi kode hidup sebagai tabel, bukan kalimat di prompt — dan penegakannya
di boundary permission engine. Pemilihan tool mana yang dipanggil tetap judgment
model; yang berbasis data adalah **kelas risikonya**, bukan routingnya. `[inferred]`

## Sumber

- `[code]` `andrewyng/openworker` @ `141d02a` (2026-08-22), dibaca via
  `git clone --depth 1`. File yang dibaca: `coworker/risk.py` (utuh),
  `coworker/inbox.py:77,142,362-380,387-406`, `coworker/engine.py:31-37,55,65,356-360,75`,
  `coworker/config.py:34`, `coworker/agent.py:505-515`,
  `coworker/compaction.py:86-94`, `coworker/sessions.py:37-39`,
  `coworker/tools/subagent.py:42,79-100`, `coworker/toolchain.py:171,227`,
  `tests/test_unattended.py:22-60`.
- `[docs]` README repo — status open beta, klaim single-operator, daftar 25+
  konektor, arsitektur desktop app + local agent server (di atas `aisuite`).
- `[docs]` GitHub API: 14.948 bintang, Python, MIT, dibuat 2026-07-20.
