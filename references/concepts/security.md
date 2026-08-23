# Security

## Masalah

Model tidak punya cara struktural membedakan "instruksi dari user yang sah"
dari "teks yang kebetulan ada di hasil tool" — keduanya masuk context sebagai
token yang sama-sama meyakinkan, dan model dilatih mengikuti instruksi yang
meyakinkan siapa pun sumbernya. Di agent loop, sebagian besar konten yang
masuk context **bukan** dari user: hasil web fetch, isi dokumen retrieval,
respons API, isi file yang dibaca tool. Setiap satu dari itu adalah jalur
serangan yang tidak pernah lewat input filter sama sekali (yang biasanya
cuma memeriksa pesan pertama user) — penyerang tidak perlu bicara ke chat,
cukup menaruh instruksi di halaman web/dokumen/email yang **akan** dibaca
agent atas nama user yang sah. `[docs]` OWASP Gen AI Security Project
menandai ini LLM01:2025 Prompt Injection, dengan varian *indirect* persis
pola di atas: "attackers embed instructions in documents, websites, or other
content that the LLM later processes" — dan menjadikannya risiko #1 untuk
edisi kedua berturut-turut.

Masalah kedua adalah kombinasi dari yang pertama dengan agency: agent
biasanya memegang satu identitas layanan (API key operator, service account,
bot token) yang dipakai untuk **semua** user, bukan identitas per-user yang
sempit. Kalau tool call yang dieksekusi memakai otoritas penuh identitas
layanan itu — bukan otoritas yang dipersempit ke user dan aksi yang sedang
diminta — agent jadi *confused deputy*: identitas layanannya sah, tapi
lingkup aksinya tidak seharusnya sebesar itu. `[docs]` OWASP GenAI
merumuskan persis kombinasi ini: "the combination of tools performing
actions on behalf of users with exposure to untrusted input effectively
allows attackers to make these tools do whatever they want" (LLM06:2025
Excessive Agency) — prompt injection dan confused deputy bukan dua risiko
independen, satu adalah jalan masuk untuk yang lain.

Masalah ketiga khusus multi-user: retrieval (RAG) py permukaan otorisasi
sendiri, terpisah dari database aplikasi. `isolation-and-scoping.md` dan
`persistence-schema.md` sudah menetapkan model scope `user_id` + RLS untuk
tabel Postgres aplikasi — file ini **tidak mengusulkan model baru**, tapi
index retrieval (vector store, search engine) sering **bukan** Postgres yang
sama, tidak otomatis ikut RLS yang sudah ditegakkan di tabel lain, dan bisa
bocor lewat bug yang bentuknya identik dengan yang sudah dijelaskan
`isolation-and-scoping.md` §Masalah untuk `WHERE` manual — cuma di sistem
yang berbeda.

Masalah keempat: agent yang menulis kode (arketipe Generative Builder) bisa
menaruh secret sungguhan ke file yang digenerate — baik karena secret itu
memang ada di context (env var/connection string yang dibaca lalu dikutip
ulang jadi contoh) maupun karena agent men-generate placeholder yang
kebetulan berbentuk valid dan kelak diperlakukan sebagai secret asli.

## Pola

### Prompt injection lewat hasil tool — pertahanan berlapis, bukan satu filter

Tidak ada satu guardrail yang menutup ini sendirian; tiga lapis yang saling
melengkapi (dirujuk dari `guardrails.md` titik 1-3, tidak diusulkan ulang di
sini):

1. **Tandai konten tak-dipercaya secara eksplisit** — hasil tool/retrieval
   ditandai (delimiter/metadata role) sebagai data, bukan instruksi, saat
   masuk state (guardrail titik 2). Ini sinyal untuk guardrail lain dan
   untuk model, **bukan** pencegah — sebuah tag tidak menghentikan model
   yang tetap memutuskan mengikuti instruksi di dalam data yang ditandai.
2. **Least-privilege tool scope sebagai pertahanan kedua** — bahkan kalau
   injeksi berhasil membujuk model, model cuma bisa memanggil tool yang
   memang di-allowlist untuk peran/konteks itu (guardrail titik 3). Injeksi
   yang berhasil tapi tool-nya dibatasi = blast radius kecil.
3. **Instruksi yang datang lewat hasil tool tidak pernah dipendekkan jalur
   gerbangnya** — kalau agent "menyimpulkan" instruksi baru dari hasil tool
   lalu langsung mengeksekusinya, itu instruksi baru yang wajib lewat gerbang
   approval/allowlist yang sama seperti instruksi dari user (guardrail
   titik 3, approval gate) — tidak ada jalur pintas karena "instruksinya
   masuk akal".

### Confused deputy & penyempitan scope token

Pola penanggulangan: jangan pernah beri agent kredensial identitas-layanan
penuh untuk dipakai apa adanya di tiap tool call. Sebagai gantinya, **mint
kredensial sempit per turn/tool-call** yang merefleksikan (a) `user_id` yang
sedang diproses dan (b) aksi minimum yang dibutuhkan tool itu — bukan
otoritas penuh identitas layanan:

- Untuk akses Postgres: ini **persis** pola `SET LOCAL app.current_user_id`
  yang sudah ditetapkan `isolation-and-scoping.md` — koneksi yang dipakai
  tool tetap satu identitas DB, tapi RLS memaksa setiap query di koneksi itu
  discope ke `user_id` aktif terlepas dari apa yang diminta model. Agent
  yang berhasil dibujuk menjalankan query sewenang-wenang tetap tidak bisa
  melihat baris user lain — bukan karena modelnya jujur, tapi karena
  Postgres yang menegakkannya di luar jangkauan model.
- Untuk API eksternal (Slack, GitHub, dst.): kalau provider mendukung token
  bercakupan sempit (GitHub App installation token per-repo, token OAuth
  per-user Slack), pakai itu per turn — bukan satu bot token app-wide yang
  disuntik ke semua tool call terlepas siapa yang minta.

### Kebocoran otorisasi di retrieval multi-user

Model scope tetap `user_id` seperti yang sudah ditetapkan
`isolation-and-scoping.md`/`persistence-schema.md`. Yang berbeda di sini:
retrieval sering punya **index kedua** (vector store terpisah, search
engine) yang tidak ikut RLS Postgres, dan filter otorisasi di index itu
harus ditegakkan sendiri:

- **Filter scope di dalam query ANN, sebelum top-k dihitung** — bukan
  ambil top-k dari seluruh index lalu buang hasil yang bukan milik user
  (query yang "lupa" filter itu = tetap balik top-k dari seluruh index,
  bug yang bentuknya identik dengan `WHERE` manual yang lupa filter di
  `isolation-and-scoping.md` §Masalah, cuma sistemnya vector store bukan
  Postgres).
- Kalau vector store yang dipakai mendukung metadata filter native (mis.
  filter `user_id` yang diterapkan **sebelum** pencarian similarity, bukan
  post-filter di aplikasi), pakai itu — post-filter di aplikasi berarti
  similarity score top-k sudah dihitung dari kandidat lintas-user, dan kalau
  post-filter itu lupa ditulis di satu endpoint, kebocorannya identik
  dengan RLS yang lupa dipasang.

### Scan secret di kode yang digenerate

Titik penegakan sama dengan `guardrails.md` titik 4 (Output) — tidak
diusulkan ulang, cuma dua sumber secret yang perlu dibedakan penanganannya:

- **Secret asli yang sudah ada di context** (env var, connection string yang
  dibaca tool lalu dikutip model ke file baru) — dicegah di titik Input/
  Retrieval dengan redaksi sebelum konten itu masuk context sama sekali
  (pola sama dengan `PIIMiddleware`, tapi detector-nya pola secret:
  `sk-…`, `AKIA…`, private key PEM header, dst.), bukan disaring belakangan
  di Output.
- **Placeholder yang kebetulan valid-looking** — dicegah di titik Output/
  pre-write: scan pola secret pada diff yang akan ditulis, sebelum
  `write_file`/`edit_file` commit ke disk. Tooling-nya sama seperti untuk
  kode yang ditulis manusia (mis. kelas gitleaks/trufflehog) — kode yang
  ditulis agent tidak butuh perlakuan spesial, cuma titik pemasangannya
  wajib **sebelum** commit, bukan sesudah (lihat mode kegagalan fail-closed
  di `guardrails.md` untuk baris ini).

## Trade-off

- **Token bercakupan sempit per tool-call vs satu kredensial layanan
  dibagi** — token sempit adalah pertahanan-berlapis sungguhan (blast
  radius injeksi/kompromi terbatas ke satu user/satu aksi, persis yang
  dibutuhkan untuk menutup confused deputy) tapi menambah biaya infra nyata
  (layanan minting token, rotasi kredensial berumur pendek, kerja integrasi
  per provider tool). Kredensial dibagi itu murah di awal — itulah kenapa
  confused deputy umum terjadi di produk agent tahap awal — tapi
  penyempitan wajib diadopsi begitu tool menyentuh sesuatu yang privileged,
  bukan ditunda tanpa batas.
- **Tag konten tak-dipercaya vs percaya penuh ke judgment model** — tag
  murah (deterministik, ditempel sekali di wrapper tool) tapi tidak
  menghentikan injeksi sendirian — cuma memberi sinyal ke lapis berikutnya.
  Wajib dikombinasi dengan allowlist tool (titik 3), bukan berdiri sendiri.
- **Filter scope di dalam query ANN vs index terpisah per user** — filter
  dalam query lebih murah operasional (satu index, satu pipeline ingest)
  tapi tiap query harus ingat memasang filter (bug shape yang sama dengan
  `WHERE` manual — pasti ada satu yang lupa di codebase yang hidup cukup
  lama, argumen yang sama seperti `isolation-and-scoping.md`); index
  terpisah per user membuat kesalahan itu mustahil secara struktural (tidak
  bisa query index yang salah tanpa menyebutnya eksplisit) dengan biaya
  jumlah index yang naik linear terhadap jumlah user — cuma masuk akal untuk
  populasi user terbatas (on-prem enterprise, puluhan tenant), bukan skala
  konsumen jutaan user.

## Di deepagents

`deepagents` tidak punya tool retrieval/web fetch bawaan dan
`PatchToolCallsMiddleware` cuma menambal `ToolMessage` yang dangling di
riwayat — tidak menandai level kepercayaan konten. `[code]` — dikutip
`../systems/deepagents.md` §Middleware bawaan. Akibatnya:

- **Penandaan konten tak-dipercaya** 100% tanggung jawab tool kustom yang
  dipasang aplikasi (retrieval/web fetch), lewat isi `ToolMessage` yang
  dikembalikan atau lewat hook `wrap_tool_call` yang membungkus hasilnya
  sebelum masuk state — sama seperti dijelaskan `guardrails.md` §Di
  deepagents titik 2, tidak diusulkan ulang.
- **Penyempitan scope token untuk Postgres** memakai pola persis yang sudah
  ditetapkan `isolation-and-scoping.md` §Di deepagents: `deepagents` tidak
  pernah membuat koneksi DB sendiri, jadi `SET LOCAL app.current_user_id`
  dipasang di lapis tool kustom yang membuat koneksi itu — dieksekusi tiap
  transaksi, bukan sekali per koneksi pool.
- **`FilesystemBackend`/`LocalShellBackend` tidak punya *hook* scoping** —
  fakta yang sama yang sudah dicatat `isolation-and-scoping.md`
  §Di deepagents, relevan lagi di sini karena kalau satu proses agent
  melayani banyak user di atas backend ini, prosesnya sendiri **adalah**
  deputy yang memegang identitas filesystem host — isolasi antar user harus
  dibangun di lapis proses/container, bukan sesuatu yang datang gratis dari
  `deepagents`. `[code]` — dikutip `../systems/deepagents.md` §Backend
  filesystem.
- **`StoreBackend(namespace=...)`** tetap jadi *hook* scoping resmi untuk
  state durable lintas-thread — dikutip ulang dari `isolation-and-scoping.md`,
  tidak diusulkan ulang di sini.
- **Scan secret pre-write** dipasang di titik yang sama dengan
  `guardrails.md` §Di deepagents titik 4 (`after_model` atau hook sebelum
  `write_file`/`edit_file` commit) — tidak ada mekanisme bawaan `deepagents`
  untuk ini.

## Sumber

- `[docs]` OWASP Gen AI Security Project — `genai.owasp.org/llmrisk/llm01-prompt-injection`
  (LLM01:2025 Prompt Injection, direct vs indirect) dan
  `genai.owasp.org/llmrisk/llm06-...` (LLM06:2025 Excessive Agency, kutipan
  langsung soal kombinasi tool-atas-nama-user + input tak-dipercaya =
  confused deputy).
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — model
  scope `user_id`, pola `SET LOCAL app.current_user_id`, `FORCE ROW LEVEL
  SECURITY`, fakta `FilesystemBackend`/`StoreBackend` — dikutip ulang tanpa
  mengusulkan model baru, sesuai instruksi task.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — DDL RLS yang
  jadi dasar argumen "otorisasi ditegakkan di DB, bukan di kode aplikasi
  yang bisa lupa".
- `[code]` [`guardrails.md`](guardrails.md) — titik 1-4 (input tagging, tool
  allowlist, approval gate, scan secret Output) yang dirujuk berulang di
  file ini sebagai titik penegakan konkret, tidak diusulkan ulang.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Middleware bawaan (`PatchToolCallsMiddleware`), §Backend filesystem — tier-1
  reference terverifikasi Task 3, dikutip tanpa membaca ulang source
  `deepagents` di task ini.
