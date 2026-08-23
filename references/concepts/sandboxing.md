# Sandboxing

## Masalah

Tool `execute` — kode yang ditulis LLM, dijalankan sebagai perintah shell
nyata — adalah permukaan tool yang paling berbahaya di harness manapun.
Beda dari tool bertipe/berskema (baca file, panggil API tertentu) yang
argumennya bisa divalidasi sebelum eksekusi, isi command shell bisa berupa
apa saja yang model putuskan untuk ditulis, dan validasi "apakah command
ini aman" secara umum tidak decidable. Pertanyaan yang harus dijawab
bukan "bagaimana mencegah command berbahaya" (tidak bisa dijamin general),
tapi **"kalau command itu berbahaya, seberapa jauh kerusakannya bisa
menyebar?"** — itulah blast radius, dan jawabannya murni fungsi dari
lapisan isolasi yang membungkus eksekusi itu.

Bahaya konkret yang harus dijawab lapisan isolasi: baca/tulis file di luar
yang dimaksud (termasuk file milik sesi/tenant lain kalau eksekusi
berbagi host), akses jaringan keluar tak terbatas (exfiltrasi data,
serangan ke sistem internal lain), konsumsi resource tak terbatas
(fork bomb, infinite loop menghabiskan CPU/memory host), dan — paling
sering luput — akses ke kredensial/socket yang kebetulan ada di
proses/container yang sama (Docker socket, environment variable API key
aplikasi, filesystem host di luar workspace).

## Pola

### Spektrum blast radius

| Lapisan isolasi | Yang dibatasi kalau kode jahat/buggy | Cold start | Contoh |
|---|---|---|---|
| Tanpa isolasi (subprocess di proses host) | Tidak ada — kode punya akses penuh sebagaimana proses yang menjalankannya | Nol (langsung jalan) | `LocalShellBackend` bawaan `deepagents` (lihat `## Di deepagents`) |
| Container (namespace + cgroup) | Filesystem/proses terisolasi dari host **kalau** dikonfigurasi benar; jaringan dan resource limit **opsional**, tidak otomatis | Detik (image sudah di-pull) | OpenHands docker runtime — satu container per task |
| MicroVM (kernel terisolasi per sandbox) | Kernel sendiri, bukan cuma namespace — blast radius tidak menyentuh host meski container escape klasik | Lebih lama dari container biasa, tapi provider menyediakan pause/resume untuk memotongnya | E2B, Daytona (mode default) |
| VM/host terdedikasi | Isolasi fisik penuh, termasuk dari sandbox tenant lain di infrastruktur yang sama | Paling lama, atau dibayar sebagai kapasitas selalu-nyala | Daytona VM sandbox (Linux/Windows VM eksplisit) |

Baris tabel ini naik dalam **jaminan isolasi**, dan turun dalam **latency +
biaya**. Tidak ada baris yang benar secara universal — pilihannya
tergantung siapa yang menulis kode yang dieksekusi (developer terpercaya di
Workspace Agent, vs pengguna anonim di produk publik) dan seberapa mahal
kalau blast radius meleset.

### OpenHands: container per task, tapi limit resource opsional

OpenHands men-spawn Docker container terpisah untuk tiap task, dengan
agent's code berjalan di dalam sandbox terisolasi dari host controller
`[docs]`. Tapi **isolasi resource** (CPU/memory) di dalamnya opsional,
bukan default: PR `All-Hands-AI/OpenHands#6616` menambahkan opsi
`memory_limit` ke `SandboxConfig` dan memetakannya ke parameter Docker
`mem_limit` saat start container — sebelum PR itu (dan kalau opsi ini tidak
diset), *"the container will have access to all available system
memory"* `[code]` — dikutip dari diff PR itu (`openhands/core/config/sandbox_config.py`,
`openhands/runtime/impl/docker/docker_runtime.py`). Container tanpa
`mem_limit` eksplisit adalah isolasi filesystem/proses, bukan isolasi
resource — kode jahat masih bisa menghabiskan seluruh memory host.

Detail kedua yang memperbesar blast radius kalau tidak disadari:
`entrypoint.sh` OpenHands memasang **Docker-out-of-Docker (DooD)** —
memasang socket Docker host ke dalam container, dan menambahkan user
container ke group yang punya akses socket itu `[docs]`. Ini pola yang
kelihatannya "container = terisolasi" tapi sebenarnya container itu
memegang kemampuan mengontrol container **sibling** lain di host yang
sama lewat socket yang sama — kalau kode dalam sandbox itu sendiri jahat,
DooD adalah jalan keluar dari batas container yang seharusnya
membatasinya. Ini contoh konkret defect class yang harus dijaga di seluruh
KB: nama "container isolation" tidak otomatis berarti kemampuan isolasi
yang dibayangkan — harus dicek konfigurasi sebenarnya.

> **Catatan repo (2026-08-23):** `All-Hands-AI/OpenHands` sudah di-redirect
> ke `OpenHands/OpenHands`, yang isinya berganti total jadi "Agent Canvas";
> agent coding aslinya pindah ke repo terpisah `OpenHands/software-agent-sdk`.
> Path `openhands/core/config/sandbox_config.py` dan
> `openhands/runtime/impl/docker/docker_runtime.py` yang dikutip di atas
> tidak lagi ada di struktur repo saat ini — klaimnya tetap berlaku untuk
> commit `db37f350` / PR `#6616` yang disitasi (snapshot historis, bukan
> path yang bisa ditelusuri hari ini). Lihat
> [`../systems/openhands.md`](../systems/openhands.md) untuk pivot repo ini
> secara lengkap.

### E2B dan Daytona: microVM, dua model penentuan resource yang berbeda

Keduanya microVM-class isolation per sandbox — kernel terpisah, bukan
sekadar namespace di kernel host — tapi cara ukuran resource ditentukan
berbeda, dan ini trade-off ops yang nyata:

- **E2B** — resource (CPU/memory) ditentukan di level **template/image**
  saat build (`e2b.toml`), bukan parameter per panggilan `create()` di
  Python SDK. `[code]` — `e2b/sandbox/main.py` (`class SandboxBase`):
  `default_sandbox_timeout = 300` (5 menit) sebagai default; parameter
  `create(template=None, timeout=None, metadata=None, ..., lifecycle=...)`
  `[code]` `e2b/sandbox_sync/main.py` tidak punya parameter `cpu`/`memory`
  langsung — resource envelope sudah tetap begitu template dipilih.
  Lifecycle: `lifecycle.on_timeout` bisa `"kill"` atau `"pause"`; pause
  dengan `keep_memory=False` menjatuhkan state in-memory dan hanya
  mempertahankan filesystem — resume dari kondisi itu **cold-boot ulang**
  dari disk, bukan lanjut dari memory snapshot `[docs]` (dikutip dari
  dokumentasi lifecycle E2B via WebFetch).
- **Daytona** — resource ditentukan **per panggilan create**, lewat objek
  `Resources(cpu, memory, disk, gpu, gpu_type)` `[code]` —
  `daytona/common/sandbox.py` (`class Resources`, atribut
  `cpu: int | None`, `memory: int | None` dalam GiB, `disk: int | None`
  dalam GiB, `gpu`/`gpu_type`). Lifecycle-nya juga lebih granular:
  `auto_stop_interval` (default 15 menit, 0 = nonaktif),
  `auto_pause_interval` (default 60 menit untuk sandbox class yang
  mendukung pause, saling eksklusif dengan `auto_stop_interval`),
  `auto_archive_interval` (default 7 hari), `auto_delete_interval`
  (nonaktif secara default), dan `ttl_minutes` sebagai batas keras
  wall-clock sejak pembuatan — `[code]` `daytona/common/daytona.py`
  (`class CreateSandboxBaseParams`, `class CreateSandboxFromImageParams`).

Catatan status: per pertengahan 2026, Daytona sudah tidak lagi
self-hostable — codebase produksinya dipindah ke repo closed-source;
paket `daytona` (klien Python) yang dikutip di atas tetap open dan yang
dipakai untuk verifikasi ini, tapi jaminan isolasi sisi server (bagaimana
persis microVM itu diimplementasikan) tidak lagi bisa dibaca dari source
publik `[inferred]` — perilaku sisi-server disimpulkan dari dokumentasi
publik, bukan dibaca dari implementasinya sendiri.

## Trade-off

- **Container per sesi (OpenHands) vs microVM per sandbox (E2B/Daytona)
  vs tanpa isolasi (deepagents default)** — tanpa isolasi paling murah dan
  paling cepat (zero cold start) tapi blast radius = seluruh proses/host
  yang menjalankannya; layak cuma kalau kode yang dieksekusi datang dari
  operator terpercaya (mis. Workspace Agent single-tenant lokal). Container
  murah dan cepat relatif, tapi jaminannya bergantung penuh pada
  konfigurasi (limit resource eksplisit, tidak ada DooD) — kalau
  konfigurasinya longgar, "container" cuma nama, bukan jaminan. MicroVM
  memberi jaminan terkuat yang masih terjangkau untuk multi-tenant publik,
  dengan biaya cold-start lebih tinggi dan ketergantungan pada provider
  pihak ketiga (dan untuk Daytona per 2026, ketergantungan pada layanan
  closed-source, bukan self-hosted).
- **Resource ditentukan di build-time (E2B) vs call-time (Daytona)** —
  build-time lebih sederhana untuk operasi (satu image, kapasitas
  predictable untuk capacity planning) tapi tidak bisa di-right-size per
  task — `pip list` yang ringan dapat envelope resource yang sama dengan
  build berat. Call-time (Daytona `Resources(...)`) lebih fleksibel tapi
  menambah permukaan yang harus divalidasi: kalau nilai `cpu`/`memory`
  datang dari argumen yang bisa dipengaruhi output model atau input user,
  itu harus dibatasi ceiling di sisi aplikasi sebelum diteruskan ke SDK —
  `[ours]`, bukan sesuatu yang dipaksakan SDK Daytona sendiri (SDK
  menerima nilai apa pun yang valid secara tipe); vanilla-nya adalah
  meneruskan nilai apa pun yang diminta caller mentah-mentah ke API
  Daytona, kita memilih menambah validasi ceiling di sisi aplikasi karena
  argumen resource yang bisa dipengaruhi hasil generate model adalah
  permukaan abuse (minta `cpu=64` berulang) yang tidak boleh dipercaya
  begitu saja.
- **Cold start murni vs warm pool** — dibahas lebih lanjut di
  `scaling.md`, relevan di sini karena `on_timeout: "pause"` (E2B) dan
  `auto_pause_interval` (Daytona) ada justru untuk memotong biaya
  cold-start lewat resume, bukan create dari nol — keduanya menyediakan
  primitive-nya, keputusan memakainya untuk warm pool ada di lapis
  scaling.

## Di deepagents

`execute` di `deepagents` cuma jalan lewat backend yang mengimplementasi
`SandboxBackendProtocol` — protokol itu sendiri **tidak** menjamin
isolasi apa pun; ia cuma kontrak interface (§Backend filesystem
`../systems/deepagents.md`). Isolasi sungguhan bergantung sepenuhnya pada
implementasi backend yang dipasang:

| Backend | Isolasi eksekusi |
|---|---|
| `LocalShellBackend` (bawaan) | Tidak ada — `subprocess.run(shell=True)` di proses/host yang sama, tanpa validasi isi command selain cek non-kosong; `virtual_mode` cuma membatasi operasi file (`read_file`/`write_file`/dst), **tidak** membatasi `execute()`. Secara eksplisit dilabeli *"not the default; it must be explicitly provided by the user"* di `THREAT_MODEL.md` `deepagents`. `[code]` — [`../systems/deepagents.md`](../systems/deepagents.md) §6 (kutipan langsung `THREAT_MODEL.md`). |
| `LangSmithSandbox` | Isolasi mengikuti jaminan sandbox terkelola LangSmith, bukan proses host — satu-satunya implementasi `SandboxBackendProtocol` selain `LocalShellBackend`/`FilesystemBackend` yang disebut eksplisit di source. `[code]` — `deepagents/backends/langsmith.py`. |
| Backend kustom (mis. pembungkus E2B/Daytona) | `deepagents` **tidak** menyediakan backend E2B/Daytona bawaan — memakai isolasi microVM berarti mengimplementasikan `SandboxBackendProtocol` sendiri yang membungkus SDK E2B/Daytona (buat sandbox, kirim command, kembalikan hasil sesuai kontrak protocol). `[code]`+`[inferred]` — disimpulkan dari daftar backend di §Backend filesystem yang tidak menyebut keduanya. |

Implikasi langsung: memilih baris mana dari tabel "Spektrum blast radius"
di atas, untuk proyek berbasis `deepagents`, murni ditentukan oleh backend
mana yang disuntikkan ke `create_deep_agent(backend=...)` — bukan sesuatu
yang `deepagents` putuskan sendiri secara default selain memberi
`LocalShellBackend` sebagai opsi paling longgar (dan bukan default kalau
tidak diminta eksplisit).

## Sumber

- `[docs]` OpenHands — arsitektur runtime/sandbox (container per task,
  isolasi dari host controller), dikutip via WebFetch dari
  `docs.openhands.dev/openhands/usage/architecture/runtime`.
- `[code]` OpenHands `openhands/core/config/sandbox_config.py`,
  `openhands/runtime/impl/docker/docker_runtime.py` — field `memory_limit`
  dan pemetaannya ke `mem_limit` Docker, dibaca lewat diff PR
  `All-Hands-AI/OpenHands#6616` via WebFetch.
- `[docs]` OpenHands `containers/app/entrypoint.sh` — pola
  Docker-out-of-Docker (mount socket Docker host, tambah user ke group
  akses socket), dikutip via DeepWiki
  (`deepwiki.com/All-Hands-AI/OpenHands/3.1-docker-runtime`) yang
  mengutip baris `containers/app/entrypoint.sh#L31-L58` pada commit
  `db37f350`.
- `[code]` E2B Python SDK, paket `e2b` versi 2.45.1 dari PyPI, diunduh dan
  dibaca langsung: `e2b/sandbox/main.py` (`class SandboxBase`,
  `default_sandbox_timeout = 300`), `e2b/sandbox_sync/main.py` (signature
  `create(template, timeout, metadata, ..., lifecycle)`).
- `[docs]` E2B — semantik `lifecycle.on_timeout` (`"kill"`/`"pause"`) dan
  `keep_memory` saat pause/resume, dikutip via WebFetch dari dokumentasi
  E2B sandbox lifecycle.
- `[code]` Daytona Python SDK, paket `daytona` versi 0.205.1 dari PyPI,
  diunduh dan dibaca langsung: `daytona/common/sandbox.py` (`class
  Resources`: `cpu`, `memory`, `disk`, `gpu`, `gpu_type`),
  `daytona/common/daytona.py` (`class CreateSandboxBaseParams`:
  `auto_stop_interval`, `auto_pause_interval`, `auto_archive_interval`,
  `auto_delete_interval`, `ttl_minutes`; `class
  CreateSandboxFromImageParams`: `resources: Resources | None`).
- `[inferred]` Status self-hosting Daytona (produksi jadi closed-source
  per pertengahan 2026) — disimpulkan dari dokumentasi/analisis pihak
  ketiga yang dikutip via WebSearch, bukan diverifikasi langsung dari
  pengumuman resmi Daytona.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §6,
  §Backend filesystem — tier-1 reference terverifikasi Task 3, dikutip
  tanpa membaca ulang source.
