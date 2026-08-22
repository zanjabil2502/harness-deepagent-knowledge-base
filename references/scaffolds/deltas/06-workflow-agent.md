# Delta 06 — Workflow Agent

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya. Rasional
lengkap: [`../../archetypes/06-workflow-agent.md`](../../archetypes/06-workflow-agent.md)
§Bangun ini pakai deepagents.

## Ganti

- **Trigger & routes**: `_base` memicu turn lewat `POST /turns` +
  `GET /turns/{id}/events` (SSE, manusia menonton real-time). Arketipe ini
  **tidak punya** manusia real-time — `api/routes/turns.py` diganti
  consumer event (webhook handler/cron/worker antrean) yang memanggil
  `Orchestrator.run_turn(...)` langsung, hasil ditulis ke log/dashboard,
  bukan di-stream ke koneksi HTTP yang menunggu. `[ours]` archetype 06:
  `create_deep_agent(...)` ditaruh sebagai satu node di graph LangGraph
  yang lebih besar (atau di belakang worker antrean) yang dipicu event
  eksternal — deepagents menangani "apa yang dilakukan LLM saat dipanggil",
  bukan "kapan dipanggil", yang berada di luar tanggung jawab library.
- **Derivasi `thread_id`**: `_base` menerima `thread_id` sebagai parameter
  request dari client manusia. Di sini, `thread_id` diturunkan dari
  idempotency key event trigger (mis. hash `delivery_id` webhook), **bukan**
  dari sesi/percakapan manusia — supaya retry event yang sama (webhook
  retry, restart antrian) jatuh ke checkpoint yang sama, bukan membuat run
  baru. `[ours]` archetype 06: `ARCHITECTURE.md` hanya menyatakan
  checkpointer disuntik aplikasi, tidak menyebutkan bagaimana `thread_id`
  dibentuk — ini pola kami, bukan sesuatu yang dijamin/didokumentasikan
  library.
- **Resolusi `Scope`**: `ScopeMiddleware` (`_base`) membaca `user_id` dari
  header request HTTP berautentikasi manusia — tidak berlaku di sini karena
  trigger bukan request manusia. `Scope` untuk satu workflow run diturunkan
  dari **konfigurasi workflow** (`user_id` pemilik workflow, tersimpan saat
  workflow didaftarkan), dibaca oleh consumer event sebelum memanggil
  `Orchestrator.run_turn(...)` — bukan dari middleware HTTP yang sama.

## Tambah

- **Idempotency di titik admisi**: consumer event wajib menegakkan
  idempotency di level infra antrean (dedupe by `delivery_id`) **selain**
  idempotency `thread_id` di atas — dua lapis, karena checkpointer resume
  mencegah duplikasi *kerja LLM*, bukan duplikasi *efek samping tool* yang
  sudah terjadi sebelum crash (`## Jebakan khas` archetype 06, poin 1).
- **Safety gate**: `interrupt_on` untuk aksi berisiko tinggi (mis.
  `send_email: True`) tetap dipasang meski tidak ada manusia real-time —
  approval-nya async lewat channel terpisah (dashboard/Slack), bukan
  menunggu di koneksi SSE (yang memang tidak ada di arketipe ini). `[code]`
  sumber `test_hitl.py`.
- **Kill switch level-workflow**: flag di database dicek consumer event
  **sebelum** memanggil `Orchestrator.run_turn(...)` untuk workflow itu.
  `[ours]` archetype 06: tidak ada API "matikan semua run" bawaan
  `deepagents` — ini tanggung jawab layer orchestrator/queue aplikasi,
  eksplisit dinyatakan supaya scaffold tidak salah asumsi `create_deep_agent`
  menyediakan kill switch bawaan.

## Buang

- **`GET /turns/{turn_id}/events` (SSE)** — tidak ada yang menonton
  real-time; observability arketipe ini lewat log terstruktur + trace OTel
  (`_base.md` §Observability tetap dipakai apa adanya), bukan stream.
- **`lifecycle/drain.py` `start_turn()`/`end_turn()` dipanggil dari SSE
  generator** (`_base` pola) — dipanggil dari consumer event sebagai
  gantinya, mekanismenya (gauge + `wait_empty` saat shutdown) tidak berubah.
