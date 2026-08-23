# Streaming protocol

## Masalah

Dua kesalahan berbeda muncul dari sumber yang sama: memperlakukan streaming
sebagai pemanis UX (token muncul progresif alih-alih menunggu jawaban utuh)
alih-alih sebagai **kontrak** untuk sebuah proses yang berjalan lama dan
banyak-langkah.

Pertama, pemilihan SSE vs WebSocket sering diputuskan dari familiaritas tim
atau tren, bukan dari kebutuhan arah komunikasi yang sebenarnya — berakhir
memasang WebSocket (kompleksitas infra: upgrade handshake, sticky session di
load balancer, reconnect manual) untuk pola yang sebenarnya cuma butuh
server mendorong output satu arah.

Kedua, dan lebih mahal: stream diperlakukan sebagai **satu-satunya** tempat
event agent hidup — begitu koneksi client putus (jaringan mobile drop, tab
ditutup dan dibuka lagi, server di belakang load balancer di-restart saat
deploy), event yang lewat selama terputus **hilang permanen** kalau tidak
ada yang lain menyimpannya. Untuk turn agent biasa ini cuma UX buruk (user
lihat jawaban terpotong, refresh, dapat versi lengkap). Untuk turn yang
sedang menunggu approval HITL (lihat
[`human-in-the-loop.md`](human-in-the-loop.md)), ini serius: client yang
reconnect tanpa tahu ada gerbang approval yang sedang menunggu berarti turn
itu diam-diam macet sampai seseorang kebetulan menyadarinya.

## Pola

### SSE vs WebSocket — kapan masing-masing

| Dimensi | SSE (Server-Sent Events) | WebSocket |
|---|---|---|
| Arah | Server → client saja; client kirim pesan lewat request HTTP biasa (POST) di luar stream | Dupleks penuh, dua arah di koneksi yang sama |
| Protokol | HTTP biasa — lewat proxy/load balancer HTTP standar tanpa konfigurasi tambahan | Butuh upgrade handshake (`Upgrade: websocket`); sebagian infra proxy/LB butuh konfigurasi eksplisit (sticky session, timeout berbeda) |
| Reconnect | Bawaan browser (`EventSource`) — otomatis reconnect + kirim header `Last-Event-ID` berisi id event terakhir yang diterima, tanpa kode tambahan di client `[docs]` | Tidak ada mekanisme reconnect bawaan protokol; harus ditulis manual di client (deteksi `onclose`, buka koneksi baru, kirim ulang state) |
| Framing pesan | Baris teks `event:`/`data:`/`id:`/`retry:` sederhana, satu arah | Frame biner/teks bebas, aplikasi mendefinisikan sendiri |

**Kapan SSE**: pola interaksi berbasis-turn — satu permintaan user memicu
satu aliran output (token, event tool call, hasil), dan permintaan
berikutnya (termasuk keputusan approval HITL) tetap lewat endpoint
request/response biasa, bukan lewat stream itu sendiri. Ini pola default
loop agent (`agent-loop.md`): user mengirim, server merespons dengan aliran,
selesai. Reconnect otomatis `EventSource` + `Last-Event-ID` juga selaras
langsung dengan kebutuhan reattach di bawah — protokolnya sudah menyediakan
setengah dari mekanisme yang dibutuhkan tanpa kode tambahan di client.

**Kapan WebSocket**: kebutuhan push dua arah **di luar** batas satu turn —
banyak stream event independen dimultipleks di satu koneksi, event yang
diinisiasi server tanpa dipicu request client tertentu (presence user lain,
notifikasi job background selesai, edit kolaboratif di kanvas — lihat
[`artifacts-and-canvas.md`](artifacts-and-canvas.md)), atau client perlu
mengirim data di tengah stream tanpa membuka request HTTP baru (audio/voice
duplex, live cursor). Default `_base` untuk antarmuka turn chat/agent adalah
**SSE** — kebutuhannya cocok dengan pola turn-based di atas; WebSocket
ditambahkan hanya kalau fitur konkret (kolaborasi real-time, voice) benar-
benar butuh dupleks.

### Skema event

Satu amplop event per baris `data:` SSE (atau satu frame WebSocket), field
minimal:

```json
{
  "event_id": "01J...",      // ULID/sequence monoton PER TURN, dipakai untuk Last-Event-ID & reattach
  "turn_id": "uuid",
  "type": "message.delta",
  "data": { "...": "..." },
  "ts": "2026-08-23T10:00:00Z"
}
```

Tipe event minimal yang dibutuhkan satu turn agent:

| `type` | Kapan dikirim | Isi `data` |
|---|---|---|
| `turn.started` | Turn mulai diproses | `{ "message_id": ... }` |
| `message.delta` | Tiap potongan token teks jawaban | `{ "text_delta": "..." }` |
| `tool_call.delta` | Tiap potongan argumen tool call yang sedang dibentuk model | `{ "index": 0, "name": "...", "args_delta": "..." }` — lihat §Rendering tool call parsial |
| `tool_call.result` | Tool call selesai dieksekusi | `{ "tool_call_id": ..., "status": "success"/"error", "result": ... }` |
| `interrupt` | Gerbang HITL diangkat, turn berhenti menunggu | `{ "action_requests": [...], "review_configs": [...] }` — bentuk persis dari `human-in-the-loop.md` |
| `turn.completed` | Turn selesai normal | `{ "message_id": ... }` |
| `turn.error` | Turn berhenti karena error (bukan interrupt) | `{ "message": "..." }` |
| `heartbeat` | Berkala (mis. tiap 15-30 detik) selama tidak ada event lain | `{}` — semata menjaga proxy/LB tidak menutup koneksi SSE idle |

### Rendering tool call parsial

Argumen tool call yang di-*stream* datang sebagai potongan JSON string yang
**belum valid** sampai lengkap. Ground konkretnya di `langchain`:
`AIMessageChunk.tool_call_chunks: list[ToolCallChunk]`, tiap `ToolCallChunk`
punya `name` (opsional, biasanya cuma di chunk pertama), `args` (potongan
string JSON), `id`, dan `index` — chunk-chunk dengan `index` sama digabung
dengan **konkatenasi string** (`left.args + right.args`), bukan merge objek.
`[code]` — `langchain_core/messages/tool.py` kelas `ToolCallChunk`,
`langchain_core/messages/ai.py` kelas `AIMessageChunk` field
`tool_call_chunks`.

Aturan render di client, turunan langsung dari mekanisme itu:

1. Buffer `args_delta` per `index` (satu tool call yang sedang dibentuk =
   satu buffer), jangan coba `JSON.parse` tiap potongan.
2. Tampilkan progres sebagai teks argumen yang terus tumbuh (mis. area teks
   read-only yang membesar), **jangan** coba render field terstruktur dari
   JSON yang belum lengkap — parser JSON toleran-parsial boleh dipakai untuk
   preview UI, tapi hasilnya tidak pernah dipakai untuk keputusan apa pun.
3. Tool call baru **boleh dieksekusi atau ditampilkan sebagai keputusan
   nyata** (termasuk masuk ke gerbang HITL) hanya dari `tool_call.result`
   atau saat `message.delta`/`tool_call.delta` berhenti dan chunk final
   sudah digabung jadi JSON valid — never dari buffer parsial yang masih
   tumbuh.

### Reattach setelah client disconnect

Ini syarat yang memaksa **event log durable per turn**, bukan stream
ephemeral broadcast-saja. Alurnya:

1. Client menyimpan `turn_id` + `event_id` terakhir yang diterima (untuk
   SSE, `EventSource` melakukan ini otomatis lewat `Last-Event-ID`; untuk
   WebSocket, aplikasi harus menyimpannya sendiri di client).
2. Saat reconnect, client mengirim `(turn_id, last_event_id)` — untuk SSE
   ini datang otomatis sebagai header `Last-Event-ID` di request GET baru
   `[docs]` (WHATWG HTML spec, algoritma `EventSource`: *"If the
   EventSource object's last event ID string is not the empty string... Set
   ('Last-Event-ID', lastEventIDValue) in request's header list"*).
3. Server mengecek status turn itu. **Durable log-nya bukan tabel event
   baru** — ia proyeksi dari transkrip yang sudah wajib ada di
   [`persistence-schema.md`](persistence-schema.md): kolom
   `messages.status` (`'complete'`/`'streaming'`/`'error'`) memberitahu
   apakah masih ada yang perlu di-resume sama sekali, dan tabel `tool_calls`
   (`status` `'pending'`/`'success'`/`'error'`, satu row per tool call)
   memberitahu **granularitas** apa yang sudah pasti selesai.
   - Kalau `messages.status = 'complete'` — kirim balik konten final utuh,
     tidak perlu resume stream sama sekali.
   - Kalau `'streaming'` — kirim semua `tool_calls` yang sudah
     `'success'`/`'error'` sebagai event `tool_call.result` yang "diputar
     ulang" (replay), lalu sambung ke live tail dari titik itu.
   - Kalau turn sedang berhenti di gerbang HITL — event `interrupt` yang
     sama dikirim ulang (state-nya memang masih ada, lihat `## Di
     deepagents`), supaya client yang reconnect langsung tahu ada approval
     yang menunggu alih-alih diam-diam kehilangan sinyal itu.

**Granularitas yang dipilih `[ours]`: per unit (pesan/tool call), bukan per
token.** Delta token individual (`message.delta`/`tool_call.delta`) **tidak
pernah dipersist satu-per-satu** — itu men-generate satu row per token untuk
manfaat yang nol setelah unit-nya selesai (begitu satu pesan/tool call
`'complete'`, isinya sudah ada utuh di kolom `content`/`result`, delta
individualnya tidak berguna lagi). Yang dipersist inkremental adalah row
`messages`/`tool_calls` itu sendiri, dimutakhirkan tiap unit selesai. Live
tail token-per-token tetap jalan lewat jalur pub/sub ephemeral (mis. Redis
Pub/Sub atau broadcast in-process) yang **layer di atas** transkrip durable,
bukan store paralel — kalau koneksi live putus di tengah satu unit yang
sedang dibentuk, celah reattach maksimalnya adalah "kehilangan delta token
dari SATU unit yang sedang berjalan", bukan seluruh riwayat turn, dan client
bisa langsung minta ulang konten unit itu (kalau harness men-checkpoint
progres parsialnya secara berkala) atau cukup menunggu unit itu selesai.
Vanilla yang ditolak: mempersist tiap token delta sebagai row sendiri
(reattach sempurna sampai ke token, tapi ledakan jumlah row untuk data yang
tidak pernah dibaca lagi begitu unit-nya selesai) — lihat `## Trade-off`.

Ini **memakai** model transkrip `persistence-schema.md`/`session-state.md`
apa adanya, tidak membangun store paralel — file itu memiliki skema
tabelnya; file ini memiliki kontrak event/reattach yang dibangun di
atasnya.

## Trade-off

- **SSE vs WebSocket** — sudah dibahas di §Pola; ringkas: SSE lebih
  sederhana infra dan dapat reconnect otomatis gratis untuk pola satu-arah
  (mayoritas kasus turn agent), WebSocket perlu untuk dupleks nyata dengan
  biaya kompleksitas infra + reconnect manual.
- **Durabilitas per token vs per unit vs tanpa durabilitas** — per token
  memberi reattach paling presisi (tidak kehilangan satu karakter pun) tapi
  membengkakkan storage untuk data yang tidak berguna lagi setelah unitnya
  selesai; per unit (pilihan proyek ini) menyisakan celah kecil (delta dari
  satu unit yang belum selesai saat disconnect) dengan storage yang sama
  dengan yang sudah wajib ada untuk transkrip; tanpa durabilitas sama sekali
  (stream ephemeral murni, restart total tiap disconnect) paling murah tapi
  tidak bisa diterima untuk sistem dengan gerbang HITL — approval yang
  sedang menunggu bisa hilang dari pandangan client sepenuhnya.
- **Pub/sub terkelola (Redis Streams/Pub-Sub) vs polling DB untuk fan-out
  live tail ke banyak pod gateway** — pub/sub terkelola menambah satu
  komponen infra tapi latensi rendah dan tidak membebani Postgres dengan
  polling frekuensi tinggi; polling DB tidak perlu komponen baru tapi
  menambah beban baca berulang dan latensi lebih tinggi. Ini keputusan
  komponen Gateway/SSE yang skalanya dimiliki
  [`serving-topology.md`](serving-topology.md) (sinyal HPA: koneksi aktif)
  — file ini cuma menandai bahwa kontrak event/reattach di atas tidak
  mengasumsikan salah satu, keduanya bisa memenuhi kontraknya.

## Di deepagents

`langgraph` (fondasi `deepagents`) punya mekanisme streaming native yang
jadi bahan baku langsung untuk skema event di atas, tapi **tidak**
menyelesaikan sendiri masalah reattach lintas-koneksi:

- **`stream_mode`** pada `.stream()`/`.astream()` LangGraph: `"values"`
  (state penuh tiap step), `"updates"` (delta per node/task),
  `"messages"` (token LLM streaming per-token, sebagai tuple `(chunk,
  metadata)` — sumber langsung `message.delta`/`tool_call.delta` di atas
  lewat `AIMessageChunk.tool_call_chunks`), `"custom"` (data bebas lewat
  `StreamWriter`), `"checkpoints"` (event tiap checkpoint dibuat),
  `"tasks"` (event mulai/selesai tiap task, termasuk error). Bisa
  dikombinasikan sebagai list untuk menerima beberapa mode sekaligus.
  `[code]` — `langgraph/types.py` (`StreamMode = Literal["values",
  "updates", "checkpoints", "tasks", "debug", "messages", "custom"]`),
  `langgraph/pregel/main.py` docstring parameter `stream_mode` pada
  `.stream()`.
- **`durability`** (`"sync"`/`"async"`/`"exit"`) mengatur **kapan**
  checkpoint dipersist relatif terhadap eksekusi step — parameter ini
  langsung menentukan seberapa jauh reattach bisa dipercaya:
  `"sync"` mempersist sebelum step berikutnya mulai (paling aman untuk
  reattach — checkpoint selalu mencerminkan step yang benar-benar selesai,
  dengan biaya latensi tambahan tiap step); `"async"` (default) mempersist
  bersamaan dengan step berikutnya berjalan (throughput lebih baik, ada
  jendela kecil di mana crash bisa kehilangan checkpoint step terakhir);
  `"exit"` cuma mempersist saat graph selesai total (termurah, tapi paling
  buruk untuk reattach di tengah run panjang — nyaris tidak ada checkpoint
  untuk resume kalau proses mati di tengah). `[code]` —
  `langgraph/pregel/main.py` docstring parameter `durability` pada
  `.stream()`.
- **Interrupt HITL sudah otomatis jadi bagian checkpoint** — `interrupt()`
  (dipakai `HumanInTheLoopMiddleware`, lihat
  [`human-in-the-loop.md`](human-in-the-loop.md)) menghentikan graph di
  titik itu dan state-nya persisten lewat `checkpointer` yang sama dengan
  yang menjaga Run state (`../systems/deepagents.md` §5). Artinya separuh
  dari reattach untuk turn yang sedang HITL — "state approval yang
  menunggu tidak hilang" — sudah didapat gratis dari mekanisme resume
  `langgraph` yang ada, tidak perlu dibangun ulang. `[code]` — dikutip
  `../systems/deepagents.md` §6.
- **Yang TIDAK diselesaikan `langgraph`**: `.stream()`/`.astream()` adalah
  generator Python yang terikat ke proses dan koneksi pemanggilnya saat
  itu. Kalau koneksi client A putus lalu proses gateway yang sama (atau
  proses lain) melanjutkan run yang sudah di-`interrupt`/checkpoint,
  `langgraph` memberi **state ter-checkpoint untuk dilanjutkan
  eksekusinya** (`Command(resume=...)`), bukan **replay delta token yang
  sudah pernah di-broadcast ke koneksi lama**. Dua hal itu beda: yang
  pertama "lanjutkan mengeksekusi graph yang berhenti", yang kedua "putar
  ulang apa yang sudah client A lihat sebelum putus". `langgraph` cuma
  menyediakan yang pertama. `[inferred]` — disimpulkan dari kontrak
  `.stream()` sebagai generator per-invocation (`langgraph/pregel/main.py`)
  dan tidak ditemukannya mekanisme "resume watching an existing broadcast"
  di modul yang dibaca — bridging keduanya (event log per turn di
  §Reattach) tetap tanggung jawab lapisan gateway aplikasi, `deepagents`/
  `langgraph` tidak menyediakannya.

## Sumber

- `[code]` `langgraph/types.py` — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langgraph/types.py`,
  definisi `StreamMode`.
- `[code]` `langgraph/pregel/main.py` — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py`,
  docstring parameter `stream_mode`, `durability`, `subgraphs` pada
  `.stream()`.
- `[code]` `langchain_core/messages/ai.py`, `langchain_core/messages/tool.py`
  — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langchain_core/messages/`,
  kelas `AIMessageChunk` (field `tool_call_chunks`) dan `ToolCallChunk`
  (`name`/`args`/`id`/`index`, semantik penggabungan per-`index`).
- `[docs]` WHATWG HTML Standard — §9.2 Server-sent events
  (`https://html.spec.whatwg.org/multipage/server-sent-events.html`),
  dikutip via WebFetch untuk algoritma reconnect `EventSource` (header
  `Last-Event-ID`, field `id:`/`retry:`, delay reconnect default
  implementation-defined).
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5, §6 —
  tier-1 reference terverifikasi, dikutip untuk checkpointer & interrupt.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — tabel
  `messages` (kolom `status`), `tool_calls` (kolom `status`), dikutip
  sebagai dasar durable log untuk reattach; skema tidak diubah di file ini.
- `[code]` [`session-state.md`](session-state.md) — heuristik ephemeral vs
  durable per lapis, dikutip untuk justifikasi "delta token ephemeral,
  unit pesan/tool call durable".
- `[code]` [`human-in-the-loop.md`](human-in-the-loop.md) — bentuk payload
  `interrupt`, dikutip untuk skema event, tidak diulang mekanismenya.
