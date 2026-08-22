# Session state

## Masalah

"State" di sistem agent adalah lima hal berbeda yang kebetulan dipanggil
dengan nama yang sama: riwayat obrolan yang dilihat user, potongan teks yang
sungguh dikirim ke model tiap call, progres satu run graph yang bisa
di-resume, fakta yang bertahan lintas sesi, dan file/dokumen yang dihasilkan
agent. Selama lima hal ini belum dipisah, tidak ada cara bernalar soal
persistence — pertanyaan "apakah ini butuh disimpan di Postgres?" tidak
punya jawaban tunggal karena jawabannya beda untuk tiap lapis.

Gejala konkret dari kebingungan ini: kompaksi context disalahpahami sebagai
"menghapus riwayat" (padahal cuma memangkas apa yang dikirim ke model);
fitur daftar chat dibangun di atas checkpointer (yang bukan database produk,
lihat di bawah); byte artefak ditaruh langsung di kolom pesan (transcript
jadi bengkak, context ikut bengkak tiap kali riwayat dimuat ulang).

**Heuristik pemilahan**: kalau state ini hilang, **bisakah dihitung ulang**
dari sumber lain (transcript, memory, artefak)? Bisa → boleh ephemeral di
sisi AI/harness (cache, in-memory, dibuang setelah call). Tidak bisa →
wajib durable di BE. Garis batas tegasnya: **BE punya kebenaran, AI punya
proyeksi.**

## Pola

### Lima lapis (§8.1)

| Lapis | Store | Lifetime | Pemilik |
|---|---|---|---|
| Transcript | Postgres append-only | permanen | BE |
| Model context | dihitung, cache Redis | 1 call | Harness |
| Run state | Checkpointer (Postgres) | 1 run, resumable | Harness |
| Memory | Postgres + vector | lintas sesi | BE + AI |
| Artefak | S3/GCS + row metadata | permanen, berversi | BE |

Cek tiap lapis lewat heuristik di atas: transcript tidak bisa dihitung ulang
(itu satu-satunya sumber kebenaran percakapan) → durable, BE. Model context
bisa dihitung ulang kapan saja dari transcript + memory + artefak-by-reference
→ boleh ephemeral. Run state ada di tengah: bisa dihitung ulang secara teori
(replay transcript dari awal), tapi mahal untuk sesi panjang — makanya
checkpointer tetap durable meski dimiliki harness, bukan BE, karena isinya
representasi kerja graph, bukan arsip produk.

### Kenapa transcript ≠ model context

Ini bukan dua nama untuk hal yang sama, dan menyamakannya adalah sumber bug
paling umum di lapis ini:

- **Transcript** — arsip lengkap, permanen, append-only, dimiliki BE. Pesan
  lama tidak pernah hilang hanya karena tidak lagi dikirim ke model.
- **Model context** — proyeksi yang **dihitung ulang tiap call** dari
  transcript (+ memory + artefak-by-reference) lewat assembly: windowing,
  kompaksi/ringkas, eviction hasil tool yang besar. Dibuang atau di-cache
  pendek (mis. Redis) setelah call selesai.

Konsekuensinya: kompaksi (mis. `SummarizationMiddleware`, lihat
[`../systems/deepagents.md`](../systems/deepagents.md) §2) **tidak menghapus
baris dari transcript** — ia mengubah apa yang dikirim ke model di call
berikutnya. Yang dicatat di transcript adalah *event* kompaksi yang menunjuk
pesan-pesan yang digantikan (lihat `compaction_events` di
[`persistence-schema.md`](persistence-schema.md)), bukan penghapusan pesan.
Tim yang menyamakan dua hal ini berakhir "menghapus riwayat" untuk menghemat
token, padahal yang seharusnya dipangkas cuma yang dikirim ke model — arsip
tetap utuh.

### Aturan turunan (§8.1)

- Transcript adalah **tree**, bukan list — edit pesan lama = pesan baru
  bercabang dari `parent_id` yang sama, bukan menimpa (lihat
  [`persistence-schema.md`](persistence-schema.md)).
- Checkpointer **bukan database produk** — jangan bangun fitur daftar
  chat/history browsing di atasnya. Skema internalnya (`thread_id`,
  `checkpoint_id`, blob biner) dioptimalkan untuk resume satu thread, bukan
  query lintas-user/lintas-waktu.
- Artefak **by reference** — transcript menyimpan `artifact_id + version`,
  model context menyimpan handle + ringkasan, byte sungguhnya hidup di
  object store (lihat [`artifacts-and-canvas.md`](artifacts-and-canvas.md)).
- Tool call & hasilnya adalah **row transcript kelas satu**, bukan field
  JSON terkubur di dalam pesan — supaya bisa di-query, di-redact, dan
  di-scope per user secara independen.
- Idempotency key **per turn**, bukan per pesan — satu turn bisa berisi
  banyak tool call, retry jaringan/duplicate-submit pada level turn tidak
  boleh membuat turn kedua.

## Trade-off

- **Ephemeral vs durable per lapis**: menyimpan lebih banyak (durable
  semuanya) menghindari kehilangan data tapi memperbesar permukaan RLS dan
  biaya storage; membuang lebih agresif (ephemeral semuanya) murah tapi
  kehilangan data yang sebenarnya tidak bisa dihitung ulang (mis. hasil
  tool call yang nondeterministik — memanggil ulang API eksternal bisa
  menghasilkan nilai berbeda atau punya efek samping berbayar).
- **Tree vs flat list untuk transcript**: tree menambah kerumitan query
  (perlu jalan dari root ke leaf aktif) dibanding list, tapi flat list tidak
  bisa merepresentasikan "user edit pesan lalu regenerate" tanpa menimpa
  riwayat — kehilangan kemampuan itu sama dengan kehilangan data yang tidak
  bisa dihitung ulang.
- **Tool call sebagai row terpisah vs field di message**: row terpisah butuh
  join tambahan untuk merender satu bubble pesan, tapi field JSON terkubur
  tidak bisa di-index/di-redact per baris dan menyulitkan retention selektif
  (mis. menghapus hasil tool yang mengandung PII tanpa menghapus pesannya).
- **Checkpointer durable meski "hanya" Run state**: alternatif murni-ephemeral
  (replay transcript dari awal tiap resume) menghemat storage tapi mahal di
  latency dan token untuk sesi panjang — trade-off recompute-cost vs
  storage-cost yang sama dengan heuristik di atas, cuma di titik yang
  berbeda.

## Di deepagents

`deepagents` tidak membangun lapis Transcript sendiri — ini murni tanggung
jawab aplikasi (lihat [`persistence-schema.md`](persistence-schema.md)).
Yang disediakan `deepagents` adalah mekanisme konkret untuk tiga lapis
lainnya, lewat `checkpointer`/`store` yang **diteruskan apa adanya** ke
`langchain.agents.create_agent` — `deepagents` tidak pernah membangun
checkpointer/store sendiri. `[code]` — lihat
[`../systems/deepagents.md`](../systems/deepagents.md) §5 (`deepagents/graph.py`
baris 546-553, 922-931).

| Lapis (spec) | Konkret di deepagents | Sumber |
|---|---|---|
| Transcript | Tidak ada — `DeepAgentState.messages` (direduksi `DeltaChannel`) adalah representasi kerja graph untuk resume, bukan arsip bercabang permanen. Aplikasi tetap wajib punya tabel `messages` sendiri. | `[inferred]` dari absennya mekanisme ini di §5/Backend filesystem `../systems/deepagents.md` |
| Model context | `SummarizationMiddleware` (kompaksi otomatis berbasis threshold token) + `FilesystemMiddleware` (eviction hasil tool besar ke backend, diganti preview + rujukan path) | `[code]` `../systems/deepagents.md` §2 |
| Run state | `DeepAgentState` lewat `checkpointer` yang disuntik aplikasi — resumable per thread | `[code]` `../systems/deepagents.md` §5 |
| Memory | `MemoryMiddleware` (statis — isi `AGENTS.md` disuntik sekali di awal sesi) + `StoreBackend(namespace=...)` (durable lintas-thread, butuh `store` disuntik aplikasi) | `[code]` `../systems/deepagents.md` §2, §5, Backend filesystem |
| Artefak | Tidak ada primitive "artifact"/versioning bawaan; `StoreBackend`/`CompositeBackend` bisa dipakai sebagai lapisan durable-nya, tapi object-store S3 + metadata versi tetap tanggung jawab aplikasi | `[code]`+`[inferred]` `../systems/deepagents.md` Backend filesystem |

Implikasi langsung: kalau sebuah project butuh riwayat chat yang bisa
dicari/dipaginasi/di-branch lintas sesi (yaitu Transcript sungguhan), itu
**tidak** datang gratis dari `checkpointer`. Harus dibangun sebagai tabel
`messages` aplikasi sendiri (lihat `persistence-schema.md`), dan
`checkpointer`/`store` yang disuntik ke `create_deep_agent` tetap dipakai
apa adanya untuk Run state + Memory durable — dua hal berbeda yang kebetulan
sama-sama "Postgres" di tabel lima lapis di atas.

## Sumber

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2
  (Context), §5 (State & resume), dan §Backend filesystem — tier-1 reference
  yang sudah diverifikasi terhadap source `deepagents==0.7.8`; dikutip
  langsung di sini tanpa membaca ulang source karena sudah divalidasi di
  Task 3.
- `[docs]` LangGraph — skema `checkpoints`/`writes` dan kontrak
  `BaseCheckpointSaver` (`thread_id`, `checkpoint_ns`, `checkpoint_id`,
  `parent_checkpoint_id`), dikutip via Context7 dari
  `docs.langchain.com/oss/python/langgraph/checkpointers` — dipakai untuk
  memverifikasi klaim "checkpointer bukan database produk": skemanya
  dioptimalkan untuk lookup satu thread (PK `thread_id, checkpoint_ns,
  checkpoint_id`), bukan untuk query lintas-user.
