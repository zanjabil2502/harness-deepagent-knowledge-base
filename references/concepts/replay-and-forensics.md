# Replay & forensics

## Masalah

Kejadian nyata: satu run agent melakukan sesuatu yang tidak seharusnya —
memanggil tool destruktif, membocorkan sesuatu, tersesat 40 langkah — dan
tim butuh tahu **persis** apa yang terjadi di run **itu**. Ini beda dari
`evaluation.md`: bukan menjalankan banyak kasus golden terhadap dunia yang
dibekukan untuk mendeteksi regresi, tapi merekonstruksi **satu eksekusi
nyata yang sudah terjadi**, di dunia yang variabel dan tidak terkontrol,
untuk investigasi. Tanpa rekaman yang cukup, "apa yang terjadi" cuma bisa
ditebak dari hasil akhirnya — argumen tool call yang sebenarnya, hasil
mentah yang diterima, keputusan guardrail mana yang terpicu/tidak, versi
model/prompt/threshold yang aktif saat itu — kalau salah satu dari itu tidak
tercatat, celahnya permanen untuk run itu, tidak bisa diisi belakangan.

Masalah kedua: apa yang wajib dicatat harus diputuskan **sebelum** insiden,
bukan sesudahnya — insiden tidak bisa ditambah logging setelah kejadian.
Field yang diam-diam tidak tercatat (mis. versi system prompt yang sungguh
aktif, argumen mentah tool call) adalah celah yang baru ketahuan tepat saat
paling dibutuhkan: saat investigasi insiden nyata sedang berlangsung.

## Pola

### Apa yang sudah tercatat, dan apa yang belum

`persistence-schema.md` sudah menyediakan sebagian besar bahan mentah —
file ini **tidak mengusulkan skema baru**, cuma memetakan apa yang cukup dan
apa yang masih celah:

- **Checkpoint per langkah** (`checkpoints`/`writes`, dimiliki library
  checkpointer, `thread_id` disamakan konvensi dengan `conversations.id`) —
  state graph penuh di tiap batas langkah, cukup untuk **menjalankan ulang**
  eksekusi persis dari titik itu (lihat §Rekonstruksi vs eksekusi-ulang di
  bawah). Kelemahannya sudah dilaporkan jujur di `persistence-schema.md`:
  byte-nya opaque, tidak ikut RLS, tidak bisa diquery per field (tidak bisa
  `SELECT` argumen tool call tertentu dari blob checkpoint tanpa
  mendeserialisasinya).
- **`tool_calls`** (`message_id`, `sequence`, `tool_name`, `arguments`
  JSONB, `result` JSONB, `status`, timestamp) — melengkapi kelemahan
  checkpoint di atas: tabel biasa yang bisa diquery ("tampilkan semua
  panggilan tool user ini dengan `tool_name=X` antara jam 2-3 pagi"), tidak
  perlu mendeserialisasi apa pun.
- **Celah yang belum tertutup skema Task 4** (dilaporkan di sini, bukan
  didesain ulang — di luar scope task ini): (a) versi model yang sungguh
  dipakai run itu — versi model berubah dari waktu ke waktu, replay dengan
  model hari ini terhadap insiden kemarin bukan rekonstruksi yang setia;
  (b) versi/threshold guardrail yang aktif saat itu — celah yang sama yang
  sudah ditandai `guardrails.md` §Di deepagents titik 6 ("tidak ada tabel
  audit bawaan"); (c) versi system prompt yang aktif — sudah ditandai
  gerbang production-readiness KB ini ("Prompt & policy versioning: tidak
  bisa rollback"). Ketiganya butuh **penanda versi eksplisit yang disimpan
  bersama run** (mis. sebagai bagian metadata turn/trace), bukan diasumsikan
  bisa direkonstruksi dari kode saat ini — kode saat ini bukan kode yang
  jalan saat insiden terjadi.
- **Keputusan guardrail per langkah** — tidak ada tempatnya di skema
  Postgres Task 4 (tabel `tool_calls` mencatat *hasil* tool, bukan *kenapa*
  guardrail meloloskan/memblokirnya). Rumah yang tepat untuk ini adalah
  trace observability (`observability.md` §Span per langkah), **dengan
  syarat** retensi trace itu cukup panjang untuk investigasi — kalau trace
  dihapus lebih cepat dari jendela investigasi insiden, keputusan guardrail
  untuk run lama tidak lagi bisa direkonstruksi dari mana pun.

### Rekonstruksi vs eksekusi-ulang — dua aktivitas beda di bawah satu kata "replay"

- **Rekonstruksi (read-only)** — menyusun linimasa dari checkpoint history +
  `tool_calls` + trace yang sudah terekam, tanpa menjalankan apa pun ulang.
  Selalu aman (tanpa efek samping, tanpa biaya tambahan), selalu bisa
  dilakukan selama rekamannya masih ada.
- **Eksekusi-ulang** — melanjutkan graph dari checkpoint tertentu, atau
  menjalankan ulang input yang sama, dan membiarkannya jalan lagi. Ini
  aktivitas yang **beda pertanyaan** dari rekonstruksi: bukan "apa yang
  terjadi saat itu", tapi "apa yang terjadi kalau dijalankan ulang sekarang
  (dg kode/model/guardrail hari ini)" — berguna untuk verifikasi fix, tapi
  bukan bukti forensik tentang insiden aslinya kalau kode yang jalan sudah
  berubah sejak itu.

Untuk eksekusi-ulang forensik, tool call **wajib** jalan lewat implementasi
mock/dry-run, tidak pernah tool destruktif nyata — beda dg replay harness
`evaluation.md` yang memang sejak awal didesain terhadap respons tool yang
dibekukan; di sini risikonya lebih tinggi karena input asalnya insiden nyata
yang mungkin memang memicu aksi destruktif — mengeksekusi ulang secara
literal mengulang kerusakannya.

## Trade-off

- **Retensi penuh trace/checkpoint (demi forensik) vs biaya penyimpanan +
  kewajiban retensi/privasi** (`retention-and-deletion.md` sudah menetapkan
  kebijakan hapus untuk data aplikasi) — forensik ingin menyimpan selama
  mungkin, retensi/privasi ingin menghapus sesuai jadwal/permintaan user.
  Selesaikan dengan mengikat retensi trace/checkpoint ke jadwal retensi yang
  **sudah** ditetapkan untuk data yang menjadi asalnya (bukan jam retensi
  kedua yang terpisah) — dikutip, tidak didesain ulang di sini.
- **Rekonstruksi-saja vs eksekusi-ulang** — rekonstruksi selalu aman tapi
  cuma bisa menjawab dari apa yang **sudah** tercatat (kalau field tertentu
  tidak pernah direkam, rekonstruksi tidak bisa mengisinya); eksekusi-ulang
  bisa mengungkap perilaku baru (mis. "apakah fix ini memperbaiki kasusnya")
  tapi punya biaya nyata (panggilan model/tool lagi) dan risiko efek samping
  kalau tool call tidak di-mock — untuk investigasi insiden, mock **wajib**,
  tidak opsional.
- **Checkpoint (state graph literal, bisa dilanjutkan eksekusinya) vs tabel
  aplikasi (`tool_calls`/`messages`, bisa diquery lintas banyak insiden)** —
  keduanya perlu untuk tujuan berbeda, bukan salah satu menggantikan yang
  lain; dualitas ini sudah ditetapkan `persistence-schema.md`, tidak
  diusulkan ulang.

## Di deepagents

Checkpoint per langkah yang membuat eksekusi-ulang mungkin secara prinsip
berasal dari `checkpointer` yang diteruskan **apa adanya** oleh `deepagents`
ke `langchain.agents.create_agent` — `deepagents` tidak pernah membangun
checkpointer sendiri, dan tidak membatasi kapabilitas checkpointer yang
disuntik aplikasi. `[code]` — dikutip `../systems/deepagents.md` §5 (State &
resume), `persistence-schema.md` §checkpointer.

LangGraph (fondasi `create_agent`/`create_deep_agent`) mendokumentasikan
fitur ini resmi sebagai **"time travel"**: tiap checkpoint disimpan dengan
kunci `(thread_id, checkpoint_id)`, dan melanjutkan eksekusi dari checkpoint
tertentu (bukan cuma checkpoint terbaru) dilakukan dengan meneruskan
`config={"configurable": {"thread_id": ..., "checkpoint_id": ...}}` ke
`invoke(None, config)` — argumen input `None` berarti "lanjutkan dari state
tersimpan", bukan mulai state baru. Riwayat checkpoint suatu thread bisa
dilihat lewat `get_state_history(config)`. `[docs]` —
`docs.langchain.com/oss/python/langgraph/use-time-travel`. `deepagents`
tidak menambah atau membatasi API ini — API `checkpointer` yang diekspos
persis API LangGraph, karena `deepagents` cuma meneruskannya.

Konsekuensi konkret untuk pola di atas: eksekusi-ulang forensik (dari
checkpoint tertentu) dan replay regresi `evaluation.md` (dari input awal
terhadap tool yang dibekukan) sama-sama memakai mekanisme `checkpointer`
yang sama secara teknis — bedanya cuma **titik mulai** (checkpoint tengah
run vs awal run baru) dan **apakah tool call di-mock** (forensik: wajib;
regresi: memang sejak awal didesain begitu) — bukan dua sistem berbeda yang
perlu dibangun terpisah.

## Sumber

- `[code]` [`persistence-schema.md`](persistence-schema.md) §checkpointer,
  tabel `tool_calls`, §Di deepagents — bahan mentah rekonstruksi
  (checkpoint + tabel aplikasi), gap checkpoint tidak ikut RLS/tidak
  queryable per field, dikutip tanpa mengusulkan skema baru.
- `[code]` [`guardrails.md`](guardrails.md) §Di deepagents titik 6 — gap
  "tidak ada tabel audit bawaan" untuk keputusan gerbang, dikutip ulang
  sebagai celah yang sama untuk keputusan guardrail per langkah.
- `[code]` [`observability.md`](observability.md) §Span per langkah — rumah
  yang tepat untuk keputusan guardrail per langkah, dg syarat retensi trace
  cukup panjang.
- `[code]` [`evaluation.md`](evaluation.md) §Golden transcript + replay
  harness — dirujuk untuk membedakan replay-regresi dari replay-forensik,
  ditulis dalam task yang sama, tidak diusulkan ulang.
- `[code]` [`retention-and-deletion.md`](retention-and-deletion.md) —
  kebijakan hapus data aplikasi yang jadi dasar argumen "retensi
  trace/checkpoint mengikuti jadwal yang sudah ada, bukan jam kedua".
- `[docs]` LangGraph "time travel" —
  `docs.langchain.com/oss/python/langgraph/use-time-travel`, resume dari
  checkpoint tertentu lewat `config={"configurable": {"thread_id":,
  "checkpoint_id":}}` + `invoke(None, config)`, `get_state_history(config)`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 (State
  & resume) — `checkpointer`/`store` diteruskan apa adanya oleh
  `deepagents`, tier-1 reference terverifikasi Task 3, dikutip tanpa
  membaca ulang source `deepagents` di task ini.
