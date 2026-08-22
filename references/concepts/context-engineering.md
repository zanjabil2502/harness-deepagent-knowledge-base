# Context engineering

## Masalah

Context window yang penuh dengan riwayat tool call, hasil pencarian, dan
pesan lama terlihat seperti masalah tunggal dengan solusi jelas: kompaksi —
ringkas pesan lama jadi lebih pendek, kirim lebih sedikit token per call.
Instingnya benar untuk satu sumbu biaya (token per request) dan salah untuk
sumbu lain yang jarang ditulis siapa pun: **kompaksi merusak prefix prompt
cache**, dan begitu prefix berubah, penghematan dari mengirim lebih sedikit
token bisa kalah telak oleh hilangnya diskon cache-hit pada *setiap* call
berikutnya sampai cache alami itu kedaluwarsa lagi.

Mekanismenya, dikutip persis dari dokumentasi resmi Anthropic `[docs]`: cache
dibentuk sebagai **hierarki kumulatif** — `tools` → `system` → `messages`.
Tiap breakpoint (`cache_control`) menulis hash dari seluruh prefix sampai ke
titik itu; sistem **tidak** menulis entri untuk posisi sebelumnya. "Changes
at each level invalidate that level and all subsequent levels" — karena
hash-nya kumulatif, **mengubah blok apa pun di titik breakpoint atau
sebelumnya menghasilkan hash berbeda di request berikutnya**, dan cache-lookup
mundur (lookback window 20 blok) tidak menemukan entri lama untuk hash baru
itu. Akibatnya satu ringkasan yang menulis ulang pesan di tengah riwayat
tidak cuma memangkas `messages` — ia menggeser identitas prefix di titik itu
dan seterusnya, sehingga *seluruh* tail sesudahnya (termasuk apa pun yang
tadinya sudah di-cache di sana) jadi cache miss.

Biaya cache miss itu konkret dan berlipat, bukan cuma "sedikit lebih mahal":
menurut dokumentasi yang sama, token yang di-cache-write dikenakan **1.25×**
harga base (TTL 5 menit) atau **2×** (TTL 1 jam), sementara cache-hit hanya
**0.1×** — selisih 12.5× antara "prefix masih valid" dan "prefix baru saja
kau tulis ulang". Di layanan multi-user di mana banyak turn berurutan
bergantung pada prefix yang sama (system prompt + tool definition + riwayat
awal yang stabil), satu keputusan kompaksi yang salah tempat membayar harga
write-cache penuh berulang kali — sekali per turn — sampai konten itu stabil
lagi cukup lama untuk ter-cache ulang. Ini yang jarang ditulis siapa pun
karena dua metrik itu (token terkirim vs cache-hit rate) muncul di baris
tagihan yang berbeda dan jarang dilihat berdampingan.

## Pola

### Urutan konteks ramah-cache: stabil di depan, volatil di belakang

Hierarki cache Anthropic (`tools` → `system` → `messages`) `[docs]` bukan
detail implementasi yang bisa diabaikan — ia **adalah** aturan urutan
konteks: taruh apa yang paling jarang berubah paling awal (definisi tool,
instruksi sistem statis, skeleton dokumen/repo map yang stabil lintas turn),
dan apa yang paling sering berubah paling akhir (giliran percakapan
terbaru, hasil tool yang baru saja dipanggil). Breakpoint ditaruh di ujung
blok stabil terakhir — **bukan** di ujung blok yang berubah tiap request.
Dokumentasi Anthropic sendiri memberi contoh kesalahan paling umum: taruh
breakpoint di blok yang memuat timestamp per-request, dan cache miss total
tiap kali karena hash-nya selalu baru; perbaikannya adalah memindahkan
breakpoint ke blok stabil terakhir **sebelum** konten yang berubah `[docs]`.

### Kompaksi bukan langkah pertama — teknik struktural lebih murah kalau bisa

Sebelum menulis-ulang riwayat, tiga teknik menurunkan pertumbuhan konteks
tanpa pernah menyentuh prefix yang sudah stabil:

- **Bentuk tool output di sumbernya, jangan ringkas belakangan** — prinsip
  *Agent-Computer Interface* SWE-agent: file viewer bawaan menampilkan 100
  baris per giliran (bukan `cat` seluruh file), dan command pencarian
  direktori sengaja dibuat ringkas — cuma daftar file yang match, tanpa
  konteks tiap match, karena tim SWE-agent menemukan versi yang lebih
  verbose "too confusing for the model" sekaligus lebih boros token.
  `[code]` `docs/background/aci.md`, repo `SWE-agent/SWE-agent` (dibaca via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/docs/background/aci.md`).
  Konsekuensinya: hasil tool yang masuk context sejak awal kecil, jadi tidak
  pernah butuh diringkas nanti — masalah dicegah di hulu, bukan dibersihkan
  di hilir.
- **Evict, jangan rewrite** — `FilesystemMiddleware` `deepagents` memindah
  hasil tool besar (>20000 token) ke file di backend begitu melewati
  ambang, menyisakan preview head/tail + rujukan path di posisi pesan
  aslinya (`TOO_LARGE_TOOL_MSG`). `[code]` dikutip `../systems/deepagents.md`
  §2. Ini beda mekanisme dari kompaksi meski efeknya sama-sama "hemat
  token": eviction terjadi pada pesan yang **baru ditambahkan** (di ujung
  volatil, sebelum breakpoint manapun sempat menandainya), bukan menulis
  ulang pesan lama yang sudah jadi bagian prefix ter-cache.
- **Hitung ulang konteks tiap turn dari sumber, jangan akumulasi lalu
  pangkas** — repo map Aider membangun graf definisi/referensi simbol lintas
  file, memberi bobot lebih tinggi ke identifier yang disebut di chat/nama
  panjang (`mul *= 10`) dan file yang sedang dibuka (`mul *= 50`), lalu
  menjalankan `networkx.pagerank` untuk meranking file mana yang paling
  relevan disertakan. `[code]` `aider/repomap.py` baris 480-511 (bobot),
  365-380 (pagerank), repo `Aider-AI/aider`. Ukuran keluaran dijaga pas
  anggaran token lewat binary search jumlah tag yang disertakan
  (`get_ranked_tags_map_uncached`, baris 629-703) `[code]` `aider/repomap.py`.
  Pola ini menghindari pertanyaan "kapan kompaksi" sama sekali untuk bagian
  konteks itu — repo map dihitung ulang tiap kali, bukan ditulis sekali lalu
  diringkas belakangan.

### Kalau kompaksi tak terhindarkan, jaga batas pemisahan pesan tetap valid

Kompaksi yang memotong di tengah pasangan `tool_use`/`tool_result` membuat
provider menolak request (setengah pasangan jadi anak yatim). Cline
menegakkan ini eksplisit: titik potong "aman" hanya di pesan user berjenis
teks atau di pesan asisten (karena `tool_use`-nya dan hasilnya tetap di sisi
yang sama dari potongan); pesan user yang isinya cuma `tool_result` **tidak
pernah** jadi titik potong yang aman karena `tool_use` pasangannya ada di
pesan asisten sebelumnya dan akan terlipat ke ringkasan, meninggalkan
`tool_result` yatim. `[code]` `sdk/packages/core/src/extensions/context/compaction-shared.ts`
baris 317-325, repo `cline/cline`. `deepagents` menangani kelas masalah yang
sama dengan cara berbeda — bukan mencegah potongan tak-aman, tapi menambal
sesudahnya: `PatchToolCallsMiddleware` menyisipkan `ToolMessage` sintetis
untuk tool call yang jadi dangling akibat kompaksi/interrupt, menjaga
riwayat tetap valid untuk model berikutnya. `[code]` dikutip
`../systems/deepagents.md` §2.

Cline juga membedakan **kapan** kompaksi dipicu dari **berapa banyak** yang
dipangkas: trigger di 90% anggaran input yang dapat dipakai
(`COMPACTION_TRIGGER_RATIO = 0.9`), target turun ke 70%
(`DEFAULT_TARGET_RATIO = 0.7`), dan 20000 token terbaru
(`DEFAULT_PRESERVE_RECENT_TOKENS`) selalu dipertahankan verbatim, tidak ikut
dilipat. `[code]` `sdk/packages/core/src/extensions/context/compaction-shared.ts`
baris 12-21. Pola "sisakan tail besar verbatim" ini selaras dengan aturan
urutan ramah-cache di atas — tapi **tidak menyelesaikan** masalah
invalidasi: bagian yang dilipat ada di *tengah* prefix, dan menurut mekanisme
hierarki di atas, menulis ulang tengah tetap menggeser hash semua breakpoint
di titik itu dan sesudahnya. Menyisakan tail verbatim mengurangi berapa
banyak yang perlu ditulis ulang ke cache setelah kompaksi (tail-nya tidak
perlu ditulis ulang), tapi tidak membuat kompaksi itu sendiri cache-neutral.

## Trade-off

- **Kompaksi vs biarkan cache-hit jalan** — bandingkan dua angka sebelum
  memutuskan: (a) token yang dihemat dengan meringkas dikali harga token
  base, versus (b) harga cache-write penuh (1.25×/2× base, bukan 0.1×) untuk
  seluruh prefix yang sekarang harus ditulis ulang, dikali berapa banyak
  turn lagi yang diperkirakan terjadi dalam TTL sebelum cache itu kedaluwarsa
  secara alami. Kalau sesi masih akan berlanjut banyak turn dalam jendela
  TTL, kehilangan cache-hit di semuanya biasanya lebih mahal dari sekali
  penghematan token kompaksi. Kompaksi baru jelas untung kalau: (i) context
  window benar-benar mendekati limit keras (tidak ada pilihan), atau (ii)
  sesi memang akan diam lama sesudahnya (cache toh akan kedaluwarsa sendiri,
  jadi tidak ada cache-hit yang hilang dengan menuliskannya lebih awal).
- **Teknik struktural (ACI, eviction, repo map dihitung ulang) vs kompaksi
  generik** — struktural mencegah pertumbuhan di sumbernya dan tidak pernah
  menyentuh prefix stabil, tapi butuh kerja desain per jenis tool/konten di
  muka (window viewer, threshold eviction, graf ranking) dan tidak generik —
  tiap tool baru butuh pemikiran sendiri. Kompaksi generik (ringkas apa saja
  yang lama) bekerja untuk konten apa pun tanpa desain khusus, tapi selalu
  membayar ongkos cache di atas, dan reaktif (baru jalan setelah context
  sudah penuh, bukan mencegahnya).
- **Breakpoint di ujung blok besar (jarang berubah) vs breakpoint lebih ke
  belakang (dekat konten terbaru)** — breakpoint yang menandai blok besar
  dan stabil (system prompt + definisi tool, seperti yang dipilih
  `AnthropicPromptCachingMiddleware` — menandai **blok terakhir** system
  message dan **tool terakhir** saja, satu breakpoint trailing untuk seluruh
  set tool `[code]` `langchain_anthropic/middleware/prompt_caching.py`
  baris 232-262, repo `langchain-ai/langchain`) memberi cache-hit rate
  tinggi karena jarang invalid, tapi kalau sesuatu di blok itu **harus**
  berubah (mis. isi memory yang disuntik ke system prompt), seluruh blok
  besar itu invalid sekaligus. Breakpoint yang ditaruh lebih dekat ke ujung
  volatil membatasi blast radius invalidasi tapi menyisakan lebih sedikit
  konten yang benar-benar ter-cache setiap saat.

## Di deepagents

`AnthropicPromptCachingMiddleware` (dari `langchain-anthropic`, disuntik
otomatis oleh `deepagents` lewat `append_prompt_caching_middleware`)
mengimplementasikan persis aturan "stabil di depan" di atas: ia menandai
**blok konten terakhir** dari system message dan **tool terakhir** dalam
daftar tool dengan `cache_control`, bukan tiap pesan — karena tool
didefinisikan sebagai satu blok kontiguo, satu breakpoint trailing pada tool
terakhir sudah men-cache seluruh set tool. `[code]`
`langchain_anthropic/middleware/prompt_caching.py` baris 42-56, 122-151, 232-262
(terinstal sebagai dependency `deepagents==0.7.8`,
`langchain-anthropic==1.6.1`, venv riset yang sama dengan `../systems/deepagents.md`).

Koreksi presisi atas apa yang dikutip `../systems/deepagents.md` §2 soal
urutan ini: dibaca ulang langsung dari `deepagents/graph.py` untuk task
ini, urutan konstruksi list-nya adalah `append_prompt_caching_middleware(
deepagent_middleware)` (baris 860) **lebih dulu**, baru `MemoryMiddleware`
ditambahkan sesudahnya (baris 861-865) kalau `memory` diisi — kebalikan
dari framing "memory dipasang sebelum tail prompt-caching" yang
disimpulkan dari prosa `../systems/deepagents.md`. `[code]`
`deepagents/graph.py` baris 860-865.

Mekanisme sesungguhnya yang membuat update memory **tidak** merusak prefix
cache bukan soal urutan antar-middleware itu — `MemoryMiddleware` punya
parameter `add_cache_control: bool = False` sendiri (`deepagents` men-set
`True` khusus untuk instance di stack utama), dan `wrap_model_call`-nya
(lewat `modify_request`, method internal yang dipanggilnya langsung di
baris pertama) menandai **blok terakhir** system message (setelah
kontennya sendiri disisipkan) dengan `cache_control` kalau flag itu aktif
dan `request.model` adalah `ChatAnthropic` — independen dari apakah
`AnthropicPromptCachingMiddleware` berjalan sebelum atau sesudahnya di
list. `[code]` `deepagents/middleware/memory.py` baris 193 (parameter
`add_cache_control`), 342-374 (`modify_request`, penandaan blok terakhir),
380, 394 (`wrap_model_call` memanggil `modify_request`); dipanggil dg
`add_cache_control=True` di `deepagents/graph.py` baris 861-866. Komentar
sumber di `deepagents/graph.py` baris 856-858 menyebut alasan berbeda
untuk urutan **profil harness vs memory** (bukan caching vs memory):
middleware ekstra profil disisipkan di antara middleware inti dan memory
secara sengaja "supaya update memory (yang mengubah system prompt) tidak
menginvalidasi prefix cache" milik konten profil — pola "stabil dulu,
volatil belakangan" dari `## Pola` di atas, diterapkan ke posisi profil
relatif terhadap memory, bukan ke posisi `AnthropicPromptCachingMiddleware`
relatif terhadap memory seperti klaim awal `../systems/deepagents.md`
sebelum dikoreksi. `[code]` `deepagents/graph.py` baris 856-858 (komentar
sumber, dikutip apa adanya). Detail ini juga sudah dipakai memperbaiki
`../systems/deepagents.md` §2 langsung (paragraf
`AnthropicPromptCachingMiddleware`) di task ini — bukan cuma dicatat di
sini, karena file itu tier-1 yang dibaca task-task lain sebagai otoritas.

Sisi lain dari koin: `SummarizationMiddleware` (juga default, selalu
terpasang) bekerja dengan menulis ulang segmen `messages` begitu token
terlampaui ambang yang dihitung dari profil model
(`compute_summarization_defaults`). `[code]` dikutip
`../systems/deepagents.md` §2. Menurut hierarki cache di atas, penulisan
ulang ini **selalu** menggeser hash level `messages` di titik itu —
`deepagents` tidak melakukan apa pun secara default untuk menahan trigger
`SummarizationMiddleware` sampai titik yang cache-neutral (mis. hanya
kompaksi tepat sebelum context window mentok, bukan pada ambang yang lebih
dini) — keputusan *kapan* threshold itu tercapai relatif terhadap siklus
TTL cache sepenuhnya diserahkan ke aplikasi pemanggil lewat parameter model
yang dipakai. `[inferred]` — disimpulkan dari tidak ditemukannya parameter
di `create_summarization_middleware`/`compute_summarization_defaults` yang
menyadari status cache TTL saat ini; ini bukan klaim bug, cuma observasi
bahwa dua mekanisme (`SummarizationMiddleware` dan
`AnthropicPromptCachingMiddleware`) berjalan independen tanpa saling
memberi tahu.

`FilesystemMiddleware` (evict tool result besar, lihat `## Pola` di atas)
adalah mitigasi tersedia yang **tidak** membayar ongkos ini, karena ia
bekerja pada pesan yang baru ditambahkan sebelum breakpoint manapun sempat
menandainya — konsekuensinya, menaikkan agresivitas eviction (menurunkan
`tool_token_limit_before_evict`) adalah tuas yang lebih murah untuk menahan
pertumbuhan context sebelum `SummarizationMiddleware` sempat terpicu sama
sekali, dibanding mengandalkan kompaksi sebagai satu-satunya katup.

## Sumber

- `[docs]` Anthropic — `platform.claude.com/docs/en/build-with-claude/prompt-caching`,
  hierarki cache `tools`→`system`→`messages`, mekanisme hash kumulatif per
  breakpoint, lookback window 20 blok, batas 4 breakpoint eksplisit, TTL
  5 menit/1 jam, pricing multiplier (write 1.25×/2×, read 0.1×), contoh
  kesalahan breakpoint pada konten yang berubah tiap request.
- `[code]` `langchain_anthropic/middleware/prompt_caching.py` (paket
  `langchain-anthropic==1.6.1`, dibaca dari
  `references/recipes/.venv/lib/python3.13/site-packages/`, venv yang sama
  dipakai `../systems/deepagents.md`) — `AnthropicPromptCachingMiddleware`,
  `_tag_system_message`, `_tag_tools`.
- `[code]` `deepagents/middleware/_prompt_caching.py` (venv sama) —
  `append_prompt_caching_middleware`, pemasangan otomatis tanpa syarat.
- `[code]` `deepagents/middleware/memory.py` baris 193, 342-374, 380, 394
  (venv sama) — parameter `add_cache_control`, `modify_request` (dipanggil
  `wrap_model_call`) menandai blok terakhir system message sendiri,
  independen dari `AnthropicPromptCachingMiddleware`.
- `[code]` `deepagents/graph.py` baris 856-866 (venv sama, dibaca ulang
  langsung untuk task ini) — urutan konstruksi list middleware utama
  (`append_prompt_caching_middleware` sebelum `MemoryMiddleware`
  ditambahkan), komentar sumber soal posisi middleware profil vs memory;
  dasar koreksi presisi atas `../systems/deepagents.md` §2 (diperbaiki
  langsung di task ini, lihat `## Di deepagents`).
- `[code]` `docs/background/aci.md`, repo `SWE-agent/SWE-agent`, dibaca via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/docs/background/aci.md` —
  prinsip desain ACI: linter gate, file viewer 100-baris, search ringkas.
- `[code]` `tools/search/config.yaml`, repo `SWE-agent/SWE-agent`, dibaca
  via `raw.githubusercontent.com/SWE-agent/SWE-agent/main/tools/search/config.yaml` —
  signature command pencarian yang dirujuk di `## Pola`.
- `[code]` `aider/repomap.py`, repo `Aider-AI/aider`, dibaca via
  `raw.githubusercontent.com/Aider-AI/aider/main/aider/repomap.py` — bobot
  personalisasi (baris 480-511), `get_ranked_tags` + `nx.pagerank` (baris
  365-380, 519-529), binary search anggaran token
  `get_ranked_tags_map_uncached` (baris 629-703).
- `[code]` `sdk/packages/core/src/extensions/context/compaction-shared.ts`,
  repo `cline/cline`, dibaca via
  `raw.githubusercontent.com/cline/cline/main/sdk/packages/core/src/extensions/context/compaction-shared.ts` —
  konstanta `COMPACTION_TRIGGER_RATIO`/`DEFAULT_TARGET_RATIO`/
  `DEFAULT_PRESERVE_RECENT_TOKENS` (baris 12-21), aturan titik-potong aman
  (baris 317-325).
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2
  Context (`SummarizationMiddleware`, `FilesystemMiddleware`,
  `AnthropicPromptCachingMiddleware`, urutan tail stack, alasan urutan
  memory-sebelum-caching) — tier-1 reference terverifikasi Task 3, dikutip
  tanpa membaca ulang source `deepagents/graph.py` di task ini kecuali file
  `_prompt_caching.py` dan `langchain_anthropic/middleware/prompt_caching.py`
  yang dibaca ulang langsung untuk task ini.
