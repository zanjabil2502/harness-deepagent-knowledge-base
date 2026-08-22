# Queueing & backpressure

## Masalah

Model request-response naif — terima HTTP request, jalankan turn inline di
handler yang sama, kembalikan respons setelah selesai — bekerja untuk
request yang selesai dalam milidetik. Untuk turn agent yang berjalan menit
(lihat `resource-profiling.md`, `serving-topology.md`), model ini pecah
dengan tiga cara berbeda:

1. **Tidak ada backpressure** — burst turn baru memenuhi seluruh worker
   pool yang sedang menunggu LLM/tool call selesai, request berikutnya
   antre di level TCP/load balancer tanpa kontrol, dan satu-satunya tuas
   yang tersedia adalah menolak koneksi mentah-mentah di layer paling
   depan.
2. **Tidak ada prioritas** — turn latency-sensitive (user menunggu di UI)
   dan turn batch/background (job terjadwal, retry) diperlakukan sama;
   burst dari yang kedua bisa menunda yang pertama tanpa batas.
3. **Tidak ada reattach** — koneksi HTTP yang menahan turn adalah
   satu-satunya jalan client tahu hasilnya. Tab browser tertutup, koneksi
   mobile terputus, atau load balancer memutus socket → turn yang sedang
   berjalan (dan mungkin sudah memanggil tool berbayar/tidak-idempoten)
   jadi orphan: masih berjalan di server tapi tidak ada jalan bagi client
   untuk tahu hasilnya.

## Pola

### Turn masuk antrean, bukan dieksekusi inline

Turn diterima, diberi `turn_id` (idempotency key per turn, sudah
dispesifikasikan skemanya di `persistence-schema.md` — kolom
`turns.idempotency_key` + `turns.status`), lalu **dimasukkan ke antrean**
dan HTTP handler langsung kembali dengan `turn_id` — bukan menunggu turn
selesai. Worker pool terpisah menarik dari antrean dan mengeksekusi. Ini
memisahkan tiga hal yang sebelumnya menyatu di satu request-response:
**diterima** (turn tercatat, dapat `turn_id`), **berjalan** (worker sedang
memprosesnya), dan **selesai** (hasil tersedia) — masing-masing terlihat
lewat `turns.status` (`pending` → `completed`/`failed`).

### Backpressure: queue depth sebagai sinyal, bukan cuma tuas HPA

Queue depth adalah sinyal yang sudah dipetakan ke baris Tool executor di
tabel HPA `serving-topology.md` (`queue depth, CPU`) — tapi backpressure
bukan cuma soal scale-out otomatis. Di titik masuk (admission), kalau
antrean melewati ambang tertentu, sistem harus **menolak turn baru secara
eksplisit** (respons yang jelas retriable, bukan diam-diam menumpuk tanpa
batas) alih-alih menerima semuanya dan membiarkan memory/koneksi menumpuk
sampai proses jatuh. Preseden nyata untuk pola "antre dulu, jangan langsung
fan-out semua request ke sisi eksekusi" ada di LiteLLM: proxy-nya
menyediakan `scheduler_acompletion()` di Router yang menaruh request di
antrean lalu **poll** apakah ada deployment sehat/apakah request sudah di
puncak antrean, dengan `polling_interval` default 3ms dan `default_priority`
opsional per request `[code]` — `litellm/router.py`
(`Router.scheduler_acompletion`, parameter `polling_interval`,
`default_priority`), dikutip via WebFetch/WebSearch dari
`docs.litellm.ai/docs/scheduler` dan source `BerriAI/litellm`.

### Prioritas: nilai lebih kecil menang, sama seperti LiteLLM

LiteLLM proxy mendukung antrean prioritas berdasar level prioritas key —
`priority` dikirim per panggilan, nilai lebih rendah berarti prioritas
lebih tinggi `[docs]` — dikutip dari `docs.litellm.ai/docs/scheduler`.
Bentuk yang sama berlaku untuk antrean turn di harness ini: field
`priority` di baris `turns`, worker menarik dari antrean berurutan
prioritas dulu baru FIFO dalam prioritas yang sama. Tidak ada mekanisme
anti-starvation (aging) yang dispesifikasikan di sini secara default —
YAGNI sampai ada bukti nyata prioritas rendah kelaparan; kalau dibutuhkan,
itu penambahan lokal ke query "ambil turn berikutnya", bukan perubahan
skema.

### Reattach setelah client putus

Karena turn punya `turn_id` yang durable dan statusnya tersimpan
(`turns.status`) terlepas dari koneksi HTTP yang memicunya, **turn tidak
berhenti kalau client putus** — worker tetap menyelesaikannya. Client yang
reconnect (refresh tab, buka app lagi) cukup:

- `GET /turns/{turn_id}` — ambil status + hasil-sejauh-ini kalau turn masih
  jalan, atau hasil final kalau sudah selesai.
- Subscribe ulang ke stream event turn itu (SSE baru dengan `turn_id` yang
  sama) untuk terus menerima event baru sejak titik itu, bukan dari awal.

Ini secara sadar berbeda dari asumsi "koneksi putus = turn batal" —
asumsi itu salah untuk turn yang mungkin sudah memanggil tool berbayar
atau tidak-idempoten (memanggil API eksternal, menulis file) sebelum
putus; membatalkannya karena tab ditutup membuang kerja yang sudah terjadi
dan bisa meninggalkan efek samping setengah jalan tanpa pernah dilaporkan
ke user.

## Trade-off

- **Queue-then-execute vs eksekusi inline** — inline lebih sederhana dan
  latency lebih rendah untuk sistem yang jarang overload (tidak ada
  komponen antrean tambahan untuk dijaga), tapi tidak punya tuas
  backpressure selain menolak koneksi TCP mentah-mentah, dan tidak bisa
  memprioritaskan. Antre dulu menambah komponen (antrean + worker pool +
  status polling/subscribe) tapi membuat beban eksplisit dan terkontrol —
  keputusan yang masuk akal begitu turn cukup lama dan cukup sering
  meledak volumenya untuk butuh kontrol itu; untuk trafik rendah/steady,
  inline tetap valid dan lebih sederhana.
- **Priority queue vs FIFO murni** — FIFO sederhana dan adil-by-construction
  (tidak ada turn yang "dipotong antrean" secara tak terduga), tapi turn
  bervolume-tinggi bernilai-rendah (job batch) bisa menunda turn
  interaktif tanpa batas kalau keduanya berbagi antrean yang sama.
  Priority queue menyelesaikan itu tapi membuka risiko starvation kelas
  prioritas rendah kalau kelas tinggi terus-menerus datang — mitigasinya
  (aging) sengaja tidak dibangun sekarang, YAGNI sampai ada bukti nyata.
- **Reattach lewat polling/SSE baru vs WebSocket persisten** — polling/SSE
  ulang lebih mudah di-scale di belakang load balancer stateless: pod
  mana pun bisa melayani `GET /turns/{id}` karena statusnya dibaca dari
  Postgres, bukan dari memory proses tertentu, dan reconnect otomatis
  mendarat di pod mana pun tanpa sticky session. WebSocket persisten
  dengan state di memory satu proses butuh sticky session (reconnect
  harus mendarat di pod yang sama) atau infrastruktur pub/sub tambahan
  (mis. Redis pub/sub) supaya event turn bisa di-fan-out ke pod mana pun
  yang menerima reconnect — latency update lebih rendah, tapi infra lebih
  berat.

## Di deepagents

Konsep "turn" dan antrean HTTP-nya sama sekali berada di luar
`deepagents` — `deepagents` adalah library invoke-graph, tidak tahu apa
itu HTTP request atau antrean; ini murni tanggung jawab aplikasi, seperti
Transcript di `session-state.md`. Yang `deepagents` **sudah** sediakan,
dengan bentuk yang persis sama ("detach, cek status by id, reattach"),
adalah di level **subagent async**, satu lapis di bawah turn:
`AsyncSubAgentMiddleware` menyediakan tool untuk start/check/update/
cancel/list task background, disimpan di `AsyncSubAgentState.tasks` (dict
`task_id -> AsyncTask`) — status di-cache lalu **dicek ulang ke server**,
bukan diasumsikan dari memory lokal. `[code]` —
[`../systems/deepagents.md`](../systems/deepagents.md) §5 (`API
permukaan`: `AsyncSubAgentMiddleware`, `AsyncSubAgent`).

Pola turn-level queue di file ini bisa memakai bentuk yang sama persis di
satu level lebih tinggi: `turn_id` yang addressable, status enum yang
dipoll/subscribe, dan "cek ulang ke sumber kebenaran" (di sini: Postgres
`turns.status`) alih-alih percaya cache lokal begitu saja — bukan
kebetulan bentuknya sama, ini pola umum untuk kerja asinkron yang
outlive koneksi yang memicunya, dan `deepagents` sudah menerapkannya di
lapisnya sendiri.

## Sumber

- `[code]` LiteLLM `litellm/router.py` — `Router.scheduler_acompletion()`,
  parameter `polling_interval` (default 3ms), `default_priority`, dibaca
  lewat WebFetch atas source `BerriAI/litellm` dan dikonfirmasi silang
  dengan dokumentasi.
- `[docs]` LiteLLM — semantik prioritas (nilai lebih rendah = prioritas
  lebih tinggi) dan model antrean `[BETA] Request Prioritization`, dikutip
  via WebSearch dari `docs.litellm.ai/docs/scheduler`.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — skema
  `turns` (`idempotency_key`, `status`) yang jadi fondasi turn-addressable
  di file ini, Task 4.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 —
  `AsyncSubAgentMiddleware`/`AsyncSubAgentState.tasks` sebagai preseden
  pola detach/reattach di dalam `deepagents` sendiri, tier-1 reference
  terverifikasi Task 3, dikutip tanpa membaca ulang source.
- `[code]` `serving-topology.md`, `resource-profiling.md` (file ini KB) —
  argumen queue depth sebagai sinyal Tool executor dibangun di atas tabel
  komponen→bound→sinyal HPA yang sudah dijelaskan di sana.
