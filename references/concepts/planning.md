# Planning

## Masalah

Dua kegagalan simetris, dan keduanya nyata: task multi-langkah yang
dikerjakan tanpa rencana tertulis apa pun kehilangan jejak begitu langkah
ke-4 menemukan hal yang mengubah langkah ke-6 dan ke-7 — tidak ada artefak
yang menyimpan rencana, cuma reasoning sesaat yang hidup di context call
saat ini dan hilang begitu context itu dikompaksi atau sesi di-resume.
Sebaliknya, task trivial yang dipaksa lewat proses perencanaan formal
(tulis daftar todo, tandai in-progress, kerjakan, tandai completed) membayar
beberapa round-trip tool cuma untuk mengonfirmasi struktur yang sudah jelas
sejak awal — token dan giliran terpakai untuk overhead yang tidak menambah
apa pun ke hasil.

Kesalahan yang mendasari keduanya sama: memperlakukan "selalu rencanakan"
atau "jangan pernah rencanakan" sebagai kebijakan global, bukan keputusan
per-task dengan ambang batas yang jelas. Tanpa ambang eksplisit, keputusan
itu jatuh ke default yang kebetulan — kalau tool planning selalu tersedia,
sebagian model memakainya untuk apa saja "biar aman"; kalau tidak pernah
disediakan, task yang sungguh butuh dekomposisi dikerjakan serampangan.

## Pola

### Ambang konkret: tiga langkah, bukan perasaan

Deskripsi tool `write_todos` di `langchain` menaruh angka pada keputusan
yang biasanya dibiarkan kabur: **"if the user's request is trivial and
takes less than 3 steps, it is better to NOT use this tool and just do the
task directly."** `[code]` `langchain/agents/middleware/todo.py`
(`WRITE_TODOS_TOOL_DESCRIPTION`). Ini bukan saran vibes — ini heuristik
dengan angka yang bisa dipakai ulang: kalau dekomposisi tugas menghasilkan
kurang dari tiga langkah berbeda, biaya menulis+memperbarui daftar (minimal
satu tool call untuk membuat, satu lagi untuk menandai progres, satu lagi
untuk menutup) lebih besar dari nilai yang didapat — daftarnya sendiri jadi
tugas tambahan, bukan alat bantu tugas.

### Eksplisit (artefak yang bertahan) vs implisit (reasoning sesaat)

Bedanya bukan soal seberapa detail rencananya, tapi **di mana rencana itu
hidup**:

- **Implisit** — rencana ada di reasoning model untuk giliran saat ini,
  tidak pernah ditulis sebagai state terpisah. Murah (nol tool call
  tambahan), tapi menghilang begitu context yang menampungnya dikompaksi
  atau sesi di-resume dari checkpoint — pemanggil di luar model tidak bisa
  melihat rencana itu sama sekali, cuma efeknya (urutan tool call yang
  terjadi), dan kalau sesi terputus di tengah, rencana harus disimpulkan
  ulang dari transkrip, bukan dibaca langsung.
- **Eksplisit** — rencana ditulis sebagai state terstruktur yang bertahan
  lepas dari pesan percakapan. `PlanningState.todos` (`langchain`) adalah
  field state terpisah dari `messages` — `write_todos` menimpa field
  `todos` lewat `Command(update={"todos": todos, ...})`, bukan menulis
  rencana sebagai teks yang tercampur di riwayat pesan. `[code]`
  `langchain/agents/middleware/todo.py` (fungsi `_write_todos`, kelas
  `TodoListMiddleware`, `state_schema = PlanningState`). Konsekuensinya
  konkret: `SummarizationMiddleware`/kompaksi apa pun beroperasi pada
  `messages`, bukan pada field state lain — daftar todo yang sudah ditulis
  tidak ikut hilang saat riwayat pesan lama diringkas, karena ia bukan
  bagian dari `messages` yang diringkas. Ini beda konkret dengan rencana
  implisit yang hanya ada sebagai reasoning di dalam pesan — begitu pesan
  itu ikut terlipat kompaksi, rencananya ikut hilang.

Bentuk eksplisit juga memaksa disiplin yang tidak didapat gratis dari
reasoning implisit: dokumentasi tool `write_todos` mendaftar aturan kapan
**tidak boleh** menandai selesai — ada isu belum terselesaikan, kerjaan
parsial, ada blocker, standar kualitas belum terpenuhi `[code]`
`langchain/agents/middleware/todo.py` (`WRITE_TODOS_TOOL_DESCRIPTION`,
bagian "Never mark a task as completed if"). Daftar eksplisit dengan status
per-item bisa diperiksa terhadap aturan ini secara langsung (baris mana
yang ditandai selesai, apakah memang beres); reasoning implisit tidak
punya objek yang bisa diperiksa sama sekali.

### Rencana bukan jawaban — dan bukan sinyal berhenti

Dua jebakan yang berulang pada bentuk eksplisit, keduanya didokumentasikan
langsung di deskripsi tool `write_todos` `[code]`: (1) menandai todo
terakhir selesai **bukan** jawaban untuk user — hasil substantif yang
diminta (angka, ringkasan, perbandingan) wajib muncul sebagai konten pesan
**setelah** panggilan `write_todos` terakhir, bukan dianggap terwakili oleh
status "completed"; (2) selesainya semua item todo tidak dengan sendirinya
jadi sinyal loop berhenti — mekanisme berhenti tetap seperti dijelaskan
[`agent-loop.md`](agent-loop.md) (implisit: tidak ada `tool_calls` lagi;
atau eksplisit kalau proyek membangun tool penyelesaian sendiri). Todo list
adalah alat bantu memori/progres, **bukan** loop shape — loop ReAct biasa
tetap bisa memakai todo list sebagai pencatat internal tanpa berubah jadi
bentuk plan-execute (yang berhenti karena rencana habis, lihat
`agent-loop.md`); keduanya sumbu yang berbeda dan bisa dikombinasikan atau
tidak secara independen.

### Rencana yang tidak dijaga jujur lebih buruk dari tidak ada rencana

Daftar todo yang menandai satu langkah "completed" padahal jejak tool call
menunjukkan langkah itu sebenarnya gagal/dilewati memberi kepercayaan diri
palsu ke pembaca (user, atau proses lain yang membaca state) — lebih buruk
dari tidak ada rencana sama sekali, karena tidak ada rencana setidaknya
tidak mengklaim apa-apa. Aturan "jangan tandai selesai kecuali sungguh
selesai" di atas adalah pertahanan terhadap ini, tapi aturan itu cuma di
prompt/deskripsi tool — kepatuhannya bergantung pada model, sama seperti
argumen `guardrails.md` §Kebijakan tidak boleh hanya di prompt. Berbeda
dengan kelas kebijakan yang dibahas [`policy-as-data.md`](policy-as-data.md),
"apakah langkah ini sungguh selesai" pada umumnya **tidak** verifiable
lewat kode murni — memverifikasinya butuh definisi "selesai" per task yang
biasanya sama kompleksnya dengan menjalankan taskny sendiri (mis. lulus
test untuk task koding bisa diverifikasi kode, tapi "riset ini sudah
cukup mendalam" tidak). Batas ini penting diakui eksplisit: sebagian
disiplin planning tetap tinggal di ranah judgment model, bukan semuanya
bisa dipindah ke enforcement kode.

## Trade-off

- **Todo list eksplisit vs reasoning implisit** — eksplisit membayar token
  + giliran tool call ekstra per pembaruan, sebagai gantinya dapat
  resumability (bertahan lepas dari kompaksi pesan), visibilitas ke
  pemanggil/observer, dan disiplin status yang bisa diperiksa. Implisit
  nol biaya tambahan tapi rencananya hilang begitu context yang
  menampungnya dikompaksi, dan pemanggil di luar model tidak pernah melihat
  rencana itu, cuma efeknya.
- **Ambang ≥3 langkah ditegakkan lewat judgment model (deskripsi tool) vs
  ditegakkan harness (keputusan aplikasi di muka, per tipe task/arketipe)**
  — judgment model fleksibel per permintaan (beradaptasi ke kompleksitas
  aktual tiap request) tapi bergantung pada model sungguh mengikuti
  instruksi deskripsi tool, dan menghitung "berapa langkah" sebelum rencana
  itu sendiri ada adalah masalah ayam-telur yang pada dasarnya butuh
  judgment, bukan pemeriksaan kode murni. Keputusan di level harness
  (mis. arketipe Workflow Agent selalu memakai plan-execute, arketipe
  In-App Copilot nyaris tidak pernah butuh todo list karena horizon-nya
  pendek) menghapus keputusan per-request tapi kurang presisi untuk task
  yang tidak cocok pola arketipenya.
- **Todo list sebagai bantu-memori (ReAct + state todos) vs plan-execute
  penuh (loop berhenti karena rencana habis)** — bantu-memori murni tetap
  fleksibel menghadapi kejutan di tengah jalan (todo cuma dicatat ulang,
  loop tidak terikat menyelesaikan rencana persis seperti ditulis semula),
  tapi tidak memberi jaminan "semua langkah rencana akan dieksekusi" —
  model bisa berhenti (implisit) sebelum rencana tuntas tanpa mekanisme
  yang memaksanya kembali. Plan-execute penuh menjamin cakupan rencana tapi
  butuh mesin replanning terpisah begitu rencana ternyata salah di tengah
  jalan (lihat `agent-loop.md`).

## Di deepagents

`TodoListMiddleware` **bukan** bagian stack default `create_deep_agent` —
harus disuntik eksplisit lewat `middleware=[TodoListMiddleware()]`, sumbernya
`langchain.agents.middleware`, bukan `deepagents`. `[code]` dikutip
`../systems/deepagents.md` §5 (`deepagents/graph.py` baris 361-402, daftar
base stack tidak menyebut `TodoListMiddleware`). `DeepAgentState` sendiri
tidak menambah field `todos` — begitu `TodoListMiddleware` dipasang, state
graph bertambah `PlanningState.todos` dari `langchain`, lihat `## Pola` di
atas untuk sifatnya (terpisah dari `messages`, tidak ikut terlipat
kompaksi). `[code]` `langchain/agents/middleware/todo.py`, dikutip
`../systems/deepagents.md` §5.

Middleware ini menyuntik `WRITE_TODOS_SYSTEM_PROMPT` ke ujung system
message lewat `wrap_model_call` **tiap kali** model dipanggil (`request.override(
system_message=new_system_message)`, membangun ulang `SystemMessage` dengan
blok tambahan) — bukan sekali di awal sesi. `[code]`
`langchain/agents/middleware/todo.py` (method `wrap_model_call`,
`TodoListMiddleware`). Isi teks yang disuntikkan itu sendiri statis (sama
persis tiap call), jadi tidak mengubah argumen cache-friendliness di
[`context-engineering.md`](context-engineering.md) — yang berubah tiap
giliran adalah **field state** `todos`, bukan teks instruksi penggunaannya.

Tool `write_todos` sendiri hanya boleh dipanggil sekali per giliran model
(mencegah dua panggilan paralel yang saling menimpa field `todos`, karena
tool ini mengganti seluruh daftar, bukan menambah satu item), dan
deskripsinya secara eksplisit memisahkan "menandai todo selesai" dari
"memberi jawaban ke user" — dua tindakan berbeda yang wajib dua pesan
berbeda. `[code]` docstring kelas `TodoListMiddleware`,
`WRITE_TODOS_TOOL_DESCRIPTION` bagian "When You Finish",
`langchain/agents/middleware/todo.py`.

## Sumber

- `[code]` `langchain/agents/middleware/todo.py` (paket `langchain==1.3.16`,
  dibaca dari `references/recipes/.venv/lib/python3.13/site-packages/`,
  venv riset yang sama dengan `../systems/deepagents.md`) —
  `WRITE_TODOS_TOOL_DESCRIPTION` (ambang ≥3 langkah, aturan "Never mark a
  task as completed if", bagian "When You Finish"), `WRITE_TODOS_SYSTEM_PROMPT`,
  kelas `Todo`/`PlanningState`/`TodoListMiddleware`, fungsi `_write_todos`,
  method `wrap_model_call`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 State
  & resume (`TodoListMiddleware` bukan default, tidak ada field `todos` di
  `DeepAgentState` bawaan) — tier-1 reference terverifikasi Task 3.
- `[code]` [`agent-loop.md`](agent-loop.md) — taksonomi loop shape
  (implisit/eksplisit/plan-execute) yang dirujuk untuk membedakan todo list
  sebagai bantu-memori dari plan-execute sebagai bentuk loop; ditulis dalam
  task yang sama, tidak diusulkan ulang di sini.
- `[code]` [`policy-as-data.md`](policy-as-data.md) §Tes pembeda — dirujuk
  untuk batas "apakah suatu langkah sungguh selesai" umumnya tidak
  verifiable kode, kontras dengan kelas policy yang bisa dipindah ke data.
- `[code]` [`context-engineering.md`](context-engineering.md) — dirujuk
  untuk klaim teks `WRITE_TODOS_SYSTEM_PROMPT` yang statis tidak mengganggu
  cache-friendliness system message.
- `[code]` [`guardrails.md`](guardrails.md) §Kebijakan tidak boleh hanya di
  prompt — dasar argumen kepatuhan aturan "jangan tandai selesai sebelum
  sungguh selesai" yang cuma di deskripsi tool, tidak diusulkan ulang di
  sini.
