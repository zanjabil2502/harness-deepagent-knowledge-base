# Policy as data

## Masalah

`guardrails.md` §Kebijakan tidak boleh hanya di prompt sudah menutup argumen
**enforcement**: aturan di system prompt itu advisory, model bisa dibujuk
mengabaikannya (paling sering lewat teks di hasil tool yang menyamar sebagai
instruksi), jadi penegakan nyata harus hidup di kode yang berjalan di luar
kendali model. File ini tidak mengulang argumen itu — ia menambahkan argumen
yang berbeda dan berdiri sendiri, yang tetap berlaku **bahkan kalau model
selalu patuh 100%**: cara aturan **direpresentasikan** menentukan apakah
aturan itu bisa dikelola sama sekali, terlepas dari apakah model
mematuhinya.

Bayangkan model yang sempurna patuh — tidak pernah dibujuk, tidak pernah
salah paham. Prosa-sebagai-aturan tetap punya tiga penyakit struktural yang
murni soal representasi:

1. **Dilusi** — aturan ke-47 di system prompt melemahkan salience aturan
   1–46. Bukan karena model "lupa", tapi karena tidak ada mekanisme bahasa
   alami yang menjamin bobot perhatian merata di antara 47 kalimat imperatif
   yang bersaing, dan penulis prompt tidak punya cara memeriksa aturan mana
   yang kalah bersaing sebelum insiden membuktikannya.
2. **Presedensi implisit** — ketika dua aturan bertentangan ("selalu minta
   konfirmasi sebelum menghapus" vs "kalau user bilang 'langsung saja',
   jangan tanya lagi"), yang menang biasanya yang ditulis paling belakangan
   di prompt, bukan yang paling penting secara sengaja. Tidak ada penulis
   yang mendesain ini — itu efek samping urutan penulisan, dan berubah
   diam-diam tiap kali seseorang menambah kalimat baru di tempat yang salah.
3. **Tidak terlihat saat runtime** — prosa tidak punya identitas. Tidak ada
   cara menjawab "aturan mana yang aktif di turn ini", "aturan mana yang
   berubah minggu lalu", atau "tunjukkan semua kasus di mana aturan X
   seharusnya berlaku" tanpa membaca ulang paragraf demi paragraf secara
   manual. Aturan yang tidak punya identitas tidak bisa diuji di CI, tidak
   bisa di-diff di code review, dan tidak bisa dihitung presisi/recall-nya
   seperti tuntutan `evaluation.md` §Guardrail sebagai objek terukur —
   karena tidak ada objek untuk diukur, cuma teks.

Ketiganya adalah alasan `guardrails.md` mensyaratkan tiap guardrail
"menyatakan tiga hal: kebijakan, titik penegakan, mode kegagalan" sebagai
struktur eksplisit, bukan kalimat bebas — file ini menggeneralisasi struktur
itu jadi aturan tunggal yang berlaku lintas semua kebijakan, bukan cuma
guardrail: **kalau sebuah aturan bisa diverifikasi kode, aturan itu tidak
boleh hidup di prompt.** Prompt disisakan murni untuk hal yang butuh
judgment bahasa alami — nada bicara, cara merangkai jawaban, keputusan yang
memang tidak punya definisi benar/salah yang bisa dihitung.

## Pola

### Tes pembeda: bisa diverifikasi kode atau butuh judgment?

Pertanyaan pembeda bukan "apakah aturan ini penting" (semua aturan yang
ditulis orang terasa penting) tapi: **kalau diberi input dan output
konkret, bisakah fungsi deterministik memutuskan pass/fail tanpa memanggil
model?** Nama tool yang boleh dipanggil peran tertentu — verifiable (set
keanggotaan). Format sitasi wajib ada di jawaban yang mengklaim fakta —
verifiable (schema/regex check). "Jawab dengan empatik" — tidak verifiable,
tidak ada fungsi yang menghitung skor empati tanpa model itu sendiri
menjadi pemeriksa (dan begitu jadi model-as-judge, itu sudah guardrail
tingkat 3-4 di `guardrails.md` §Bertingkat, bukan lagi "policy as data").
Aturan yang verifiable pindah ke data + middleware; aturan yang tidak,
tetap di prompt — dan diberi label eksplisit sebagai keputusan, bukan
dibiarkan campur aduk dalam satu blok prosa yang sama.

### Bentuk data: satu policy = satu objek dengan identitas

Satu kebijakan verifiable direpresentasikan sebagai satu record, bukan satu
kalimat di tengah paragraf. Contoh konkret — kebijakan "jawaban yang
mengandung klaim faktual wajib menyertakan sitasi", salah satu dari daftar
`policies` yang dirujuk manifest skill di [`skill-composition.md`](skill-composition.md):

```yaml
id: require_citation
version: 3
applies_to: output
rule:
  type: schema_check
  condition: "claims_factual == true implies citations.length >= 1"
enforcement:
  point: output          # federasi ke titik 4 (`guardrails.md` §Enam titik)
  mechanism: RubricMiddleware
  failure_mode: fail-open-with-flag   # habiskan max_iterations, kirim + flag "belum lolos rubric"
owner: trust-and-safety
updated_at: 2026-08-20
```

Field yang membuat ini beda dari kalimat prosa bukan isinya (isinya bisa
dikatakan dalam satu kalimat juga) — tapi **strukturnya**: `id` memberi
identitas yang bisa dirujuk (dari manifest skill, dari golden test, dari
dashboard eval), `version` + `updated_at` memberi jejak yang bisa di-diff,
`applies_to`/`enforcement.point` menjawab langsung "di titik mana ini
ditegakkan" tanpa perlu membaca kode middleware untuk tahu, dan
`enforcement.failure_mode` memaksa keputusan eksplisit yang menurut
`guardrails.md` §Masalah kedua sering sengaja dilewatkan sampai default
kebetulan dari `try/except` yang menentukannya. Tiga field terakhir ini
langsung membalikkan tiga penyakit di `## Masalah`: `id` melawan invisibility
(bisa diquery), `version`/`updated_at` melawan presedensi implisit (urutan
perubahan tercatat, bukan tersirat dari posisi kalimat), dan keberadaan
sebagai record terpisah (bukan satu di antara 47 kalimat) melawan dilusi —
policy engine memproses tiap record independen, tidak ada "kalimat ke-47"
yang melemahkan kalimat lain karena tidak ada urutan baca linear yang
dilalui model untuk sampai ke situ.

### Titik penegakan: middleware membaca data, bukan menghafalnya

Policy sebagai data tidak berguna kalau middleware yang menegakkannya
mengulang logikanya sebagai kode hardcoded terpisah untuk tiap `id` — itu
cuma memindahkan dilusi dari prompt ke source code (47 `if` block yang
saling melemahkan alih-alih 47 kalimat). Pola yang benar: middleware generik
membaca record policy sebagai konfigurasi, bukan meng-hardcode isinya.
Untuk `require_citation` di atas, `enforcement.mechanism: RubricMiddleware`
berarti record ini **adalah** parameter yang disuntikkan ke rubric yang
dievaluasi `RubricMiddleware` — mengubah kebijakan berarti mengubah baris
YAML dan redeploy config, bukan mengubah kode middleware. Untuk kebijakan
yang lebih sederhana secara struktural — "tool `delete_file` hanya boleh
dipanggil peran `admin`" — bentuk datanya adalah baris di tabel
allowlist-per-peran, dan penegakannya adalah `excluded_tools`
(`HarnessProfile`) yang dibaca `_ToolExclusionMiddleware`
(`../systems/deepagents.md` §7, dikutip lagi di `guardrails.md` titik 3)
— middleware yang sama, tanpa perubahan kode, menegakkan set tool yang
berbeda untuk peran berbeda karena datanya yang berbeda, bukan cabang kode
yang berbeda per peran.

## Trade-off

- **Policy engine generik (baca data, satu middleware banyak policy) vs
  kode hardcoded per aturan** — engine generik memberi identitas/versi/query
  gratis untuk tiap policy baru (tinggal tambah record), tapi butuh
  investasi awal menulis engine + schema yang cukup ekspresif untuk kelas
  aturan yang akan datang; kalau cuma ada dua-tiga aturan verifiable yang
  tidak akan bertambah, `if` block langsung di middleware kustom lebih
  murah dan tidak butuh lapisan abstraksi tambahan. Titik baliknya bukan
  jumlah aturan hari ini, tapi laju pertambahannya — kalau policy baru
  ditambah tiap minggu, biaya engine terbayar cepat; kalau statis, tidak.
- **Granularitas policy (banyak record sempit vs sedikit record luas)** —
  policy sempit (`require_citation`, `pii_redact` terpisah) gampang
  dikomposisi ulang per skill (manifest `skill-composition.md` bisa
  menyalakan/mematikan satu-satu), tapi jumlah record membengkak dan tiap
  interaksi antar-policy (dua policy sama-sama menyentuh field output yang
  sama) harus dipikirkan eksplisit di layer resolusi. Policy luas
  ("kebijakan output komprehensif" satu record berisi banyak sub-aturan)
  lebih sedikit untuk dikelola tapi menghidupkan kembali dilusi di dalam
  satu record — masalah yang coba dihindari file ini pindah ke dalam field
  `rule` yang jadi paragraf lagi.
- **Data statis (YAML di repo, versioned bareng kode) vs data di
  database yang bisa diubah tanpa deploy** — YAML di repo memberi
  code-review dan rollback gratis lewat git (selaras `guardrails.md`
  §Prompt & policy versioning di checklist gerbang §12 spec), tapi
  perubahan kebijakan (mis. menaikkan threshold moderasi) butuh siklus
  deploy penuh. Policy di DB memungkinkan perubahan cepat tanpa deploy
  (penting untuk insiden yang butuh mitigasi dalam menit), tapi kehilangan
  jejak review/rollback git kecuali dibangun ulang secara terpisah
  (tabel audit sendiri, approval flow sendiri) — investasi yang persis
  argumen sirkular yang coba dihindari: kalau tidak dibangun eksplisit,
  perubahan policy di DB **juga** bisa jadi tidak terlihat saat runtime.

## Di deepagents

Tidak ada policy engine generik bawaan `deepagents` yang membaca skema YAML
seperti contoh di atas — ini `[ours]`. Vanilla-nya: `deepagents`/`langchain`
menyediakan middleware siap pakai yang parameternya **sudah** berbentuk data
terstruktur (bukan prosa) tapi tiap middleware membaca bentuk data miliknya
sendiri, bukan satu skema policy universal. Kita menyimpang dengan
mengusulkan satu skema (`id`/`applies_to`/`rule`/`enforcement`) yang
memetakan ke middleware yang beda-beda, karena tanpa lapisan itu tim yang
menambah policy baru harus tahu detail konstruksi tiap middleware satu
per satu alih-alih menulis satu record dan merujuk `enforcement.mechanism`
yang sudah ada.

Yang **bukan** `[ours]` — sudah data-shaped secara native di `deepagents`/
`langchain`, siap jadi target `enforcement.mechanism`:

| Kelas policy verifiable | Bentuk data native | Middleware pembaca |
|---|---|---|
| Tool mana boleh dipakai peran mana | `excluded_tools` (list nama tool) di `HarnessProfile` | `_ToolExclusionMiddleware` `[code]` dikutip `../systems/deepagents.md` §7 |
| Path/operasi filesystem mana yang diizinkan/dilarang/butuh approval | `FilesystemPermission(operations=[...], paths=[...], mode=...)`, list aturan urut, match pertama menang | `FilesystemMiddleware` `[code]` dikutip `../systems/deepagents.md` §6 |
| Tipe PII mana yang di-block/redact/mask/hash, di sisi mana (input/output/tool result) | Parameter `PIIMiddleware(pii_type=, strategy=, apply_to_*=)` | `PIIMiddleware` `[code]` `langchain/agents/middleware/pii.py`, dikutip `guardrails.md` |
| Batas jumlah tool-call/model-call per thread/run | `thread_limit=`/`run_limit=`/`exit_behavior=` | `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` `[code]` dikutip `guardrails.md` |

Baris-baris ini **sudah** policy-as-data dalam pengertian file ini —
parameter konstruksi middleware itu sendiri adalah data, bukan prosa di
system prompt. Yang ditambahkan skema `[ours]` di atas hanyalah lapisan
identitas/versi/lookup-by-id yang menyatukan baris-baris berbeda ini di
bawah satu cara merujuknya dari manifest skill (`skill-composition.md`),
karena tanpa itu tiap policy tetap harus dirujuk lewat nama parameter
middleware yang berbeda-beda, bukan satu `id` yang konsisten.

Untuk policy yang **tidak** punya middleware siap pakai (mis.
`require_citation` di atas, yang butuh evaluasi terhadap rubric, bukan
sekadar cek keanggotaan/regex) — `RubricMiddleware` (`../systems/deepagents.md`
§Middleware bawaan, tidak default) adalah target `enforcement.mechanism`
paling dekat: ia menerima rubric sebagai state yang disuntikkan aplikasi
(data), mengiterasi jawaban terhadapnya sampai lolos atau `max_iterations`.
`[code]` dikutip `../systems/deepagents.md` §Middleware bawaan
(`deepagents/middleware/rubric.py`).

## Sumber

- `[code]` [`guardrails.md`](guardrails.md) §Kebijakan tidak boleh hanya di
  prompt, §Masalah kedua (mode kegagalan yang tidak diputuskan), Enam titik
  penegakan — dasar argumen enforcement yang **tidak** diulang di file ini,
  hanya dirujuk dan digeneralisasi lewat field `enforcement`/`applies_to`.
- `[code]` [`evaluation.md`](evaluation.md) §Guardrail sebagai objek terukur
  — dasar klaim "tanpa identitas, tidak bisa diukur presisi/recall" di
  penyakit ketiga (§Masalah).
- `[code]` [`skill-composition.md`](skill-composition.md) — konsumen skema
  `id` policy lewat field `policies: [+require_citation, +pii_redact]` di
  manifest §8.5; ditulis dalam task yang sama, tidak diusulkan ulang di
  sini.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §6, §7,
  §Middleware bawaan — `FilesystemPermission`, `HarnessProfile.excluded_tools`,
  `_ToolExclusionMiddleware`, `RubricMiddleware` — tier-1 reference
  terverifikasi Task 3, dikutip tanpa membaca ulang source `deepagents` di
  task ini.
- `[code]` `langchain/agents/middleware/pii.py`, `tool_call_limit.py`,
  `model_call_limit.py` (langchain 1.3.16) — dikutip via `guardrails.md`,
  tidak dibaca ulang di task ini.
