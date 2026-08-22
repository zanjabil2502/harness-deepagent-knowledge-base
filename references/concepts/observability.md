# Observability

## Masalah

Agent gagal diam-diam jauh lebih sering daripada agent gagal keras. Tool
call yang gagal lalu ditelan sebuah `try/except` yang tidak seharusnya ada,
model yang memilih tool yang salah tapi tetap menghasilkan jawaban yang
kedengarannya masuk akal, loop yang melebar jadi 20 langkah padahal
seharusnya 3 — semuanya mengembalikan HTTP 200 dan teks yang terlihat wajar.
Tanpa visibilitas per-langkah, "debug" jadi baca seluruh transcript dan
menebak langkah mana yang sebenarnya salah, karena tidak ada yang menandai
langkah spesifik itu sebagai anomali saat kejadian.

Masalah kedua: trace yang tidak ditandai `user_id` tidak berguna untuk
investigasi per-user. "User X melaporkan X" tidak bisa dijawab dengan
menyaring trace ke user itu kalau tag itu tidak pernah dipasang saat trace
direkam — sama seperti query tanpa `WHERE user_id` di `isolation-and-scoping.md`,
bedanya di sini konsekuensinya bukan kebocoran data (trace bukan data
produk), tapi ketidakmampuan menjawab "apa yang sebenarnya terjadi untuk
user ini" setelah kejadian, termasuk saat investigasi insiden butuh tahu
scope-nya (user mana saja yang terdampak) dan itu tidak bisa direkonstruksi
dari trace yang tidak bertag.

## Pola

### Span per langkah, bukan satu span per turn

Satu trace = satu turn; di dalamnya, **satu span per langkah graph** — satu
panggilan model = satu span (`LangfuseGeneration`), satu panggilan tool =
satu span anak (`LangfuseTool`), disarangkan di bawah span turn/agent
(`LangfuseChain`/`LangfuseAgent`). `[code]` — nama kelas span dikutip dari
`langfuse/langchain/CallbackHandler.py` (Langfuse Python SDK 4.14.4,
terinstal lewat `pip install langfuse` di venv riset terpisah). Struktur
bersarang ini memetakan langsung ke semantik OpenTelemetry standar (span
parent-child), yang jadi fondasi kedua pustaka yang dirujuk task ini
(Langfuse dan OpenLLMetry/Traceloop sama-sama dibangun di atas OTel). Dengan
span per langkah, waktu/token/biaya/error jadi bisa diatribusikan ke langkah
spesifik, bukan cuma ke agregat satu turn — ini yang membuat "langkah mana
yang gagal" terjawab langsung dari trace, bukan dari menebak.

### Label `user_id` di setiap trace

Baik Langfuse maupun OpenLLMetry tidak tahu apa-apa soal model scope
aplikasi (`user_id` dari `isolation-and-scoping.md`) secara native — tag itu
wajib disuntik eksplisit tiap invoke, dengan mekanisme berbeda per pustaka:

- **Langfuse** — lewat `config={"metadata": {"langfuse_user_id": ...,
  "langfuse_session_id": ...}}` yang diteruskan ke pemanggilan LangChain
  runnable; `CallbackHandler` membaca kunci metadata itu dan menyalinnya
  jadi atribut span `user_id`/`session_id`. `[code]` —
  `langfuse/langchain/CallbackHandler.py` baris ~496-504 (deteksi
  `langfuse_session_id`/`langfuse_user_id` di metadata, ditulis ke
  `attributes["session_id"]`/`attributes["user_id"]`).
- **OpenLLMetry/Traceloop** — lewat pemanggilan eksplisit
  `traceloop.sdk.tracing.set_association_properties({"user_id": ...,
  "session_id": ...})` sebelum invoke; ini menempel ke OTel context
  (`attach(set_value("association_properties", properties))`) sehingga tiap
  span yang dibuat setelahnya otomatis mendapat atribut
  `traceloop.association.properties.user_id`. `[code]` —
  `traceloop/sdk/tracing/tracing.py` fungsi `set_association_properties`
  dan `_set_association_properties_attributes` (paket
  `opentelemetry-instrumentation-langchain`==0.62.3, satu rilis dengan
  `traceloop-sdk`).

Kedua mekanisme itu bentuknya beda tapi disiplinnya sama persis dengan
`SET LOCAL app.current_user_id` di lapis RLS (`isolation-and-scoping.md`):
harus dipasang **tiap** invoke, bukan sekali di awal proses, dan trace yang
lupa ditag itu bukan salah — cuma tidak berguna untuk filter per-user,
persis seperti query tanpa `WHERE user_id` bukan query yang salah secara
sintaksis, cuma tidak aman untuk scope. Sumber tag-nya wajib scope object
yang sama yang sudah ditetapkan `isolation-and-scoping.md` (`(user_id,)` →
`(tenant_id, user_id)`), bukan diturunkan ulang di lapis observability —
satu tempat berubah saat migrasi tenant, bukan dua.

## Trade-off

- **Langfuse (produk observability LLM khusus, UI+eval+prompt management
  siap pakai) vs OpenLLMetry/OTel-native (vendor-netral, ekspor ke backend
  OTel apa pun — Honeycomb, Datadog, Jaeger, Grafana Tempo, termasuk
  self-hosted)** — Langfuse memberi UI khusus LLM (breakdown token/biaya,
  tampilan session) siap pakai dengan biaya jadi satu backend/dependency
  khusus lagi untuk dijalankan/dibayar; OpenLLMetry memberi span lewat
  protokol OTel standar sehingga bisa diarahkan ke stack observability yang
  sudah ada (termasuk on-prem, relevan untuk asumsi A1 cloud-dan-on-prem)
  dengan biaya harus merakit sendiri tampilan khusus LLM. Keduanya tidak
  eksklusif secara teknis di level wire (Langfuse sendiri dibangun di atas
  OTel `[code]`, terlihat dari import `opentelemetry.trace`/`context` di
  `CallbackHandler.py`), tapi menjalankan keduanya sekaligus melipatgandakan
  overhead tanpa manfaat tambahan — pilih satu per project berdasar
  cloud-vs-on-prem dan apakah stack OTel sudah ada.
- **Granularitas span-per-langkah vs span-per-turn kasar** — halus persis
  yang dibutuhkan untuk menjawab "langkah mana yang gagal", tapi melipat-
  gandakan volume span (biaya di backend tracing hosted saat traffic
  tinggi, lebih banyak noise buat manusia yang menelusuri). Mitigasi:
  sampling di run sukses tanpa error/tanpa guardrail terpicu, selalu simpan
  detail penuh untuk run yang error atau memicu guardrail (event guardrail
  yang tercatat di trace, dari `guardrails.md`, adalah sinyal "wajib retensi
  penuh", bukan cuma catatan tambahan).

## Di deepagents

`deepagents` tidak mengemis tracing apa pun sendiri — tidak ada satu pun
penyebutan OTel/span/trace di source yang dibaca Task 3 (`../systems/deepagents.md`
tidak punya bagian itu), konsisten dengan pola "aplikasi pemanggil punya
kebenaran" yang sudah berulang di `session-state.md`/`isolation-and-scoping.md`.
`[inferred]` — disimpulkan dari tidak ditemukannya modul tracing di source
`deepagents` yang sudah dibedah Task 3. Tracing sepenuhnya ditempel di lapis
LangChain:

- `Langfuse`'s `CallbackHandler` adalah `BaseCallbackHandler` standar
  (`langchain_core.callbacks`) yang diteruskan lewat
  `config={"callbacks": [...]}` saat invoke — mekanisme generik yang sama
  yang menangkap panggilan model dan tool (termasuk tool `task` dari
  `SubAgentMiddleware`, tool background dari `AsyncSubAgentMiddleware`)
  sebagai span chain/tool bersarang otomatis, tanpa kode integrasi khusus
  `deepagents` — callback terpicu di level node graph LangChain/LangGraph
  yang cuma dirakit `deepagents`, bukan diganti olehnya. `[code]` — dikutip
  `../systems/deepagents.md` §Middleware bawaan untuk daftar
  `SubAgentMiddleware`/`AsyncSubAgentMiddleware`.
- Tag `user_id` dipasang di titik invoke yang sama dengan tempat aplikasi
  sudah meneruskan `config={"configurable": {"thread_id": ...}}` untuk
  checkpointer (`session-state.md`, `persistence-schema.md`) — memperluas
  dict config yang sama dengan `metadata` (Langfuse) atau memanggil
  `set_association_properties` (OpenLLMetry) sebelum invoke; `deepagents`
  sendiri tidak membaca/peduli metadata itu, murni diteruskan apa adanya ke
  mesin runnable LangChain.
- **Propagasi ke subagent** — `Langfuse` `CallbackHandler` menyimpan
  hierarki run eksplisit (`_RunState.parent_run_id`/`root_run_id`,
  `_RootRunState.run_ids`) `[code]` — `langfuse/langchain/CallbackHandler.py`
  — yang berarti span dari subagent (tool `task`, `SubAgentMiddleware`)
  otomatis mewarisi tag `user_id` yang dipasang di invoke level-teratas
  tanpa kode tambahan per subagent, selama config/metadata level-teratas
  membawanya. Tanpa memahami ini, orang gampang mengira subagent perlu
  ditag manual satu-satu.

## Sumber

- `[code]` `langfuse/langchain/CallbackHandler.py` (Langfuse Python SDK
  4.14.4, `pip install langfuse` di venv riset terpisah) — kelas span
  (`LangfuseGeneration`/`LangfuseTool`/`LangfuseChain`/`LangfuseAgent`),
  parsing `langfuse_user_id`/`langfuse_session_id` dari metadata,
  `_RunState`/`_RootRunState` untuk hierarki parent-child run, import
  `opentelemetry.trace`/`context` yang membuktikan Langfuse dibangun di
  atas OTel.
- `[code]` `traceloop/sdk/tracing/tracing.py` dan
  `opentelemetry/instrumentation/langchain/callback_handler.py`
  (`opentelemetry-instrumentation-langchain`==0.62.3, satu rilis dengan
  `traceloop-sdk`, `pip install traceloop-sdk opentelemetry-instrumentation`
  di venv riset terpisah) — fungsi `set_association_properties`,
  `_set_association_properties_attributes`, mekanisme OTel context attach.
- `[code]`/`[inferred]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Middleware bawaan — tidak ditemukan modul tracing di source `deepagents`
  yang dibedah Task 3; `SubAgentMiddleware`/`AsyncSubAgentMiddleware`
  dikutip untuk penjelasan span tool `task`/background.
- `[code]` [`isolation-and-scoping.md`](isolation-and-scoping.md) — model
  scope `user_id`/scope object yang jadi sumber nilai tag, dikutip tanpa
  mengusulkan model baru.
- `[code]` [`persistence-schema.md`](persistence-schema.md),
  [`session-state.md`](session-state.md) — konvensi
  `config={"configurable": {"thread_id": ...}}` yang jadi titik invoke sama
  tempat tag `user_id` dipasang.
- `[code]` [`guardrails.md`](guardrails.md) — dasar aturan "trace dg event
  guardrail wajib retensi penuh" di §Trade-off.
