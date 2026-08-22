# Guardrails

## Masalah

"Guardrail" hampir selalu menyusut jadi satu hal: content filter di output —
biasanya satu panggilan moderasi sebelum jawaban dikirim ke user. Itu cuma
menutup satu dari enam titik di mana kebijakan bisa (dan akan) dilanggar
dalam satu loop agent. Produk yang merasa "sudah punya guardrail" karena
memasang satu classifier moderasi di output tetap kebobolan lewat: prompt
injection yang masuk lewat hasil tool (bukan lewat pesan user, jadi tidak
pernah lewat input filter), retrieval yang mengembalikan dokumen milik user
lain (tidak ada "output" yang salah — teksnya valid, cuma pemiliknya salah),
tool destruktif yang dipanggil tanpa approval, atau loop yang jalan 4000
langkah sebelum ada yang sadar biayanya. Nama classifier yang benar (Llama
Guard, NeMo Guardrails, dst.) dipasang di titik yang salah tetap kebobolan di
lima titik lain — nama produk yang tepat bukan bukti cakupan yang cukup.

Masalah kedua, lebih halus: guardrail yang dipasang tanpa **memutuskan** apa
yang terjadi saat dia gagal (error klasifier, timeout, dependency down)
mewarisi perilaku dari cara error itu kebetulan ditangani di kode — biasanya
`try/except` yang menelan error dan melanjutkan (fail-open kebetulan) atau
yang membiarkan exception naik dan menghentikan request (fail-closed
kebetulan). Kedua default itu benar untuk sebagian guardrail dan salah fatal
untuk sebagian lain, dan kode tidak tahu bedanya kecuali penulisnya
memutuskan secara eksplisit per guardrail.

## Pola

### Enam titik penegakan, tiap guardrail deklarasi tiga hal

Kerangka enam titik ini `[ours]` — mengikuti kerangka spec §8.4 proyek ini,
selaras dengan taksonomi "rails" NeMo Guardrails yang independen sampai pada
titik serupa: *input rails* (pra-LLM), *dialog rails* (alur percakapan),
*retrieval rails* (validasi konten yang diambil), *execution/tool rails*
(sebelum/sesudah pemanggilan tool), *output rails* (pasca-LLM) `[docs]`.
Vanilla di industri: guardrail dijual dan dipasang sebagai satu titik —
biasanya "moderasi output", kadang ditambah input — cukup untuk chatbot
single-turn tanpa tool. Kita menyimpang dengan menambah dua titik yang tidak
dibutuhkan taksonomi single-turn manapun: **Loop** (kontrol lintas-banyak-
langkah: biaya, waktu, oscillation) dan **Sistem** (versi model, fallback,
audit lintas keputusan gerbang) — keduanya tidak eksis di produk non-agentic
karena tidak ada "banyak langkah" atau "banyak keputusan gerbang" untuk
dikontrol/diaudit.

Tiap baris di bawah adalah satu guardrail konkret, bukan satu titik — **tiap
guardrail wajib menyatakan tiga hal**: kebijakan, titik penegakan, mode
kegagalan. Mode kegagalan sengaja tidak seragam:

| # | Titik | Kebijakan (contoh) | Titik penegakan | Mode kegagalan |
|---|---|---|---|---|
| 1 | Input | Moderasi konten (kekerasan/pelecehan/abuse) | Sebelum turn masuk state, hook `before_model` | **Fail-open** — error klasifier → log + lanjut. Menahan seluruh produk demi satu pemeriksaan yang gagal lebih mahal dari membiarkan satu turn tak termoderasi |
| 1 | Input | PII redaction (email, kartu kredit di pesan user) | `before_model`, `PIIMiddleware(apply_to_input=True)` | Campuran per tipe: `strategy="block"` (fail-closed) untuk PII berisiko tinggi (kartu kredit), `strategy="redact"` (fail-open, lanjut dg versi tersamar) untuk PII risiko rendah (email) |
| 1 | Input | Deteksi injection & jailbreak, batas topik | `before_model`, classifier kustom (Llama Guard / rail input NeMo) | Fail-closed pada skor tinggi (`can_jump_to=["end"]`, turn dihentikan) — palsu-positif di sini cuma menolak satu turn, jauh lebih murah dari palsu-negatif yang meloloskan jailbreak |
| 2 | Retrieval/context | **Filter otorisasi** — hasil retrieval discope ke `user_id` aktif (§8.2) | Di dalam implementasi tool retrieval, sebelum query dieksekusi — bukan filter dari hasil sesudahnya | **Fail-closed** — error di lapis scope (mis. `current_user_id` lupa di-set) berarti nol baris, bukan seluruh index. Ini yang paling sering bocor di RAG multi-user karena kelihatannya "cuma pencarian", persis argumen `isolation-and-scoping.md` |
| 2 | Retrieval/context | Penandaan konten tak-dipercaya + provenance | Saat konten retrieval/tool result ditulis ke state, sebelum masuk context model | Fail-open untuk penandaan (selalu tandai, tidak pernah blokir isi) — labelnya yang membuat model (dan guardrail lain di titik Output) tahu konten itu tidak boleh diperlakukan sebagai instruksi. Lihat `security.md` untuk kenapa ini pertahanan utama terhadap prompt injection lewat tool result |
| 3 | Tool/aksi | Allowlist tool per peran | `excluded_tools` (`HarnessProfile`) → `_ToolExclusionMiddleware` | **Fail-closed** — tool yang tak terdaftar tidak pernah terlihat model sama sekali, bukan terlihat lalu ditolak saat dipanggil (kegagalan yang tak dilihat model = tidak ada percobaan bujuk-ulang) |
| 3 | Tool/aksi | Validasi argumen tool | Skema tool (`args_schema` Pydantic) sebelum handler dipanggil | Fail-closed — argumen yang gagal validasi tidak pernah sampai ke fungsi tool |
| 3 | Tool/aksi | Gerbang approval aksi destruktif, penyempitan scope token | `interrupt_on=`/`permissions=[...,mode="interrupt"]` → `HumanInTheLoopMiddleware` | Fail-closed — run berhenti menunggu approval; timeout approval = default *deny*, bukan default lanjut |
| 4 | Output | Validasi schema, groundedness, wajib sitasi | `RubricMiddleware` (iterasi sampai lolos rubric atau `max_iterations`) | Fail-open pada `max_iterations` tercapai — kirim jawaban terbaik yang ada dg flag "belum lolos rubric" ke lapis observability, jangan diamkan turn selamanya |
| 4 | Output | Cek kebocoran PII di jawaban | `after_model`, `PIIMiddleware(apply_to_output=True)` | Sama pola campuran seperti PII input — `hash`/`mask` untuk data pseudonim yang perlu tetap berguna, `block` untuk kelas data yang tidak boleh keluar sama sekali |
| 4 | Output | Scan secret di kode yang digenerate (API key, private key, token pola `sk-…`/`AKIA…`) | Sebelum `write_file`/`edit_file` commit ke disk, atau `after_model` pada blok kode | **Fail-closed** — temuan pola secret memblokir tulis; tulis-lalu-warn berarti secret sudah ada di disk (dan mungkin sudah ke git) sebelum siapa pun membaca warning-nya |
| 5 | Loop | Max tool call per run/thread | `ToolCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior=)` | `exit_behavior` **adalah** deklarasi mode kegagalan eksplisit: `"error"` = fail-closed (raise), `"end"` = fail-open terkendali (tutup turn dg state apa adanya), `"continue"` (default library) = tidak berhenti sama sekali — memilih default tanpa membaca dokumentasinya berarti guardrail ini tidak melakukan apa-apa |
| 5 | Loop | Budget token/biaya per run, kill switch | `ModelCallLimitMiddleware` + akumulasi biaya app-level (`cost-control.md`) | Fail-closed di level run (hentikan run itu), fail-open di level user (user tetap bisa memulai run baru — budget habis bukan larangan permanen) |
| 5 | Loop | Deteksi oscillation & no-progress | Custom `after_model` — bandingkan hash tool-call berurutan / progres state | Fail-open dg peringatan sampai N pengulangan, baru fail-closed (hentikan run) — satu pengulangan biasa terjadi (retry legit), banyak pengulangan identik adalah sinyal stuck |
| 6 | Sistem | Pin versi model | Parameter `model` eksplisit ke `create_deep_agent(model=...)`, bukan alias mengambang (`"latest"`) | Fail-closed implisit — model/alias yang tak dikenal gagal saat konstruksi agent, bukan diam-diam terselesaikan ke versi lain saat runtime |
| 6 | Sistem | Kebijakan fallback model | `ModelFallbackMiddleware(primary, *fallbacks)` | **Fail-open by design** (tujuannya availability) — tapi wajib berpasangan dg audit log per keputusan gerbang (model mana yang sebenarnya menjawab), kalau tidak "jawaban dari fallback yang lebih lemah" jadi tak tertelusuri |

### Bertingkat: deterministik dulu, model-based cuma kalau perlu

Guardrail model-based (Llama Guard, rail self-check NeMo, validator LLM-based
di Guardrails AI) melipatgandakan biaya dan latensi **setiap panggilan yang
lewat titik itu** — bukan cuma yang positif melanggar. Satu guardrail
model-based di titik Input berarti setiap turn, termasuk 99% yang aman,
sekarang menunggu satu round-trip LLM tambahan sebelum turn utama mulai.
Urutan tingkatan, murah ke mahal:

1. **Deterministik murni** — schema (Pydantic `args_schema`), regex, allowlist
   nama tool. Presidio termasuk sebagian di sini: recognizer regex/checksum
   (mis. validasi Luhn untuk kartu kredit) berjalan tanpa model sama sekali.
   `[docs]`
2. **Deterministik+NER murah** — Presidio Analyzer penuh menggabungkan
   recognizer regex dengan model NER (spaCy/Transformers/Stanza, dapat
   dipasang) plus `ContextAwareEnhancer` berbasis lemma untuk menaikkan
   confidence dari konteks sekitar — lebih mahal dari regex murni tapi jauh
   lebih murah dari satu panggilan LLM generatif, dan menangkap kelas PII
   yang regex tidak bisa (nama orang, alamat). `[docs]`
3. **Model kecil/klasifier khusus** — Llama Guard: model fine-tuned 8B yang
   di-*inference* sekali untuk menghasilkan verdict aman/tidak-aman +
   kategori (taksonomi 14 kategori selaras MLCommons: kekerasan, eksploitasi
   anak, privasi, ujaran kebencian, dll., mendukung input maupun output).
   Tetap satu panggilan model, tapi model kecil dan tugasnya sempit
   (klasifikasi, bukan generasi bebas) — lebih murah dari model utama produk
   tapi tidak gratis. `[docs]`
4. **LLM generatif penuh sebagai guardrail** — rail self-check NeMo Guardrails
   atau validator LLM-based Guardrails AI yang meminta model menilai/menulis
   ulang jawaban. Termahal, dipakai hanya untuk hal yang tidak bisa
   diperiksa deterministik/klasifier kecil: groundedness terhadap dokumen
   retrieval, kepatuhan nuansa kebijakan yang tidak bisa direduksi ke pola.
   `[docs]`

Urutan defaultnya: coba tingkat 1 dulu; naik satu tingkat hanya kalau
tingkat sebelumnya terbukti tidak cukup untuk kelas risiko itu — bukan
memasang tingkat 4 untuk semua titik karena "paling akurat".

### Guardrail punya false-positive rate — masuk eval harness

Guardrail yang dipasang dan tidak pernah diukur adalah liabilitas, bukan
kontrol: tiap deteksi (regex, NER, klasifier) punya trade-off precision/
recall, dan tanpa angka nyata, threshold-nya cuma tebakan. Guardrail yang
terlalu agresif fail-closed di permintaan sah (mis. moderasi salah memblokir
bahasa non-Inggris, PII redaction salah menandai nomor referensi biasa
sebagai kartu kredit) adalah insiden UX yang tidak akan pernah ketahuan
kalau tidak ada yang mengukurnya. Presisi/recall tiap guardrail wajib jadi
metrik eval harness, bukan cuma "terpasang" — lihat
[`evaluation.md`](evaluation.md) §Guardrail sebagai objek terukur.

### Kebijakan tidak boleh hanya di prompt

Aturan di system prompt ("jangan pernah bocorkan data user lain", "selalu
minta konfirmasi sebelum menghapus") itu **advisory** — model bisa dibujuk
mengabaikannya, dan yang paling sering membujuknya bukan user yang jujur di
pesan awal, tapi teks di hasil tool yang disamarkan sebagai instruksi (lihat
[`security.md`](security.md) §Prompt injection lewat hasil tool, isu nomor
satu keamanan multi-langkah). Penegakan yang nyata hidup di kode yang
berjalan di luar kendali model — middleware yang membaca/mengubah/memblokir
state sebelum atau sesudah model dipanggil. Prompt tetap berguna untuk
memandu perilaku *default* model, tapi tidak pernah menjadi satu-satunya
lapis untuk apa pun yang kegagalannya mahal.

## Trade-off

- **Fail-closed di semua titik vs fail-open di semua titik** — fail-closed
  seragam maksimal aman tapi menjadikan tiap guardrail titik gagal tunggal
  untuk seluruh produk (guardrail down = produk down); fail-open seragam
  maksimal tersedia tapi guardrail jadi dekoratif begitu infra-nya gagal
  atau di bawah beban. Keputusan harus per guardrail berdasar asimetri
  bahaya: kebocoran data senyap & tak-terlihat (fail-closed) vs chat
  ter-blokir yang menjengkelkan & terlihat (fail-open) — tabel di atas
  adalah penerapan aturan ini, bukan aturan baru.
- **Bertingkat vs satu classifier LLM yang memeriksa semuanya** — satu
  pemeriksa LLM generik lebih sederhana untuk dinalar (satu kode path, satu
  tempat tuning) tapi menambah satu round-trip model penuh ke *setiap* turn
  tanpa pengecualian; bertingkat lebih murah rata-rata tapi menambah
  permukaan kode (tiap tingkat = jalur terpisah yang perlu diuji) dan
  keputusan eksplisit "kapan naik tingkat" yang bisa salah diset.
- **Framework guardrail terpusat (NeMo Guardrails/Guardrails AI sebagai
  orkestrator rail) vs pustaka titik yang dirangkai sendiri** (Presidio untuk
  PII + Llama Guard untuk konten + regex kustom untuk secret, masing-masing
  dipanggil dari middleware yang kita tulis) — framework memberi bahasa
  konfigurasi/rail yang bisa dipakai ulang lintas proyek dengan biaya
  dependency tambahan dan runtime yang semantiknya tidak sepenuhnya kita
  kendalikan berjalan di dalam loop kita; rangkaian titik lebih pas dengan
  model "guardrail = middleware" `deepagents`/`langchain` (tiap pustaka jadi
  satu panggilan di dalam hook yang kita tulis sendiri) dengan biaya:
  plumbing (wiring hook, exit behavior, logging) diulang manual untuk tiap
  guardrail, tidak ada abstraksi bersama.

## Di deepagents

Tidak ada satu pun dari NeMo Guardrails, Guardrails AI, Llama Guard, atau
Presidio yang punya integrasi native ke `deepagents`/`langchain` — keempatnya
pustaka berdiri sendiri yang harus dipanggil manual dari dalam
`AgentMiddleware` kustom. Yang **memetakan 1:1 ke middleware** adalah titik
penegakannya, bukan pustaka classifier-nya:

| Titik (dari tabel di atas) | Middleware/mekanisme `deepagents`/`langchain` | Sumber |
|---|---|---|
| 1. Input — PII | `langchain.agents.middleware.PIIMiddleware(pii_type, strategy=, apply_to_input=True)`, hook `before_model` | `[code]` `langchain/agents/middleware/pii.py` (langchain 1.3.16, versi yang sama dikutip `deepagents.md`) |
| 1. Input — injection/jailbreak/topik/moderasi/abuse | Tidak ada middleware bawaan; tulis `AgentMiddleware` kustom dg hook `before_model`, panggil classifier (Llama Guard/rail input NeMo/validator Guardrails AI) di dalamnya, `@hook_config(can_jump_to=["end"])` untuk memutus turn saat positif | `[code]` hook `before_model`/`hook_config` ada di `langchain/agents/middleware/types.py`; `[inferred]` tidak ada modul classifier bawaan — disimpulkan dari tidak ditemukannya import semacam itu di `langchain/agents/middleware/` maupun `deepagents/middleware/` |
| 2. Retrieval/context — otorisasi, provenance | Tidak ada middleware generik; penegakan ada **di dalam** implementasi tool retrieval kustom (query discope RLS, lihat `isolation-and-scoping.md`), atau lewat hook `wrap_tool_call(request, handler)` yang mencegat request sebelum handler tool jalan | `[code]` `wrap_tool_call` — `langchain/agents/middleware/types.py` |
| 3. Tool/aksi — allowlist per peran | `excluded_tools` (`HarnessProfile`/`ProviderProfile`) → `_ToolExclusionMiddleware` | `[code]` dikutip `../systems/deepagents.md` §7, §Middleware bawaan |
| 3. Tool/aksi — validasi argumen | Skema Pydantic `args_schema` tiap `BaseTool`, divalidasi framework LangChain sebelum handler dipanggil | `[docs]` |
| 3. Tool/aksi — approval gate, penyempitan scope | `interrupt_on=`/`permissions=[FilesystemPermission(mode="interrupt")]` → `HumanInTheLoopMiddleware` | `[code]` dikutip `../systems/deepagents.md` §6 |
| 3. Tool/aksi — batas sandbox | Backend yang mengimplementasi `SandboxBackendProtocol` (bukan `LocalShellBackend` default, yang menurut `THREAT_MODEL.md` deepagents tidak memvalidasi isi command) | `[code]`/`[docs]` dikutip `../systems/deepagents.md` §6 |
| 3. Tool/aksi — dry-run | Tidak ada mekanisme bawaan; `permissions=[..., mode="deny"]` menolak eksekusi tanpa efek samping tapi itu blokir permanen, bukan mode "coba tanpa efek" yang bisa diulang jadi eksekusi nyata — dry-run sungguhan (tool mengembalikan simulasi hasil tanpa side effect) harus ditulis di dalam implementasi tool itu sendiri | `[inferred]` tidak ditemukan parameter/mode dry-run di `FilesystemPermission`/`interrupt_on` yang dibaca Task 3 |
| 4. Output — schema, groundedness, sitasi | `RubricMiddleware` (deepagents, iterasi terhadap rubric sampai lolos/`max_iterations`, tidak default) | `[code]` dikutip `../systems/deepagents.md` §Middleware bawaan (`deepagents/middleware/rubric.py`) |
| 4. Output — PII, scan secret | `PIIMiddleware(apply_to_output=True, apply_to_tool_results=True)` untuk PII; scan secret = hook `after_model` atau pre-write kustom (tidak ada bawaan) | `[code]` `langchain/agents/middleware/pii.py` |
| 5. Loop — max step, budget, kill switch | `ToolCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior=)`, `ModelCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior=)`; `cancel_async_task` (`AsyncSubAgentMiddleware`) sebagai kill switch task background | `[code]` `langchain/agents/middleware/tool_call_limit.py`, `model_call_limit.py`; `AsyncSubAgentMiddleware` dikutip `../systems/deepagents.md` §Middleware bawaan |
| 6. Sistem — pin model, fallback | Parameter `model` eksplisit ke `create_deep_agent(model=...)`; `ModelFallbackMiddleware(primary_model, *fallback_models)`, hook `wrap_model_call` | `[code]` `langchain/agents/middleware/model_fallback.py` |
| 6. Sistem — audit log gerbang | Tidak ada tabel audit bawaan; checkpoint state per step (`checkpointer` yang disuntik aplikasi) adalah jejak paling dekat yang tersedia gratis — lihat [`replay-and-forensics.md`](replay-and-forensics.md) untuk batasannya sebagai audit log | `[code]` dikutip `persistence-schema.md` §checkpointer, `../systems/deepagents.md` §5 |

**Peringatan konkret untuk titik 5 (Loop)**: `deepagents` menaikkan
`recursion_limit` LangGraph dari 25 (default) ke **9999**
(`.with_config({"recursion_limit": 9_999, ...})`, dipasang otomatis di
`create_deep_agent`) — ini **bukan** guardrail loop, ini jaring pengaman
supaya task legit yang panjang tidak kepotong `GraphRecursionError` di limit
default LangGraph yang jauh lebih kecil. `[code]` — dikutip
`../systems/deepagents.md` §1 (`deepagents/graph.py` baris 935-944). Akibatnya:
kalau `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` tidak dipasang
eksplisit, default `deepagents` efektif **tidak** punya batas langkah
praktis — 9999 langkah adalah budget yang bisa membakar biaya besar sebelum
berhenti sendiri. Guardrail titik 5 wajib dipasang eksplisit, bukan
diasumsikan datang gratis dari `deepagents`.

Semua middleware `langchain.agents.middleware.*` di tabel atas (`PIIMiddleware`,
`ToolCallLimitMiddleware`, `ModelCallLimitMiddleware`, `ModelFallbackMiddleware`)
bukan milik `deepagents` — sama seperti `TodoListMiddleware` yang sudah
ditandai `../systems/deepagents.md` sebagai "bukan milik `deepagents`", ia
diimpor dari `langchain.agents.middleware` dan disuntik manual lewat
`create_deep_agent(middleware=[...])`, tidak masuk stack bawaan mana pun.

## Sumber

- `[docs]` NeMo Guardrails — dokumentasi resmi NVIDIA (`docs.nvidia.com/nemo/guardrails`),
  taksonomi lima jenis rail (input/dialog/retrieval/execution/output).
- `[docs]` Guardrails AI — `guardrailsai.com/docs`, Guard/validator sebagai
  Input+Output Guards, Hub validator untuk deteksi/mitigasi risiko.
- `[docs]` Llama Guard 3 — `huggingface.co/meta-llama/Llama-Guard-3-8B`, model
  fine-tuned klasifikasi keamanan konten, taksonomi 14 kategori selaras
  MLCommons, mendukung input maupun output, model-based (butuh inferensi).
- `[docs]` Presidio — `presidio.dataprivacystack.org/analyzer/`, Analyzer
  hybrid regex+NER (`ContextAwareEnhancer`), Anonymizer untuk strategi
  redact/hash/encrypt.
- `[code]` `langchain/agents/middleware/pii.py` (langchain 1.3.16, terinstal
  lewat `pip install langchain==1.3.16` di venv riset terpisah) —
  `PIIMiddleware`, parameter `apply_to_input`/`apply_to_output`/
  `apply_to_tool_results`, strategi `block`/`redact`/`mask`/`hash`, hook
  `before_model`.
- `[code]` `langchain/agents/middleware/tool_call_limit.py` — `ToolCallLimitMiddleware`,
  `thread_limit`/`run_limit`/`exit_behavior` (`"continue"`/`"error"`/`"end"`).
- `[code]` `langchain/agents/middleware/model_call_limit.py` — `ModelCallLimitMiddleware`,
  parameter sama, hook `before_model`/`after_model` dg `can_jump_to=["end"]`.
- `[code]` `langchain/agents/middleware/model_fallback.py` — `ModelFallbackMiddleware`,
  `wrap_model_call`, retry berurutan ke model fallback saat model utama error.
- `[code]` `langchain/agents/middleware/types.py` — hook lengkap `AgentMiddleware`
  (`before_agent`/`before_model`/`wrap_model_call`/`after_model`/`wrap_tool_call`/
  `after_agent`), dasar semua mapping titik→middleware di atas.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §1 (recursion_limit
  9999), §6 (Safety gate — `interrupt_on`/`permissions`/sandbox), §7
  (`HarnessProfile`/`excluded_tools`), §Middleware bawaan (`RubricMiddleware`,
  `AsyncSubAgentMiddleware`, `TodoListMiddleware` sebagai precedent "bukan
  milik deepagents") — tier-1 reference terverifikasi Task 3, dikutip tanpa
  membaca ulang source `deepagents` di task ini.
- `[code]` [`persistence-schema.md`](persistence-schema.md) §checkpointer —
  dasar klaim "checkpoint state per step sebagai jejak audit terdekat yang
  gratis" di §6 Sistem.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — dasar
  model scope `user_id`/RLS yang dirujuk di titik 2 (Retrieval/context),
  tidak diusulkan ulang di file ini.
