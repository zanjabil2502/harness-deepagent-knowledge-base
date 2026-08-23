# Evaluation

## Masalah

Eval yang cuma menilai "jawaban akhir cocok/tidak" (pola QA klasik: satu
input, satu output, satu skor) tidak menangkap sebagian besar kegagalan yang
mungkin di agent loop. Agent bisa sampai ke jawaban akhir yang benar lewat
jalan yang salah — memanggil tool destruktif yang seharusnya minta approval
lalu membatalkannya, membaca file di luar scope yang diizinkan lalu tidak
memakainya di jawaban, atau menghabiskan 40 langkah untuk tugas yang
seharusnya 3 langkah — dan semua itu **lolos** eval yang cuma memeriksa teks
akhir, karena metriknya tidak pernah melihat apa yang terjadi di antaranya.
Regresi jenis ini (path yang memburuk, jawaban akhir tetap sama) tidak
kelihatan sampai insiden nyata terjadi — approval gate yang "kebetulan"
selalu lolos di eval karena eval tidak pernah memeriksa apakah gate itu
sungguh dipanggil.

Masalah kedua: golden test yang cuma ditulis dalam satu bahasa (biasanya
bahasa tim yang menulisnya) membuat regresi di **bahasa lain** sepenuhnya tak
terlihat, bukan cuma kurang terlihat. Perubahan prompt, ganti model, atau
geser threshold guardrail yang memperbaiki perilaku di satu bahasa bisa
merusak total di bahasa lain tanpa sinyal apa pun di CI — sinyal pertama
yang didapat tim adalah laporan user, dan user yang melapor duluan biasanya
bukan yang berbahasa mayoritas suite eval-nya.

Masalah ketiga, federasi langsung dari `guardrails.md`: guardrail yang
dipasang tanpa pernah diukur presisi/recall-nya adalah klaim vendor yang
belum diverifikasi di domain produk sendiri — file ini adalah tempat klaim
itu diverifikasi.

## Pola

### Eval berbasis trajektori, bukan cuma jawaban akhir

Unit yang dinilai adalah **trajektori** penuh — urutan (panggilan model,
panggilan tool + argumen, hasil tool, keputusan guardrail) sepanjang satu
run — bukan cuma string jawaban terakhir. `[ours]` — vanilla-nya eval NLP
klasik: satu pasangan (input, output yang diharapkan), dinilai exact-match/
similarity. Kita menyimpang karena benar tidaknya jawaban agent bergantung
pada jalan yang ditempuh (tool apa yang dipanggil, apakah approval gate
sungguh dipicu, berapa langkah dipakai) — output akhir yang identik bisa
berasal dari trajektori yang aman atau yang berbahaya, dan hanya trajektori
yang bisa membedakannya.

Metrik konkret di luar "jawaban benar":

- **Ketepatan tool call** — tool yang dipanggil dan argumennya, dibanding
  yang seharusnya untuk kasus itu.
- **Efisiensi langkah** — jumlah langkah dibanding rentang wajar untuk kelas
  tugas itu (regresi "loop makin panjang" kelihatan di sini sebelum jadi
  masalah biaya nyata — lihat `cost-control.md`).
- **Ketepatan pemicu guardrail** — apakah approval gate/blokir sungguh
  terpicu pada kasus yang seharusnya, dan **tidak** terpicu pada kasus yang
  seharusnya lolos (lihat subbagian di bawah).

Dua cara menilai trajektori, bertingkat seperti guardrail (`guardrails.md`):
**assertion deterministik** (urutan tool call persis yang diharapkan) murah
dan reproducible, cocok untuk tugas berbentuk workflow yang jalannya memang
tunggal; **LLM-as-judge** menilai trajektori penuh terhadap rubric, dipakai
untuk tugas open-ended yang punya lebih dari satu jalan benar — dan judge
itu sendiri berbentuk guardrail (punya FP/FN rate, butuh kalibrasi berkala
terhadap sampel yang dinilai manusia), bukan kebenaran mutlak.

### Golden transcript + replay harness

**Golden transcript** `[ours]` — pasangan (input awal, rentang trajektori
yang diharapkan, state akhir yang diharapkan, tag `{bahasa, guardrail_ids}`)
yang di-versioning bersama kode prompt/tool, bukan disimpan terpisah sebagai
dokumen QA. Vanilla-nya: golden set klasik cuma menyimpan (input, output
yang diharapkan) — kita menambah rentang trajektori dan tag karena keduanya
persis yang dibutuhkan dua tuntutan lain di file ini (trajektori dan
multibahasa) supaya bisa diquery/diagregasi per dimensi itu, bukan cuma
dibaca satu-satu.

**Replay harness** menjalankan ulang input yang sama terhadap build agent
**saat ini** (bukan memutar ulang output yang direkam) lalu men-diff
trajektori hasilnya terhadap ekspektasi golden. Supaya hasilnya tidak flaky
karena dunia luar berubah (API pencarian yang dipanggil tool berubah hasil
antar run), respons tool eksternal **direkam dan dibekukan** saat golden
transcript dibuat — yang boleh bervariasi run-ke-run cuma keputusan model,
bukan lingkungan yang ia tindaklanjuti. Ini beda tujuan dari
[`replay-and-forensics.md`](replay-and-forensics.md): replay di sana
merekonstruksi **satu run produksi nyata** (dunia yang variabel, kejadian
tunggal) untuk investigasi insiden; replay di sini menjalankan ulang agent
terhadap **dunia yang dibekukan** untuk mendeteksi regresi sebelum rilis.
Sumber materi golden transcript bisa berasal dari transcript produksi nyata
yang "dipromosikan" — tabel `messages`/`tool_calls`
(`persistence-schema.md`) adalah bahan mentahnya, tool result-nya dibekukan
saat dipromosikan jadi golden.

### Guardrail sebagai objek terukur

Federasi langsung dari `guardrails.md` §Guardrail punya false-positive rate:
tiap guardrail (dari keenam titik) butuh dataset berlabel sendiri —
contoh-known-positive yang **wajib** memicu guardrail, contoh-known-negative
yang **wajib tidak** memicu — dan presisi/recall/F1-nya diukur tiap kali
threshold, model classifier, atau versi guardrail berubah, bukan sekali saat
dipasang. Harness trajektori yang sama memperlakukan keputusan guardrail
sebagai kejadian kelas satu di trajektori, jadi satu golden transcript bisa
menyatakan dua arah kegagalan sekaligus: "guardrail X seharusnya **tidak**
terpicu di sini" (menangkap over-blocking, false positive) sama pentingnya
dengan "guardrail Y seharusnya terpicu di sini" (menangkap under-blocking,
false negative) — kedua arah wajib ada di golden set, bukan cuma kasus
positif.

### Kewajiban eval multibahasa

Ini bukan "nice-to-have" atau sesuatu yang ditambahkan setelah insiden
produksi membuktikan celahnya — untuk produk dengan basis user non-satu-
bahasa, golden set **wajib** mencakup campuran bahasa nyata yang dilihat
produksi sejak golden set pertama dibuat, bukan cuma bahasa tim yang menulis
kode. Golden test satu bahasa secara struktural buta terhadap regresi di
bahasa lain — bukan kurang sensitif, buta total: perubahan prompt/model/
threshold guardrail yang merusak bahasa Indonesia sambil bahasa Inggris
tetap baik menghasilkan **nol** sinyal di suite berbahasa Inggris saja,
karena suite itu tidak pernah menjalankan kasus yang bisa gagal dengan cara
itu.

Kasus konkret kenapa ini bukan spekulasi: guardrail model-based
(`guardrails.md` §Bertingkat) yang dilatih dominan pada korpus Inggris punya
performa yang tidak seragam lintas bahasa — bahkan Llama Guard yang secara
eksplisit mengklaim dukungan 8 bahasa `[docs]` (dikutip di `guardrails.md`
§Sumber) tetap butuh diukur presisi/recall-nya **per bahasa**, cakupan
"mendukung 8 bahasa" bukan bukti performa seragam di kedelapannya — ini
persis kenapa §Guardrail sebagai objek terukur di atas dan kewajiban
multibahasa di sini adalah tuntutan yang sama, bukan dua tuntutan terpisah:
golden set yang tidak berlabel bahasa tidak bisa menjawab "guardrail ini
akurat di bahasa mana saja".

## Trade-off

- **LLM-as-judge vs assertion deterministik untuk skor trajektori** — judge
  menangani trajektori open-ended yang assertion-nya mahal ditulis tangan,
  dengan biaya: judge sendiri jadi masalah berbentuk guardrail (FP/FN rate,
  butuh kalibrasi berkala, satu panggilan model per eval jadi biaya eval
  sendiri). Assertion deterministik gratis dan reproducible tapi cuma benar
  untuk tugas yang jalan benarnya memang tunggal (arketipe Workflow Agent),
  rapuh untuk apa pun yang punya lebih dari satu jalan sah.
- **Respons tool dibekukan vs panggilan live ke layanan eksternal saat
  replay** — dibekukan berarti deterministik, murah, cepat, aman dijalankan
  di CI tiap PR; live menangkap drift integrasi nyata (kontrak API berubah)
  tapi flaky/mahal/lambat dan tidak bisa memisahkan "agent regresi" dari
  "layanan eksternal berubah". Default: dibekukan sebagai gate CI utama,
  suite integrasi-live terpisah yang lebih jarang dijalankan untuk kelas
  drift yang tidak tertangkap versi beku.
- **Cakupan bahasa golden set vs biaya** — tiap bahasa tambahan melipat-
  gandakan ukuran suite dan butuh peninjau yang fasih bahasa itu untuk
  menulis/memvalidasi contohnya — biaya ini nyata, tapi bukan alasan untuk
  menunda: kegagalan lazy-nya adalah melewatkan bahasa "untuk nanti" dan
  baru dapat sinyal setelah kerusakan sudah terjadi di produksi.

## Di deepagents

`RubricMiddleware` (dikutip `guardrails.md`/`../systems/deepagents.md`
§Middleware bawaan) adalah analog *in-band* di runtime — ia mengiterasi
jawaban terhadap rubric selama satu run yang sedang berjalan — tapi **bukan**
eval harness itu sendiri: ia tidak punya konsep golden dataset, replay, atau
agregasi presisi/recall lintas banyak kasus terekam, cuma beroperasi pada
turn yang sedang aktif. `[code]` — dikutip `../systems/deepagents.md`
§Middleware bawaan (`deepagents/middleware/rubric.py`). Eval harness
karenanya adalah sistem **di luar** `deepagents`: sesuatu yang berulang kali
memanggil graph terkompilasi yang sama (`create_deep_agent(...)`, graph yang
sama persis yang melayani request nyata) dengan state/pesan awal tetap dan
lingkungan terkendali (backend/tool yang dimock), bukan sesuatu yang
disediakan `deepagents`.

Satu detail yang wajib diperhitungkan saat men-diff trajektori replay:
`SummarizationMiddleware` mengompaksi pesan lama berdasarkan threshold yang
dihitung otomatis dari profil model (`compute_summarization_defaults`,
berbasis `max_input_tokens`) — mengganti model yang dites (mis. eval
terhadap model baru) bisa mengubah **kapan** kompaksi terjadi untuk input
yang identik, walau isi jawabannya tidak berubah. `[code]` — dikutip
`../systems/deepagents.md` §2 Context. Diff trajektori golden karenanya
wajib toleran terhadap bentuk kompaksi yang berbeda (jumlah/lokasi pesan
ringkasan), bukan byte-diff pesan mentah — atau replay harness mengunci
profil model yang threshold-nya dipakai, sesuai kasus yang diuji (regresi
prompt vs regresi ganti-model adalah dua eval yang berbeda).

## Sumber

- `[code]` [`guardrails.md`](guardrails.md) — §Guardrail punya
  false-positive rate (federasi langsung ke file ini), tabel enam titik dan
  klaim dukungan-bahasa Llama Guard yang dikutip ulang di §Kewajiban eval
  multibahasa.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — tabel
  `messages`/`tool_calls`, sumber bahan mentah golden transcript yang
  dipromosikan dari transcript produksi nyata.
- `[code]` [`replay-and-forensics.md`](replay-and-forensics.md) — dirujuk
  untuk membedakan replay-untuk-regresi (file ini) dari replay-untuk-
  forensik (file itu), ditulis dalam task yang sama, tidak diusulkan ulang.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Middleware bawaan (`RubricMiddleware`), §2 Context
  (`SummarizationMiddleware`, `compute_summarization_defaults`) — tier-1
  reference terverifikasi Task 3, dikutip tanpa membaca ulang source
  `deepagents` di task ini.
