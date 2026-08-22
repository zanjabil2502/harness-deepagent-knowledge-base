# MCP (Model Context Protocol)

## Masalah

Sebelum MCP, tiap pasangan (harness agent, sumber data/tool eksternal) butuh
integrasi custom: kode berbeda untuk menghubungkan agent X ke Google Drive,
agent X ke Postgres internal, agent Y ke Google Drive lagi (integrasi
duplikat karena harness beda) — kombinasi tumbuh N×M, dan tiap integrasi
membawa asumsi implisitnya sendiri soal lifecycle koneksi, autentikasi, dan
bentuk deskripsi tool. MCP menstandardisasi sisi protokolnya: satu server
MCP untuk Google Drive bisa dipakai harness agent mana pun yang punya klien
MCP, tanpa integrasi khusus per pasangan.

Masalah kedua, yang jadi peringatan eksplisit untuk file ini: **spesifikasi
MCP dan yang diimplementasikan klien tertentu bukan hal yang sama.**
Spesifikasi mendefinisikan kapabilitas opsional (`sampling`, `elicitation`,
`roots` di sisi klien) yang server bisa coba pakai — tapi dukungan klien
untuk kapabilitas opsional itu sangat tidak seragam di ekosistem nyata.
Nama "mendukung MCP" tidak memberi tahu kapabilitas mana yang sungguh
berfungsi di klien tertentu; itu harus dicek per klien, bukan diasumsikan
dari kepatuhan nominal terhadap spesifikasi.

## Pola

### MCP sebagai standar interop, bukan implementasi

MCP mendefinisikan protokol JSON-RPC antara **klien** (bagian dari harness
agent) dan **server** (proses/endpoint yang mengekspos tool/resource/
prompt) — bukan pustaka atau produk tunggal. Server MCP mengekspos tiga
kategori kapabilitas utama: `tools` (fungsi yang bisa dipanggil model,
setara `BaseTool` di LangChain), `resources` (konten yang bisa dibaca,
mis. file/baris database), `prompts` (template prompt siap pakai). `[docs]`
— MCP Specification, dikutip via WebFetch dari
`modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle`.

### Siklus hidup server: init → operasi → shutdown

Tiga fase wajib, urutannya normatif:

1. **Initialization** — klien **wajib** memulai dengan request `initialize`
   berisi versi protokol yang didukung, kapabilitas klien
   (`roots`/`sampling`/`elicitation`), dan info implementasi klien. Server
   membalas dengan kapabilitasnya sendiri (`tools`/`resources`/`prompts`/
   `logging`/`completions`) + info implementasi. Klien lalu **wajib**
   mengirim notifikasi `initialized` sebelum operasi normal dimulai. Klien
   **seharusnya tidak** mengirim request lain (selain ping) sebelum server
   membalas `initialize`; server **seharusnya tidak** mengirim request lain
   (selain ping/logging) sebelum menerima `initialized`. `[docs]` — dikutip
   langsung dari spec (*"The client MUST initiate this phase by sending an
   `initialize` request"*, *"the client MUST send an `initialized`
   notification"*).
2. **Version & capability negotiation** — klien mengirim versi protokol
   yang didukung (idealnya versi terbaru yang dikuasainya); server membalas
   versi yang sama kalau didukung, atau versi lain yang didukungnya kalau
   tidak. Kapabilitas yang dinegosiasikan di fase ini membatasi apa yang
   **boleh** dipakai selama fase Operation — memakai kapabilitas yang tidak
   sukses dinegosiasikan adalah pelanggaran protokol, bukan sekadar tidak
   optimal. `[docs]`
3. **Operation** — pertukaran normal (`tools/list`, `tools/call`,
   `resources/read`, dst.), dibatasi kapabilitas yang dinegosiasikan.
4. **Shutdown** — untuk transport `stdio`: klien menutup stream input
   proses server, tunggu server keluar, kirim `SIGTERM` kalau tidak keluar
   dalam waktu wajar, `SIGKILL` sebagai upaya terakhir. Untuk transport
   HTTP: shutdown = menutup koneksi HTTP terkait. `[docs]`

### Transport: `stdio` vs HTTP (`streamable_http`/`sse`)

| Transport | Cocok untuk | Autentikasi |
|---|---|---|
| `stdio` | Server MCP lokal, dijalankan sebagai subprocess di mesin yang sama dengan klien (mis. tool developer lokal) | **Tidak** memakai OAuth spec MCP — kredensial diambil dari environment proses `[docs]` |
| `streamable_http` / `sse` | Server MCP remote (SaaS pihak ketiga, layanan internal di jaringan berbeda) | OAuth 2.1 per request, lihat §Konfigurasi per user |

`[docs]` — MCP Authorization spec: *"Implementations using an STDIO
transport SHOULD NOT follow this specification, and instead retrieve
credentials from the environment."*

### Konfigurasi per user

Untuk deployment multi-user (asumsi proyek ini), satu server MCP remote
sering dipakai bersama oleh banyak user tapi **kredensial aksesnya per
user** (mis. server MCP Google Drive yang mewakili akun Drive masing-masing
user, bukan satu akun bersama). Mekanisme protokol yang menutup ini adalah
OAuth 2.1 di level HTTP transport, **bukan** konfigurasi statis level
server:

- Setiap request MCP membawa `Authorization: Bearer <access-token>` —
  token **wajib** disertakan di tiap request HTTP, bahkan dalam satu sesi
  logis yang sama (tidak ada "login sekali, token implisit untuk request
  berikutnya" di level transport). `[docs]` — MCP Authorization spec §Token
  Requirements.
- Token **wajib** divalidasi server terhadap audiens-nya sendiri (klaim
  audience token harus menyebut server MCP itu, lewat parameter `resource`
  RFC 8707) — server **wajib menolak** token yang valid tapi diterbitkan
  untuk resource lain. `[docs]`
- **Token passthrough dilarang eksplisit**: kalau server MCP sendiri
  memanggil API upstream lain, ia **tidak boleh** meneruskan token yang
  diterimanya dari klien MCP ke API upstream itu — ia harus jadi klien
  OAuth sendiri ke upstream dengan token terpisah. Ini instansiasi konkret
  dari *confused deputy* yang sudah dinamai
  [`security.md`](security.md) (§Masalah: agent yang memakai otoritas penuh
  satu identitas layanan untuk semua user, alih-alih otoritas yang
  dipersempit ke user dan aksi yang sedang diminta) — file itu memiliki pola umum
  confused-deputy/token-scope-sempit; MCP Authorization spec adalah kasus
  spesifik protokol ini yang menegakkannya sebagai **wajib**, bukan
  praktik baik opsional. `[docs]` — *"MCP server MUST NOT pass through the
  token it received from the MCP client"*.
- Praktis: kredensial per user (token OAuth Drive milik user A, bukan
  server-wide) hidup sebagai bagian dari **scope object** yang sudah dipakai
  [`isolation-and-scoping.md`](isolation-and-scoping.md) untuk data lain —
  konfigurasi koneksi MCP per user di-resolve dari `(user_id)`/`(tenant_id,
  user_id)` yang sama, bukan mekanisme terpisah.

### Klien nyata mengimplementasikan subset spesifikasi

Kapabilitas sisi-klien yang dideklarasikan opsional di spec (`roots` —
server bisa minta daftar direktori yang boleh diakses; `sampling` — server
bisa minta klien menjalankan LLM call atas nama server; `elicitation` —
server bisa minta input tambahan dari user di tengah interaksi) tidak
seragam dukungannya di ekosistem klien nyata. `[inferred]` — pola umum
ekosistem MCP yang diamati luas (kapabilitas opsional protokol jarang
diimplementasi merata oleh semua klien); klaim spesifik "klien X tidak
mendukung kapabilitas Y" tidak diverifikasi task ini untuk klien tertentu
di luar `deepagents`/`langchain` (lihat `## Di deepagents`, tidak
ditemukan dukungan `sampling`/`roots`/`elicitation` di paket yang
terinstal). Konsekuensi desain: **jangan** membangun fitur produk yang
bergantung pada server MCP bisa memakai `sampling`/`elicitation` terhadap
klien tanpa memverifikasi klien produksi yang dipakai benar-benar
mengimplementasikannya — kegagalannya senyap (server dengan sopan
mendeklarasikan kapabilitas itu di negosiasi, request-nya dikirim, tapi
klien yang tidak mengimplementasikannya bisa merespons error atau
mengabaikannya tergantung implementasi, bukan hal yang dijamin sama
seragam antar klien).

## Trade-off

- **MCP vs integrasi custom per sumber** — MCP menghindari duplikasi N×M
  di atas dan memberi ekosistem server siap pakai, dengan biaya: lapis
  protokol tambahan (JSON-RPC, negosiasi kapabilitas, lifecycle) untuk
  kasus yang sebenarnya cuma butuh satu panggilan API sederhana — tool
  custom langsung (`@tool` sekali tulis) tetap lebih murah untuk integrasi
  internal satu-kali yang tidak akan pernah dipakai harness lain.
- **`stdio` vs HTTP remote** — `stdio` sederhana (tidak butuh server
  jaringan, kredensial dari environment) tapi terikat satu mesin/proses,
  tidak cocok untuk server yang dipakai bersama banyak instance
  agent/banyak user; HTTP remote skalanya benar untuk multi-user (satu
  server MCP melayani banyak klien dengan token per user) dengan biaya
  operasional server yang harus dijaga uptime-nya sendiri dan permukaan
  keamanan tambahan (OAuth flow, validasi audience token).
- **Percaya kapabilitas yang dinegosiasikan vs verifikasi eksplisit per
  klien produksi** — percaya hasil negosiasi protokol (kalau server minta
  `sampling` dan klien "mendukung MCP", asumsikan itu jalan) lebih
  sederhana untuk dikembangkan tapi rapuh persis di titik yang dinamai
  §Pola di atas; verifikasi eksplisit (uji kapabilitas opsional terhadap
  klien produksi sungguhan sebelum bergantung padanya) lebih mahal di
  waktu pengembangan tapi menutup kelas defect "nama benar, kapabilitas
  tidak ada" yang paling mahal ditemukan belakangan.

## Di deepagents

Tidak ditemukan integrasi MCP bawaan (native) di `deepagents==0.7.8` atau
`langchain==1.3.16`/`langgraph==1.2.11` yang diinstal task ini — tidak ada
paket `langchain-mcp-adapters` atau modul `mcp` apa pun di
`references/recipes/.venv/lib/python3.13/site-packages/`. `[code]` —
diverifikasi lewat `ls` direktori site-packages, tidak ada `*mcp*` yang
cocok selain yang bukan bagian ekosistem MCP.

Jalur integrasi yang tersedia lewat ekosistem `langchain` (paket terpisah,
**tidak** terinstal/diverifikasi langsung di venv task ini, dikutip
`[docs]` dari README resmi):

- **`MultiServerMCPClient`** (paket `langchain-mcp-adapters`) — dikonfigurasi
  lewat dict yang memetakan nama server ke parameter koneksi (`command`/
  `args`/`transport: "stdio"` atau `url`/`transport: "http"`). Memanggil
  `await client.get_tools()` mengembalikan tool MCP yang sudah dikonversi
  jadi `BaseTool` LangChain — bentuk yang sama dipakai `tools=[...]` pada
  `create_deep_agent(...)`, jadi secara mekanis tool MCP masuk lewat jalur
  "tool custom aditif" yang sama seperti dijelaskan
  [`tool-design.md`](tool-design.md) §Di deepagents, tidak ada jalur
  integrasi MCP khusus di `deepagents` sendiri.
- Header runtime per-koneksi (mis. `"headers": {"Authorization": "Bearer
  TOKEN"}`) adalah jalur konkret untuk §Konfigurasi per user di atas —
  token per user disuntik di konfigurasi koneksi MCP, bukan hardcode di
  level server.
- `handle_tool_errors` (default `True`) mengatur apakah error dari
  pemanggilan tool MCP ditangkap dan dikembalikan sebagai `ToolMessage`
  error (sehingga model bisa mencoba lagi) atau dibiarkan naik sebagai
  exception.

Karena tidak terverifikasi langsung terhadap instalasi task ini, detail di
atas berlabel `[docs]` (README `langchain-ai/langchain-mcp-adapters`,
dikutip via WebFetch dari
`raw.githubusercontent.com/langchain-ai/langchain-mcp-adapters/main/README.md`)
— bukan `[code]` dari source yang dibaca langsung, konsisten dengan cara
`../systems/deepagents.md` §Sumber menandai paket yang tidak terinstal di
lingkungan ini (`deepagents-cli`/`langchain_daytona`).

## Sumber

- `[docs]` MCP Specification 2025-06-18, §Basic/Lifecycle — dikutip via
  WebFetch dari
  `modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle`, untuk
  urutan `initialize`/`initialized`, negosiasi versi & kapabilitas,
  shutdown per transport.
- `[docs]` MCP Specification 2025-06-18, §Basic/Authorization — dikutip via
  WebFetch dari
  `modelcontextprotocol.io/specification/2025-06-18/basic/authorization`,
  untuk alur OAuth 2.1, kewajiban header `Authorization: Bearer`, validasi
  audience token (RFC 8707), larangan token passthrough, dan pengecualian
  `stdio` (kredensial dari environment).
- `[docs]` README `langchain-ai/langchain-mcp-adapters` — dikutip via
  WebFetch dari
  `raw.githubusercontent.com/langchain-ai/langchain-mcp-adapters/main/README.md`,
  untuk `MultiServerMCPClient`, `load_mcp_tools`, transport yang didukung,
  konfigurasi header per koneksi.
- `[code]` Diverifikasi lewat `ls` isi
  `references/recipes/.venv/lib/python3.13/site-packages/` — tidak ada
  paket MCP terinstal di venv `deepagents==0.7.8` task ini.
- `[code]` [`tool-design.md`](tool-design.md) §Di deepagents — dasar klaim
  "tool MCP masuk lewat jalur `tools=[...]` aditif yang sama".
- `[code]` [`security.md`](security.md) §Masalah — dasar pola umum
  confused-deputy, tidak diulang di file ini.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — dasar
  pola scope object per user, dikutip untuk §Konfigurasi per user.
