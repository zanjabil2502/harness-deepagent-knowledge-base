# Memory

## Masalah

Memory lintas sesi berbeda dari `session-state.md` lapis "Run state" —
bukan cuma "state yang lebih awet", tapi state yang harus **dikurasi**
aktif, bukan diakumulasi mentah. Empat pertanyaan yang jarang dijawab
sengaja:

1. **Ekstraksi** — apa yang masuk memory dari percakapan mentah? Semua
   yang dikatakan, atau cuma fakta yang dinilai penting — dan siapa/apa
   yang menilai itu?
2. **Konflik** — kalau fakta baru bertentangan dengan fakta lama (user
   dulu bilang X, sekarang bilang bukan-X), apakah keduanya disimpan
   (memory jadi internal-inkonsisten diam-diam), atau satu menang — dan
   kalau satu menang, berdasar apa dan apakah keputusan itu tercatat?
3. **Pembaruan** — kalau fakta yang sama diulang dengan detail lebih
   lengkap, apakah itu entri baru (duplikasi) atau memperbarui entri lama?
4. **Penghapusan** — paling jarang dibahas: bagaimana memory sungguh
   dihapus, bukan cuma "berhenti ditampilkan"? `retention-and-deletion.md`
   sudah menuntut penghapusan lintas lapis wajib nyata dan cascading; lapis
   memory bukan pengecualian.

Gejala sistem yang tidak menjawab ini: memory yang cuma pernah tumbuh
(ADD terus-menerus, tidak pernah UPDATE/DELETE) berubah jadi tumpukan
fakta yang mungkin saling bertentangan, dan masalah resolusi konfliknya
diam-diam dipindah ke apa pun yang membaca memory saat query — bukan
diselesaikan saat ditulis.

## Pola

### Tiga mekanisme berbeda untuk tiga pertanyaan berbeda

Sistem memory nyata yang dibaca untuk file ini (Letta) memisahkan tiga
mekanisme dengan tujuan berbeda, bukan satu penyimpanan generik:

- **Core/working memory** — set blok kecil, berlabel, **selalu** ada di
  context, diedit presisi lewat tool (`core_memory_append`,
  `core_memory_replace`, `memory_replace`, `memory_insert`, `rethink_memory`).
  Menjawab "apa yang harus selalu diingat" (mis. blok `human` berisi fakta
  inti tentang user). `[code]` `letta/functions/function_sets/base.py`
  baris 246-527, repo `letta-ai/letta` cabang `archive`.
- **Archival/long-term memory** — besar, tak terbatas, diambil lewat
  pencarian semantik, **tidak** selalu di context (`archival_memory_insert`,
  `archival_memory_search`, mendukung tag dan filter tanggal). Menjawab
  "apa yang mungkin perlu dicari nanti" — fakta yang tidak perlu selalu
  hadir tapi harus tetap bisa ditemukan. `[code]` `letta/functions/function_sets/base.py`
  baris 164-245.
- **Recall/pencarian percakapan** — pencarian atas transkrip mentah itu
  sendiri (`conversation_search`, hybrid text + semantic similarity),
  bukan atas fakta yang sudah dikurasi sama sekali. Menjawab "apa yang
  betul-betul pernah dikatakan", beda dari dua mekanisme di atas yang
  menjawab "apa yang disimpulkan penting". `[code]` `letta/functions/function_sets/base.py`
  baris 87-163. Ini pasangan konsep dari tabel `messages`/`tool_calls` di
  [`persistence-schema.md`](persistence-schema.md) — transkrip sebagai
  sumber kebenaran, dicari langsung tanpa lapis kurasi.

Mencampur ketiganya jadi satu penyimpanan generik kehilangan properti yang
justru jadi alasan masing-masing ada: core memory butuh selalu-di-context
(mahal kalau semua fakta diperlakukan begitu); archival butuh tidak-selalu-
di-context (boros kalau semua fakta wajib muncul tiap turn); recall butuh
tetap mentah (kurasi yang terlalu agresif menghapus detail yang justru
dicari nanti).

### Ekstraksi: siapa memutuskan sesuatu layak diingat

Dua mekanisme nyata, dua model aktor berbeda:

- **Digerakkan model, berbasis tool** (Letta) — agent sendiri yang
  memanggil `core_memory_append`/`archival_memory_insert` sebagai bagian
  dari reasoning-nya sendiri saat itu juga. Ekstraksi **adalah** tindakan
  tool call — eksplisit, bisa diaudit dari trajektori (`evaluation.md` bisa
  langsung menegaskan "apakah `core_memory_append` dipanggil di kasus ini"
  sebagai bagian eval trajektori). `[code]` sama seperti di atas.
- **Digerakkan pipeline, ekstraksi LLM sebagai batch step** (Mem0) —
  panggilan LLM terpisah (`ADDITIVE_EXTRACTION_PROMPT`) atas pesan terbaru
  + kandidat memory yang sudah ada menghasilkan daftar JSON fakta kandidat,
  dijalankan sebagai fase tersendiri (`_add_to_vector_store` Phase 2),
  bukan tindakan agent yang sedang bertugas. `[code]` `mem0/memory/main.py`
  baris 913-968 (Phase 2, panggilan `self.llm.generate_response` dengan
  `system_prompt = ADDITIVE_EXTRACTION_PROMPT`), repo `mem0ai/mem0`.

Aktor yang menilai "layak diingat" beda: agent yang sedang mengerjakan
tugas, seketika (Letta), vs proses ekstraksi terpisah yang membaca ulang
percakapan setelahnya (Mem0) — lihat `## Trade-off` untuk konsekuensinya.

### Konflik dan pembaruan: judgment LLM vs deterministik exact-match

Mem0 **mendokumentasikan** pola resolusi konflik empat-arah yang cukup
dikenal di literatur memory agent: untuk tiap fakta yang diekstrak,
`DEFAULT_UPDATE_MEMORY_PROMPT` meminta LLM memutuskan salah satu dari ADD
(fakta baru), UPDATE (bertentangan/menyampaikan hal yang sama tapi lebih
lengkap — ID lama dipertahankan), DELETE (fakta lama & fakta baru
bertentangan langsung), atau NONE (sudah ada/tidak relevan), lengkap
dengan contoh berpasangan untuk tiap kasus. `[code]` `mem0/configs/prompts.py`
baris 176-322, repo `mem0ai/mem0`.

**Temuan penting yang wajib dicatat jujur**: prompt ini **tidak** dipanggil
di jalur `_add_to_vector_store` versi yang dibaca saat ini (`mem0/memory/main.py`,
diverifikasi lewat pencarian `DEFAULT_UPDATE_MEMORY_PROMPT`/
`get_update_memory_messages` di file itu — nol kecocokan). Pipeline yang
sungguh berjalan hari ini murni aditif dengan dedup berbasis hash MD5
konten (`mem_hash in existing_hashes or mem_hash in seen_hashes` → lewati,
selain itu selalu `event: "ADD"`) — tidak ada keputusan UPDATE/DELETE
otomatis terhadap memory yang sudah ada saat menulis fakta baru. `[code]`
`mem0/memory/main.py` baris 1010-1039 (Phase 4-5, dedup hash),
1160-1168 (`returned_memories` selalu `"event": "ADD"`). UPDATE/DELETE yang
sungguh ada di API adalah panggilan eksplisit **by-ID**: `update(memory_id,
text=...)` dan `delete(memory_id)`, dipicu aplikasi pemanggil, bukan
diputuskan otomatis oleh sistem memory saat menulis fakta baru. `[code]`
`mem0/memory/main.py` baris 1815-1866 (`update`), 1869-1889 (`delete`).
Pola ADD/UPDATE/DELETE/NONE per-fakta tetap contoh nyata dan terdokumentasi
lengkap tentang **bagaimana** resolusi konflik berbasis judgment LLM bisa
dirancang — tapi mengutipnya sebagai "begini cara Mem0 menyelesaikan
konflik hari ini" akan salah tanpa catatan ini.

Letta menempuh jalur berlawanan untuk konflik di core memory: **deterministik,
bukan judgment**. `core_memory_replace(label, old_content, new_content)`
mensyaratkan `old_content` cocok **persis** dengan isi blok saat ini —
kalau tidak ditemukan, fungsi `raise ValueError` alih-alih menebak niat
pemanggil. `[code]` `letta/functions/function_sets/base.py` baris 263-281.
Konflik di sini tidak "diselesaikan" oleh judgment — ia ditangkap sebagai
kegagalan keras yang memaksa pemanggil (model itu sendiri, di tengah
reasoning-nya) memeriksa ulang isi blok dan mencoba lagi dengan match yang
benar. Untuk reorganisasi/dedup yang genuinely butuh menulis ulang seluruh
blok (bukan sekadar ganti satu string), jalurnya eksplisit dan terpisah:
`rethink_memory`/`memory_rethink` menulis ulang **seluruh** isi blok
sekaligus, disyaratkan dokumentasinya mengintegrasikan info baru sambil
membuang yang usang/tidak konsisten — operasi rewrite penuh, bukan
patch parsial. `[code]` `letta/functions/function_sets/base.py`
baris 283-310, 488-519.

### Penghapusan: tindakan eksplisit, bukan "berhenti ditampilkan"

Konsisten dengan `retention-and-deletion.md`: kedua sistem yang dibaca
memperlakukan penghapusan sebagai jalur kode tersendiri, bukan efek
samping dari sesuatu yang lain. Mem0: `delete(memory_id)`/
`delete_all(user_id=..., agent_id=..., run_id=...)` adalah panggilan API
kelas satu. `[code]` `mem0/memory/main.py` baris 1869-1926. Letta: tool
`memory` mendukung sub-command `"delete"` eksplisit pada path blok
tertentu, dan `core_memory_replace` dengan `new_content=""` adalah jalur
setara untuk core memory. `[code]` `letta/functions/function_sets/base.py`
baris 10-69 (docstring tool `memory`, sub-command `delete`), 263-281
(`core_memory_replace`, komentar "To delete memories, use an empty string").
Tidak satu pun dari dua sistem ini memperlakukan "tidak lagi diambil saat
retrieval" sebagai penghapusan — keduanya punya operasi hapus yang benar-
benar menghapus record.

## Trade-off

- **Ekstraksi digerakkan-model vs digerakkan-pipeline** — digerakkan-model
  bisa diaudit sebagai tindakan spesifik di trajektori dan terjadi persis
  saat agent yang bertugas menilai sesuatu layak disimpan, tapi kualitas
  memory-nya terikat pada apa yang kebetulan disadari agent itu di tengah
  mengerjakan tugas lain (bukan fokus utamanya), dan menambah overhead tool
  call di giliran mana pun ekstraksi terjadi. Pipeline terpisah bisa
  memproses seluruh percakapan dengan hindsight penuh, bisa memakai model
  lebih kecil/murah khusus ekstraksi, tapi adalah sistem terpisah yang
  harus dibangun/dipelihara sendiri dan punya jeda (ada tenggang waktu
  antara sesuatu dikatakan dan menjadi memory yang bisa dipakai ulang).
- **Resolusi konflik berbasis judgment LLM vs deterministik exact-match** —
  judgment LLM bisa mengenali penyampaian ulang yang secara makna sama
  ("suka pizza keju" = "cinta pizza keju") dan bertindak seperti editor
  manusia, tapi keputusannya black-box tiap kali (tidak reproducible,
  butuh panggilan model per batch fakta) dan bisa salah (menghasilkan
  DELETE untuk sesuatu yang sebenarnya tidak bertentangan). Deterministik
  exact-match 100% dapat diprediksi dan gratis (tanpa panggilan model
  tambahan), tapi rapuh — pemanggil harus tahu persis string lama atau
  operasinya gagal, dan tidak bisa mengenali parafrase sebagai "fakta yang
  sama" seperti judgment LLM bisa.
- **Resolusi konflik selalu-aktif vs ditunda ke panggilan eksplisit
  by-ID** (pola yang sungguh terverifikasi di jalur Mem0 saat ini) —
  menunda jauh lebih sederhana dibangun (tidak perlu menyelesaikan konflik
  terhadap memory store yang sudah ada di tiap penulisan) dan menghindari
  biaya/risiko judgment LLM di atas, tapi memindahkan masalah deteksi
  konflik ke siapa pun yang membaca memory belakangan — fakta yang nyaris
  duplikat atau bahkan bertentangan bisa hidup berdampingan diam-diam,
  kecuali aplikasi membangun rekonsiliasinya sendiri di atas.

## Di deepagents

`deepagents` **tidak** mengirim sistem memory lintas sesi terkurasi ala
Letta/Mem0 — `MemoryMiddleware` cuma memuat isi file `AGENTS.md` ke system
prompt sekali di awal sesi (`memory=["./AGENTS.md", ...]`): konteks statis
yang disuntik sekali, bukan ekstraksi/konflik/pembaruan/penghapusan fakta
diskret. `[code]` dikutip `../systems/deepagents.md` §2. `StoreBackend
(namespace=...)` memberi penyimpanan durable lintas-thread lewat `BaseStore`
LangGraph — tapi ia backend generik untuk permukaan tool filesystem
(`read_file`/`write_file`/`edit_file`), bukan pipeline khusus memory dengan
mekanisme ekstraksi/konflik sendiri. `[code]` dikutip
`../systems/deepagents.md` §Backend filesystem. `CompositeBackend` bahkan
punya konvensi contoh dokumentasi merutekan prefix path `/memories/` ke
`StoreBackend` — tapi itu tetap penamaan konvensi filesystem, bukan
mekanisme kurasi memory bawaan. `[code]`/`[docs]` dikutip
`../systems/deepagents.md` §Backend filesystem
(`docs.langchain.com/oss/python/deepagents/backends`).

Proyek yang butuh memory ala Letta/Mem0 harus membangunnya sendiri di atas
`deepagents` — baik sebagai tool kustom yang menulis ke `StoreBackend`
(pola digerakkan-model, mirip Letta: tool eksplisit yang dipanggil agent),
atau memanggil layanan memory eksternal (Letta/Mem0 sesungguhnya) sebagai
tool. `[inferred]` disimpulkan dari tidak ditemukannya modul
ekstraksi/konflik/deduplikasi fakta di `deepagents/middleware/` yang dibaca
Task 3 maupun task ini. Lapis "Memory" di tabel lima-lapis
[`session-state.md`](session-state.md) §Lima lapis (§8.1) — Postgres +
vector, lintas sesi, dimiliki BE+AI — adalah tempat arsitektural yang
disediakan proyek ini untuk hasil bangunan kustom itu; `deepagents` sendiri
tidak mengisi lapis itu.

## Sumber

- `[code]` `letta/functions/function_sets/base.py` (repo `letta-ai/letta`,
  cabang `archive` — cabang yang menyimpan source server Letta V1;
  `main` sudah jadi landing page yang mengarahkan ke `letta-ai/letta-code`,
  dikonfirmasi lewat `README.md` repo tersebut), dibaca via
  `raw.githubusercontent.com/letta-ai/letta/archive/letta/functions/function_sets/base.py` —
  `core_memory_append`/`core_memory_replace`/`rethink_memory` (baris
  246-323), `memory_replace`/`memory_insert`/`memory_rethink` (baris
  330-527), `archival_memory_insert`/`archival_memory_search` (baris
  164-245), `conversation_search` (baris 87-163), tool `memory` sub-command
  `delete` (baris 10-69).
- `[code]` `mem0/memory/main.py` (repo `mem0ai/mem0`, cabang `main`),
  dibaca via `raw.githubusercontent.com/mem0ai/mem0/main/mem0/memory/main.py` —
  `_add_to_vector_store` Phase 2 ekstraksi (baris 913-968), Phase 4-5 dedup
  hash (baris 1010-1039), `returned_memories` event selalu `"ADD"` (baris
  1160-1168), `update`/`delete` eksplisit by-ID (baris 1815-1889).
- `[code]` `mem0/configs/prompts.py` (repo `mem0ai/mem0`), dibaca via
  `raw.githubusercontent.com/mem0ai/mem0/main/mem0/configs/prompts.py` —
  `DEFAULT_UPDATE_MEMORY_PROMPT` (baris 176-322, pola ADD/UPDATE/DELETE/NONE
  terdokumentasi lengkap dengan contoh, dikutip dengan catatan tidak
  terpakai di jalur `main.py` saat ini), `ADDITIVE_EXTRACTION_PROMPT`
  (baris 468+, dipakai nyata).
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2
  (`MemoryMiddleware`), §Backend filesystem (`StoreBackend`,
  `CompositeBackend`) — tier-1 reference terverifikasi Task 3.
- `[code]` [`session-state.md`](session-state.md) §Lima lapis (§8.1) —
  lapis Memory (Postgres + vector, BE+AI) yang jadi tempat arsitektural
  hasil bangunan kustom di atas `deepagents`; tidak diusulkan ulang di
  sini.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — pasangan
  konsep tabel `messages`/`tool_calls` yang dirujuk untuk membedakan
  recall/transkrip dari memory terkurasi.
- `[code]` [`retention-and-deletion.md`](retention-and-deletion.md) —
  dasar tuntutan "penghapusan wajib nyata, bukan berhenti ditampilkan"
  yang diterapkan ke lapis memory di file ini.
- `[code]` [`evaluation.md`](evaluation.md) — dasar klaim ekstraksi
  digerakkan-model bisa dinilai lewat eval trajektori.
