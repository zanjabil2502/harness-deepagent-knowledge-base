# Human-in-the-loop

## Masalah

"Minta approval sebelum aksi berbahaya" gampang diucapkan, sulit
dioperasionalkan tanpa dua keputusan eksplisit yang sering luput:

1. **Apa yang layak dihentikan?** Menghentikan terlalu banyak (approval
   untuk tiap tool call, termasuk yang baca-saja dan tidak berbahaya)
   membuat user melatih diri klik "approve" tanpa membaca — gerbang jadi
   dekoratif, bukan kontrol. Menghentikan terlalu sedikit (cuma aksi yang
   "kelihatan" berbahaya, bukan yang sistematis diukur) membiarkan aksi
   destruktif lolos karena kebetulan tidak masuk daftar yang dipikirkan
   penulis kode. Kriteria "kapan berhenti" harus eksplisit dan terukur,
   bukan intuisi penulis kode di satu titik waktu.
2. **Bagaimana keputusan itu dicatat?** Approval yang cuma berupa klik di
   UI yang tidak meninggalkan jejak terpisah dari efek sampingnya (aksi
   yang jadi jalan) tidak bisa dijawab belakangan: siapa yang menyetujui,
   kapan, apakah argumennya diedit sebelum dieksekusi, atau ditolak lalu
   dicoba ulang dengan argumen berbeda. Tanpa jejak eksplisit, "siapa yang
   menyetujui aksi ini" cuma bisa dijawab dengan "aksinya kejadian, jadi
   pasti ada yang approve" — inferensi yang lemah untuk apa pun yang
   butuh audit.

File ini **tidak** memiliki titik penegakan approval itu sendiri —
[`guardrails.md`](guardrails.md) titik 3 (Tool/aksi) sudah memetakannya ke
`interrupt_on`/`permissions` → `HumanInTheLoopMiddleware`, dan
[`security.md`](security.md) mencakup kenapa aksi destruktif butuh
kontrol lebih ketat dari aksi baca. File ini memperdalam dua hal yang
belum dijawab di sana: kriteria memilih apa yang masuk gerbang, dan
bagaimana keputusan gerbang itu direkam sebagai data.

## Pola

### Kriteria "layak dihentikan": reversibilitas × blast radius, bukan daftar nama tool

Keputusan gerbang paling kokoh kalau diturunkan dari dua sumbu, bukan
didaftar tool-per-tool secara ad hoc:

| | Blast radius kecil | Blast radius besar |
|---|---|---|
| **Reversibel** (bisa dibatalkan/diulang tanpa efek permanen) | Tidak perlu gerbang — `read_file`, `search`, query baca-saja | Pertimbangkan gerbang kalau biaya per-eksekusi tinggi (mis. panggilan API berbayar ke pihak ketiga) meski efeknya bisa di-undo |
| **Irreversibel** (efek permanen, tidak bisa dibatalkan) | Gerbang opsional tergantung konteks — edit satu baris di file scratch milik agent sendiri | **Selalu gerbang** — `delete_file` di luar sandbox, `DROP TABLE`, kirim email/pesan ke pihak eksternal, transaksi finansial, apa pun yang menyentuh sistem di luar kendali agent (lihat "Blast radius" di 6 sumbu arketipe, `SKILL.md`) |

Reversibilitas dan blast radius adalah dua sumbu yang **sudah** dipakai KB
ini di tempat lain — blast radius persis sumbu pertama dari 6 sumbu
pembeda arketipe (`SKILL.md`), dan reversibilitas adalah alasan implisit
kenapa `guardrails.md` titik 3 memberi mode kegagalan fail-closed spesifik
untuk approval ("timeout approval = default *deny*, bukan default lanjut"
— default yang cuma masuk akal untuk aksi yang mahal dibatalkan kalau
ternyata salah jalan). Titik pentingnya: kriteria "layak dihentikan" bukan
daftar nama tool yang ditebak sekali di awal proyek, tapi turunan dari dua
properti yang bisa dinilai untuk tool **baru** sekalipun sebelum tool itu
pernah dipanggil — tool baru otomatis punya jawaban "perlu gerbang atau
tidak" begitu reversibilitas dan blast radius-nya diketahui, tanpa
menunggu insiden untuk menyadarinya.

Catatan konsisten dengan `tool-design.md` §Heuristik: kriteria ini berlaku
**per operasi**, bukan per nama tool luas — tool `execute` yang menjalankan
`ls` (reversibel, blast radius kecil) vs `execute` yang menjalankan
`rm -rf` (irreversibel, blast radius besar) punya jawaban gerbang yang
berbeda meski nama tool-nya sama; kalau gerbang cuma bisa digantung ke
nama tool (lihat `## Di deepagents`), granularitas tool itu sendiri yang
harus disesuaikan supaya klasifikasi reversibilitas/blast-radius bisa
ditegakkan tanpa membaca isi argumen di dalam gerbang.

### Approver sebagai strategi yang ditukar, bukan cabang di dalam engine

Gerbang persetujuan punya satu masalah yang jarang ditulis: **mode sesi berubah**.
Sesi yang dimulai attended bisa ditinggal; automation terjadwal berjalan tanpa
siapa pun menunggu. Kalau logika "tanya siapa" hidup sebagai `if` di dalam loop
agent, tiap mode baru menambah cabang di jalur terpanas.

OpenWorker memisahkannya: permission engine-nya satu, yang ditukar adalah
**approver**-nya. Sesi attended memakai prompt inline; sesi unattended memakai
`inbox_approver(store, session_id)`. `[code]` `andrewyng/openworker` @ `141d02a`,
`coworker/inbox.py:387`; rutingnya diuji eksplisit di
`tests/test_unattended.py:22-60` dengan komentar *"an unattended session uses the
inbox approver, so consequential actions park in the Inbox instead of prompting
inline."*

Bentuk kembaliannya tetap satu enum apa pun approver-nya — `ApprovalOutcome`
dengan `ONCE`, `ALWAYS_TOOL`, `ALWAYS_COMMAND`, `READONLY_SESSION`, `DENY`
(`coworker/engine.py:31-37`). `[code]` Itu yang membuat penukaran aman: engine
tidak perlu tahu dari permukaan mana jawaban datang.

### Transisi attended ↔ unattended butuh rekonsiliasi

Konsekuensi yang mudah terlewat: kalau persetujuan dapat dijawab dari permukaan
lain selagi operator pergi, ia kembali tanpa tahu **apa yang sudah disetujui atas
namanya**.

OpenWorker menjawabnya dengan `reconcile_on_resume` (`coworker/inbox.py:374-380`):
saat operator kembali ke kendali attended, item yang masih pending dimunculkan
inline **dan** disertai rekap yang sudah terjawab selama ia pergi, dengan prinsip
yang dinyatakan di docstring-nya — *"Single source of truth: every item already has
one authoritative resolution."* `[code]`

Satu resolusi otoritatif per item adalah bagian yang penting. Tanpa itu, permukaan
kedua (Slack, inbox, TUI) menjadi jalur persetujuan paralel yang bisa berbeda
jawaban untuk permintaan yang sama.

### Merekam keputusan sebagai data, bukan cuma efek sampingnya

Satu keputusan approval punya empat bentuk mungkin — **approve** (jalankan
apa adanya), **edit** (jalankan dengan argumen yang diubah manusia sebelum
eksekusi), **reject** (jangan jalankan), **respond** (manusia memberi
jawaban tanpa menjalankan aksi sama sekali, mis. untuk aksi yang ternyata
tidak perlu). Empat kemungkinan ini sendiri adalah properti protokol,
bukan konvensi UI bebas — lihat `## Di deepagents` untuk bentuk konkretnya.

Yang **wajib** direkam untuk tiap keputusan, terlepas dari mekanisme
mananya dipakai: *siapa* (identitas approver — bisa beda dari `user_id`
pemilik percakapan kalau approval didelegasikan ke reviewer terpisah),
*kapan* (timestamp keputusan, terpisah dari timestamp aksi dieksekusi —
jeda antara keduanya adalah sinyal berguna: approval yang di-*klik* sedetik
setelah muncul, berulang kali, adalah sinyal rubber-stamping yang sama
persis dengan gerbang yang terlalu sering dipicu di §Kriteria), *apa
keputusannya* (salah satu dari empat di atas), dan *argumen final* (kalau
`edit` — argumen asli yang diajukan model **dan** argumen hasil edit
manusia, dua-duanya, supaya bisa dibedakan "model minta X, manusia ubah
jadi Y" dari "model minta X, dijalankan apa adanya").

**Gap yang jujur dilaporkan**: [`persistence-schema.md`](persistence-schema.md)
punya tabel `tool_calls` (`status` `'pending'`/`'success'`/`'error'`,
`arguments`, `result`) yang menyimpan **hasil** eksekusi, tapi skema itu
**tidak** punya kolom untuk approver/timestamp-keputusan/jenis-keputusan/
argumen-sebelum-edit — status `'success'` sesudah gerbang HITL tidak bisa
dibedakan dari status `'success'` tanpa gerbang sama sekali hanya dari
tabel itu. Ini bukan cacat skema `persistence-schema.md` (approval belum
masuk cakupan task yang menulisnya) — ini kebutuhan tambahan yang file ini
tandai eksplisit: project yang memasang HITL wajib memperluas skema
(kolom tambahan di `tool_calls`, atau tabel `tool_call_approvals` terpisah
yang mengaitkan `tool_call_id` → approver/keputusan/argumen-asli) supaya
"siapa menyetujui apa" bisa dijawab dari data, bukan dari inferensi. Ini
konsisten dengan gap serupa yang sudah dicatat
[`guardrails.md`](guardrails.md) §6 Sistem untuk audit log gerbang secara
umum ("checkpoint state per step... jejak paling dekat yang tersedia
gratis") — file ini mempersempitnya ke bentuk konkret satu tabel tambahan
untuk kasus HITL secara spesifik.

## Trade-off

- **Kriteria reversibilitas × blast radius vs daftar nama tool statis** —
  kriteria berbasis properti butuh disiplin menilai tiap tool
  baru/operasi baru terhadap dua sumbu itu (satu langkah tidak-langsung
  tambahan dibanding "tambahkan nama tool ke daftar"), tapi generalisasi
  ke tool yang belum pernah ada; daftar nama statis cepat ditulis di awal
  tapi diam-diam gagal untuk tool baru yang lupa ditambahkan — persis
  penyakit yang §Kriteria coba hindari.
- **Approval granular (per operasi/argumen) vs granular per nama tool
  saja** — granular per operasi paling presisi (cuma menghentikan yang
  betul-betul perlu) tapi butuh tool yang cukup sempit atau gerbang yang
  membaca isi argumen (dua-duanya biaya desain tambahan, lihat
  `tool-design.md`); granular per nama tool lebih murah dipasang (satu
  flag per tool) tapi memaksa semua pemanggilan tool itu masuk kebijakan
  yang sama, termasuk yang sebenarnya aman.
- **Timeout approval default-deny vs default-lanjut** — default-deny
  (dipilih `guardrails.md` titik 3) aman untuk aksi mahal dibatalkan tapi
  bisa memblokir alur kerja legit kalau approver lambat merespons (mis.
  approver offline); default-lanjut tidak pernah memblokir alur kerja
  tapi berarti aksi irreversibel bisa jalan tanpa approval nyata kalau
  timeout kebetulan tercapai — asimetri bahaya yang sama dengan yang
  dijelaskan `guardrails.md` §Trade-off (kebocoran/aksi salah senyap vs
  gangguan UX terlihat) menentukan default-deny menang untuk kelas aksi
  yang memang layak digerbang.
- **Simpan approval sebagai kolom tambahan di `tool_calls` vs tabel
  terpisah `tool_call_approvals`** — kolom tambahan di `tool_calls`
  sederhana (satu tabel, satu join lebih sedikit) tapi mayoritas baris
  `tool_calls` (yang tidak pernah lewat gerbang) akan punya kolom-kolom
  itu selalu `NULL` — skema jadi jarang terisi untuk kasus mayoritas;
  tabel terpisah menjaga `tool_calls` tetap bersih dan cuma ada barisnya
  kalau memang ada keputusan HITL, dengan biaya satu join tambahan tiap
  kali riwayat approval perlu ditampilkan.

## Di deepagents

`interrupt_on={"tool_name": True | InterruptOnConfig}` memasang
`HumanInTheLoopMiddleware` (dari `langchain.agents.middleware`) — sudah
dipetakan `guardrails.md` titik 3 dan `../systems/deepagents.md` §6; file
ini menambah detail bentuk keputusan dan mekanisme resume:

- Empat jenis keputusan di §Pola **persis** `DecisionType = Literal["approve",
  "edit", "reject", "respond"]` di implementasi middleware — bukan
  konvensi bebas yang file ini usulkan, tapi tipe yang sudah ada di
  pustaka. `ReviewConfig.allowed_decisions` membatasi subset keputusan
  yang valid **per aksi** (mis. aksi tertentu cuma boleh `approve`/`reject`,
  tidak `edit`, kalau argumennya tidak masuk akal untuk diedit manusia).
  `[code]` — `langchain/agents/middleware/human_in_the_loop.py`, kelas
  `DecisionType`, `ReviewConfig`, `ActionRequest`.
- Mekanisme jeda: `HumanInTheLoopMiddleware` memanggil `interrupt(hitl_request)`
  dari `langgraph.types` — ini **menghentikan eksekusi graph** di titik itu
  dan mem-persist state-nya lewat `checkpointer` yang sama dengan Run state
  (`../systems/deepagents.md` §5). Resume dilakukan lewat `Command(resume=
  {"decisions": [...]})` yang dikirim aplikasi setelah manusia memutuskan.
  Konsekuensi langsung untuk §Reattach di
  [`streaming-protocol.md`](streaming-protocol.md): karena state interrupt
  sudah otomatis ter-checkpoint, "approval yang sedang menunggu tidak
  hilang saat client disconnect" **datang gratis** dari mekanisme resume
  `langgraph` — yang harus dibangun aplikasi cuma cara memberi tahu client
  yang reconnect bahwa interrupt itu ada (event `interrupt` di
  `streaming-protocol.md` §Skema event). `[code]` —
  `langchain/agents/middleware/human_in_the_loop.py` (`interrupt(...)`
  dipanggil, hasilnya dibaca sebagai `decisions = interrupt(hitl_request)
  ["decisions"]`).
- **Gerbang per nama tool, bukan per isi argumen** — `interrupt_on`
  dikonfigurasi per nama tool (`{"execute": True}`), konsisten dengan
  batasan yang sudah dinamai `tool-design.md` "Approval granular (HITL)":
  tidak ada mekanisme bawaan untuk menggerbang berdasarkan isi argumen
  tool call (mis. `execute` cuma digerbang kalau argumennya mengandung
  `rm`) — kalau butuh itu, harus ditulis sebagai logika kustom di dalam
  `_should_interrupt`/hook `wrap_tool_call` sendiri. `[code]` — dikutip
  `langchain/agents/middleware/human_in_the_loop.py`
  (`_should_interrupt`), tidak ditemukan parameter bawaan untuk kondisi
  berbasis isi argumen di file itu.
- **Rekaman keputusan tidak otomatis jadi baris audit** — hasil `interrupt()`
  (keputusan `approve`/`edit`/`reject`/`respond`, siapa yang memutuskan)
  hidup sebagai bagian dari **payload resume** yang dikirim aplikasi
  (`Command(resume=...)`), bukan sebagai row terpisah yang otomatis
  ditulis `deepagents`/`langgraph` ke tempat yang bisa di-query lintas
  waktu — cuma checkpoint biner yang menyimpan snapshot state graph.
  Ini yang mendasari gap eksplisit di §Pola: aplikasi wajib menulis
  keputusan itu ke tabel sendiri (perluasan `tool_calls`/tabel baru) kalau
  butuh audit yang bisa di-query, `deepagents`/`langgraph` tidak
  menyediakannya. `[inferred]` — disimpulkan dari tidak ditemukannya
  mekanisme penulisan audit terpisah di `human_in_the_loop.py` maupun
  `deepagents/middleware/`, hanya jalur checkpoint yang dikutip di atas.
- `permissions=[FilesystemPermission(mode="interrupt")]` **otomatis**
  membangkitkan entri `interrupt_on` yang setara (`_build_interrupt_on_from_permissions`),
  digabung dengan `interrupt_on` eksplisit — sudah dipetakan
  `../systems/deepagents.md` §6, tidak diulang detailnya di sini.

## Sumber

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5, §6 —
  tier-1 reference terverifikasi terhadap `deepagents==0.7.8`, dikutip
  langsung tanpa membaca ulang source `deepagents/graph.py` di task ini.
- `[code]` `langchain/agents/middleware/human_in_the_loop.py` — dibaca
  langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langchain/agents/middleware/human_in_the_loop.py`,
  kelas `DecisionType`, `ReviewConfig`, `ActionRequest`, `HITLRequest`,
  pemanggilan `interrupt(hitl_request)` dan pembacaan
  `interrupt(...)["decisions"]`.
- `[code]` [`guardrails.md`](guardrails.md) titik 3 (Tool/aksi), §6 Sistem
  — dasar pemetaan `interrupt_on`/`permissions` → middleware, dan gap
  audit log yang dipersempit file ini; tidak diulang mekanismenya.
- `[code]` [`tool-design.md`](tool-design.md) §Pola (baris "Approval
  granular (HITL)"), §Heuristik pemilihan — dasar klaim gerbang per nama
  tool vs per operasi.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — tabel
  `tool_calls`, dikutip untuk gap kolom approval; skema tidak diubah di
  file ini.
- `[code]` [`streaming-protocol.md`](streaming-protocol.md) §Reattach —
  dasar klaim state interrupt otomatis ter-checkpoint mendukung reattach.
- `[code]` `SKILL.md` §6 sumbu pembeda — dasar sumbu "Blast radius" yang
  dipakai ulang di §Kriteria.
