# Best practice teknis — ekstraksi dokumentasi resmi deepagents

Praktik yang **dinyatakan sendiri** oleh dokumentasi resmi
`docs.langchain.com/oss/python/deepagents/`, disarikan dari 40 halaman
snapshot di [`../upstream/deepagents-docs/`](../upstream/deepagents-docs/README.md).

## Cara membaca file ini

Tiap butir menyebut halaman dan baris di snapshot, jadi klaimnya bisa
dilacak ke kalimat aslinya. Tiga hal yang wajib dipegang saat memakainya:

- **Ini `[docs]`, bukan `[code]`.** Kalau source paket terpasang
  bertentangan dengan halaman dokumentasi, source yang menang. Di beberapa
  butir di bawah pertentangan itu sudah ditemukan dan ditandai.
- **Sebagian "Tip" adalah penempatan produk.** Dari 76 blok `<Tip>`/
  `<Warning>` yang dipanen, belasan di antaranya adalah ajakan memakai
  LangSmith (tracing, Deployments, Engine, Gateway, Sandboxes, Fleet).
  Itu bukan praktik rekayasa yang netral vendor — nasihat "pasang
  observability" tetap benar, tapi pilihan alatnya keputusanmu. Yang
  terkait produk dikumpulkan di §Baca dengan skeptis, tidak dicampur ke
  butir teknis.
- **Beberapa peringatan sudah basi.** Dokumentasi masih memuat catatan
  transisi dari versi lama; yang ketahuan disebut di tempatnya.

Butir yang menyangkut interpreter, PTC, dan dynamic subagent tidak
diulang di sini — semuanya di
[`../concepts/code-orchestration.md`](../concepts/code-orchestration.md).

## 1. Invokasi & multi-user

**Tiap invokasi membawa dua parameter run-level, dan keduanya
independen.** `thread_id` (lewat `config={"configurable": {...}}`)
menentukan **percakapan** — riwayat pesan dan checkpoint. `context`
membawa data **per-run** yang dibaca tool dan middleware: `user_id`,
API key, feature flag, metadata sesi; bentuknya dideklarasikan lewat
`context_schema` dan diakses lewat `runtime.context`. Mengubah salah
satunya tidak memengaruhi yang lain, dan keduanya hampir selalu dikirim
bersamaan. `[docs]` — `going-to-production.md` baris 67-69, 322-324.

Bagi pola multi-user berbasis `user_id`, ini pemisahan yang tepat:
identitas user **tidak** boleh diturunkan dari `thread_id`, karena satu
user bisa punya banyak thread dan `thread_id` datang dari klien.

**Tiga primitif menentukan apa yang terbagi**: Thread (satu percakapan;
riwayat dan file scratch tidak terbawa keluar), User (memori dan file
bisa privat atau terbagi; identitas dan otorisasi datang dari lapis auth
sendiri), Assistant (instance agent terkonfigurasi). `[docs]` —
`going-to-production.md` baris 15-17.

**Bangun async sejak awal.** Beban kerja LLM I/O-bound; tiga anjuran
konkret: tulis tool async native (LangChain menjalankan tool sync di
thread terpisah — bekerja, tapi menambah overhead threading), pakai hook
middleware async (`abefore_agent`, bukan `before_agent`), dan await
lifecycle resource eksternal (pembuatan sandbox, koneksi MCP server).
`[docs]` — `going-to-production.md` baris 387-397.

## 2. Backend & filesystem

**Pilih backend dari apa yang harus bertahan, bukan dari kemudahan.**
`StateBackend` (bawaan) = scratch per-thread, bertahan antar giliran lewat
checkpointer tapi tidak lintas thread — **di-checkpoint tiap langkah,
jadi hindari menulis file besar**. `StoreBackend` = lintas thread, wajib
di-scope lewat namespace factory. `CompositeBackend` = campuran, scratch
per-thread sebagai default dengan route lintas thread untuk path tertentu
seperti `/memories/`. `[docs]` — `going-to-production.md` baris 551-561.

**`FilesystemBackend` dan `LocalShellBackend` tidak boleh dipakai di agent
yang di-deploy.** Dokumentasi menyebutnya eksplisit sebagai
"inappropriate use cases: web servers or HTTP APIs" dan "production
environments (such as web servers, APIs, multi-tenant systems)".
`[docs]` — `backends.md` baris 207, 346; `going-to-production.md` baris
566.

Dua rincian yang menentukan apakah pengamanannya nyata:

- `virtual_mode=True` **wajib** dipasang bersama `root_dir` untuk
  mengaktifkan pembatasan path (memblokir `..`, `~`, dan path absolut di
  luar root). Bawaannya `virtual_mode=False` yang **tidak memberi
  keamanan sama sekali meski `root_dir` diset**. `[docs]` —
  `backends.md` baris 230.
- Pada `LocalShellBackend`, `virtual_mode=True` **tidak memberi keamanan
  apa pun**, karena perintah shell bisa menjangkau path mana pun di
  sistem. `[docs]` — `backends.md` baris 375.

Ini pola yang sama dengan temuan RLS-di-bawah-superuser di
[`../concepts/isolation-and-scoping.md`](../concepts/isolation-and-scoping.md):
kontrol yang terlihat aktif tapi prasyaratnya tidak terpenuhi.

**Bungkus `FilesystemBackend` dalam `CompositeBackend`** untuk hampir
semua kasus. Alasannya bukan gaya: deepagents menulis data internalnya
sendiri ke backend — hasil tool besar yang di-offload ke
`/large_tool_results/` dan riwayat percakapan ke `/conversation_history/`.
Dengan `FilesystemBackend` telanjang, semua itu mendarat di disk nyata di
bawah `root_dir`, bercampur dengan berkas project. Route `/workspace/` ke
`FilesystemBackend` dan biarkan sisanya di `StateBackend`. `[docs]` —
`backends.md` baris 322; `customization.md` baris 1947. Lihat
[`middleware.md`](middleware.md) §`artifacts_root` untuk mekanisme yang
menentukan ke mana prefix-prefix itu benar-benar menulis.

**Namespace `StoreBackend` sudah wajib, bukan lagi anjuran.**
Dokumentasi menulis "The `namespace` parameter will be **required** in
v0.5.0" (`[docs]` — `backends.md` baris 631) — peringatan transisi yang
sudah lewat. Di `deepagents==0.7.8` `namespace` adalah argumen
keyword-only **tanpa default**, jadi lupa mengisinya gagal saat
konstruksi, bukan diam-diam berbagi data. `[code]` —
`deepagents/backends/store.py` baris 99-104.

**Metode backend di luar graph run tidak berefek.** Memanggil
`state_backend.upload_files(...)` di luar eksekusi graph tidak berlaku
sampai graph berjalan. `[docs]` — `backends.md` baris 191.

**Pola backend factory sudah deprecated** sejak 0.5.0 — kirim instance
backend yang sudah dikonstruksi, bukan fungsi factory. `[docs]` —
`backends.md` baris 1075.

## 3. Konteks

**Kompresi konteks sudah menyala tanpa middleware tambahan.** Tiap
`create_deep_agent` sudah memuat offloading dan summarization; tidak perlu
memasang apa pun. `[docs]` — `context-engineering.md` baris 811.

Angka bawaannya perlu diketahui sebelum menyetel apa pun:

- Offload terjadi saat input **atau** hasil tool melewati **20.000
  token**. Hasil besar diganti path berkas plus preview 10 baris pertama;
  input besar dipangkas jadi pointer saat konteks sesi melewati **85%**
  jendela model. `[docs]` — `context-engineering.md` baris 831-841.
- Summarization terpicu di **85% `max_input_tokens`** dari profil model,
  menyisakan **10%** token sebagai konteks terkini, dan jatuh ke
  **170.000 token / 6 pesan** bila profil model tak tersedia. Bila
  panggilan model melempar `ContextOverflowError`, agent langsung jatuh ke
  summarization lalu mencoba ulang. `[docs]` —
  `context-engineering.md` baris 860-866.
- Summarization menulis dua hal: ringkasan terstruktur di konteks
  (intent sesi, artefak, langkah berikutnya) **dan** rendering teks
  percakapan asli ke filesystem sebagai catatan kanonik. `[docs]` —
  `context-engineering.md` baris 852-856.

**Pangkas skema tool sebelum kompresi apa pun berjalan.** Tool bawaan yang
tak terpakai tetap mengirim skema penuh **tiap giliran**. `excluded_tools`
di harness profile membuangnya dan mengecilkan baseline prompt untuk
seluruh run — ini konfigurasi, bukan kompresi otomatis, dan bekerja lebih
awal daripada keduanya. `[docs]` — `context-engineering.md` baris 315.

**Token summarization ikut terbawa saat streaming.** Saring lewat
metadata: `metadata.get("lc_source") == "summarization"`. Tanpa itu,
ringkasan internal muncul di UI sebagai jawaban asisten. `[docs]` —
`context-engineering.md` baris 869-881.

**Keluaran tool biner disimpan ke backend, bukan dikembalikan utuh.**
Saat tool menghasilkan gambar atau data biner besar, simpan artefaknya ke
backend lalu kembalikan deskripsi teks singkat plus path/URL. Kompresi
bawaan **tidak** mengecilkan gambar atau menurunkan resolusinya, jadi
media yang masuk konteks tetap di sana seukuran aslinya. `[docs]` —
`multimodal.md` baris 64; `context-engineering.md` baris 844-846.

**Enam praktik yang dirangkum dokumentasi sendiri**: mulai dari input
context yang benar (memori minimal untuk konvensi yang selalu relevan,
skill terfokus untuk kapabilitas per-tugas); delegasikan kerja berat ke
subagent; kalau saat debugging terlihat subagent menghasilkan output
panjang, tambahkan arahan meringkas di `system_prompt`-nya; pakai
filesystem untuk output besar; dokumentasikan struktur memori jangka
panjang kepada agent; kirim metadata user/API key/konfigurasi statis lewat
`context`. `[docs]` — `context-engineering.md` baris 1210-1216.

## 4. Delegasi & subagent

**Kontrak hasil diatur lewat `system_prompt` subagent, dan itu memang
satu-satunya tuas.** Anjuran eksplisitnya: instruksikan subagent
mengembalikan ringkasan, bukan data mentah — contoh dokumentasi memakai
"Return only the essential summary (under 500 words). Do NOT include raw
search results or detailed tool outputs." `[docs]` —
`context-engineering.md` baris 1024-1036. Ini sisi praktis dari kontrak
hasil di [`../concepts/delegation.md`](../concepts/delegation.md).

**Untuk data besar, subagent menulis ke file dan induk membaca
seperlunya** — bukan mengembalikannya lewat pesan. `[docs]` —
`context-engineering.md` baris 1040.

**Menjalankan agent tanpa tool `task`** butuh dua hal sekaligus:
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`
**dan** tidak mengirim subagent sinkron lewat `subagents=`.
`SubAgentMiddleware` hanya terpasang kalau ada minimal satu subagent
sinkron. Async subagent tidak terpengaruh. `[docs]` — `profiles.md`
baris 68; `subagents.md` baris 71.

**Jangan pakai `excluded_middleware` untuk itu.** Mendaftarkan
`FilesystemMiddleware`, `SubAgentMiddleware`, atau middleware permission
internal di `excluded_middleware` melempar `ValueError` — semuanya
scaffolding wajib. Untuk menyembunyikan tool-nya dari model tanpa
membuang middleware-nya, pakai `excluded_tools`. `[docs]` —
`profiles.md` baris 68; `subagents.md` baris 71. Mekanisme penegakannya
ada di [`middleware.md`](middleware.md) §Exclusion.

## 5. Skills

Halaman ini relevan dua kali: sebagai cara memberi kapabilitas ke agent,
dan sebagai spesifikasi yang KB ini sendiri patuhi.

**Dua lapis, dua anggaran.** Frontmatter tiap skill masuk ke system prompt
saat discovery; body-nya baru dibaca saat aktivasi. Karena itu: frontmatter
ringkas, body `SKILL.md` **di bawah 5.000 token**, dan spesifikasi Agent
Skills menganjurkan `SKILL.md` **di bawah 500 baris**. Menjaga keduanya
kecil membuat banyak skill bisa dimuat tanpa menyesaki jendela konteks.
`[docs]` — `skills.md` baris 197, 214.

**`description` adalah satu-satunya informasi yang dilihat agent saat
memilih.** Ia harus menyatakan **apa** yang skill lakukan **dan kapan**
mengaktifkannya, dengan kata kunci yang bisa dicocokkan. "Helps with
PDFs." disebut dokumentasi sebagai contoh yang terlalu kabur untuk
pencocokan yang andal. `[docs]` — `skills.md` baris 199-212.

**Sedikit skill yang ter-scope baik mengalahkan banyak yang tumpang
tindih.** Deskripsi yang beririsan membuat agent mengaktifkan skill yang
salah atau ragu di antara pilihan; kalau dua skill tujuannya mirip,
gabungkan. Semakin banyak skill berdeskripsi mirip, semakin turun
kemampuan agent memilih yang benar. `[docs]` — `skills.md` baris 212,
239-243.

**Rujukan berkas satu tingkat dari `SKILL.md`.** Rantai rujukan bersarang
dalam memaksa agent melakukan beberapa kali baca sebelum sampai ke
informasinya. Agent **tidak** menemukan berkas pendukung sendiri —
`SKILL.md` harus menyatakan isi tiap berkas dan kapan dipakai. `[docs]` —
`skills.md` baris 230, 1776.

**Tiga kegagalan diam yang perlu dicek saat skill tidak aktif**:
`SKILL.md` di atas **10 MB** dilewati saat discovery tanpa error;
`name` di frontmatter wajib sama dengan nama direktori induk; dan bila
nama skill yang sama muncul di beberapa sumber, **sumber terakhir yang
menang** — skill lama atau kosong dari path belakangan bisa menimpa yang
dimaksud. `[docs]` — `skills.md` baris 1841, 1766-1768.

**Skill tidak otomatis ada di dalam sandbox.** Berkas skill di luar
kontainer tidak tersedia sampai disalin masuk. `[docs]` — `skills.md`
baris 1780.

## 6. Memory

**Bawaannya scope user.** Tabel scope-nya: `(user_id)` untuk preferensi
dan konteks per-user (disebut "recommended default"), `(assistant_id)`
untuk instruksi bersama satu assistant, `(org_id)` untuk kebijakan
read-only lintas semua user. `[docs]` — `going-to-production.md` baris
425-429.

**Memori bersama adalah vektor prompt injection.** Kalau satu user bisa
menulis ke memori yang dibaca percakapan user lain, user jahat bisa
menyuntikkan instruksi ke state bersama. Mitigasinya berlapis: default ke
scope user; jadikan kebijakan bersama **read-only** dan isi lewat kode
aplikasi (bukan oleh agent); pasang approval manusia sebelum agent menulis
ke path sensitif; tegakkan lewat `permissions` (deklaratif) atau backend
policy hook (logika kustom). `[docs]` — `going-to-production.md` baris
431-433; `memory.md` baris 473-486.

**Tulis bersamaan ke berkas yang sama = last-write-wins.** Jarang jadi
masalah untuk memori scope-user (satu user biasanya satu percakapan
aktif), tapi nyata untuk scope assistant/organisasi. Mitigasinya:
serialisasi lewat konsolidasi background, atau pecah memori jadi berkas
terpisah per topik untuk mengurangi kontensi. `[docs]` — `memory.md`
baris 488-492.

**Beberapa agent dalam satu deployment** dipisah dengan menambahkan
`assistant_id` ke namespace, mis.
`namespace=lambda rt: (rt.server_info.assistant_id, rt.server_info.user.identity)`.
`[docs]` — `memory.md` baris 494-508.

**Konsolidasi terjadwal wajib sinkron dengan jendela lookback-nya.**
Kalau cron berjalan lebih sering daripada lookback, percakapan yang sama
diproses ulang; kalau lebih jarang, memori yang jatuh di luar jendela
hilang. `[docs]` — `memory.md` baris 466.

## 7. Permissions

**Evaluasinya first-match-wins, dan bila tidak ada aturan yang cocok
panggilan itu DIIZINKAN.** Default permisif ini menentukan bentuk daftar
aturannya: aturan spesifik lebih dulu, penutup `deny` di `/**` paling
akhir. Dokumentasi menyertakan contoh salah yang persis jadi bug —
`/workspace/**` mode allow ditaruh sebelum `/workspace/.env` mode deny,
sehingga deny-nya tak pernah tercapai. `[docs]` — `permissions.md` baris
53, 193-236.

Dalam kerangka [`../concepts/guardrails.md`](../concepts/guardrails.md),
default tanpa penutup adalah **fail-open**.

**Cakupan `operations` tidak seintuitif namanya**: `"read"` mencakup `ls`,
`read_file`, `glob`, `grep`; `"write"` mencakup `write_file`, `edit_file`,
`delete`. `[docs]` — `permissions.md` baris 49-51.

**Pola `interrupt` harus dijangkar dengan segmen literal di depan**
(mis. `/secrets/**`, bukan `/**/secrets`). Tool massal (`ls`, `glob`,
`grep`, dan `delete` pada direktori) memicu interrupt kalau subtree
pencariannya **bisa** beririsan dengan prefix aturan, jadi pola tanpa
jangkar over-fire secara konservatif. `[docs]` — `permissions.md` baris
91.

**Subagent mewarisi permission induk; mengisi `permissions` di spec-nya
MENGGANTI seluruh aturan induk**, bukan menambah. `[docs]` —
`permissions.md` baris 239.

**Dengan `CompositeBackend` bawaan sandbox, tiap path permission wajib
berada di bawah prefix route yang dikenal** — di luar itu melempar
`NotImplementedError`, termasuk `/**` yang mencakup semua route. Alasannya
prinsipil: sandbox mengizinkan eksekusi perintah sembarang, jadi
pembatasan berbasis path saja tidak bisa mencegah akses filesystem lewat
shell. `[docs]` — `permissions.md` baris 286, 316-340.

**Pilih alat yang tepat**: `permissions` untuk aturan allow/deny berbasis
path pada tool filesystem bawaan; backend policy hook saat butuh logika
validasi kustom (rate limiting, audit logging, inspeksi konten) atau saat
perlu mengendalikan tool kustom. `[docs]` — `permissions.md` baris 18.

## 8. Human-in-the-loop

**Checkpointer wajib.** HITL butuh state yang bertahan antara interrupt
dan resume; tanpa checkpointer polanya tidak bisa jalan. `[docs]` —
`human-in-the-loop.md` baris 880-895.

**Resume memakai config dan `thread_id` yang sama.** `[docs]` —
`human-in-the-loop.md` baris 896-907.

**Urutan `decisions` harus sama persis dengan urutan `action_requests`** —
satu keputusan per aksi, berurutan. `[docs]` — `human-in-the-loop.md`
baris 909-929.

**Sesuaikan konfigurasi dengan tingkat risiko**, jangan seragam: risiko
tinggi dapat `["approve", "edit", "reject"]` penuh, risiko menengah tanpa
`edit`, risiko rendah `False` (tanpa interrupt sama sekali). `[docs]` —
`human-in-the-loop.md` baris 931-949.

**Sunting argumen tool secara konservatif.** Modifikasi besar pada argumen
asli bisa membuat model menilai ulang pendekatannya dan berpotensi
menjalankan tool berkali-kali atau mengambil aksi tak terduga. `[docs]` —
`human-in-the-loop.md` baris 334.

## 9. Fault tolerance & anggaran

**Taksonomi error berdasarkan siapa yang memperbaikinya** — ini tabel
paling bisa dipakai ulang di seluruh dokumentasi, dan langsung memetakan
ke mode kegagalan di blueprint:

| Jenis error | Yang memperbaiki | Strategi | Mekanisme |
|---|---|---|---|
| Transient (jaringan, rate limit) | Sistem, otomatis | Retry dengan exponential backoff | `ModelRetryMiddleware`, `ToolRetryMiddleware` |
| Bisa dipulihkan LLM (tool gagal, parsing) | LLM | Ubah jadi `ToolMessage` error, biarkan model menyesuaikan | `ToolErrorMiddleware` |
| Butuh manusia (informasi kurang, instruksi tak jelas) | Manusia | Jeda dengan `interrupt()` | `interrupt_on` |
| Provider tumbang | Sistem, otomatis | Pindah ke model alternatif | `ModelFallbackMiddleware` |
| Panggilan berlebih (loop lari) | Sistem, otomatis | Batasi panggilan model & tool per run | `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware` |
| Tak terduga | Developer | **Biarkan naik** | tanpa middleware |

`[docs]` — `fault-tolerance.md` baris 15-22.

Baris terakhir yang paling sering dilanggar: "Do not catch what you cannot
handle." `ToolErrorMiddleware` hanya memunculkan exception yang secara
eksplisit kamu kembalikan isinya; sisanya merambat naik dan menghentikan
run — itu perilaku yang diinginkan. `[docs]` — `fault-tolerance.md`
baris 130-138.

**Batasi retry ke tool yang memang diuntungkan olehnya.** `read_file`
yang gagal tidak akan tertolong oleh retry; web search yang timeout
kemungkinan besar iya. Karena itu `ToolRetryMiddleware` menerima daftar
`tools=[...]` dan `retry_on=(...)`. `[docs]` — `fault-tolerance.md`
baris 212.

**Dua anggaran yang berbeda, keduanya perlu.** `run_limit` membatasi per
satu invokasi (reset tiap giliran); `thread_limit` membatasi lintas
seluruh percakapan dan **butuh checkpointer**. `[docs]` —
`fault-tolerance.md` baris 187. Ini persis pembedaan yang dibahas
[`../concepts/cost-control.md`](../concepts/cost-control.md).

**Rate limit provider diatur di model, bukan di middleware** — lewat
`rate_limiter=InMemoryRateLimiter(...)` saat `init_chat_model`. Perhatikan
namanya: **in-memory**, jadi pada deployment banyak proses tiap proses
punya bucket sendiri dan batas efektifnya berlipat sejumlah proses.
`[docs]` — `fault-tolerance.md` baris 148-166; catatan tentang implikasi
banyak-proses `[inferred]` dari nama dan sifat kelasnya, belum diuji.

**Exception integrasi membawa flag `is_retryable`** yang dihormati
middleware retry secara bawaan (`ModelAuthenticationError`,
`ModelRateLimitError`, `ModelTimeoutError`, dll). `[docs]` —
`fault-tolerance.md` baris 215.

## 10. Middleware kustom

**Jangan memutasi atribut instance setelah inisialisasi.** Ini peringatan
paling operasional di seluruh dokumentasi untuk pola server multi-user:
`self.x += 1` di dalam hook menyebabkan race condition, karena banyak
operasi berjalan bersamaan — subagent, tool paralel, dan invokasi paralel
di thread berbeda. Untuk melacak nilai lintas invokasi hook, pakai **graph
state**, yang memang di-scope per-thread secara desain. `[docs]` —
`customization.md` baris 1480-1516.

Konsekuensinya untuk penerapan: satu instance middleware **dipakai
bersama** lintas percakapan dan lintas user. Semua state per-user harus
hidup di graph state atau di-key oleh `thread_id`, tidak pernah sebagai
atribut. Bentuk kegagalan yang sama muncul di `CodeInterpreterMiddleware`
(lihat [`../concepts/code-orchestration.md`](../concepts/code-orchestration.md)
§Isolasi per-user).

## 11. Sandbox & rahasia

**Jangan pernah menaruh rahasia di dalam sandbox.** API key, token,
kredensial database — apa pun yang disuntikkan lewat environment variable,
berkas ter-mount, atau opsi `secrets` bisa dibaca dan dieksfiltrasi oleh
agent yang konteksnya disuntik. Berlaku **juga** untuk kredensial
berumur pendek atau ber-scope sempit: kalau agent bisa mengaksesnya,
penyerang juga. `[docs]` — `sandboxes.md` baris 2080;
`going-to-production.md` baris 861.

Kalau tetap terpaksa, dokumentasi menyebutnya "remains an unsafe
workaround" dan menuntut empat hal sekaligus: HITL untuk **semua**
panggilan tool (bukan hanya yang sensitif), blokir/batasi akses jaringan
dari sandbox, kredensial ber-scope sesempit dan seumur sependek mungkin,
serta pemantauan trafik keluar. `[docs]` — `sandboxes.md` baris 2092.
Jalur yang dianjurkan justru menjaga rahasia **tak pernah masuk**:
proxy auth yang menyuntikkan kredensial ke request keluar.

**Sandbox ber-scope assistant menumpuk state.** Berkas, paket terpasang,
dan state lain tumbuh tanpa batas. Konfigurasikan TTL di penyedia
sandbox, pakai snapshot untuk reset berkala, atau bangun logika cleanup.
`[docs]` — `sandboxes.md` baris 709, 929; `going-to-production.md`
baris 652.

## 12. Streaming & observability

**Untuk aplikasi baru, pakai event streaming**, bukan percabangan
`stream_mode`. API proyeksi bertipe yang masuk di Deep Agents v0.6 memberi
iterator terpisah per proyeksi (subagent, message, tool call, value) yang
bisa dikonsumsi independen. `[docs]` — `streaming.md` baris 10.

**Audit tulisan agent ke memori lewat trace**: tiap penulisan berkas
muncul sebagai tool call. `[docs]` — `memory.md` baris 510. Klaimnya
netral vendor meski contohnya LangSmith — yang penting: penulisan memori
teramati sebagai tool call, apa pun backend trace-nya.

## 13. Migrasi & kompatibilitas versi

**Rollback dari v0.6.0 tidak didukung setelah thread ter-persist.**
v0.6.0 memindahkan riwayat pesan dan berkas agent ke `DeltaChannel`, yang
menulis checkpoint dalam format yang versi sebelumnya tidak bisa baca.
Menurunkan versi mengembalikan channel ke non-delta dan membuat checkpoint
delta yang ada tak terbaca — hasilnya rekonstruksi state yang tidak
lengkap atau salah. Prinsip umumnya: **jangan pernah memindahkan channel
ter-persist antara representasi delta dan non-delta.** `[docs]` —
`changelog-py.md` baris 78.

Untuk sistem dengan percakapan berumur panjang, ini berarti upgrade
deepagents lintas 0.6.0 adalah operasi satu arah yang butuh rencana
migrasi atau pembuangan thread — bukan sekadar bump versi.

## Baca dengan skeptis

Butir-butir berikut muncul sebagai "Tip" di dokumentasi tapi merupakan
anjuran produk, bukan praktik rekayasa netral. Prinsip di baliknya sering
benar; pilihan alatnya tetap keputusanmu:

- Tracing/observability lewat LangSmith — muncul di sedikitnya sembilan
  halaman (`backends.md:25`, `customization.md:143`, `overview.md:178`,
  `subagents.md:1007`, `sandboxes.md:687`, `mcp.md:70`, `memory.md:510`,
  `rag.md:272`, `going-to-production.md:36`), beberapa disertai anjuran
  memasang LangSmith Engine. **Prinsipnya benar** (harness tanpa trace
  tidak bisa didiagnosis, lihat
  [`../concepts/observability.md`](../concepts/observability.md));
  implementasinya tidak harus vendor ini.
- Checkpointer, auth, RBAC, cron, dan webhook diuraikan terutama sebagai
  fitur LangSmith Deployments (`going-to-production.md` baris 327-368,
  412). Untuk deployment sendiri di VM/K8s, yang terpakai adalah
  primitifnya (`thread_id`, `context`, checkpointer LangGraph,
  namespace store), bukan platformnya.
- Sandbox terkelola, LLM gateway, dan Fleet (`sandboxes.md:687`,
  `quickstart.md:111`, `comparison.md:65`) — sepenuhnya penawaran produk.

Selain itu, dua peringatan di dokumentasi sudah tertinggal dari kodenya:
`namespace` "will be required in v0.5.0" (sudah wajib di 0.7.8, §2 di
atas), dan syarat versi `langchain-quickjs>=0.2.0` (paketnya sendiri
menuntut `>=0.3.5`, lihat
[`../concepts/code-orchestration.md`](../concepts/code-orchestration.md)).

## Sumber

- `[docs]` [`../upstream/deepagents-docs/`](../upstream/deepagents-docs/README.md)
  — snapshot verbatim 40 halaman, diambil 2026-08-26 dari
  `docs.langchain.com/oss/python/deepagents/`. Semua nomor baris di file
  ini merujuk ke snapshot itu, bukan ke halaman web yang bisa berubah.
  Halaman yang paling banyak dipakai: `going-to-production.md`,
  `fault-tolerance.md`, `context-engineering.md`, `backends.md`,
  `permissions.md`, `skills.md`, `memory.md`, `human-in-the-loop.md`,
  `sandboxes.md`, `customization.md`, `changelog-py.md`.
- `[code]` `deepagents/backends/store.py` baris 99-104 (paket
  `deepagents==0.7.8`, venv `../recipes/.venv/lib/python3.13/site-packages/`)
  — `namespace` sebagai argumen keyword-only tanpa default, dasar koreksi
  atas peringatan "will be required in v0.5.0".
- `[code]` [`middleware.md`](middleware.md) §`artifacts_root`, §Exclusion
  — mekanisme di balik anjuran `CompositeBackend` dan penolakan
  `excluded_middleware`; dirujuk tanpa membaca ulang source-nya.
- `[inferred]` Satu klaim ditandai di tempatnya: implikasi banyak-proses
  dari `InMemoryRateLimiter`, disimpulkan dari nama dan sifat kelasnya,
  belum diuji.
