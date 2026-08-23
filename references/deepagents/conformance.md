# Audit kesesuaian — KB ini vs contoh resmi maintainer

Menjawab pertanyaan: **apakah cara KB ini memakai `deepagents` memang wajar,
atau modifikasi asal yang kebetulan jalan.**

## Batas audit ini — baca dulu

Tiga hal yang membatasi seberapa jauh audit ini bisa menyimpulkan, dan
semuanya harus dinyatakan sebelum tabelnya dibaca:

1. **`langchain-ai/deepagents-quickstarts` sudah diarsipkan.** Commit
   terakhirnya `31f9a02` (2026-01-23) berjudul *"docs: deprecate repo, point
   to main deepagents examples"*; README-nya sekarang hanya berisi
   "⚠️ This repo has moved … This repo is archived and no longer updated."
   Isinya tinggal **satu** contoh (`deep_research/`), dan `pyproject.toml`-nya
   masih menyematkan `deepagents>=0.2.6` — lima rilis minor di bawah 0.7.8
   yang didokumentasikan KB ini. Membandingkan pola 0.7.8 terhadap contoh
   yang dipin ke 0.2.6 akan menghasilkan "tidak muncul" untuk hampir semua
   parameter, dan kesimpulan itu tidak berarti apa-apa.
2. **Karena itu audit diperluas** ke `langchain-ai/deepagents/examples/`
   (14 contoh, tempat maintainer memindahkan quickstarts) dan
   `libs/code/deepagents_code/` (CLI/TUI resmi — kode produksi maintainer
   sendiri di atas `deepagents`). Tabel di bawah punya kolom terpisah untuk
   masing-masing, supaya "tidak ada di quickstarts" tidak tertukar dengan
   "tidak ada di praktik maintainer".
3. **`deepagents` masih muda.** Banyak permukaannya belum punya praktik
   komunitas yang mapan. Sebagian rekomendasi KB ini adalah penilaian kami,
   bukan kanon — itulah gunanya label `[ours]` dan roster di bagian akhir.

Metode: `git clone --depth 1` kedua repo dan `grep` terhadap source, bukan
ringkasan dokumentasi. Repo utama pada commit `23b83ad` (2026-08-21).

## Tabel kesesuaian

Kolom **QS** = `deepagents-quickstarts` (arsip, satu contoh).
Kolom **EX** = `deepagents/examples/` (14 contoh).
Kolom **CODE** = `libs/code/deepagents_code/` (CLI resmi).

| # | Pola yang dipakai KB ini | QS | EX | CODE | Catatan |
|---|---|---|---|---|---|
| P-01 | `create_deep_agent(model=<instance eksplisit>)` | ya | ya | ya | Semua contoh memberi model eksplisit; tidak ada yang mengandalkan `model=None`. |
| P-02 | `subagents=[<dict SubAgent>]` dengan `tools` sempit | ya | ya | ya | `deep_research`, `nvidia_deep_agent`, `content-builder-agent`. |
| P-03 | `tools=[...]` custom | ya | ya | ya | |
| P-04 | `system_prompt=` prosa panjang | ya | ya | ya | |
| P-05 | `backend=FilesystemBackend(root_dir=...)` | tidak | ya | varian | `text-to-sql-agent`, `better-harness`, `llm-wiki` (sebagai route). CLI memakainya di dalam `CompositeBackend`. |
| P-06 | `memory=["./AGENTS.md"]` | tidak | ya | ya | `text-to-sql-agent`, `nvidia_deep_agent`, `content-builder-agent`. |
| P-07 | `skills=["./skills/"]` | tidak | ya | ya | `text-to-sql-agent`, `content-builder-agent`. |
| P-08 | `CompositeBackend(default=..., routes={...})` | tidak | ya | ya | `nvidia_deep_agent`, `llm-wiki`. |
| P-09 | `StoreBackend(namespace=lambda rt: ...)` | tidak | **tidak** | tidak | Hanya ada di docstring/dokumentasi, **tidak** di satu pun contoh maintainer. → **D-08** |
| P-10 | `LocalShellBackend(root_dir=...)` | tidak | **tidak** | varian | Contoh memakai `LangSmithSandbox`/Modal/`FilesystemBackend`; CLI memakai sandbox terkelola. → **D-09** |
| P-11 | backend sandbox (`DaytonaSandbox` dsb.) | tidak | varian | ya | `llm-wiki` memakai `LangSmithSandbox`; `DaytonaSandbox` hanya di README `libs/partners/daytona`. → **D-17** |
| P-12 | `permissions=[FilesystemPermission(...)]` | tidak | ya | ya | `llm-wiki/helpers.py` baris 548-565, 633-638. |
| P-13 | `interrupt_on={...}` | tidak | varian | ya | Di `examples/` hanya muncul **sebagai baris komentar** (`nvidia_deep_agent/src/agent.py:85,98`); pemakaian nyata ada di CLI. → **D-10** |
| P-14 | `checkpointer=` disuntik aplikasi | tidak | ya | ya | `async-subagent-server/supervisor.py` (`MemorySaver`). |
| P-15 | `context_schema=` | tidak | ya | ya | `nvidia_deep_agent`. |
| P-16 | `AsyncSubAgent` (Agent Protocol) | tidak | ya | tidak | `async-subagent-server/`. |
| P-17 | `recursion_limit` lewat `.with_config`/`config=` | tidak | ya | ya | `better-harness:225`, `libs/code/deepagents_code/agent.py:3110`. |
| P-18 | `middleware=[...]` pada `create_deep_agent` | tidak | **tidak** | ya | Nol contoh di `examples/`; CLI memakainya berat (`agent_middleware`, ~15 middleware kustom). → **D-11** |
| P-19 | `AgentMiddleware` kustom | tidak | **tidak** | ya | `ShellAllowListMiddleware`, `LocalContextMiddleware`, `ManagedMemoryGuardMiddleware`, dll. di `libs/code`. → **D-11** |
| P-20 | `TodoListMiddleware()` ditambah eksplisit | tidak | **tidak** | tidak | Satu-satunya pemakaian di seluruh `deepagents` 0.7.8 adalah profil `_openai_codex.py:77`. → **D-12** |
| P-21 | `response_format=` pada `create_deep_agent` | tidak | **tidak** | tidak | Ada di signature dan didokumentasikan untuk `SubAgent`, tapi nol contoh. → **D-13** |
| P-22 | `state_schema=` kustom | tidak | **tidak** | varian | CLI memakai `state_schema=` pada `create_agent` (bukan `create_deep_agent`) di `reliable_rubric.py`, `goal_rubric.py`. → **D-14** |
| P-23 | `HarnessProfile` / `register_harness_profile` | tidak | **tidak** | tidak | Hanya dipakai `deepagents` untuk profil bawaannya sendiri. → **D-15** |
| P-24 | `agent.json` untuk deploy | tidak | ya | — | **Empat** di level proyek (`deploy-coding-agent`, `deploy-content-writer`, `deploy-gtm-agent`, `deploy-mcp-docs-agent`) plus **satu** di level subagent (`deploy-gtm-agent/subagents/market-researcher/`). Tiga yang pertama berisi `{name, runtime}` saja; hanya `deploy-gtm-agent` yang punya `description`; yang level-subagent berisi `{description, model_id}` tanpa `runtime`. **Nol** di antaranya memakai kunci `backend`. → **D-16** |
| P-25 | Loop luar di atas `invoke` | tidak | varian | tidak | `ralph_mode` melakukannya, tapi dengan **thread baru tiap iterasi** dan filesystem sebagai memori — strategi context, bukan pembatas langkah. |
| P-26 | Subagent dimuat dari file konfigurasi | tidak | varian | ya | `content-builder-agent` melakukannya lewat helper YAML kustom, dengan komentar eksplisit bahwa "`deepagents` doesn't natively load subagents from files". Preseden resmi bahwa loader konfigurasi sendiri itu wajar. |
| P-27 | `RubricMiddleware` | tidak | tidak | ya | KB ini menyebutnya sebagai opsional non-default; sesuai. |

## Divergence log

Sembilan belas entri, mencakup setiap baris `tidak` dan sebagian besar
`varian`. **Empat baris `varian` sengaja tidak punya entri sendiri** —
P-05, P-25, dan P-26 karena alasannya sudah tuntas di kolom Catatan
barisnya dan tidak ada keputusan kami yang perlu dipertanggungjawabkan
(ketiganya adalah pola maintainer yang kita ikuti apa adanya); P-11
dirujuk ke D-17. Tidak ada pola yang perlu dihapus: tidak satu pun
`tidak`/`varian` berdiri tanpa alasan tertulis, entah di entri D-xx atau
di kolom Catatan.

Untuk penyimpangan per-arketipe (D-01…D-07) sumbernya adalah label
`[ours]` yang sudah ada di `references/archetypes/`.

### D-01 — Arketipe 01 tanpa subagent — **PREMIS SALAH, harus dikoreksi**

- **Yang kita lakukan**: Workspace Agent (01) sengaja tidak memakai subagent.
- **Klaim vanilla di KB**: *"Vanilla contoh deepagents (`content-builder-agent`,
  `deep_research`) hampir selalu menyertakan minimal satu subagent"*
  (`references/archetypes/01-workspace-agent.md:104`, diulang di
  `references/scaffolds/deltas/01-workspace-agent.md:47`).
- **Temuan audit**: klaim itu **tidak benar**. Dari 10 pemanggilan
  `create_deep_agent` di `examples/`, **5 tidak mengirim subagent sinkron
  sama sekali**: `text-to-sql-agent/agent.py:45` (`subagents=[]`, dengan
  komentar "No subagents needed"), `llm-wiki/helpers.py:633`,
  `better-harness/better_harness/agent.py:206` dan `:611`, serta
  `async-subagent-server/server.py:155`. Nuansa penting: subagent
  `general-purpose` tetap ditambahkan otomatis di semuanya, jadi tool `task`
  selalu ada kecuali dimatikan lewat profil.
- **Kesimpulan**: ini **bukan divergensi**. Tidak ada yang perlu
  dipertahankan sebagai penyimpangan — yang perlu diperbaiki adalah klaim
  vanilla-nya. **Tindakan wajib**: turunkan label `[ours]` di
  `archetypes/01-workspace-agent.md:104` dan `scaffolds/deltas/01-workspace-agent.md:47`
  menjadi `[code]`, dan ganti kalimat "hampir selalu menyertakan subagent"
  dengan fakta 5-dari-10 di atas. Belum dikerjakan di task ini karena berada
  di luar file yang boleh disentuh.
- **Biaya kalau dibiarkan**: pembaca menyimpulkan bahwa tidak memakai
  subagent itu tidak lazim, lalu menambahkan subagent yang tidak dibutuhkan —
  biaya token dan kompleksitas tanpa manfaat.

### D-02 — Arketipe 02 tanpa `interrupt_on` di loop build

- **Yang kita lakukan**: gate hanya di tool publish/deploy.
- **Vanilla**: `interrupt_on=None` adalah default `create_deep_agent`, dan
  nol contoh `examples/` memasang `interrupt_on` secara aktif (P-13).
- **Alasan**: kendali manusia arketipe ini adalah review preview di akhir,
  bukan approval per langkah.
- **Status**: **bukan divergensi dari library** — ini pilihan produk yang
  kebetulan sama dengan default. Label `[ours]`-nya tepat karena keputusan
  produknya milik kita, bukan karena librarynya beda.
- **Biaya kalau salah**: aksi ireversibel (deploy ke produksi) lolos tanpa
  persetujuan. Mitigasinya sudah ada: gate di tool publish.

### D-03 — Guard pengulangan tool-call untuk arketipe 03

- **Yang kita lakukan**: middleware kustom yang menghentikan agent kalau
  memanggil tool yang sama dengan argumen identik N kali berturut-turut.
- **Vanilla**: `recursion_limit` (default `9_999`),
  `ModelCallLimitMiddleware`, dan `ToolCallLimitMiddleware`. Ketiganya
  menghitung **jumlah**, tidak ada yang mendeteksi **pengulangan**.
- **Alasan menyimpang**: batas jumlah mencegah loop tak berhenti, tapi tidak
  mendeteksi agent yang berputar di tempat sambil membakar budget.
- **Bentuk yang benar**: `wrap_tool_call` yang mengembalikan
  `ToolMessage(status="error")` — jalur ekstensi resmi, dan pola yang sama
  dipakai maintainer sendiri di `ShellAllowListMiddleware`. Contoh kode yang
  sudah diverifikasi jalan ada di [`middleware.md`](middleware.md).
- **Biaya kalau salah**: false positive menghentikan agent yang sebenarnya
  sedang melakukan retry sah (mis. polling). Karena itu ambangnya harus
  memperhitungkan tool yang memang idempoten-berulang.

### D-04 — Validasi provenance sitasi post-hoc (arketipe 04)

- **Yang kita lakukan**: mencocokkan tiap sitasi di `response_format`
  terhadap hasil tool call `web_search` nyata di transkrip.
- **Vanilla**: `response_format` saja. Nol contoh maintainer memakainya di
  `create_deep_agent` (P-21).
- **Alasan menyimpang**: `response_format` memvalidasi bentuk, bukan
  kebenaran isi — sitasi halusinasi lolos validasi skema.
- **Biaya kalau salah**: validator yang terlalu ketat menolak sitasi sah
  (mis. yang datang dari pengetahuan model, bukan pencarian). Perlu
  keputusan eksplisit: apakah klaim tanpa tool call ditolak atau ditandai.

### D-05 — Tool `undo_*` alih-alih `interrupt_on` (arketipe 05)

- **Yang kita lakukan**: tiap tool aksi produk dipasangkan tool
  `undo_<aksi>`, dipanggil dari UI host.
- **Vanilla**: `HumanInTheLoopMiddleware` — approve/edit/reject/respond
  **sebelum** eksekusi.
- **Alasan menyimpang**: horizon pendek; jeda approval terasa regresi UX
  dibanding produk tuan rumah.
- **Yang perlu diketahui**: ada opsi tengah yang vanilla dan mungkin lebih
  tepat — `InterruptOnConfig.when`, predikat yang memutuskan per panggilan
  apakah interrupt perlu. Aksi berisiko rendah lewat, yang berisiko tinggi
  di-gate. Pertimbangkan ini sebelum membangun mesin undo penuh.
- **Biaya kalau salah**: aksi yang tidak bisa di-undo (kirim email, panggil
  webhook pihak ketiga) tidak punya jaring pengaman sama sekali.

### D-06 — `create_deep_agent` sebagai node dalam graph event-driven (arketipe 06)

- **Yang kita lakukan**: `create_deep_agent(...)` di dalam graph/worker yang
  dipicu event, bukan sebagai loop interaktif.
- **Klaim vanilla di KB**: *"Vanilla penggunaan deepagents di
  dokumentasi/contoh selalu berupa loop interaktif dipicu manusia"*
  (`references/archetypes/06-workflow-agent.md:82`).
- **Temuan audit**: klaim itu **terlalu kuat**.
  `examples/async-subagent-server/server.py` memanggil
  `await _agent.ainvoke(...)` di baris **174**, dari dalam `_execute_run`
  (baris 169) yang di-dispatch sebagai task `asyncio.ensure_future` di baris
  **287** di bawah endpoint HTTP `POST /threads/{thread_id}/runs`
  (baris **234**) — tanpa manusia di loop.
  `examples/ralph_mode/` berjalan tanpa pengawasan. Contoh `deploy-*` adalah
  layanan ter-deploy, bukan REPL.
- **Kesimpulan**: pemakaian non-interaktif **punya preseden resmi**.
  Yang tetap benar dan tetap `[ours]` adalah pembagian
  tanggung jawabnya: `deepagents` menentukan "apa yang dilakukan LLM saat
  dipanggil", trigger/antrian di luar. **Tindakan disarankan**: perlemah
  kalimat "selalu berupa loop interaktif" di
  `archetypes/06-workflow-agent.md:82`.
- **Biaya kalau dibiarkan**: pembaca mengira memakai `deepagents` di luar
  konteks interaktif berisiko/tidak didukung, lalu membangun harness sendiri
  yang tidak perlu.

### D-06b — `thread_id` diturunkan dari idempotency key event

- **Yang kita lakukan**: `thread_id` = fungsi dari idempotency key event.
- **Vanilla**: `examples/async-subagent-server/supervisor.py:57` memakai
  `str(uuid.uuid4())`; tidak ada contoh maintainer yang menurunkan
  `thread_id` dari identitas event.
- **Alasan menyimpang**: retry event yang sama harus jatuh ke checkpoint
  yang sama, bukan memulai run baru.
- **Biaya kalau salah**: dua event yang **berbeda** dengan key yang tabrakan
  akan berbagi riwayat percakapan — kebocoran konteks lintas event. Kunci
  harus benar-benar unik per event, bukan per tipe event.

### D-06c — Kill switch di luar `deepagents`

- **Yang kita lakukan**: flag di database yang dicek worker sebelum
  memanggil agent.
- **Vanilla**: tidak ada API kill switch di `deepagents`; yang ada hanya
  `interrupt()` (jeda kooperatif per run).
- **Status**: **bukan divergensi** — ini pernyataan tentang ketiadaan
  fitur, bukan penggantian pola library. Label `[ours]`-nya menandai bahwa
  desain kill switch-nya milik kita.
- **Biaya kalau salah**: pengecekan flag yang jarang berarti run yang sudah
  "dimatikan" masih menyelesaikan langkahnya.

### D-07 — Verifikasi setelah aksi UI lewat konvensi prompt (arketipe 07)

- **Yang kita lakukan**: tool `verify_state` wajib dipanggil setelah tiap
  aksi UI, ditegakkan lewat instruksi system prompt.
- **Vanilla**: tidak ada mekanisme penegak urutan tool di `deepagents`.
  `PatchToolCallsMiddleware` **tidak** melakukannya (hanya menambal
  `ToolMessage` dangling) — ini sudah diverifikasi dari
  `middleware/patch_tool_calls.py`.
- **Alasan menyimpang**: computer-use tidak punya jaminan bahwa hasil aksi =
  hasil yang terlihat.
- **Penguatan yang tersedia**: `wrap_tool_call` yang menolak aksi UI kedua
  berturut-turut tanpa `verify_state` di antaranya. Lebih kuat dari prompt,
  tetap bukan jaminan struktural.
- **Biaya kalau salah**: model mengabaikan konvensi prompt dan tetap
  mengklik membabi buta. Prompt bukan penegakan.

### D-08 — `StoreBackend(namespace=...)` sebagai pola isolasi per-user

- **Yang kita lakukan**: `StoreBackend(namespace=lambda rt: (user_id, ...))`
  untuk file durable ter-scope per user. **Dua komposisi berbeda dipakai di KB
  ini, dan perilaku artefaknya tidak sama** — lihat
  [`middleware.md`](middleware.md) §`artifacts_root`:
  - `scaffolds/_base.md:157-168` dan arketipe 03/06 memakai `StoreBackend`
    **polos**. `artifacts_root` jatuh ke cabang `"/"`
    (`middleware/summarization.py:598`), sehingga `/conversation_history/`,
    media-nya, dan `/large_tool_results/` **semuanya** mendarat di dalam
    namespace user. Isolasi penuh, tanpa konfigurasi tambahan. `[code]`
  - recipe `04_custom_backend.py` memakai `CompositeBackend(default=StateBackend(),
    routes={"/memories/": StoreBackend(namespace=...)})`. Di sini `/memories/`
    durable dan ter-scope, tapi `/conversation_history/` **tidak cocok route mana
    pun** sehingga jatuh ke `StateBackend` — ephemeral. Bukan kebocoran
    (`StateBackend` per-thread), tapi ringkasan percakapan tidak persist. `[code]`
- **Vanilla**: pola ini **hanya ada di docstring** — `FilesystemMiddleware`
  (`middleware/filesystem.py:1602-1614`) dan `StoreBackend.__init__`
  (`backends/store.py:110-117`) mencontohkannya, tapi **nol** contoh
  maintainer memakainya. Contoh yang butuh persistence memakai
  `FilesystemBackend(root_dir=...)`.
- **Alasan menyimpang**: contoh maintainer semuanya single-tenant lokal
  (CLI, notebook, skrip). KB ini menargetkan layanan multi-user, dan
  `namespace` adalah **satu-satunya** *hook* scoping per-user yang resmi.
- **Yang sebenarnya diisolasi — lebih luas dari "file user"**. `[code]`
  `BackendProtocol` (`backends/protocol.py:378`) mendeklarasikan 18 metode
  (`ls`/`read`/`grep`/`glob`/`write`/`edit`/`delete`/`upload_files`/`download_files`,
  masing-masing plus varian async), dan konsumennya **bukan hanya tool file**.
  Diverifikasi dengan membaca pemanggilan di `middleware/`:

  | Middleware | Metode backend yang dipanggil | Yang mendarat di backend |
  |---|---|---|
  | `filesystem.py` | `ls read grep glob write edit delete` (+async) | file kerja user |
  | `summarization.py:1102,1155,1218,1233` | `upload_files download_files write edit` (+async) | **ringkasan percakapan & media inline yang di-offload** |
  | `_message_eviction.py:134,154` | `write awrite` | **isi tool message yang dibuang dari konteks** |
  | `memory.py:295,329` | `download_files adownload_files` | **file memory lintas sesi** |
  | `skills.py:613,639,679,705` | `ls als download_files adownload_files` | **skill yang terlihat oleh agent** |

  Empat dari lima konsumen itu bukan tool file — mereka fitur lain yang
  kebetulan butuh tempat menaruh byte. Konsekuensinya dua arah:

  **Risiko lebih besar dari yang terlihat.** `namespace` yang salah tidak
  membocorkan file saja; ia membocorkan ringkasan percakapan user lain,
  potongan transkrip yang di-offload saat eviction, memory-nya, dan daftar
  skill-nya. Membaca `filesystem.py` saja akan melewatkan seluruh kelas
  kebocoran ini — inilah alasan `extension-points.md` menempatkan backend,
  bukan `create_deep_agent`, sebagai titik ekstensi utama.

  **Tapi juga proteksi lebih besar.** Karena kelimanya lewat protokol yang
  sama, satu `namespace` yang benar mengunci kelimanya sekaligus — dan karena
  parameter itu wajib serta agent dirakit per turn
  (`scaffolds/_base.md:183-185`), tidak ada jalur di mana salah satunya
  ter-scope dan yang lain tidak. Ini kekuatan desain yang tidak tertangkap
  saat entri ini pertama ditulis.
- **Biaya kalau salah** — dan di sini penting membedakan risiko yang nyata
  dari yang tidak. Di level API **tidak ada** yang bisa gagal diam-diam:
  `namespace` adalah parameter keyword-only **wajib** bertipe
  `Callable[[Runtime[Any]], tuple[str, ...]]`
  (`backends/store.py:41,99-104`), lupa mengisinya adalah `TypeError` saat
  konstruksi, dan komponen namespace divalidasi terhadap
  `_NAMESPACE_COMPONENT_RE` sehingga nilai berbentuk aneh ditolak. Sisa
  eksposurnya ada dua, keduanya di luar jangkauan library:
  (a) **kebenaran `scope.user_id` milik aplikasi sendiri** —
  `scaffolds/_base.md:160` sengaja memakai `user_id` dari `Scope` hasil
  `ScopeMiddleware`, bukan `rt.server_info.user.identity` seperti contoh
  dokumentasi; kalau `Scope` salah diisi (mis. header tidak tervalidasi),
  `namespace` akan mengembalikan tuple yang **valid** untuk user yang
  **salah**, dan tidak ada lapisan di bawahnya yang bisa menangkap itu;
  (b) **nol contoh maintainer yang multi-tenant**, jadi pola ini tidak
  punya bukti lapangan sama sekali. Gabungan keduanya membuat ini
  penyimpangan dengan biaya kegagalan tertinggi di seluruh KB. Yang
  menutupnya: uji isolasi end-to-end di lapisan aplikasi (dua user, satu
  path, pastikan tidak saling terbaca), bukan pembacaan ulang API.

### D-09 — `LocalShellBackend` untuk arketipe 01

- **Yang kita lakukan**: `LocalShellBackend(root_dir=repo)` untuk Workspace
  Agent.
- **Vanilla**: nol contoh maintainer memakainya. Yang butuh shell memakai
  sandbox terkelola (`LangSmithSandbox` di `llm-wiki`, Modal di
  `nvidia_deep_agent`); CLI resmi juga memakai sandbox.
- **Alasan menyimpang**: arketipe 01 **didefinisikan** oleh blast radius
  "mesin user" — itu justru intinya, bukan kecelakaan.
- **Biaya kalau salah**: sangat tinggi, dan `THREAT_MODEL.md` maintainer
  sudah menyatakannya: shell tak terisolasi, `virtual_mode` tidak membatasi
  `execute()`, file bisa dibaca/ditulis di luar `root_dir` lewat shell.
  Ketidakhadirannya di contoh maintainer **konsisten** dengan peringatan
  itu — bukan bukti bahwa backend-nya salah, tapi bukti bahwa maintainer
  tidak menganggapnya default yang aman. KB ini harus tetap menyandingkan
  pilihan ini dengan gate HITL wajib, dan itu sudah dilakukan.

### D-10 — `interrupt_on` sebagai gate utama

- **Yang kita lakukan**: `interrupt_on` per tool untuk arketipe 01, 06, 07.
- **Vanilla**: di `examples/` `interrupt_on` hanya muncul **sebagai komentar
  yang dinonaktifkan** (`nvidia_deep_agent/src/agent.py:85,98`:
  `# "interrupt_on": {"execute": True} # enable human in the loop`).
  Pemakaian nyata ada di `libs/code`, tapi lewat middleware turunannya
  sendiri (`AsyncApprovalHITLMiddleware`), bukan parameter `interrupt_on`
  polos.
- **Alasan menyimpang**: contoh dirancang untuk dijalankan tanpa hambatan;
  produk nyata tidak punya kemewahan itu.
- **Biaya kalau salah**: `interrupt_on` **tidak berguna tanpa
  `checkpointer`** — tanpa itu tidak ada tempat menyimpan titik jeda. Setiap
  scaffold yang memakai `interrupt_on` wajib memasangkannya dengan
  checkpointer durable (bukan `MemorySaver`) kalau approval-nya async.
  Pola CLI resmi menunjukkan bahwa untuk mode non-interaktif jalur yang
  lebih tepat adalah **menolak** lewat `wrap_tool_call`, bukan interrupt —
  karena interrupt/resume memecah trace jadi beberapa run.

### D-11 — Middleware kustom lewat `middleware=[...]`

- **Yang kita lakukan**: menyarankan middleware kustom untuk guard,
  audit, dan limit (arketipe 03, 07).
- **Vanilla**: **nol** contoh di `examples/` memakai parameter `middleware=`.
- **Tetapi**: `libs/code/deepagents_code/agent.py` — kode produksi
  maintainer sendiri — membangun daftar `agent_middleware` berisi belasan
  middleware kustom (`ShellAllowListMiddleware`, `LocalContextMiddleware`,
  `ManagedMemoryGuardMiddleware`, `ConfigurableModelMiddleware`,
  `ServerHooksMiddleware`, …) dan meneruskannya lewat
  `create_deep_agent(middleware=agent_middleware)` (baris 3098-3110).
- **Kesimpulan**: pola ini **idiomatik**; ketiadaannya di `examples/` adalah
  soal ruang lingkup contoh (masing-masing sengaja fokus satu fitur), bukan
  sinyal bahwa middleware kustom tidak dianjurkan. Tidak ada divergensi
  substantif.
- **Biaya kalau salah**: kesalahan tersering bukan "memakai middleware",
  tapi memakainya di lapisan yang salah — lihat
  [`extension-points.md`](extension-points.md) anti-pattern #1 dan #2.

### D-12 — `TodoListMiddleware` ditambah eksplisit (arketipe 03)

- **Yang kita lakukan**: `middleware=[TodoListMiddleware()]` untuk planning
  eksplisit.
- **Vanilla**: nol contoh maintainer. Satu-satunya pemakaian
  `TodoListMiddleware` di `deepagents` 0.7.8 adalah profil harness
  `profiles/harness/_openai_codex.py:77`, yang memasangnya lewat
  `extra_middleware` untuk model Codex.
- **Alasan menyimpang**: planning eksplisit adalah axis pembeda arketipe 03;
  tanpanya arketipe itu tidak ada.
- **Catatan penting yang ditemukan audit**: cara maintainer memasangnya
  adalah lewat `HarnessProfile.extra_middleware`, bukan `middleware=[...]`.
  Bedanya nyata — `extra_middleware` berlaku juga ke subagent deklaratif dan
  GP subagent, sedangkan `middleware=[...]` hanya ke main agent (dan ke GP
  subagent **hanya** kalau namanya menimpa slot GP default). Untuk arketipe
  03 yang berat delegasi, subagent tidak akan punya `write_todos`.
  Kalau planning di subagent juga diinginkan, jalurnya adalah profil.
- **Biaya kalau salah**: planning yang dikira aktif di seluruh pohon agent
  ternyata hanya di akar.

### D-13 — `response_format` pada `create_deep_agent`

- **Yang kita lakukan**: memakainya untuk memaksa bentuk laporan (arketipe 04).
- **Vanilla**: ada di signature dan didokumentasikan panjang lebar untuk
  `SubAgent`, tapi nol contoh maintainer memakainya di level agent utama.
- **Alasan menyimpang**: keluaran arketipe 04 dikonsumsi program, bukan
  manusia.
- **Biaya kalau salah**: `response_format` mengubah bentuk graph (menambah
  structured-output tool dan edge tambahan). Kombinasinya dengan
  `interrupt_on` dan subagent belum banyak dicoba di lapangan — uji dulu di
  jalur nyata sebelum mengandalkannya.

### D-14 — `state_schema=` kustom

- **Yang kita lakukan**: menyebutkannya sebagai extension point, dengan
  catatan bahwa cara yang **disarankan** adalah `state_schema` pada
  middleware.
- **Vanilla**: nol contoh memakai `create_deep_agent(state_schema=)`. CLI
  memakai `state_schema=` tapi pada `create_agent` langsung
  (`reliable_rubric.py:244`, `goal_rubric.py:1453,1498`).
- **Kesimpulan**: rekomendasi KB ini (utamakan `state_schema` middleware)
  **sejalan** dengan docstring `create_deep_agent` sendiri dan dengan
  praktik CLI. Bukan divergensi.
- **Biaya kalau salah**: `state_schema` yang tidak diturunkan dari
  `DeepAgentState` menghilangkan reducer `DeltaChannel` — checkpoint tumbuh
  O(N²), dan **tidak ada** validasi runtime yang mengeluh.

### D-15 — `HarnessProfile` sebagai extension point yang disarankan

- **Yang kita lakukan**: [`extension-points.md`](extension-points.md)
  menyarankan `register_harness_profile` sebagai alternatif resmi untuk
  menyalin-tempel `create_deep_agent`.
- **Vanilla**: tidak ada pengguna eksternal di repo maintainer — hanya
  `deepagents` sendiri yang memakainya untuk profil bawaan, dan modulnya
  ditandai **beta** ("may receive minor changes in future releases").
- **Alasan**: ini satu-satunya jalur resmi untuk mengubah stack di semua
  agent+subagent sekaligus. Alternatifnya (menyalin `graph.py`) jauh lebih
  buruk.
- **Biaya kalau salah**: API beta bisa berubah di rilis minor. Rekomendasi
  ini harus ditinjau ulang tiap kali `deepagents` naik versi minor.
  **Ini rekomendasi `[ours]` dengan risiko perubahan API tertinggi.**

### D-16 — `agent.json` dengan `backend.sandbox_config` (arketipe 02)

- **Yang kita lakukan**: `references/archetypes/02-generative-builder.md`
  mencontohkan `{"backend": {"type": "sandbox", "sandbox_config": {"scope":
  "thread", "policy_ids": [...]}}}`.
- **Status verifikasi**: klaim ini sebelumnya **belum terverifikasi** karena
  `deepagents-cli` tidak terpasang. Sekarang **terverifikasi dari source**:
  `libs/cli/deepagents_cli/deploy/project.py` baris 239-240 dan 290-322
  menormalkan kunci itu, dan `libs/cli/tests/unit_tests/deploy/test_project.py`
  baris 219-249 menegaskan bentuknya persis
  (`{"type": "sandbox", "sandbox_config": {"scope": "agent", "policy_ids":
  ["p-1"], "idle_ttl_seconds": 900, "delete_after_stop_seconds": 300}}`).
  Nilai `scope` yang sah: `"thread"` dan `"agent"`; `"workspace"` ditolak.
  Bentuk lama `{"type": "thread_scoped_sandbox", "sandbox": {...}}`
  dinormalkan ke bentuk baru.
- **Divergensi yang tersisa**: **tidak ada satu pun `agent.json` contoh** yang
  memakai kunci `backend` — ketiganya (`deploy-coding-agent`,
  `deploy-content-writer`, `deploy-gtm-agent`) hanya berisi `name`,
  `description`, dan `runtime.model.model_id`. Jadi kuncinya nyata, tapi
  pemakaiannya belum dicontohkan maintainer.
- **Biaya kalau salah**: skema CLI berubah tanpa deprecation dan `agent.json`
  scaffold gagal di-deploy. Sudah ada preseden: bentuk `sandbox` lama
  dideprekasi menjadi `sandbox_config`.

### D-17 — `DaytonaSandbox(sandbox=..., timeout=300)` (arketipe 02 & 07)

- **Status verifikasi**: sebelumnya **belum terverifikasi** karena
  `langchain_daytona` tidak terpasang. Sekarang **terverifikasi dari
  source**: `libs/partners/daytona/langchain_daytona/sandbox.py` baris 30-36
  — `DaytonaSandbox(*, sandbox: daytona.Sandbox, timeout: int = 30*60,
  sync_polling_interval: SyncPollingInterval = 0.1)`, semua **keyword-only**,
  `sandbox` wajib, kelasnya turunan `BaseSandbox` yang memenuhi
  `SandboxBackendProtocol`. README paket mencontohkan persis bentuk yang
  dipakai KB ini.
- **Divergensi**: nol contoh di `examples/` memakainya (yang butuh sandbox
  memakai `LangSmithSandbox` atau Modal). Paket ini juga rilis terpisah
  dengan siklus versinya sendiri.
- **Biaya kalau salah**: ketergantungan pada paket partner yang tidak
  ikut ter-tes di CI `deepagents`. Alternatif yang lebih aman untuk KB ini
  adalah menyebut `LangSmithSandbox` sebagai contoh utama (ada di
  `deepagents` inti dan dipakai `llm-wiki`), dengan `DaytonaSandbox` sebagai
  varian.

## Yang tetap belum terverifikasi

Tidak ada. Kedua item yang tertunda dari task sebelumnya (`agent.json`
CLI dan `DaytonaSandbox`) sudah diselesaikan lewat `git clone` repo
`langchain-ai/deepagents` — lihat D-16 dan D-17. Paket-paketnya sendiri
tetap **tidak terpasang** di `references/recipes/.venv`, jadi keduanya
diverifikasi dari **source dan test maintainer**, bukan dari eksekusi.
Yang akan menuntaskannya sepenuhnya: `uv add deepagents-cli langchain-daytona`
di `references/recipes/` lalu sebuah recipe yang mengkonstruksi
`DaytonaSandbox` dan mem-parse sebuah `agent.json`.

## Residu yang tercatat

Ditemukan saat audit, awalnya di luar file yang boleh disentuh task itu;
kelimanya diperbaiki di fix wave berikutnya (2026-08-23, lihat kolom Status):

| Lokasi | Isu | Perbaikan | Status |
|---|---|---|---|
| `archetypes/01-workspace-agent.md`, `scaffolds/deltas/01-workspace-agent.md`, `per-archetype.md` §01 | Klaim "vanilla hampir selalu menyertakan subagent" tidak benar (D-01) | Diganti dengan fakta 5-dari-10 beserta lokasi tiap call site; label diturunkan `[ours]` → `[code]` di ketiga tempat | **selesai** |
| `archetypes/06-workflow-agent.md` | Klaim "vanilla selalu loop interaktif dipicu manusia" terlalu kuat (D-06) | Diganti: `async-subagent-server/server.py` baris 174 (`ainvoke`), 169 (`_execute_run`), 287 (dispatch), 234 (endpoint) dan `ralph_mode` disebut sebagai preseden non-interaktif; `[ours]` dipersempit ke pembagian tanggung jawab trigger/antrian, yang memang tetap milik kami | **selesai** |
| `archetypes/01-workspace-agent.md` | Daftar tool `FilesystemMiddleware` menyertakan `delete` — **benar**; daftar di `systems/deepagents.md` justru yang kurang lengkap (tanpa `delete`) | Tambahkan `delete` ke daftar tool di `systems/deepagents.md` | **selesai** |
| `recipes/03_subagents.py` docstring | "mengembalikan `messages` akhirnya sebagai `ToolMessage` ringkas" — longgar dengan cara yang sama seperti koreksi di `systems/deepagents.md` | Ganti dengan "teks `AIMessage` non-kosong terakhir, atau `structured_response` ter-JSON" | **selesai** |
| `archetypes/03-general-task-agent.md:95` | Menyebut `recursion_limit` sebagai satu-satunya batas vanilla; `ModelCallLimitMiddleware` dan `ToolCallLimitMiddleware` tidak disebut | Tambahkan keduanya (D-03 tetap berdiri, alasannya justru menguat) | **selesai** |

Kelima baris di atas sudah dikerjakan (fix wave lanjutan, 2026-08-23) —
semuanya bersifat akurasi, bukan struktur. Tidak ada pola KB yang perlu
**dihapus** — setiap `tidak`/`varian` di tabel punya alasan tertulis, entah
di entri D-xx atau di kolom Catatan barisnya.

## Roster `[ours]`

Dibangun dengan perintah ini, dijalankan dari root repo:

```bash
grep -rn '\[ours\]' references/ --include='*.md'
```

Hasilnya **74 baris** pada saat task ini selesai, terbagi tiga:

- **51** di luar `references/deepagents/` — inilah klaim yang sesungguhnya,
  didaftar lengkap di tabel bawah. (Sebelum fix round 1 jumlahnya 53; dua
  dicabut karena D-01 terbukti bukan penyimpangan.)
- **10** di `references/deepagents/per-archetype.md` — semuanya **penunjuk**
  ke entri D-xx di file ini, bukan klaim baru.
- **13** di file ini sendiri — seluruhnya meta (judul bagian, penjelasan,
  kesimpulan, dan perintah `grep` di atas).

Angka ini harus dicek ulang setiap kali KB berubah: `grep` di atas wajib
mengembalikan tepat himpunan yang didaftar roster ini.

Kolom `#` adalah indeks stabil dari audit pertama, bukan hitungan berjalan —
baris bertanda `—` adalah klaim yang **dicabut** di fix round 1 dan sudah
tidak muncul di `grep`, sehingga nomor 1 dan 17 sengaja kosong.

| # | Lokasi | Inti klaim | Divergensi |
|---|---|---|---|
| — | `archetypes/01-workspace-agent.md` | Arketipe 01 tanpa subagent | D-01 — **dicabut**, premis salah; kini `[code]` |
| 2 | `archetypes/02-generative-builder.md:94` | Gate hanya di publish/deploy | D-02 |
| 3 | `archetypes/03-general-task-agent.md:95` | Guard pengulangan tool-call | D-03 |
| 4 | `archetypes/04-research-agent.md:95` | Validasi provenance sitasi | D-04 |
| 5 | `archetypes/05-in-app-copilot.md:94` | Tool `undo_*` alih-alih `interrupt_on` | D-05 |
| 6 | `archetypes/06-workflow-agent.md:82` | Pembagian tanggung jawab trigger/antrian di luar `deepagents` | D-06 (dipersempit; klaim "selalu interaktif" dicabut) |
| 7 | `archetypes/06-workflow-agent.md:104` | `thread_id` dari idempotency key | D-06b |
| 8 | `archetypes/06-workflow-agent.md:116` | Kill switch di luar library | D-06c |
| 9 | `archetypes/07-computer-use-agent.md:99` | Verifikasi lewat konvensi prompt | D-07 |
| 10 | `archetypes/README.md:53` | Deployment dipisah dari taksonomi arketipe | taksonomi, bukan `deepagents` |
| 11 | `systems/INDEX.md:93` | Meta: kenapa label `[ours]` ada | meta |
| 12-16 | `scaffolds/_base.md:56,77,160,450,493` | Protocol `Orchestrator`; `namespace` dari `Scope` aplikasi bukan `rt.server_info.user.identity`; `AsyncConnectionPool`; eksekusi turn inline di generator SSE | **:160 → D-08 (risiko tertinggi)**; sisanya arsitektur aplikasi, di luar `deepagents` |
| — | `scaffolds/deltas/01-workspace-agent.md` | Turunan D-01 | **dicabut**, kini `[code]` |
| 18-19 | `scaffolds/deltas/02-generative-builder.md:23,35` | Turunan dari #2 | D-02 |
| 20 | `scaffolds/deltas/03-general-task-agent.md:22` | Turunan dari #3 | D-03 |
| 21 | `scaffolds/deltas/04-research-agent.md:44` | Turunan dari #4 | D-04 |
| 22 | `scaffolds/deltas/05-in-app-copilot.md:34` | Turunan dari #5 | D-05 |
| 23-25 | `scaffolds/deltas/06-workflow-agent.md:14,24,49` | Turunan dari #6, #7, #8 | D-06, D-06b, D-06c |
| 26 | `scaffolds/deltas/07-computer-use-agent.md:29` | Turunan dari #9 | D-07 |
| 27 | `concepts/artifacts-and-canvas.md:88` | Versi artefak pakai integer monoton, bukan timestamp | di luar `deepagents` |
| 28-29 | `concepts/evaluation.md:37,66` | Eval terhadap trajektori penuh; "golden transcript" | di luar `deepagents` |
| 30 | `concepts/guardrails.md:31` | Kerangka enam titik guardrail dari spec proyek | di luar `deepagents` |
| 31-37 | `concepts/skill-composition.md:34,96,167,190,199,210,217` | Lapisan resolusi manifest skill **sebelum** `deepagents`; pemisahan intent/ekspresi | berdampingan dengan `SkillsMiddleware`, tidak menggantikannya |
| 38-40 | `concepts/multilingual.md:58,160,223` | Titik terkunci bahasa di pipeline intent/ekspresi | di luar `deepagents` |
| 41-45 | `concepts/persistence-schema.md:37,294,337,342,351` | Tabel `users` lokal; RLS tanpa subquery; penamaan; jalur migrasi `user_id`→`tenant_id` | di luar `deepagents` |
| 46-48 | `concepts/policy-as-data.md:160,170,182` | Skema policy-as-data di atas yang sudah data-shaped di `deepagents` | eksplisit menyatakan bagian mana yang **bukan** `[ours]` — model penulisan yang benar |
| 49 | `concepts/queueing-and-backpressure.md:68` | Skema antrian | di luar `deepagents` |
| 50 | `concepts/resource-profiling.md:95` | Kolokasi fase vs pisah per bound | di luar `deepagents` |
| 51 | `concepts/sandboxing.md:140` | Kebijakan sandbox bukan paksaan SDK Daytona | terkait D-17 |
| 52 | `concepts/serving-topology.md:167` | Monolith dulu, split belakangan | di luar `deepagents` |
| 53 | `concepts/streaming-protocol.md:142` | Granularitas stream per unit | di luar `deepagents` |
| 54 | `concepts/guardrails.md:94` | Fail-deferred wajib dipasangkan timeout + kebijakan saat habis (vanilla: `await` tanpa batas, OpenWorker `inbox.py:362-371`) | di luar `deepagents` |
| 55 | `concepts/isolation-and-scoping.md:121` | Audit katalog RLS tidak cukup; bukti isolasi harus query lintas user sebagai role aplikasi non-superuser (vanilla: periksa `relrowsecurity`/`relforcerowsecurity` lalu nyatakan cukup) | di luar `deepagents` |

Bacaan roster ini: dari 51 klaim, **12** benar-benar menyangkut cara memakai
`deepagents` (arketipe 02-07, `_base.md:56,77,160`, `sandboxing.md:129`) dan
tercatat di divergence log.
Sisanya adalah keputusan arsitektur aplikasi di lapisan **di atas**
`deepagents` — bukan penyimpangan dari library, dan bukan sesuatu yang bisa
diaudit terhadap contoh maintainer.

Yang paling perlu ditinjau ulang saat library matang, berurutan:
**D-08** (`namespace` untuk isolasi per-user — biaya kegagalan tertinggi,
gagal diam-diam), **D-15** (`HarnessProfile` masih beta),
**D-16/D-17** (skema CLI dan paket partner yang bisa berubah),
lalu **D-01/D-06** (dua klaim vanilla yang audit ini temukan tidak akurat).

## Sumber

Repo yang di-clone dan di-`grep` langsung (bukan ringkasan):

- `langchain-ai/deepagents-quickstarts`, commit `31f9a02` (2026-01-23),
  `git clone --depth 1`. **Arsip.** Isi: `README.md` (pemberitahuan pindah),
  `deep_research/` (`agent.py`, `research_agent/{prompts,tools}.py`,
  `research_agent.ipynb`, `pyproject.toml` dengan `deepagents>=0.2.6`).
- `langchain-ai/deepagents`, commit `23b83ad` (2026-08-21),
  `git clone --depth 1`. Dibaca: seluruh `examples/` (14 contoh, 10 pemanggilan
  `create_deep_agent`), `libs/code/deepagents_code/agent.py`,
  `libs/cli/deepagents_cli/deploy/project.py`,
  `libs/cli/tests/unit_tests/deploy/test_project.py`,
  `libs/partners/daytona/{README.md,langchain_daytona/sandbox.py}`.

Paket terinstal `[code]` (`deepagents==0.7.8`, `langchain==1.3.16`) di
`references/recipes/.venv/lib/python3.13/site-packages/` — daftar file
lengkapnya ada di [`api-reference.md`](api-reference.md) §Sumber.

Perintah audit yang dijalankan tercatat di
`.superpowers/sdd/2026-08-23-agent-harness-kb/task-11-report.md`.

## Kesimpulan

Pertanyaan di kepala file ini: **apakah cara KB ini memakai `deepagents` wajar,
atau modifikasi asal yang kebetulan jalan?**

**Wajar.** 27 pola diaudit. Terhadap contoh maintainer yang masih hidup
(`deepagents/examples/`): 14 cocok, 4 varian, 9 tidak muncul. Terhadap CLI
resmi (`libs/code/`): 17 cocok, 3 varian, 6 tidak muncul, 1 tidak berlaku.
Sembilan belas entri divergence log ditulis; **setiap** baris `tidak`/`varian`
punya alasan tertulis, dan **nol pola dihapus** karena menyimpang tanpa alasan.
Tidak ditemukan satu pun tempat di mana KB ini menulis kode custom di lapisan
yang sudah punya extension point — kekhawatiran yang memicu audit ini.

Yang tidak wajar justru ditemukan di arah sebaliknya: **dua klaim "vanilla"
milik KB ini sendiri terbukti salah** (D-01 dan D-06), keduanya membuat
perilaku maintainer terlihat lebih seragam daripada kenyataannya. Keduanya
sudah diperbaiki di file sumbernya.

Kesimpulan ini punya tiga batas yang sudah dinyatakan di kepala file:
`deepagents-quickstarts` sudah diarsipkan sehingga perbandingan terhadapnya
nyaris tak bermakna; `deepagents` masih muda sehingga sebagian permukaannya
belum punya praktik komunitas; dan dua belas dari 51 klaim `[ours]` adalah
penilaian kami, bukan kanon. Yang paling perlu ditinjau ulang saat library
matang tercantum di akhir §Roster.
