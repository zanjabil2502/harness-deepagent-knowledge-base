# Delegation

## Masalah

"Spawn subagent, dapat hasilnya kembali" terlihat sederhana sampai dua hal
yang jarang diputuskan sengaja jadi masalah nyata. Pertama, **kontrak
hasil** — apa persis yang mengalir kembali dari subagent ke pemanggil —
sering dibiarkan implisit: kalau seluruh transkrip kerja subagent (semua
tool call, semua langkah coba-salah) ikut mengalir balik, delegasi
kehilangan tujuannya sendiri (mengisolasi dan memampatkan kerja jadi satu
serah-terima bersih), context pemanggil membengkak persis oleh hal yang
delegasi seharusnya mencegah. Kalau sebaliknya cuma state privat yang
bocor balik, itu kebocoran isolasi yang tidak diinginkan siapa pun.

Kedua, **kedalaman delegasi** — tidak ada yang mencegah subagent men-spawn
subagent-nya sendiri, dan tanpa batas eksplisit, blast radius (biaya, loop
yang lari) bertambah senyap lintas level. Ini pola yang sama dengan
`agent-loop.md` §Masalah: kalau keputusan "berapa dalam boleh bercabang"
tidak dibuat sengaja, perilaku sebenarnya ditentukan oleh apa pun batas
kebetulan yang disediakan platform — dan batas kebetulan itu biasanya satu
penghitung langkah **global** yang dibagi seluruh pohon, bukan penjaga
kedalaman per-cabang, sehingga tidak bisa membedakan "satu agent jalan 9000
langkah" dari "30 subagent masing-masing 300 langkah" — keduanya
menghabiskan anggaran yang sama, tapi cuma yang kedua adalah pola fan-out
rekursif yang biasanya jadi tanda ada yang salah.

## Pola

### Taksonomi jalur delegasi

- **Flat** — satu agent, tidak ada subagent sama sekali. Baseline; semua
  yang di bawah adalah penyimpangan darinya untuk alasan spesifik
  (isolasi kerja, paralelisme, model/tool berbeda per sub-tugas).
- **Inline sinkron** — pemanggil memblokir sampai subagent selesai, dapat
  satu hasil bersih kembali. Cocok untuk sub-tugas yang hasilnya dibutuhkan
  sebelum pemanggil bisa lanjut.
- **Runnable pra-kompilasi milik pemanggil** — subagent yang dibangun dan
  dikendalikan sepenuhnya oleh aplikasi pemanggil sendiri (bukan lewat
  konstruktor harness), dipakai apa adanya. Cocok kalau kerangka
  subagent-nya sudah punya bentuk graph sendiri di luar harness dan tidak
  perlu mewarisi apa pun dari agent utama.
- **Remote/async** — didispatch ke proses/server terpisah, non-blocking;
  pemanggil bisa lanjut bekerja sambil menunggu. Butuh mekanisme
  tracking-nya sendiri (task ID, polling status) karena hasilnya tidak
  langsung tersedia di giliran yang sama.

### Kontrak hasil adalah keputusan desain, bukan default kebetulan

Yang mengalir balik dari subagent ke pemanggil wajib diputuskan eksplisit
sebagai salah satu dari dua bentuk (atau kombinasi bertingkat), bukan
dibiarkan jadi "apa pun yang ada di state subagent saat selesai":

- **Transkrip penuh** — semua yang subagent lakukan ikut kembali. Tidak
  ada informasi hilang, tapi meniadakan alasan mendelegasikan sama sekali:
  context pemanggil membengkak persis oleh detail yang delegasi
  seharusnya mengisolasi (kembali ke kekhawatiran biaya/cache
  `context-engineering.md`), dan detail internal yang tidak relevan buat
  pemanggil (coba-salah, tool result mentah yang cuma dibutuhkan reasoning
  subagent) ikut terekspos.
- **Ringkasan tersaring** — subagent mengembalikan satu hasil bersih yang
  sudah disaring sesuai kebutuhan pemanggil. Kompak, tidak membocorkan
  detail kerja internal, tapi memindahkan beban desain ke `system_prompt`
  subagent: kalau subagent tidak diberi tahu bentuk jawaban yang dibutuhkan
  pemanggil, penyaringan itu sendiri bisa membuang informasi yang justru
  dibutuhkan.

Kontrak juga wajib menyatakan **apa yang sengaja tidak boleh mengalir
balik** — state privat yang cuma relevan untuk kerja internal subagent
(riwayat percobaan yang gagal, kredensial/scope sementara) tidak boleh
bocor ke state pemanggil, bukan cuma "kebetulan tidak disebut".

### Batas kedalaman: sengaja atau kebetulan

Prinsip yang sama dengan "siapa memutuskan berhenti" di `agent-loop.md`
berlaku di sini untuk sumbu kedalaman: sistem delegasi butuh batas
kedalaman **eksplisit**, kalau tidak ia mewarisi apa pun batas platform
yang kebetulan ada. Dua bentuk batas menangkap kegagalan yang berbeda dan
idealnya dipasang bersama, bukan salah satu saja:

- **Batas per-cabang** — tiap subagent tahu seberapa dalam dirinya di
  pohon delegasi, menolak men-spawn lagi begitu melewati N. Menangkap
  fan-out rekursif tak terbatas (agent men-spawn agent men-spawn agent)
  bahkan kalau tiap levelnya murah — blast radius yang tumbuh secara
  struktur, bukan cuma biaya.
- **Anggaran bersama lintas pohon** — satu batas langkah/biaya total untuk
  seluruh pohon (akar + semua turunannya), tidak peduli bentuknya.
  Menangkap overrun biaya total apa pun bentuknya, tapi tidak bisa
  membedakan "satu cabang sangat dalam tapi murah" dari "banyak cabang
  dangkal tapi mahal" — keduanya kena batas yang sama, padahal keduanya
  risiko yang berbeda (nesting dalam tapi murah tetap risiko audit/
  observability tersendiri yang tidak ditangkap anggaran saja).

## Trade-off

- **Inline sinkron vs remote/async** — sinkron lebih mudah dinalar
  (pemanggil memblokir, dapat hasil di giliran yang sama, urutan alami),
  tapi menyita seluruh eksekusi pemanggil selama subagent berjalan
  (latensi aditif). Async membiarkan pemanggil terus bekerja, wall-clock
  lebih baik, tapi butuh mekanisme tracking state sendiri (ID task,
  polling) — permukaan benar/salah yang sepenuhnya baru, dan pertanyaan
  kontrak hasil jadi lebih rumit (bagaimana kalau pemanggil selesai lebih
  dulu dari subagent-nya, bagaimana kalau sesi user berakhir di tengah).
- **Transkrip penuh vs ringkasan tersaring** — sudah dibahas di `## Pola`;
  intinya trade-off klasik kelengkapan vs kompresi, dengan konsekuensi
  nyata di biaya context (`context-engineering.md`) di satu sisi dan risiko
  kehilangan informasi di sisi lain.
- **Batas kedalaman eksplisit vs cuma anggaran bersama** — batas kedalaman
  menangkap fan-out rekursif secara murah dan bisa diprediksi (langit-langit
  tetap), tapi alat yang tumpul kalau ada kasus legit yang butuh nesting
  lebih dalam sesekali (perlu di-tune manual per arketipe). Anggaran
  bersama lebih umum (menangkap overrun apa pun bentuknya) dan tidak butuh
  pembukuan per-cabang, tapi tidak bisa menjawab "apakah kedalaman ini
  aman" secara independen dari "apakah ini mahal" — dua pertanyaan yang
  kadang butuh jawaban berbeda.

## Di deepagents

Tiga jalur delegasi memetakan langsung ke taksonomi `## Pola`: `SubAgent`
(inline sinkron, lewat tool `task`), `CompiledSubAgent` (runnable
pra-kompilasi milik pemanggil, tidak mewarisi `state_schema` dari
`create_deep_agent`), `AsyncSubAgent` (remote/background, lima tool
`start_async_task`/`check_async_task`/`update_async_task`/
`cancel_async_task`/`list_async_tasks`, non-blocking). `[code]` dikutip
`../systems/deepagents.md` §4.

**Kontrak hasil** untuk `SubAgent`/`CompiledSubAgent` sudah konkret dan
sesuai pola "ringkasan tersaring": `messages` state akhir subagent menjadi
isi `ToolMessage` yang dikembalikan ke tool `task` — bukan seluruh
transkrip kerja subagent. Field yang ditandai `PrivateStateAttr` di
middleware manapun (dikumpulkan lewat `private_state_field_names`) tidak
ikut mengalir balik ke state agent utama — inilah mekanisme konkret
"state privat tidak boleh bocor" di `## Pola`. `[code]` dikutip
`../systems/deepagents.md` §4 (`deepagents/middleware/subagents.py`,
`deepagents/graph.py` baris 894-898). `AsyncSubAgent` punya bentuk kontrak
berbeda sama sekali — bukan `ToolMessage` sinkron, tapi status yang
di-cache di `AsyncSubAgentState.tasks` (`task_id -> AsyncTask`) dan dicek
ulang ke server lewat tool `check_async_task`, sesuai sifat non-blocking-nya.
`[code]` dikutip `../systems/deepagents.md` §5.

**Kedalaman**: `deepagents` **tidak** punya penjaga kedalaman-maksimum
eksplisit — subagent tidak otomatis mewarisi kemampuan men-spawn
subagent-nya sendiri. Stack middleware default subagent
(`FilesystemMiddleware` + `SummarizationMiddleware` +
`PatchToolCallsMiddleware`, lalu custom `middleware` milik spec-nya) tidak
menyertakan `SubAgentMiddleware` kecuali spec subagent itu sendiri
menambahkannya secara eksplisit di `middleware=[...]` — nesting mungkin
tapi butuh opt-in sadar di tiap level, bukan default. `[code]` dikutip
`../systems/deepagents.md` §4, `deepagents/middleware/subagents.py`
(daftar field `SubAgent`, tidak ada field `subagents` bawaan). Satu-satunya
backstop terhadap kedalaman yang lari adalah `recursion_limit=9999` yang
**dibagi** seluruh pohon (parent + semua turunan) — bukan penghitung per-
cabang: komentar kode menyatakan config parent (termasuk `recursion_limit`)
diteruskan ke tiap subagent lewat `ensure_config` LangGraph yang menyeed
tiap run dari config ambien parent. `[code]`
`deepagents/middleware/subagents.py` baris 558-566, 586-594 (komentar
tentang propagasi `recursion_limit`/tag/metadata lewat merge per-key). Ini
persis pola "anggaran bersama lintas pohon" di `## Trade-off` di atas,
tanpa batas per-cabang yang berdampingan dengannya — proyek yang butuh
membedakan "cabang dalam tapi murah" dari "banyak cabang mahal" harus
membangun penghitung kedalaman sendiri (mis. lewat state kustom yang
diturunkan tiap kali `task` dipanggil), `deepagents` tidak menyediakannya.
`[inferred]` disimpulkan dari tidak ditemukannya parameter/field
depth-tracking di `SubAgent`/`SubAgentMiddleware`/`create_deep_agent` yang
dibaca Task 3 maupun task ini.

## Sumber

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §4
  Delegation, §5 State & resume (tiga jalur `SubAgent`/`CompiledSubAgent`/
  `AsyncSubAgent`, kontrak hasil `messages`→`ToolMessage`,
  `PrivateStateAttr`, `AsyncSubAgentState.tasks`) — tier-1 reference
  terverifikasi Task 3, dikutip tanpa membaca ulang
  `deepagents/middleware/subagents.py` inti kecuali baris spesifik di
  bawah.
- `[code]` `deepagents/middleware/subagents.py` baris 558-566, 586-594
  (paket `deepagents==0.7.8`, dibaca dari
  `references/recipes/.venv/lib/python3.13/site-packages/`, venv sama
  dengan `../systems/deepagents.md`) — komentar propagasi config
  (`recursion_limit`) parent→subagent lewat `ensure_config`, dasar klaim
  "anggaran bersama, bukan per-cabang" di `## Di deepagents`.
- `[code]` `deepagents/middleware/subagents.py` — definisi `class SubAgent`
  (field yang tersedia: `tools`/`model`/`middleware`/`interrupt_on`/
  `skills`/`permissions`/`response_format`, tidak ada field `subagents`
  bawaan), dasar klaim "nesting butuh opt-in eksplisit" di `## Di
  deepagents`.
- `[code]` [`agent-loop.md`](agent-loop.md) §Masalah — pola "siapa
  memutuskan" yang digeneralisasi ke sumbu kedalaman delegasi di file ini;
  ditulis dalam task yang sama, tidak diusulkan ulang di sini.
- `[code]` [`context-engineering.md`](context-engineering.md) — dirujuk
  untuk konsekuensi biaya context dari kontrak hasil "transkrip penuh".
