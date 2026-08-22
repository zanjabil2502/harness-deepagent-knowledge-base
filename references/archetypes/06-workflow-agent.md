# 6. Workflow Agent

## Definisi

Agent yang dipicu oleh event (webhook, cron, pesan antrian) dan berjalan
**tanpa manusia yang sedang aktif mengawasi** — beda dari kelima arketipe
sebelumnya yang selalu punya operator di ujung sesi. Karena tidak ada
manusia di loop, jaminan yang biasanya datang dari review manusia (koreksi
kalau salah) harus digantikan sepenuhnya oleh mekanisme sistem: retry,
idempotency, observability, dan kill switch.

Batas terhadap tetangga: beda dari **General Task Agent** (03) karena
tidak ada planning eksplisit berbasis LLM per run — bentuknya lebih
sering DAG/graph deterministik dengan simpul LLM di beberapa titik; beda
dari **In-App Copilot** (05) karena tidak ada manusia aktif memakai
aplikasi saat run terjadi.

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Sistem eksternal yang di-integrasikan (API pihak ketiga, database) |
| Artefak | Aksi di sistem lain (kirim pesan, update record, panggil webhook) |
| Horizon | Berulang/hidup di background, dipicu event |
| Kendali manusia | Tanpa manusia di loop saat run; review terjadi di log/dashboard setelahnya |
| Permukaan domain | General (platform) atau vertikal (workflow spesifik) |
| Antarmuka | Tidak ada — trigger-based, observability lewat dashboard terpisah |

## Konsekuensi harness

1. **Retry dengan backoff wajib di tiap step**, bukan cuma di level run —
   tanpa manusia yang mengawasi, kegagalan transien (rate limit, timeout
   jaringan) yang tidak di-retry otomatis berarti run gagal permanen
   tanpa ada yang tahu sampai seseorang mengeceknya.
2. **Idempotency key per run/step** — event trigger bisa terkirim dobel
   (webhook retry, restart antrian), dan tanpa idempotency, aksi yang
   punya efek samping (kirim email, buat record) akan terduplikasi.
3. **Observability sebagai pengganti mata manusia** — karena tidak ada
   operator yang melihat proses berjalan secara langsung, tiap step wajib
   ninggalkan jejak (log terstruktur, trace) yang cukup untuk
   merekonstruksi apa yang terjadi setelah fakta.
4. **Kill switch di level workflow, bukan cuma per run** — kalau satu
   workflow ternyata rusak (mis. loop tak sengaja memicu dirinya sendiri),
   harus ada cara mematikan seluruh trigger tanpa menunggu tiap run yang
   sedang jalan selesai satu-satu.

## Sistem contoh

- **n8n** `[docs]` — mesin workflow berbasis node visual; AI Agent node
  membungkus tool use, human approval, dan observability sebagai bagian
  dari node yang bisa disusun di canvas, dan mendukung banyak provider
  model (OpenAI, Anthropic, Google, model open-source) tanpa vendor
  lock-in. Sumber: github.com/n8n-io/n8n.
- **Zapier (AI agents/Zaps)** `[inferred]` — dari perilaku produk: trigger
  event memicu chain aksi lintas aplikasi, tanpa operator aktif di
  tengah eksekusi.
- **Cron agent (pola umum)** `[inferred]` — dari perilaku umum
  scheduler+LLM: job berjalan berkala tanpa trigger manusia, hasilnya
  dicek lewat log atau notifikasi setelah run selesai.

## Jebakan khas

1. **Retry tanpa idempotency** — step yang di-retry setelah gagal
   sebagian (mis. email terkirim tapi konfirmasi ke sistem gagal dicatat)
   mengeksekusi ulang efek samping yang seharusnya sekali saja.
2. **Error ditelan diam-diam** — workflow gagal di tengah tanpa
   notifikasi, dan karena tidak ada manusia yang menonton real-time,
   kegagalan baru diketahui saat downstream sudah rusak berhari-hari.
3. **Tidak ada kill switch granular** — satu workflow yang salah konfigurasi
   terus jalan (mis. memicu ribuan panggilan API berbayar) karena
   mematikannya butuh mengubah kode/deploy ulang, bukan satu toggle.
4. **LLM di dalam DAG deterministik diperlakukan seolah deterministik** —
   step berbasis LLM bisa menghasilkan output berbeda tiap run untuk
   input sama, tapi step berikutnya di workflow ditulis seakan-akan
   outputnya selalu berbentuk sama persis.

## Bangun ini pakai deepagents

- **Loop shape**: `[ours]` deepagents adalah harness percakapan/misi
  (dipicu pesan manusia atau task tertulis), bukan mesin event-trigger.
  Untuk arketipe ini kami menaruh `create_deep_agent(...)` sebagai satu
  node di dalam graph LangGraph yang lebih besar (atau di belakang
  worker antrian) yang dipicu event eksternal — deepagents menangani
  "apa yang dilakukan LLM saat dipanggil", bukan "kapan dipanggil".
  Vanilla penggunaan deepagents di dokumentasi/contoh selalu berupa
  loop interaktif dipicu manusia; kami menyimpang karena arketipe ini
  butuh trigger non-manusia, yang berada di luar tanggung jawab library.
- **Idempotency**: dilakukan di layer pemanggil (worker/queue) dengan
  `checkpointer` LangGraph yang disuntikkan lewat parameter
  `checkpointer` di `create_deep_agent` — checkpoint per thread_id yang
  dideterminasi dari idempotency key event, bukan random. `[code]` —
  sumber: `ARCHITECTURE.md`.
- **Safety gate**: `interrupt_on` untuk aksi berisiko tinggi (mis.
  `send_email: True`) tetap dipasang meski tidak ada manusia real-time —
  interrupt di LangGraph berarti run berhenti dan menunggu approval
  async lewat channel terpisah (dashboard/Slack), bukan langsung gagal.
  `[code]` — sumber: `test_hitl.py`.
- **Kill switch**: `[ours]` tidak ada API "matikan semua run" bawaan di
  deepagents — itu tanggung jawab layer orchestrator/queue di atasnya
  (mis. flag di database yang dicek sebelum tiap node LangGraph
  dieksekusi). Kami menyebut ini eksplisit supaya scaffold tidak salah
  asumsi bahwa `create_deep_agent` menyediakan kill switch built-in.

## Sumber

- n8n README — `[docs]` — https://github.com/n8n-io/n8n
- deepagents `ARCHITECTURE.md`, `test_hitl.py` — `[code]` — Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Zapier, pola cron agent umum — `[inferred]` — perilaku produk/pola
  umum, closed-source atau tidak spesifik satu implementasi.
