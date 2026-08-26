# Code orchestration (interpreter, PTC, dynamic subagent)

## Masalah

Satu giliran model menghasilkan satu batch tool call, dan batch itu **beku
begitu diterbitkan**. Tidak ada yang bisa mengulang, bercabang atas hasil,
mencoba lagi setelah gagal, atau menyuapkan keluaran satu panggilan ke
panggilan berikutnya tanpa giliran model baru. Tiga biaya mengalir dari
satu fakta ini, dan ketiganya sering disalahartikan sebagai masalah yang
berbeda-beda:

- **Biaya token.** Tiap hasil antara mendarat di context, termasuk hasil
  yang cuma jadi masukan langkah berikutnya dan tak pernah dibaca manusia
  maupun dipakai model untuk apa pun selain menyaring. Ini persoalan yang
  sama dengan `context-engineering.md`, tapi sumbernya bukan riwayat
  panjang — melainkan orkestrasi yang dipaksa lewat context.
- **Biaya cakupan.** Model yang memutuskan berapa panggilan diterbitkan
  cenderung mengambil **sampel**, bukan sensus. Minta ia memproses 300
  item dan yang kembali biasanya belasan yang "mewakili". Kegagalannya
  senyap: keluarannya terlihat benar, cuma tidak lengkap.
- **Biaya latensi.** N langkah berurutan = N giliran model, padahal
  banyak di antaranya tidak butuh penalaran sama sekali (sortir, gabung,
  parse, hitung, filter).

Memindahkan orkestrasi ke kode menyelesaikan ketiganya sekaligus. Tapi di
situ masalah yang sebenarnya buat perancang harness dimulai, dan ia tidak
kelihatan dari daftar keuntungan di atas: **setiap gerbang yang dibangun
harness dibangun di titik tool call.** Approval manusia, exclusion tool,
log per-panggilan, anggaran laju, kebijakan per-kapabilitas — semuanya
memasang diri di sana karena di sanalah dulu satu-satunya tempat agent
menyentuh dunia luar. Kode yang memanggil tool dari **dalam satu tool call
yang sudah disetujui** tidak melewati satu pun dari gerbang itu.

Jadi pola ini menukar giliran model dan token dengan **hilangnya kendali
per-panggilan**, dan pertukaran itu hampir selalu tak terlihat di
konfigurasi: yang tertulis cuma "aktifkan interpreter", sementara yang
berubah adalah letak batas kapabilitas seluruh sistem.

## Pola

### Interpreter di dalam loop ≠ sandbox terhadap lingkungan

Dua hal yang sama-sama "menjalankan kode" tapi punya blast radius,
gerbang, dan alasan hidup yang berbeda — menyamakannya membuat keduanya
salah dikonfigurasi:

- **Sandbox** (`sandboxing.md`) — kode yang **bertindak atas lingkungan**:
  perintah shell, pasang dependensi, jalankan tes, sunting berkas OS.
  Blast radius-nya lingkungan itu sendiri; isolasinya proses/kontainer.
- **Interpreter di dalam loop** — kode yang **menyusun tool, menyimpan
  state, dan memutuskan apa yang kembali ke model**. Secara bawaan ia
  tidak menyentuh apa pun: tanpa jembatan eksplisit ia cuma bisa
  menghitung dan menulis ke konsol. Blast radius-nya persis seluas
  jembatan yang dipasang, bukan seluas mesinnya.

Konsekuensi praktis: interpreter tanpa jembatan nyaris inert dan tidak
butuh gerbang berat. Yang butuh gerbang adalah **jembatannya**, satu per
satu.

### Dua jembatan kapabilitas, dua keputusan terpisah

Interpreter yang berguna selalu menembus batasnya lewat jembatan, dan tiap
jembatan adalah keputusan izin tersendiri — bukan satu sakelar "aktifkan
interpreter":

- **Jembatan tool (programmatic tool calling / PTC)** — sebagian tool
  agent diekspos sebagai fungsi di dalam kode. Allowlist-nya adalah
  batas izin: yang masuk daftar bisa dipanggil dalam loop, paralel, dan
  berulang tanpa satu pun giliran model di antaranya. Tool yang mahal,
  merusak, atau menyentuh sistem sensitif tidak otomatis pantas ada di
  sana hanya karena agent boleh memanggilnya lewat jalur normal — di
  jalur normal ia dipanggil sekali per giliran dan terlihat; di sini ia
  bisa dipanggil ratusan kali dalam satu tool call.
- **Jembatan subagent (dynamic subagent)** — kode men-dispatch subagent
  yang sudah dikonfigurasi. Ini menjadikan delegasi sebuah **operasi
  program**, bukan pilihan model per giliran: fan-out atas N item jadi
  loop, verifikasi jadi panggilan kedua ke subagent lain, dan alur
  rekursif (simpan working set di variabel, ambil irisan, panggil
  subagent, sintesiskan) jadi mungkin tanpa membanjiri context induk.
  Lihat [`delegation.md`](delegation.md) untuk kontrak hasil dan batas
  kedalaman yang tetap berlaku di jalur ini.

Postur bawaan yang sehat: kedua jembatan **tertutup**, dibuka satu per satu
dengan alasan tertulis. Sistem yang membuka keduanya lebar-lebar "supaya
fleksibel" telah memindahkan seluruh permukaan kapabilitasnya ke dalam satu
tool call yang tak terinspeksi.

### Kontrak "apa yang kembali ke model"

Tugas sebenarnya interpreter bukan menjalankan kode, melainkan **memutuskan
apa yang tidak perlu dilihat model**. Kontraknya perlu eksplisit di tiga
hal: nilai apa yang dianggap hasil (ekspresi terakhir? nilai yang
di-return?), apakah keluaran konsol ikut kembali, dan pada batas berapa
hasil dipotong. Tanpa pemotongan, pola ini gagal pada tujuannya sendiri —
kode yang mengembalikan array 300 elemen memindahkan seluruh hasil antara
ke context, persis yang hendak dihindari.

### Persistensi state interpreter adalah keputusan ketiga

Variabel di dalam interpreter bisa hidup dalam tiga rentang, dan pilihannya
menentukan hal-hal yang jauh dari sekadar kenyamanan:

- **per-panggilan** — tiap eksekusi mulai dari nol. Paling mudah dinalar,
  tidak menambah apa pun ke state sesi.
- **per-giliran** — variabel bertahan antar eksekusi dalam satu giliran,
  hilang di giliran berikutnya. Cukup untuk hampir semua orkestrasi.
- **per-thread** — variabel bertahan lintas giliran. Ini memindahkan
  memori interpreter **ke dalam state sesi**, dan dengan itu mewarisi
  seluruh pertanyaan `session-state.md`: di mana disimpan, seberapa besar
  boleh tumbuh, apa yang terjadi kalau restore gagal, dan milik siapa
  (`isolation-and-scoping.md` — memori interpreter yang bocor antar user
  adalah kebocoran data, bukan sekadar bug).

Yang mudah terlewat: snapshot memori interpreter memulihkan **variabel**,
bukan efek samping. Kalau kode di dalamnya sudah memanggil tool yang
mengubah dunia luar, memulihkan snapshot lama tidak membatalkan perubahan
itu — ia cuma mengembalikan catatan tentangnya. Rollback state ≠ rollback
efek.

### Gerbang bergeser dari "tiap tool call" ke "tiap eksekusi kode"

Ini konsekuensi paling penting dan paling sering ditemukan terlambat. Kalau
orkestrasi pindah ke kode, satu-satunya gerbang yang masih menyala adalah
gerbang pada **tool eksekusi kode itu sendiri**. Tiga strategi tersedia,
dan pilihannya wajib eksplisit di blueprint:

1. **Gerbang di eksekusi kode** — manusia menyetujui *program*-nya, bukan
   tiap panggilan. Kasar tapi masih satu titik henti; ia bergantung pada
   manusia yang benar-benar membaca kodenya, jadi hanya bermakna kalau
   kode yang disetujui pendek dan bisa dinilai.
2. **Gerbang di dalam yang didelegasikan** — approval dipasang di dalam
   spec subagent, sehingga tetap menyala meski dispatch-nya dari kode.
   Berlaku untuk jembatan subagent, tidak untuk jembatan tool.
3. **Tutup jembatannya** — untuk kapabilitas yang memang wajib
   di-approve per panggilan, jangan bawa ke dalam interpreter sama
   sekali; biarkan tetap di jalur tool call normal.

Dalam kerangka `guardrails.md`, jembatan yang terbuka tanpa salah satu dari
tiga di atas adalah titik penegakan yang **fail-open**: kebijakannya masih
tertulis di config, penegakannya tidak pernah dipanggil.

## Trade-off

- **Ekonomi context & cakupan vs kendali per-panggilan.** Keuntungannya
  nyata dan besar (hasil antara tidak masuk context, fan-out jadi sensus
  bukan sampel, N giliran model jadi satu). Ongkosnya juga nyata:
  approval per-panggilan, exclusion tool, dan audit per-panggilan berhenti
  bekerja di dalam kode. Ini bukan bug yang bisa ditambal — jalur
  eksekusinya memang berbeda. Sistem dengan blast radius kecil (baca-baca,
  hitung, cari) mendapat hampir seluruh keuntungan tanpa ongkosnya;
  sistem yang menulis, membelanjakan, atau mengirim ke pihak ketiga
  membayar penuh.
- **Determinisme vs permukaan kegagalan baru.** Kode menghilangkan
  variasi model dari langkah-langkah mekanis, tapi menambah kelas
  kegagalan yang sebelumnya tidak ada: error runtime bahasa, timeout,
  anggaran panggilan habis, hasil terlalu besar. Semua itu kembali ke
  model sebagai teks yang harus ia baca dan tafsirkan — jadi kualitas
  pesan error jadi bagian dari desain prompt, bukan cuma urusan runtime.
- **Persistensi lintas giliran vs berat state.** Nyaman (agent bisa
  melanjutkan pekerjaan panjang tanpa membangun ulang), tapi snapshot
  memori jadi bagian dari state sesi yang ikut ditulis tiap giliran.
  Pertanyaannya bukan "apakah muat" melainkan "apakah pantas ada di
  checkpoint yang disimpan, di-replay, dan dihapus menurut aturan
  retensi" (`retention-and-deletion.md`, `replay-and-forensics.md`).
- **Allowlist lebar vs sempit.** Lebar membuat model bisa menyusun apa
  pun tanpa kembali minta izin; sempit memaksa sebagian orkestrasi tetap
  lewat giliran model. Ukuran yang benar bukan "berapa tool" melainkan
  "kalau kode ini dipanggil 200 kali dalam satu eksekusi, apa yang
  terjadi" — dan itu pertanyaan per-tool, bukan per-daftar.
- **Observabilitas.** Fan-out dari dalam kode tidak terlihat di transkrip:
  yang tercatat cuma satu tool call berisi program dan satu hasil.
  Kecuali runtime-nya memancarkan event siklus hidup tersendiri, UI dan
  jejak audit kehilangan seluruh struktur pekerjaan yang sebenarnya
  terjadi (`observability.md`, `streaming-protocol.md`).

## Di deepagents

Kapabilitas ini **tidak ada di paket `deepagents`**. Ia hidup di paket
terpisah `langchain-quickjs`, yang `deepagents==0.7.8` deklarasikan sebagai
extra: `Requires-Dist: langchain-quickjs>=0.3.5; extra == "quickjs"`
(`[code]` — `deepagents-0.7.8.dist-info/METADATA`). Dokumentasi upstream
menyebut syaratnya `langchain-quickjs>=0.2.0` (`[docs]` —
`../upstream/deepagents-docs/interpreters.md` baris 18) — **lebih longgar
daripada yang dipaksakan paketnya sendiri**; ikuti METADATA, bukan
dokumentasi. Statusnya `@beta()` (`[code]` — `middleware.py:120`), jadi
perilaku lifecycle-nya bisa berubah antar rilis.

Masuknya lewat `middleware=[CodeInterpreterMiddleware(...)]`, artinya ia
mendarat di **slot middleware user** — di antara base stack dan tail stack
([`../deepagents/middleware.md`](../deepagents/middleware.md) §Urutan
stack). Seluruh konsekuensi urutan di bawah mengalir dari posisi itu.

**Jembatan tool (PTC)** — `ptc=` menerima daftar nama tool atau instance
`BaseTool`; `None` (bawaan) = tertutup. Tool diekspos sebagai
`tools.<camelCase>(input) => Promise<string>` (`[code]` —
`_ptc.py:35,48-116`). Pemetaan camelCase-nya sendiri disebut dokumentasi
(`[docs]` — `interpreters.md` baris 184); tiga batasan berikut tidak:

- Nama tool wajib memetakan ke identifier JavaScript yang sah
  (`/^[A-Za-z_$][A-Za-z0-9_$]*$/`), kalau tidak konstruksi melempar
  `ValueError` (`[code]` — `_ptc.py:134-144`). Relevan buat permukaan tool
  MCP yang namanya sering berprefiks/berpemisah tak lazim (`mcp.md`).
- `ptc=["task"]` **ditolak** dengan `ValueError` — tool `task` dicadangkan
  karena sudah tersedia sebagai global `task()`, dan jalur `tools.task`
  akan membuang `responseSchema` (`[code]` — `_ptc.py:37-45,86-93`).
- Anggaran `max_ptc_calls` (bawaan 256) dihitung per eksekusi kode;
  melewatinya melempar dari sisi host sebelum tool dipanggil
  (`[code]` — `middleware.py:51,132-137`, `_repl.py:90-106`).
  `max_ptc_calls=None` mematikan anggaran dan membuka pola DoS
  panggilan-host tak terbatas — docstring-nya menyebut ini eksplisit.

**Jembatan subagent** — `subagents=True` (bawaan) memasang global `task()`
begitu agent punya tool `task` deepagents, dideteksi lewat nama tool plus
kehadiran field `description`+`subagent_type` di skemanya (`[code]` —
`_subagent.py:165-173`). `task()` menerima `description`, `subagentType`,
serta dua field yang **tidak lengkap disebut dokumentasi**: `label`
(untuk pelabelan event; `[code]` — `_repl.py:539-566`) dan `responseSchema`.
`responseSchema` dipasang sebagai `AutoStrategy` per-dispatch dan hasilnya
di-`json.loads` sebelum kembali ke kode, dengan batas keras: ≤4096 byte
terserialisasi, kedalaman ≤5, total properti ≤32 (`[code]` —
`_subagent.py:33-40,209-213,275-307`). Ini `structured-output.md` yang
berlaku di dalam loop kode, bukan di batas API.

**Gerbang** — inilah bagian yang paling penting dicatat. **Dua** jalur
melewati `interrupt_on`, dan keduanya diperingatkan baik oleh source maupun
dokumentasi:

- PTC "do **not** go through the normal `ToolNode` path… `interrupt_on` /
  HITL approval workflows are not enforced per PTC-invoked tool call"
  (`[code]` — `middleware.py:179-183`, `_ptc.py:76-79`; `[docs]` —
  `interpreters.md` baris 282-284).
- `task()` "run inside an already-approved `eval` invocation and do not
  trigger parent-level `interrupt_on` / HITL approval per dispatch"
  (`[code]` — `middleware.py:158-163`; `[docs]` — `dynamic-subagents.md`
  baris 1278-1280). Peringatan kedua ini **hanya ada di halaman
  `dynamic-subagents`** — ringkasan §Dynamic subagents di halaman
  `interpreters` (baris 286-311) tidak membawanya, dan tabel konfigurasi
  di baris 564 cuma menyebut `subagents=False` sebagai cara "require
  dispatch through the normal `task` tool" tanpa mengaitkannya ke
  approval. Pembaca yang berhenti di halaman interpreters melewatkannya.

Tiga mitigasi di §Pola bukan karangan KB ini — ketiganya disebut docstring
`middleware.py:161-163`: "Gate the `eval` tool itself, add approval
middleware inside subagent specs, or set `subagents=False`". Dokumentasi
hanya menyebut yang pertama (`dynamic-subagents.md` baris 1279). Yang pertama
bekerja karena `HumanInTheLoopMiddleware` ada di tail stack dan menyala
atas nama tool di `interrupt_on`, sementara tool `eval` didaftarkan
middleware user — jadi `interrupt_on={"eval": True}` menggerbangi
programnya (`[inferred]` dari `../deepagents/middleware.md` §Urutan stack +
`middleware.py:263`; belum dieksekusi). Yang kedua bekerja karena
`GraphInterrupt` sengaja di-**re-raise** tanpa dibungkus, jadi interrupt
dari dalam subagent merambat naik menembus jembatan (`[code]` —
`_subagent.py:247-248`).

**Exclusion tool tidak mengikat PTC.** `_ToolExclusionMiddleware`
di-`append` paling akhir sehingga jadi lapisan `wrap_model_call` **paling
dalam**, sementara `CodeInterpreterMiddleware` sebagai middleware user
berada lebih luar dan membaca `request.tools` **sebelum** exclusion
berjalan (`[code]` — `middleware.py:446,455-463`; aturan komposisi onion
`m[0]` terluar terverifikasi di `../deepagents/middleware.md` §Interaksi
berbahaya, `langchain/agents/factory.py:349`). Artinya tool yang dibuang
`HarnessProfile.excluded_tools` tetap terjangkau lewat `tools.*` bila
namanya ada di allowlist PTC. `[inferred]` — disusun dari dua fakta
`[code]` di atas, belum dieksekusi; kalau profil dan allowlist PTC
dikelola dua orang berbeda, ini lubang yang tidak akan muncul di review
config mana pun.

**Persistensi** — `mode="thread"` (bawaan) / `"turn"` / `"call"`
(`[code]` — `middleware.py:81-95,211-224`). Snapshot dipulihkan di
`before_agent` dan ditulis di `after_agent`, lalu slot REPL selalu
di-evict (`[code]` — `middleware.py:343-365,501-533`). Dua hal yang tidak
disebut dokumentasi:

- Snapshot disimpan sebagai **rantai patch biner**, bukan salinan penuh:
  field `_quickjs_snapshot_payload` adalah `PrivateStateAttr` beranotasi
  `DeltaChannel(replay_snapshot_chain)`, dan paketnya menarik `bsdiff4`
  sebagai dependensi (`[code]` — `middleware.py:58-67`,
  `langchain_quickjs-0.3.5.dist-info/METADATA`). Karena `PrivateStateAttr`,
  ia tidak mengalir balik ke induk lewat kontrak hasil subagent
  ([`delegation.md`](delegation.md) §Di deepagents) — tapi ia **ada** di
  checkpoint.
- `max_snapshot_bytes` bawaan = `memory_limit` = 64 MiB (`[code]` —
  `middleware.py:49,242-244`). Itu langit-langit per-thread yang sangat
  tinggi untuk sesuatu yang ikut tertulis ke checkpointer tiap giliran;
  turunkan sadar-sadar, jangan biarkan bawaan.

Kegagalan snapshot — baik saat restore maupun create — ditangkap,
di-`logger.warning`, lalu payload di-set `None` (`[code]` —
`middleware.py:358-364,524-530`). Dalam taksonomi `guardrails.md` ini
**fail-open**: pekerjaan lanjut dengan memori interpreter hilang
diam-diam, dan yang menandainya cuma satu baris log.

**Isolasi per-user butuh `thread_id`.** REPL di-key oleh `thread_id` dari
config LangGraph; kalau tidak ada, dipakai fallback `session_<uuid8>` yang
di-generate **sekali per instance middleware** (`[code]` —
`middleware.py:98-117,262`). Docstring kelas menjanjikan "globals from one
conversation cannot leak into another" (`middleware.py:122-125`) — janji
itu berlaku **hanya** kalau `thread_id` benar-benar diset. Satu instance
`CodeInterpreterMiddleware` yang dipakai ulang lintas user tanpa
`thread_id` membagi satu REPL, dan variabel JS user A terbaca user B.
Ini [`isolation-and-scoping.md`](isolation-and-scoping.md) §Prasyarat yang
membatalkan semuanya dalam bentuk lain: kontrol yang benar, dinonaktifkan
oleh konfigurasi yang hilang.

**Observabilitas fan-out** tersedia dan berguna: tiap dispatch memancarkan
`start` → `complete`/`error` di stream `custom` LangGraph, bertipe
`"subagent"`, dengan `id` per-dispatch, `eval_id` yang mengelompokkan satu
batch fan-out, `duration_ms`, dan `error` (`[code]` — `_subagent.py:30,
55-134,221-271`). Ini yang membuat panel fan-out langsung mungkin dibangun
(`streaming-protocol.md`). Perlu dicatat: `_emit_subagent_event` menelan
semua exception agar observabilitas tak pernah menggagalkan dispatch
(`[code]` — `_subagent.py:137-154`) — jadi hilangnya event bukan tanda
subagent-nya gagal.

**Pemicunya sebagian berupa kata kunci bahasa Inggris.** Dokumentasi
menyatakan prompt sistem interpreter memperlakukan kata **"workflow"**
sebagai sinyal untuk mengorganisasi kerja lewat interpreter dan
men-dispatch subagent dari kode, dan menganjurkannya sebagai "a deliberate
lever you can pull to opt into dynamic orchestration" (`[docs]` —
`dynamic-subagents.md` baris 145). Untuk produk multilingual ini persis
masalah yang dibahas [`multilingual.md`](multilingual.md): jalur eksekusi
yang berbeda dipilih berdasarkan kata dalam satu bahasa tertentu, sehingga
user berbahasa Indonesia yang meminta hal yang sama tidak mendapat perilaku
yang sama. Kalau orkestrasi dinamis memang diinginkan secara konsisten,
jangan bergantung pada pemicu ini — nyatakan di system prompt sendiri, atau
picu lewat struktur permintaan alih-alih kosakata.

**Dua kekeliruan dokumentasi lain yang perlu diketahui sebelum tuning:**

- `timeout` dijelaskan sebagai "timeout limit in seconds for each `eval`
  call" (`[docs]` — `interpreters.md` baris 558). Source: itu benar hanya
  untuk jalur async; pada jalur **sync**, `timeout` dipakai sebagai
  anggaran **kumulatif** untuk seluruh context (`[code]` —
  `_repl.py:401-405`). Agent sync berumur panjang akan melihat semua
  eksekusinya mulai timeout tanpa satu pun program yang melambat.
- Prompt PTC di-cache berdasarkan **himpunan nama** tool yang terekspos,
  bukan identitasnya. Kalau sebuah tool tetap bernama sama tapi skemanya
  berubah antar giliran, model membaca signature basi — komentar source
  menyatakan konsekuensinya ditanggung pemanggil (`[code]` —
  `middleware.py:466-476`).

## Sumber

- `[code]` `langchain_quickjs==0.3.5` — `middleware.py`, `_ptc.py`,
  `_subagent.py`, `_repl.py`. **Bukan** dari venv `../recipes/.venv`
  (yang sengaja tidak diubah agar sitasi baris paket lain tidak bergeser);
  dibaca dari venv terpisah. Reproduksi:
  `uv venv qjs && VIRTUAL_ENV=qjs uv pip install "langchain-quickjs==0.3.5"`,
  lalu baca di `qjs/lib/python3.*/site-packages/langchain_quickjs/`.
- `[code]` `deepagents-0.7.8.dist-info/METADATA` (venv
  `../recipes/.venv/lib/python3.13/site-packages/`) — baris
  `Provides-Extra: quickjs` dan `Requires-Dist: langchain-quickjs>=0.3.5;
  extra == "quickjs"`, dasar klaim "extra ada di 0.7.8" dan pertentangan
  dengan `>=0.2.0` di dokumentasi.
- `[docs]` [`../upstream/deepagents-docs/interpreters.md`](../upstream/deepagents-docs/interpreters.md)
  — snapshot verbatim; dipakai untuk klaim tentang apa yang dokumentasi
  **sebutkan** dan **tidak sebutkan** (syarat versi baris 18, peringatan
  PTC baris 282-284, tabel konfigurasi baris 555-566).
- `[docs]` [`../upstream/deepagents-docs/dynamic-subagents.md`](../upstream/deepagents-docs/dynamic-subagents.md)
  — snapshot verbatim; input `task()` (`description`/`subagentType`/
  `responseSchema`, tanpa `label`) dan enam pola orkestrasi bernama
  (classify-and-act, fan-out, adversarial verification, generate-and-filter,
  tournament, loop-until-done).
- `[code]` [`../deepagents/middleware.md`](../deepagents/middleware.md)
  §Urutan stack, §Interaksi berbahaya — posisi slot middleware user,
  aturan komposisi onion (`langchain/agents/factory.py:349`), dan posisi
  `_ToolExclusionMiddleware`; dipakai tanpa membaca ulang `factory.py`.
- `[code]` [`delegation.md`](delegation.md) §Di deepagents —
  `PrivateStateAttr` tidak mengalir balik ke state induk; dipakai untuk
  menyimpulkan letak `_quickjs_snapshot_payload` relatif ke kontrak hasil.
- `[inferred]` Dua klaim ditandai eksplisit di badan teks dan belum
  dieksekusi: (a) `interrupt_on={"eval": True}` menggerbangi program,
  (b) `HarnessProfile.excluded_tools` tidak mengikat allowlist PTC.
  Keduanya disusun dari fakta `[code]` yang disebut di tempatnya.
