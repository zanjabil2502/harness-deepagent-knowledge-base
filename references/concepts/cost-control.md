# Cost control

## Masalah

Agent loop yang tidak dibatasi membakar biaya semalam tanpa ada yang sadar
sampai tagihan datang — ini bukan spekulasi, ini konsekuensi langsung dari
fakta yang sudah dicatat `guardrails.md`: `deepagents` menaikkan
`recursion_limit` LangGraph ke **9999** sebagai jaring pengaman terhadap
task legit yang panjang, bukan sebagai batas biaya. Aplikasi yang tidak
memasang guardrail Loop-nya sendiri secara eksplisit efektif tidak punya
langit-langit biaya sampai 9999 langkah tercapai — angka yang cukup besar
untuk membakar biaya signifikan sebelum berhenti sendiri.

Masalah kedua: "budget" tanpa level yang jelas tidak berguna untuk dua
kegagalan yang bentuknya berbeda. Satu run yang jadi patologis (satu turn
menghabiskan ratusan dolar karena loop) butuh batas **per run** supaya satu
turn buruk tidak menghabiskan budget sebulan. Satu user yang memanggil agent
berkali-kali dengan run yang masing-masing terlihat wajar tapi jumlahnya
menumpuk (abuse tersebar, bukan satu turn ekstrem) butuh batas **per user**
teragregasi lintas run/waktu, yang tidak bisa ditangkap oleh batas per-run
saja. Menyamakan keduanya jadi satu angka membuat batas itu terlalu ketat
untuk tugas besar yang sah, atau terlalu longgar untuk abuse yang tersebar.

Masalah ketiga: tanpa atribusi biaya ke langkah spesifik, alert budget cuma
bilang "sesuatu mahal", bukan "apa yang harus diperbaiki" — versi
cost-specific dari masalah "agent gagal diam-diam" di `observability.md`.

## Pola

### Dua level budget: run dan user

- **Per run/thread** — dua batas berbeda yang sering tertukar:
  `thread_limit` (akumulatif sepanjang satu thread percakapan, lintas
  banyak turn) dan `run_limit` (satu eksekusi/turn tunggal). Keduanya
  penting untuk alasan berbeda: `run_limit` menangkap satu turn yang
  spiral; `thread_limit` menangkap percakapan yang terus berlanjut tanpa
  batas lintas banyak turn yang masing-masing terlihat wajar sendiri-
  sendiri. Mekanisme konkret ada di `guardrails.md` titik 5
  (`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`), tidak diusulkan
  ulang di sini.
- **Per user** — teragregasi lintas run/thread/jendela waktu (mis. cap
  dolar harian/bulanan per `user_id`), dan ini **tidak** bisa ditegakkan
  middleware `deepagents`/`langchain` manapun karena middleware itu cuma
  melihat satu eksekusi graph pada satu waktu, tidak punya memori lintas
  run. Wajib ditegakkan di lapis aplikasi: akumulasi biaya per `user_id`
  disimpan (Postgres/Redis), dicek **sebelum** turn baru diizinkan mulai
  (preflight check, bukan post-hoc setelah biaya sudah terjadi) — scope
  `user_id`-nya sama persis dengan yang sudah ditetapkan
  `isolation-and-scoping.md`, tidak diusulkan model baru.
- **Kill switch** — dua lapis: otomatis (dari batas run/user di atas,
  `exit_behavior="error"`/`"end"` di `guardrails.md`, plus
  `cancel_async_task` untuk task background) dan **manual/operator**,
  independen dari deteksi otomatis manapun — untuk kasus mode kegagalan
  baru yang belum tertangkap detektor mana pun, operator butuh cara
  menghentikan run user tertentu atau seluruh sistem **sekarang**, bukan
  menunggu batas numerik tersentuh.

### Deteksi loop liar

Deteksi oscillation/no-progress (baris guardrail titik 5 di `guardrails.md`,
mekanismenya tidak diusulkan ulang di sini) punya sudut pandang biaya
tersendiri: loop bisa **"on-budget" menurut hitungan langkah** tapi tetap
murni pemborosan — mengulang tool call yang gagal dengan argumen nyaris
identik, masing-masing tetap memakan token nyata, tanpa membuat progres.
Batas numerik (`thread_limit`/`run_limit`) baru berbunyi setelah langkah
ke-N tercapai; deteksi oscillation bisa memotong lebih awal begitu polanya
kelihatan (mis. N panggilan tool berurutan dengan argumen/hasil identik) —
lebih murah daripada menunggu langit-langit numerik tersentuh, karena tiap
langkah tambahan yang dibiarkan berjalan sebelum limit tercapai tetap biaya
nyata yang sudah terbakar.

### Atribusi biaya per langkah

Biaya bukan pipeline terpisah dari tracing — ia atribut yang menempel di
span yang sama dengan yang sudah dijelaskan `observability.md` §Span per
langkah. `Langfuse` mengekstrak usage token per span generation
(`_parse_usage(response)`, ditulis ke `usage`/`usage_details` span) dan
punya field `cost_details` per span (default `cost_details={"total": 0}`
sebelum dihitung ulang dari usage × tabel harga model). `[code]` —
`langfuse/langchain/CallbackHandler.py` (baris memuat `_parse_usage`,
`usage_details`, beberapa default `cost_details={"total": 0}`). Konsekuensi
praktis: span per **langkah** (model call individual, bukan agregat turn)
berarti biaya juga teratribusi ke langkah spesifik — subagent mana, tool
apa, panggilan model ke berapa — bukan cuma "turn ini mahal", persis yang
dibutuhkan untuk menjawab "apa yang harus diperbaiki", bukan cuma "sesuatu
mahal".

## Trade-off

- **Batas per-run ketat vs longgar** — ketat mencegah satu turn membakar
  budget besar tapi memotong tugas besar yang sah (riset panjang, refactor
  lintas banyak file); longgar mengakomodasi tugas legit tapi memperlambat
  deteksi loop patologis. Default aman: `run_limit` cukup longgar untuk
  tugas terpanjang yang sah + wajib berpasangan dengan deteksi oscillation
  (bukan cuma limit numerik) supaya loop murni-buang-buang tetap terpotong
  sebelum limit numerik tersentuh.
- **Preflight check budget user (sebelum turn mulai) vs post-hoc (setelah
  turn selesai, baru dicek untuk turn berikutnya)** — preflight mencegah
  user yang sudah over-budget memulai run baru sama sekali (kill switch
  yang sungguh mencegah, bukan cuma mendeteksi setelah kejadian), dengan
  biaya satu query tambahan (baca akumulasi biaya user) di jalur kritis
  sebelum tiap turn mulai; post-hoc lebih murah per-turn tapi user tetap
  bisa memulai satu run mahal terakhir sebelum sistem sadar budget-nya
  habis — cocok untuk soft-limit (peringatan), tidak cocok untuk hard cap.
- **Kill switch otomatis-saja vs plus operator manual** — otomatis-saja
  lebih murah dibangun (tidak butuh panel operator) tapi buta terhadap mode
  kegagalan yang belum pernah dilihat/didefinisikan; kill switch manual
  menambah kerja (panel/endpoint operator, otorisasi siapa yang boleh
  menekannya) tapi menutup celah "detektor belum tahu bentuk kegagalan ini"
  yang otomatis-saja tidak pernah bisa menutup sendiri.

## Di deepagents

`deepagents` tidak punya akuntansi token/biaya bawaan — tidak ditemukan
modul semacam itu di source Task 3 (`deepagents/graph.py` dan middleware
terkait tidak menyebut usage/cost). `[inferred]` — disimpulkan dari tidak
ditemukannya modul akuntansi biaya di source `deepagents` yang sudah
dibedah Task 3. Konsekuensinya identik dengan §Di deepagents `guardrails.md`
titik 5: batas run/thread ditegakkan lewat `ToolCallLimitMiddleware`/
`ModelCallLimitMiddleware` (`langchain.agents.middleware`, bukan milik
`deepagents`, disuntik lewat `create_deep_agent(middleware=[...])`) — file
ini tidak mengusulkan mekanisme baru untuk itu, cuma menjelaskan sudut
pandang biayanya.

Dua hal spesifik yang relevan di sini:

- **Batas per user tidak bisa jadi middleware `deepagents`/`langchain` sama
  sekali** — bukan cuma "belum ada", tapi secara struktural tidak bisa,
  karena middleware beroperasi dalam satu eksekusi graph (`create_deep_agent`
  yang sama dipanggil ulang tiap turn, tanpa memori lintas panggilan
  kecuali lewat `checkpointer`/`store` yang disuntik aplikasi). Akumulasi
  biaya per `user_id` wajib hidup di lapis aplikasi/DB, dicek sebelum
  `create_deep_agent(...).invoke(...)` dipanggil — bukan di dalam middleware
  apa pun yang dipasang ke agent itu sendiri.
- **`AnthropicPromptCachingMiddleware`** (selalu terpasang tanpa syarat,
  no-op untuk provider non-Anthropic) langsung memengaruhi biaya nyata —
  cache prompt provider-spesifik mengurangi token yang ditagih penuh untuk
  prefix yang tidak berubah antar panggilan. `[code]` — dikutip
  `../systems/deepagents.md` §Middleware bawaan. Ini bukan guardrail biaya
  (tidak ada batas yang ditegakkan), tapi relevan untuk atribusi: span yang
  menunjukkan token cache-hit vs cache-miss (kalau backend tracing
  mencatatnya) menjelaskan kenapa biaya satu langkah bisa jauh lebih rendah
  dari perkiraan naif token-count × harga penuh.

## Sumber

- `[code]` [`guardrails.md`](guardrails.md) — titik 5 (Loop): mekanisme
  `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`, `exit_behavior`,
  `cancel_async_task`, deteksi oscillation, serta peringatan
  `recursion_limit=9999` — dikutip ulang tanpa mengusulkan mekanisme baru.
- `[code]` `langfuse/langchain/CallbackHandler.py` (Langfuse Python SDK
  4.14.4, `pip install langfuse` di venv riset terpisah) — `_parse_usage`,
  field `usage`/`usage_details`/`cost_details` per span.
- `[code]` [`observability.md`](observability.md) — §Span per langkah,
  dasar klaim "biaya menempel di span yang sama dengan tracing", tidak
  diusulkan ulang.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — model
  scope `user_id` yang jadi dasar akumulasi biaya per user.
- `[inferred]`/`[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §1 (`recursion_limit` 9999), §Middleware bawaan
  (`AnthropicPromptCachingMiddleware`) — tier-1 reference terverifikasi
  Task 3; tidak ditemukan modul akuntansi biaya di source yang sudah
  dibedah Task 3, dikutip tanpa membaca ulang source `deepagents` di task
  ini.
