# Tool design

## Masalah

Permukaan tool sebuah agent biasanya tumbuh secara organik: tiap fitur baru
"butuh tool baru", sampai model harus memilih dari puluhan-ratusan definisi
tool yang mirip di tiap giliran. Ini bukan cuma masalah estetika daftar
tool — tiap tool tambahan membesar prompt (skema + deskripsi tiap tool
dikirim ke model tiap call, lihat [`context-engineering.md`](context-engineering.md)),
memperbesar ruang pilihan yang harus dinilai model per giliran (lebih banyak
kandidat yang mirip = lebih besar peluang model memilih yang salah), dan
memperbanyak titik yang wajib dijaga guardrail-nya (`allowlist per peran` di
[`guardrails.md`](guardrails.md) titik 3 skalanya linear dengan jumlah
tool).

Arah sebaliknya — beberapa tool yang sangat luas (satu tool `execute` yang
bisa "melakukan apa saja") — punya masalah cermin: model harus
mengkonstruksi argumen yang lebih kompleks dan bebas (perintah shell bebas,
query SQL bebas) untuk tiap panggilan, validasi argumen jadi jauh lebih sulit
(skema `args_schema` untuk "string command bebas" pada dasarnya tidak
memvalidasi apa-apa selain "ini string"), dan blast radius satu kesalahan
argumen jauh lebih besar karena tool itu sendiri tidak membatasi apa yang
bisa dilakukan — pembatasannya sepenuhnya bergantung pada isi argumen yang
dihasilkan model. Tidak ada jawaban tunggal "berapa banyak tool" — pertanyaan
yang benar adalah trade-off eksplisit antara dua ekstrem itu untuk tiap
kelas kemampuan yang diekspos.

## Pola

### Sumbu granularitas: banyak-sempit vs sedikit-luas

| | Banyak tool sempit | Sedikit tool luas |
|---|---|---|
| Contoh | `create_file`, `read_file`, `list_files`, `delete_file`, `move_file`, ... satu tool per operasi | `execute` (satu nama, jalankan command shell/kode apa pun) |
| Validasi argumen | Skema per tool sempit dan spesifik — parameter `path`, `content` tervalidasi tipe/format sejak skema | Skema minim/generik (`command: str`) — validasi sesungguhnya (kalau ada) harus terjadi di dalam handler, bukan di skema |
| Beban pilihan model | Model memilih dari daftar panjang tool yang mirip; makin banyak tool, makin besar peluang pilih yang mirip tapi salah | Model tidak perlu memilih tool yang tepat (cuma satu), tapi harus mengkonstruksi argumen yang benar sendiri — beban pindah dari "pilih yang benar" ke "susun yang benar" |
| Blast radius kesalahan | Terbatasi bentuk tool itu sendiri — `delete_file` cuma bisa menghapus satu file yang disebut eksplisit di argumen | Tidak terbatasi tool — `execute("rm -rf /")` valid secara skema, salah secara niat; guardrail/sandbox harus menutup celah yang skema tidak tutup |
| Biaya prompt | Skema+deskripsi tiap tool dikirim tiap call — tumbuh linear dengan jumlah tool | Tetap kecil — satu definisi tool terlepas dari seberapa luas kemampuannya |
| Approval granular (HITL) | Bisa per-jenis-operasi (`interrupt_on={"delete_file": ...}` tanpa mengganggu `read_file`) — lihat [`human-in-the-loop.md`](human-in-the-loop.md) | Cuma bisa per-nama-tool luas itu — semua pemanggilan `execute` masuk approval yang sama meski isinya `ls` yang aman atau `rm -rf` yang destruktif, bisa dipersempit dengan predikat `InterruptOnConfig.when` atas isi argumen, tapi itu memindahkan pembedaan operasi ke kode aplikasi (parsing command) alih-alih ke skema tool yang model lihat |

### Heuristik pemilihan, bukan aturan tetap

Granularitas yang tepat bukan properti tool secara individual, tapi properti
**kelas kemampuan** yang diekspos:

- **Pisahkan tool kalau operasinya butuh kebijakan berbeda** — kalau
  `read_file` boleh dipanggil bebas tapi `delete_file` wajib approval
  (`guardrails.md` titik 3), keduanya **harus** jadi tool terpisah; satu
  tool `file_op(action, path)` yang menggabungkan keduanya memaksa gerbang
  approval untuk membaca isi argumen `action` sebelum tahu apakah harus
  berhenti — kebijakan pindah dari deklaratif (nama tool) jadi imperatif
  (baca argumen), persis penyakit yang `guardrails.md` §Kebijakan tidak
  boleh hanya di prompt tolak untuk kasus lain.
- **Gabungkan tool kalau kelas operasinya memang butuh keluasan yang
  legitimate** — eksekusi kode adalah kasus kanonik: mendaftar tiap
  kemungkinan operasi eksekusi sebagai tool terpisah (`run_python`,
  `run_shell`, `run_node`, ...) tidak menutup ruang yang sebenarnya
  terbuka (kode yang dijalankan tetap bisa melakukan apa saja dalam
  bahasa itu) — memecahnya cuma menambah daftar tool tanpa menambah
  keamanan nyata. Di sinilah "sedikit tool luas" menang: satu tool
  `execute` + sandbox/scope di *runtime*-nya (bukan di skema) adalah
  penegakan yang jujur soal di mana batasnya sungguh berada.
- **Nama tool yang benar tapi kemampuan yang salah adalah kelas defect yang
  paling mahal** — satu tool bernama `read_file` yang diam-diam juga bisa
  menulis (karena implementasinya digabung dengan `write_file` di belakang
  satu handler "biar DRY") lolos dari review yang cuma membaca nama tool
  di allowlist. Granularitas tool bukan cuma soal jumlah, tapi soal nama
  tool **secara jujur mencerminkan** cakupan kemampuannya — allowlist
  peran (`guardrails.md` titik 3) hanya seaman asumsi ini.

## Trade-off

- **Banyak tool sempit vs sedikit tool luas** — sudah dibahas penuh di
  tabel §Pola; ringkas: sempit memberi kontrol granular (approval per
  operasi, validasi ketat) dengan biaya permukaan tool yang besar dan
  beban pilihan model; luas memberi permukaan kecil dan fleksibilitas
  (tidak perlu mendaftar tiap operasi di muka) dengan biaya validasi/gerbang
  approval yang harus dipindah ke dalam handler/sandbox, bukan lagi
  didapat gratis dari bentuk tool.
- **Deskripsi tool yang detail vs ringkas** — deskripsi detail (contoh
  pemakaian, batasan eksplisit di docstring tool) membantu model memilih
  benar dan mengisi argumen benar, tapi menambah token yang dikirim tiap
  call untuk tool yang mungkin tidak dipakai giliran itu; deskripsi ringkas
  murah tapi menaikkan peluang model salah pilih di antara tool yang mirip
  — trade-off yang sama dengan disclosure progresif skill
  (`skill-composition.md`), cuma di lapis tool bukan lapis skill.
- **Skema ketat (tiap field tervalidasi Pydantic) vs skema longgar (`dict`/
  `str` bebas)** — skema ketat menolak argumen salah bentuk sebelum handler
  dipanggil sama sekali (fail-closed gratis, lihat `guardrails.md` titik 3
  "Validasi argumen tool"), tapi butuh didefinisikan ulang tiap field
  berubah; skema longgar fleksibel untuk tool yang argumennya sungguh
  bervariasi (`execute`) tapi memindah seluruh beban validasi ke dalam
  handler — kalau tidak ditulis eksplisit di sana, tidak ada validasi sama
  sekali.

## Di deepagents

`deepagents` sendiri adalah contoh konkret keputusan "sedikit tool luas,
by design" di permukaan filesystem/eksekusi-nya, bukan cuma teori:

- Tool bawaan dari `FilesystemMiddleware` — `ls`, `read_file`, `write_file`,
  `edit_file`, `glob`, `grep`, dan `execute` — tetap **satu nama** `execute`
  meski implementasinya berubah total tergantung backend yang dipasang
  (`StateBackend` vs `LocalShellBackend` vs sandbox pihak ketiga). Model
  tidak pernah melihat lebih dari satu tool eksekusi terlepas dari
  seberapa berbeda perilaku sesungguhnya di baliknya. `[code]` — dikutip
  [`../systems/deepagents.md`](../systems/deepagents.md) §3
  (`deepagents/backends/protocol.py`).
- `execute` **cuma muncul** kalau backend mengimplementasi
  `SandboxBackendProtocol` — untuk backend non-sandbox, `FilesystemMiddleware`
  memfilternya keluar sepenuhnya sebelum sampai ke model (bukan tool yang
  ada lalu menolak, tool itu tidak pernah terlihat). Ini pola yang sama
  dengan §Pola di atas: keluasan kemampuan (`execute` bisa menjalankan apa
  saja) diimbangi bukan dengan memecahnya jadi tool sempit, tapi dengan
  mengontrol **apakah tool itu ada sama sekali** berdasar backend yang
  dipasang. `[code]` — dikutip `../systems/deepagents.md` §3, §6
  (`THREAT_MODEL.md`: *"the execute tool is filtered out by
  FilesystemMiddleware when the backend does not implement
  SandboxBackendProtocol"*).
- `tools=[...]` pada `create_deep_agent` bersifat **aditif** — tool custom
  yang didaftarkan aplikasi selalu digabung dengan tool bawaan filesystem/
  eksekusi, tidak pernah menggantikannya. Ini relevan untuk keputusan
  granularitas aplikasi: menambah tool sempit khusus domain (mis.
  `send_invoice(customer_id, amount)`) tidak otomatis menghapus tool luas
  bawaan (`execute`) — kalau tim ingin tool luas itu tidak tersedia untuk
  agent tertentu, satu-satunya jalur resmi adalah
  `HarnessProfile.excluded_tools`, bukan sekadar tidak mendaftarkannya di
  `tools=`. `[code]` — dikutip `../systems/deepagents.md` §3
  (`deepagents/graph.py` baris 331-339, 787-788).
- Approval granular per tool (§Pola, baris "Approval granular (HITL)")
  dipetakan langsung ke `interrupt_on={"tool_name": True | InterruptOnConfig}`
  — per **nama** tool, bukan per isi argumen. Konsekuensi langsung dari
  granularitas: satu tool luas seperti `execute` yang diberi
  `interrupt_on={"execute": True}` menghentikan **semua** pemanggilan
  `execute` untuk approval, termasuk yang isinya perintah baca-saja yang
  aman — memecahnya jadi tool lebih sempit (mis. `execute_readonly` vs
  `execute_write`, kalau backend bisa membedakannya) adalah satu-satunya
  cara mendapat approval granular tanpa membaca isi argumen di dalam
  gerbang itu sendiri. `[code]` — dikutip
  [`../systems/deepagents.md`](../systems/deepagents.md) §6.

## Sumber

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §3
  (Tool surface), §6 (Safety gate) — tier-1 reference terverifikasi
  terhadap `deepagents==0.7.8`, dikutip langsung tanpa membaca ulang source
  di task ini.
- `[code]` [`guardrails.md`](guardrails.md) titik 3 (Tool/aksi) — dasar
  klaim allowlist per peran dan validasi argumen; tidak diusulkan ulang di
  file ini.
- `[code]` [`context-engineering.md`](context-engineering.md) — dasar
  klaim biaya prompt tumbuh dengan jumlah tool.
- `[code]` [`skill-composition.md`](skill-composition.md) — dasar analogi
  disclosure progresif untuk trade-off deskripsi tool.
- `[code]` [`human-in-the-loop.md`](human-in-the-loop.md) — dasar klaim
  approval granular per nama tool; tidak diulang mekanismenya.
