# Agent loop

## Masalah

"Agent loop" sering dianggap satu bentuk tunggal — think, act, observe,
ulangi (ReAct) — padahal itu cuma satu pilihan dari beberapa bentuk yang
valid, dan pertanyaan yang lebih penting biasanya tidak pernah dijawab
eksplisit: **siapa yang memutuskan loop berhenti, dan lewat sinyal apa?**
Tanpa jawaban eksplisit, perilaku berhenti loop jadi kecelakaan dari
apa pun default library yang kebetulan dipakai — batas rekursi yang
dipasang sebagai jaring pengaman (bukan keputusan "kapan tugas selesai")
disalahartikan sebagai mekanisme penyelesaian tugas, atau konvensi string
ajaib yang tidak pernah ditulis siapa pun sebagai keputusan sadar.

Kebingungan konkretnya: "loop berhenti karena tugas selesai" dan "loop
berhenti karena anggaran habis" adalah dua kejadian yang **berbeda sama
sekali** — satu keputusan model (implisit atau eksplisit), satu keputusan
harness yang independen dari apa yang model inginkan — tapi kalau
keduanya tidak dibedakan di titik keluar, pemanggil di hilir (kode yang
memproses hasil run) tidak bisa tahu mana yang terjadi tanpa memeriksa
ulang state secara manual. Run yang terpotong anggaran diperlakukan sama
seperti run yang selesai wajar → jawaban parsial dikirim ke user seolah itu
jawaban final, atau logic retry yang seharusnya jalan untuk run terpotong
tidak pernah terpicu karena sinyalnya tidak dibedakan.

## Pola

### Taksonomi siapa-memutuskan-berhenti

- **Implisit, model berhenti dengan tidak melakukan apa-apa** — loop
  ReAct standar: model dipanggil berulang, loop berlanjut selama respons
  terakhir masih berisi `tool_calls`, berhenti begitu respons terakhir
  **tidak** berisi `tool_calls`. Tidak ada tindakan positif yang menandai
  "saya selesai" — ketiadaan tindakan itu sendiri yang jadi sinyal.
  Konsekuensi: harness tidak punya event untuk dicatat ("model memutuskan
  selesai di step N") — kesimpulan "selesai" baru bisa diambil sesudah
  fakta, dari absennya tool call berikutnya.
- **Eksplisit, model memanggil tool penyelesaian** — pola SWE-agent: tool
  `submit` (mencatat diff akhir + mencetak sentinel `<<SWE_AGENT_SUBMISSION>>`
  yang dipindai harness) dan `exit_forfeit` (menyerah eksplisit) adalah dua
  cara **berbeda** untuk model menyatakan selesai — bukan berhenti karena
  kehabisan hal untuk dilakukan, tapi karena secara aktif memanggil tool
  yang artinya "saya selesai" atau "saya menyerah". `[code]` `tools/submit/config.yaml`,
  `tools/submit/bin/submit`, `tools/forfeit/config.yaml`, repo
  `SWE-agent/SWE-agent`. Beda dari bentuk implisit: ada event konkret yang
  bisa dicatat/diaudit ("model memanggil `submit` di step N", bukan
  disimpulkan dari ketiadaan), dan payload penyelesaiannya bisa terstruktur
  (isi patch, bukan cuma teks bebas).
- **Plan-execute, selesai = semua langkah rencana ditandai selesai** — loop
  dua fase: fase perencanaan menghasilkan daftar langkah lebih dulu, fase
  eksekusi menjalankan/memverifikasi tiap langkah; berhenti saat rencana
  habis, bukan saat model "merasa" selesai di tengah eksekusi. Lihat
  [`planning.md`](planning.md) untuk kapan planning eksplisit macam ini
  bermanfaat vs jadi beban — file ini cuma menandai bentuknya sebagai
  varian loop yang berbeda, tidak mengulang analisisnya.
- **Loop-until-done yang diawasi eksternal** — supervisor di luar model
  (scheduler, cron, event trigger) yang memutuskan kapan loop dijalankan
  dan kapan dihentikan sama sekali; model tidak pernah dimintai pendapat
  soal "kapan berhenti" untuk satu putaran, itu keputusan sistem. Relevan
  untuk arketipe Workflow Agent (`archetypes/06-workflow-agent.md`) yang
  memang dirancang tanpa human/model-in-the-loop untuk keputusan berhenti.

### Berhenti-karena-selesai vs berhenti-karena-anggaran — dua mekanisme, jangan satu sinyal

Guardrail titik 5 (`guardrails.md` — max tool call, max model call, kill
switch) adalah **pemutus ketiga** yang berdiri di luar model sepenuhnya:
`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` menghentikan loop
karena anggaran habis, terlepas dari apakah model masih ingin lanjut atau
sudah mau berhenti. `exit_behavior` middleware itu **adalah** deklarasi
eksplisit mana yang terjadi ketika anggaran habis: `"error"` (naikkan
exception, run gagal jelas), `"end"` (tutup turn paksa dengan state apa
adanya), `"continue"` (default library — loop tidak sungguh berhenti,
lihat peringatan di `guardrails.md`). Titik krusialnya: **run yang
dihentikan `exit_behavior="end"` bukan run yang selesai** — ia run yang
dipotong paksa di tengah, dan kode yang memproses hasilnya wajib membedakan
dua keadaan itu (selesai wajar vs dipotong anggaran) sebagai dua sinyal
terpisah, bukan satu boolean "run berhenti = run beres". Menyamakan
keduanya berarti jawaban parsial (kemungkinan tool call yang belum sempat
dieksekusi, state yang belum konsisten) dikirim ke hilir seolah itu jawaban
final yang model sendiri putuskan.

## Trade-off

- **Berhenti implisit vs tool penyelesaian eksplisit** — implisit tidak
  menambah permukaan tool (model tidak perlu diajari/diingatkan memanggil
  apa pun untuk selesai), tapi harness tidak punya sinyal positif untuk
  membedakan "selesai, puas dengan hasil" dari "berhenti diam-diam karena
  bingung/menyerah" — keduanya sama-sama muncul sebagai "tidak ada
  tool_calls lagi". Tool eksplisit memberi sinyal bersih + payload
  terstruktur (diff, jawaban final, tingkat keyakinan), tapi model kadang
  lupa memanggilnya — keluar dengan jawaban teks biasa tanpa `tool_calls`,
  yang membuat harness jatuh balik ke perilaku implisit persis walau tool
  eksplisitnya sudah dibangun. Mitigasinya (reprompt "apakah kamu yakin
  sudah selesai?" sebelum benar-benar menutup turn) menambah kompleksitas
  yang tidak dibutuhkan bentuk implisit sama sekali.
- **Plan-execute vs loop-until-model-memutuskan** — rencana lebih dulu
  memberi sinyal progres yang bisa diperiksa dari luar ("N dari M langkah
  selesai"), berguna untuk UI progres dan estimasi durasi; tapi rencana bisa
  salah begitu eksekusi menemukan hal yang tidak terduga, memaksa mekanisme
  replanning yang loop-until-done tidak butuh sama sekali (loop itu memang
  dirancang untuk terbuka). Loop-until-model-memutuskan fleksibel untuk
  tugas open-ended tapi tidak punya checkpoint eksternal untuk tahu progres
  sampai benar-benar tuntas.
- **Memisahkan sinyal selesai-vs-anggaran sebagai dua flag vs satu sinyal
  gabungan** — dua flag terpisah menjaga ketepatan (run terpotong anggaran
  sering layak retry dengan anggaran lebih besar; run selesai wajar tidak),
  dengan biaya: pemanggil di hilir harus menangani dua state, bukan satu.
  Satu sinyal gabungan lebih sederhana dikonsumsi tapi membuang perbedaan
  yang penting untuk akuntansi biaya dan logic retry.

## Di deepagents

Bentuk defaultnya **implisit** — `create_deep_agent(...)` mendelegasikan
loop ke `langchain.agents.create_agent(...)`, yang didokumentasikan sebagai
"creates an agent graph that calls tools in a loop until a stopping
condition is met": loop model ⇄ tool berhenti ketika `AIMessage` terakhir
tidak berisi `tool_calls` — keputusan berhenti itu murni implisit dari
absennya tool call berikutnya, bukan diputuskan `deepagents` sendiri.
`[code]` dikutip `../systems/deepagents.md` §1 (`langchain/agents/factory.py`
baris 859-860). `recursion_limit=9999` yang dipasang otomatis **bukan**
mekanisme "kapan berhenti" — ia jaring pengaman supaya task legit yang
panjang tidak kepotong `GraphRecursionError` di limit LangGraph yang jauh
lebih kecil (default 25). `[code]` dikutip `../systems/deepagents.md` §1.
Tidak ada pola tool `submit`/`exit_forfeit` bawaan — kalau proyek butuh
sinyal penyelesaian eksplisit ala SWE-agent, itu harus ditulis sebagai
custom tool sendiri, `deepagents` tidak menyediakannya. `[inferred]`
disimpulkan dari tool bawaan yang terdaftar di `../systems/deepagents.md`
§3 (`ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep`/`execute`/`task`),
tidak satu pun berfungsi sebagai sinyal penyelesaian tugas.

`response_format` pada `create_deep_agent`/`SubAgent` (skema Pydantic/dict
yang memaksa keluaran akhir mengikuti struktur tertentu) memberi payload
penyelesaian yang bisa diperiksa program — mirip efek tool `submit` SWE-agent
(hasil akhir yang terstruktur, bukan teks bebas) — tapi **tidak** mengubah
mekanisme berhenti itu sendiri: loop tetap berhenti implisit saat tidak ada
`tool_calls`, `response_format` cuma membentuk isi pesan akhir begitu titik
itu tercapai. `[code]` `deepagents/graph.py` baris 280, 507, 927;
`deepagents/middleware/subagents.py` baris 127, 337, 388-430 (parameter
`response_format` pada `create_deep_agent` dan spec `SubAgent`/`CompiledSubAgent`),
venv riset yang sama dengan `../systems/deepagents.md`.

Pembeda "selesai vs kehabisan anggaran" dari `## Pola` di atas dipetakan
langsung ke `exit_behavior` `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`,
sudah didokumentasikan lengkap di `guardrails.md` titik 5 — file ini tidak
mengulang tabelnya, cuma menegaskan bahwa dua middleware itu adalah pemutus
loop **ketiga** (selain "model implisit berhenti" dan "sinyal eksplisit
kalau dibangun custom") yang beroperasi independen dari niat model.

## Sumber

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §1 Loop
  shape (`create_agent`, kondisi berhenti implisit, `recursion_limit=9999`),
  §3 Tool surface (daftar tool bawaan, dasar klaim tidak ada tool
  penyelesaian eksplisit bawaan) — tier-1 reference terverifikasi Task 3,
  dikutip tanpa membaca ulang `deepagents/graph.py` inti di task ini.
- `[code]` `deepagents/graph.py` baris 280, 507, 927 (paket
  `deepagents==0.7.8`, dibaca dari
  `references/recipes/.venv/lib/python3.13/site-packages/`, venv sama
  dengan `../systems/deepagents.md`) — parameter `response_format` pada
  `create_deep_agent`.
- `[code]` `deepagents/middleware/subagents.py` baris 127, 337, 388-430
  (venv sama) — `response_format` pada spec `SubAgent`/`CompiledSubAgent`.
- `[code]` `tools/submit/config.yaml`, `tools/submit/bin/submit`,
  `tools/forfeit/config.yaml`, repo `SWE-agent/SWE-agent`, dibaca via
  `raw.githubusercontent.com/SWE-agent/SWE-agent/main/tools/submit/config.yaml`,
  `.../tools/submit/bin/submit`, `.../tools/forfeit/config.yaml` — tool
  `submit`/`exit_forfeit` sebagai sinyal penyelesaian eksplisit.
- `[code]` [`guardrails.md`](guardrails.md) titik 5 (Loop) — tabel
  `exit_behavior`/`ToolCallLimitMiddleware`/`ModelCallLimitMiddleware`,
  dirujuk untuk pemutus loop berbasis anggaran, tidak diusulkan ulang di
  sini.
- `[code]` [`planning.md`](planning.md) — bentuk loop plan-execute dirujuk
  sebagai varian taksonomi, analisis kapan planning eksplisit bermanfaat
  didelegasikan ke file itu; ditulis dalam task yang sama, tidak diusulkan
  ulang di sini.
