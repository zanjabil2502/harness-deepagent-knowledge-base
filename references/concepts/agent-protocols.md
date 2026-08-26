# Protokol agent (ACP, A2A) — harness sebagai endpoint

## Masalah

Hampir semua keputusan harness dibuat dengan satu pemanggil dalam bayangan:
manusia, lewat UI yang kita bangun sendiri. Begitu ada **pihak lain** yang
memanggil agent — editor kode, agent lain, penjadwal — empat hal yang
selama ini implisit berubah jadi kontrak yang harus dinyatakan:

- **Identitas** — siapa yang bertanya, dan atas wewenang siapa. Di UI
  sendiri jawabannya datang dari sesi login. Di protokol, tidak ada
  yang membawakannya kecuali kita yang memasangnya.
- **Kontinuitas sesi** — apa yang mengelompokkan giliran jadi satu
  percakapan. Tiap protokol punya identifier sendiri, dan hampir selalu
  **dua**, bukan satu: satu untuk percakapan, satu untuk permintaan.
  Memetakannya salah ke `thread_id` internal membuat riwayat pecah atau
  justru tercampur antar penelepon.
- **Gerbang** — di mana approval terjadi, dan **bentuk approval apa yang
  bisa dirender pemanggil**. Ini yang paling sering terlewat: harness bisa
  saja memasang jeda yang benar, tapi kalau pemanggil tidak punya cara
  menampilkannya, jeda itu jadi kebuntuan, bukan gerbang.
- **Permukaan kapabilitas** — siapa yang memutuskan tool apa yang ada.
  Pada sebagian protokol, jawabannya bukan penulis agent melainkan
  **klien**.

Salah di empat hal ini bukan bug yang ketahuan saat tes. Protokol
membekukan bentuknya, jadi keputusan yang keliru tidak bisa ditambal
belakangan tanpa memutus kompatibilitas dengan semua yang sudah terhubung.

Masalah kedua lebih senyap: **endpoint yang ada karena bawaan.** Platform
yang menyalakan permukaan protokol secara default membuat "siapa yang boleh
memanggil agent ini" jadi keputusan yang tak pernah diambil siapa pun.

## Pola

### Tiga arah, bukan tiga protokol

Yang membedakan protokol-protokol ini bukan fiturnya, melainkan **ke mana
panah panggilan menunjuk**. Sekali arahnya jelas, sisa keputusannya
mengikuti:

| | Agent **mengonsumsi** | Agent **dikemudikan** | Agent **dipanggil** |
|---|---|---|---|
| Contoh | MCP | ACP | A2A |
| Lawan bicara | server tool | editor/IDE seorang manusia | agent lain (mesin) |
| Transport lazim | stdio / HTTP | **stdio**, subprocess milik editor | HTTP, JSON-RPC |
| Identitas | milik kita, ke server | manusia yang menjalankan editor | **tidak ada bawaan** |
| Sesi | koneksi server | sesi editor, satu proses | id percakapan + id tugas |
| Gerbang | kita yang pasang | dirender editor, bentuknya terbatas | tak ada gerbang manusia |
| Siapa memilih tool | penulis agent | **sebagian klien** | penulis agent |

[`mcp.md`](mcp.md) sudah menutup kolom pertama. Dua kolom sisanya adalah
isi file ini, dan keduanya membalik asumsi yang dipakai kolom pertama.

### Identitas tidak datang dari protokol

Tidak satu pun dari ketiganya membawa identitas end-user sebagai bagian
protokol. Konsekuensinya berbeda per arah:

- **Dikemudikan editor** — proses agent dijalankan oleh manusia itu
  sendiri, di mesinnya, dengan hak aksesnya. Identitas implisit dan
  benar, tapi juga berarti blast radius-nya adalah blast radius orang
  itu: tidak ada lapisan yang membatasi agent lebih sempit dari
  penggunanya kecuali kita yang memasangnya.
- **Dipanggil agent lain** — tidak ada manusia sama sekali. Yang datang
  cuma permintaan HTTP. Otentikasi, otorisasi, dan atribusi **wajib**
  dibangun di lapis transport, dan pertanyaan "atas nama user yang mana
  agent ini bertindak" tidak punya jawaban bawaan. Untuk pola multi-user
  berbasis `user_id`, ini berarti endpoint agent-ke-agent tidak boleh
  mewarisi jalur otorisasi yang dipakai UI — ia butuh jalurnya sendiri.

### Kontinuitas selalu dua identifier

Protokol agent membedakan **percakapan** dari **permintaan**, dan harness
biasanya cuma punya satu konsep (`thread_id`). Pemetaannya harus
diputuskan sengaja: id percakapan → `thread_id`, id permintaan → satu run
di dalam thread itu. Menyamakan keduanya membuat tiap permintaan jadi
percakapan baru (riwayat hilang) atau seluruh penelepon berbagi satu
thread (riwayat tercampur — dan pada sistem multi-user itu kebocoran
data, bukan sekadar kekacauan tampilan).

Pihak yang memulai percakapan biasanya **menghilangkan** id-nya di
permintaan pertama dan menerima id yang di-generate server, lalu
mengembalikannya di tiap giliran berikutnya. Artinya server yang
memegang otoritas atas id, dan klien yang bertanggung jawab
membawanya — dua peran yang harus jelas sebelum ada yang menulis kode.

### Gerbang dibatasi oleh yang bisa dirender pemanggil

Ini pembalikan yang paling penting. Biasanya harness yang memutuskan
bentuk approval-nya. Saat dikemudikan protokol, **protokol yang
memutuskan**, dan harness harus menyesuaikan.

Protokol editor umumnya hanya mengenal himpunan keputusan tetap —
setujui, tolak, sunting — yang terikat ke satu tool call. Jeda berbentuk
bebas ("agent bertanya sesuatu dan menunggu jawaban prosa") tidak punya
representasi. Konsekuensi desainnya: **semua titik henti harus berbentuk
approval terstruktur atas tool call**, bukan dialog. Kalau alurnya
benar-benar butuh bertanya, itu harus jadi tool dengan skema, bukan
`interrupt` bebas.

Sebaliknya pada arah agent-ke-agent tidak ada manusia sama sekali. Semua
gerbang harus otomatis — kebijakan, batas, validasi — karena tidak ada
yang akan menekan tombol.

### Permukaan kapabilitas bisa datang dari pemanggil

Pada integrasi editor, klien lazim menyuntikkan server tool-nya sendiri
saat membuka sesi. Artinya daftar tool efektif = tool yang kita daftarkan
**plus** apa pun yang editor bawa, dan penulis agent tidak mengendalikan
bagian kedua. Semua penalaran soal permukaan tool di
[`tool-design.md`](tool-design.md) dan soal exclusion di
[`../deepagents/middleware.md`](../deepagents/middleware.md) berlaku atas
himpunan yang baru diketahui saat runtime.

### Advertensi kapabilitas adalah pengungkapan

Arah agent-ke-agent biasanya menyertakan mekanisme penemuan: dokumen
publik yang menyebutkan nama, deskripsi, dan **daftar kemampuan** agent
supaya pihak lain tahu cara memanggilnya. Itu memang gunanya — tapi
sekaligus berarti struktur internal harness jadi metadata yang bisa
diambil siapa saja yang bisa menjangkau endpoint-nya. Nama skill yang
menyebut sistem internal, atau deskripsi yang membocorkan proses bisnis,
ikut terbit di sana.

### Endpoint bawaan adalah keputusan yang tak pernah diambil

Kalau platform menyalakan permukaan protokol secara default, gerbang
pertama bukan approval melainkan **apakah endpoint itu ada sama sekali**.
Ini masuk ke inventaris [`guardrails.md`](guardrails.md) sebagai titik
penegakan tersendiri dengan mode kegagalan **fail-open**: tidak ada yang
salah, tidak ada yang error, hanya permukaan yang terbuka karena tidak ada
yang menutupnya.

## Trade-off

- **Satu proses per sesi vs satu server banyak sesi.** Model subprocess
  (editor menjalankan agent sebagai anak proses, bicara lewat stdio)
  memberi isolasi paling kuat yang bisa didapat gratis: tiap sesi punya
  memori sendiri, tidak ada state bersama, tidak ada permukaan jaringan.
  Ongkosnya: tidak ada yang bertahan melewati proses kecuali sengaja
  dibuat bertahan, tidak ada skala horizontal, dan tidak ada tempat untuk
  kebijakan terpusat. Model server HTTP kebalikannya di setiap sumbu —
  termasuk kebalikannya soal isolasi, yang jadi urusan kita.
- **Kontinuitas milik protokol vs milik kita.** Memakai id sesi protokol
  langsung sebagai kunci penyimpanan itu paling sederhana dan langsung
  salah pada sistem multi-user: id itu datang dari klien, jadi ia
  mengidentifikasi percakapan, bukan pemiliknya. Memetakannya ke id
  internal menambah satu tabel dan satu langkah, tapi memisahkan "siapa"
  dari "percakapan mana" — pemisahan yang sama yang dituntut
  [`isolation-and-scoping.md`](isolation-and-scoping.md).
- **Interop vs subset yang benar-benar terpasang.** Sama seperti
  peringatan di `mcp.md` §"Klien nyata mengimplementasikan subset
  spesifikasi": mendukung sebuah protokol tidak berarti tiap klien
  mendukung tiap fiturnya. Fitur yang dipakai harness harus dibatasi ke
  irisan yang benar-benar dirender klien target, dan itu diketahui dengan
  mencoba, bukan dengan membaca spesifikasi.
- **Terbuka untuk dipanggil vs permukaan serangan.** Endpoint
  agent-ke-agent adalah cara paling langsung mengubah agent jadi
  komponen yang bisa dipakai ulang, sekaligus cara paling langsung
  mengekspos seluruh kapabilitasnya ke apa pun yang bisa mengirim HTTP.
  Nilainya nyata; keputusannya harus sadar.

## Di deepagents

**Keduanya di luar paket `deepagents`, dan keduanya berbeda jenis.** ACP
adalah paket pendamping yang membungkus agent; A2A bukan fitur library
sama sekali melainkan endpoint milik server deployment.

### ACP — `deepagents-acp`

Paket terpisah `deepagents-acp`, versi terbaru **0.0.10** — nomor 0.0.x
yang perlu dibaca apa adanya. Dependensinya: `agent-client-protocol>=0.10.1`
dan **`deepagents` tanpa batas versi sama sekali** (`[code]` — metadata
PyPI `deepagents-acp` 0.0.10). Tanpa constraint, resolusi bisa menarik
versi deepagents mana pun; pada venv uji, ia menarik 0.7.9 sementara KB ini
pin 0.7.8. Pin sendiri kalau dipakai serius.

Bentuk pemakaiannya: `AgentServerACP(agent)` lalu `await run_agent(server)`,
berjalan **stdio** sebagai subprocess yang diluncurkan editor. `[docs]` —
`../upstream/deepagents-docs/acp.md` baris 32, 54-55. Klien yang disebut:
Zed, JetBrains, VS Code lewat ekstensi, Neovim. `[docs]` — `acp.md` baris
226-229.

Yang tidak terbaca dari dokumentasi, dan menentukan desain:

- **Agent boleh berupa factory, dan itu bukan detail.**
  `AgentServerACP` menerima `CompiledStateGraph` **atau**
  `Callable[[AgentSessionContext], CompiledStateGraph]`, di mana
  `AgentSessionContext` membawa `cwd`, `mode`, dan `model`. Ini jalur
  satu-satunya untuk membangun harness berbeda per sesi editor —
  direktori kerja berbeda, postur izin berbeda, model berbeda. Parameter
  `modes=` dan `models=` **hanya sah bila agent berupa factory**;
  mengirimnya bersama graph terkompilasi melempar `ValueError`.
  `[code]` — `deepagents_acp/server.py:156-206`.
- **Postur izin adalah opsi sesi yang diubah manusia dari UI editor**,
  bukan konstanta konfigurasi: mode dirender sebagai selector dengan
  deskripsi "Controls how the agent requests permission". `[code]` —
  `server.py:222-257`. Ini [`policy-as-data.md`](policy-as-data.md) yang
  muncul di permukaan antarmuka.
- **ACP menolak `interrupt()` berbentuk bebas.** Kalau agent memunculkan
  interrupt yang nilainya bukan `dict` ber-`action_requests`, server
  melempar `RequestError(-32600)` dengan pesan yang menyebutnya "ACP
  limitation… ACP only supports human-in-the-loop permission prompts with
  a fixed set of decisions (approve/reject/edit)". `[code]` —
  `server.py:972-994`. Inilah wujud konkret §"Gerbang dibatasi oleh yang
  bisa dirender pemanggil": HITL bergaya `HumanInTheLoopMiddleware` jalan,
  dialog bebas tidak.
- **"Selalu izinkan" berbutir jenis perintah, dan hanya seumur proses.**
  Opsi approval yang ditawarkan: `allow_once`, `reject_once`, dan
  `approve_always` yang — untuk tool `execute` — mengingat **jenis
  perintah** yang diekstrak dari command, bukan command persisnya.
  Ingatannya disimpan di `_allowed_command_types[session_id]`, sebuah
  dict di memori proses. `[code]` — `server.py:214-216, 1150-1215`.
  Artinya keputusan "selalu izinkan `git`" hilang saat editor menutup
  agent, dan tidak pernah tersimpan di mana pun yang bisa diaudit.
- **`write_todos` di-auto-approve** bila merupakan pembaruan atas plan
  yang sudah ada, dan plan-nya dirender ke panel plan editor. `[code]` —
  `server.py:489-541, 1118-1120, 1160-1170`.
- **Sesi durable bersifat opt-in dan bukan bawaan.** `load_sessions=False`
  secara default; menyalakannya mengiklankan `session/load` ke klien dan
  **mensyaratkan checkpointer yang bertahan melewati restart server** —
  sementara semua contoh dokumentasi memakai `MemorySaver()`. `[code]` —
  `server.py:169-192, 286-302`; `[docs]` — `acp.md` baris 40, 51.
- **Semua state sesi ada di memori proses**: `_session_cwds`,
  `_session_mcp_servers`, `_session_modes`, `_session_models`,
  `_session_plans`, `_allowed_command_types` — semuanya dict biasa di-key
  `session_id`. `[code]` — `server.py:207-216`. Konsisten dengan model
  satu-proses-per-editor, dan tidak bisa dipindahkan ke topologi banyak
  proses tanpa mengganti lapisan ini.
- **Klien menyuntikkan server MCP-nya sendiri** lewat
  `new_session(mcp_servers=...)`. `[code]` — `server.py:304-315`.
  Permukaan tool efektif karena itu baru diketahui saat sesi dibuka.
- Satu subtilitas konkurensi yang dicatat source: checkpoint yang
  mendasari sebuah update **belum tentu terlihat** sampai iterator stream
  ditutup, jadi membaca state di dalam iterator bisa mengembalikan
  snapshot pra-interrupt yang basi. `[code]` — `server.py:996-1000`.

### A2A — bukan deepagents, melainkan Agent Server

Halaman A2A di bawah seksi deepagents sebenarnya dokumen LangSmith
(sumbernya `src/langsmith/server-a2a.mdx`). Yang mengimplementasikan
protokolnya adalah **Agent Server / `langgraph-api>=0.4.21`**, di endpoint
`/a2a/{assistant_id}`. `[docs]` — `../upstream/deepagents-docs/a2a.md`
baris 9-11, 35, 445.

- **Endpointnya menyala secara bawaan.** Cara mematikannya adalah menulis
  `{"http": {"disable_a2a": true}}` di `langgraph.json`. `[docs]` —
  `a2a.md` baris 426-435. Inilah §"Endpoint bawaan adalah keputusan yang
  tak pernah diambil" dalam bentuk konkret: deploy dengan Agent Server dan
  agent bisa dipanggil agent lain kecuali ada yang sengaja menutupnya.
- **Penemuan kapabilitas bersifat publik**:
  `GET /.well-known/agent-card.json?assistant_id={id}` mengembalikan nama,
  deskripsi, **daftar skill**, mode input/output, dan URL endpoint.
  `[docs]` — `a2a.md` baris 23-29. Isi kartu itu adalah pengungkapan;
  perlakukan penamaan skill sebagai teks yang menghadap publik.
- **Tiga metode**: `message/send`, `message/stream` (SSE), `tasks/get`.
  `[docs]` — `a2a.md` baris 17-19.
- **Dua identifier, persis pola di §Pola**: `contextId` mengelompokkan
  percakapan, `taskId` menandai tiap permintaan. Permintaan pertama
  menghilangkan keduanya dan server yang men-generate; giliran berikutnya
  wajib membawanya kembali. Server memetakan `contextId` → `thread_id`.
  `[docs]` — `a2a.md` baris 57-64, 270-272.
- **Syarat bentuk state**: agent wajib punya kunci `messages` di
  state-nya agar kompatibel dengan A2A "text parts". `[docs]` — `a2a.md`
  baris 55.
- Satu jebakan penempatan yang disebut eksplisit: `thread_id` diletakkan
  di `metadata` **tingkat atas** payload JSON-RPC, bukan di dalam
  `params`. `[docs]` — `a2a.md` baris 368.

Perlu dicatat soal kualitas halamannya: contoh kodenya memakai
`StateGraph` mentah dengan `gpt-3.5-turbo` dan panggilan OpenAI langsung —
**tidak ada `create_deep_agent` sama sekali**. `[docs]` — `a2a.md` baris
68-152. Jadi halaman ini menunjukkan cara membuat graph LangGraph
kompatibel A2A, bukan cara mengekspos deep agent; sisanya sebagian besar
tentang menyatukan trace lintas agent di LangSmith.

## Sumber

- `[code]` `deepagents-acp==0.0.10` — `deepagents_acp/server.py`, dibaca
  dari venv terpisah (bukan `../recipes/.venv`, yang sengaja tidak diubah).
  Reproduksi:
  `uv venv acpv && VIRTUAL_ENV=acpv uv pip install "deepagents-acp==0.0.10"`,
  lalu baca `acpv/lib/python3.*/site-packages/deepagents_acp/server.py`.
- `[code]` Metadata PyPI `deepagents-acp` 0.0.10
  (`https://pypi.org/pypi/deepagents-acp/json`, diambil sebagai JSON
  mentah) — `requires_dist` memuat `deepagents` tanpa batas versi, dasar
  peringatan pin di §Di deepagents. Resolusi nyata di venv uji menarik
  `deepagents` 0.7.9.
- `[docs]` [`../upstream/deepagents-docs/acp.md`](../upstream/deepagents-docs/acp.md)
  — snapshot verbatim; mode stdio, bentuk pemakaian, daftar klien,
  `MemorySaver` di semua contoh.
- `[docs]` [`../upstream/deepagents-docs/a2a.md`](../upstream/deepagents-docs/a2a.md)
  — snapshot verbatim; seluruh bagian A2A bersumber di sini, termasuk
  `disable_a2a`, agent card, `contextId`/`taskId`, dan syarat kunci
  `messages`.
- `[code]` [`mcp.md`](mcp.md) §Pola, §Trade-off — arah konsumsi dan
  peringatan "klien nyata mengimplementasikan subset spesifikasi", yang
  digeneralisasi ke dua arah lain di file ini; dirujuk tanpa ditulis
  ulang.
- Tidak ada klaim `[inferred]` di file ini: tiap butir teknis punya
  sitasi source atau baris snapshot.
