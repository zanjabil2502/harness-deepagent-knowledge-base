# Multilingual

## Masalah

Multilingual biasanya direduksi jadi "terjemahkan UI-nya" — string tombol dan
label diterjemahkan, lalu tim menganggap sistem sudah multibahasa. Itu
menutup satu permukaan dari sebuah loop agent yang punya banyak titik yang
diam-diam mengasumsikan satu bahasa (dan hampir selalu, bahasa Inggris):
regex guardrail yang divalidasi terhadap format identitas AS, classifier
deteksi injection yang dilatih dominan korpus Inggris, golden test yang
cuma ditulis dalam satu bahasa, dan kalkulasi budget token yang diam-diam
mengasumsikan rasio token-per-kata bahasa Latin. Tiap titik ini gagal
**senyap** — tidak ada error, cuma perilaku yang lebih buruk untuk user di
bahasa yang kalah cakupan, dan itu baru ketahuan setelah user melapor.

Masalah kedua, independen: kalau routing/kebijakan digantungkan ke *frasa*
bahasa alami ("kalau user bilang X, lakukan Y"), setiap penambahan bahasa
baru berarti menulis ulang seluruh permukaan yang menggantung ke frasa itu.
[`skill-composition.md`](skill-composition.md) §Masalah sudah menamai versi
sempit masalah ini untuk trigger skill; file ini memperluasnya ke pipeline
penuh (spec §8.6): masalahnya bukan cuma skill mana yang dipicu, tapi *tiap*
titik keputusan sepanjang loop yang kebetulan dibaca dari teks bahasa
pengguna alih-alih dari kode yang sudah dinetralkan.

Asumsi proyek ini (multi-user, cloud + on-prem) berarti basis user
lintas-bahasa adalah kasus **default**, bukan edge case yang ditambal
belakangan. Spec §9 menegaskan ini lewat cara lain: multilingual bukan salah
satu dari 7 sumbu `systems/`, ia kolom catatan di INDEX — **ketiadaan**
desain multilingual di sebuah sistem itu sendiri temuan yang wajib dicatat,
bukan default yang aman.

## Pola

### Pipeline: pisahkan intent dari ekspresi (spec §8.6)

```
input (bahasa apa pun)
   │
   ▼
[1] klasifikasi intent          — model/classifier baca teks apa adanya
   │                               (bahasa apa pun, campuran sekalipun)
   ▼
[2] kode netral (mis. "deploy.request", "research.legal")
   │                               ── nol bahasa mulai titik ini ──
   ▼
[3] lookup policy/skill BY KODE  — pencocokan string, bukan pencocokan frasa
   │                               (lihat skill-composition.md §`intents`
   │                               memakai kode netral)
   ▼
[4] eksekusi                     — tool beroperasi atas nilai terstruktur/
   │                               kode, tidak pernah atas teks bahasa mentah
   ▼
[5] render output di locale user — lokalisasi terjadi SEKALI, di ujung
```

Titik krusial: garis antara [2] dan [3] adalah garis "nol bahasa" — begitu
teks user sudah menjadi kode intent, tidak ada satu pun keputusan kebijakan/
routing di sisa pipeline yang boleh membaca teks bahasa lagi. Ini `[ours]` —
mengikuti spec §8.6 proyek ini secara literal; vanilla-nya (dan yang kita
simpang) adalah pipeline satu-lapis yang umum di produk chatbot: prompt
sistem berisi instruksi routing dalam bahasa alami ("kalau user minta X,
panggil tool Y"), dan model membaca instruksi + pesan user dalam bahasa yang
sama sepanjang alur — bahasa bocor ke setiap keputusan karena tidak pernah
ada titik potong eksplisit. Kita menyimpang karena vanilla itu berarti
menguji *setiap* keputusan kebijakan terhadap *setiap* bahasa yang didukung
untuk tahu apakah routing masih benar — biaya uji tumbuh kali jumlah bahasa
di titik yang seharusnya tidak peduli bahasa sama sekali.

Detail mekanisme kode intent dan manifest skill (`intents: [...]`, resolusi
`extends`/`precedence`) **dimiliki penuh oleh
[`skill-composition.md`](skill-composition.md)** — file ini tidak
mengulanginya, cuma menempatkannya sebagai satu simpul ([3]) dalam pipeline
yang lebih besar. Bentuk data policy yang dituju lookup [3] dimiliki
[`policy-as-data.md`](policy-as-data.md).

### Locale adalah konteks kelas satu di session, bukan tebakan per turn

Locale (preferensi bahasa render output user — `id`, `en`, dst.) **ditetapkan
sekali** saat sesi/percakapan dibuat (dari profil user, header
`Accept-Language`, atau pilihan eksplisit), lalu **dibawa sebagai bagian
konteks session**, bukan disimpulkan ulang dari tiap pesan yang masuk.

Alasan ini bukan preferensi gaya: dua sumber sinyal yang berbeda gampang
tertukar kalau locale ditebak ulang per turn —

- **Bahasa pesan** — bahasa yang kebetulan dipakai user di satu turn
  tertentu. Input pipeline (tahap [1] di atas) memang harus menangani ini
  apa adanya, termasuk campuran bahasa dalam satu pesan.
- **Locale render** — bahasa yang user *harapkan* dipakai sistem untuk
  membalas, menampilkan pesan error, dan seterusnya.

Kalau locale ditebak ulang dari bahasa pesan terakhir, satu kalimat berbahasa
Inggris di tengah percakapan Indonesia (mis. user menempel potongan log
error berbahasa Inggris) bisa membuat balasan sistem berikutnya diam-diam
berganti bahasa — bug yang terlihat seperti "fitur pintar" tapi sebenarnya
locale yang tidak stabil. Locale sebagai field session yang dipersist
memutus ketergantungan itu: bahasa pesan individual tetap bebas berganti-
ganti (ditangani classifier intent), tapi locale render tidak ikut berubah
kecuali user mengubahnya secara eksplisit.

Secara skema, ini artinya locale layak jadi kolom di lapis session/percakapan
milik [`persistence-schema.md`](persistence-schema.md) (mis. `conversations.
locale` atau `users.locale` sebagai default, bisa di-override per
percakapan) — file itu belum mendeklarasikan kolom ini di DDL-nya; ini
tambahan yang disarankan file ini, bukan koreksi atas skema yang sudah ada.

### Yang dilokalkan, dan yang tidak (spec §8.6)

| Dilokalkan | Tidak dilokalkan |
|---|---|
| Leksikon guardrail (regex, daftar kata moderasi) | Instruksi sistem/prompt inti |
| Few-shot example | Nama kode intent, nama tool, skema data |
| Template output (format tanggal/mata uang, salam) | Skema policy/manifest skill |
| Pesan error user-facing | Log internal, trace observability |

Instruksi sistem **tidak perlu diterjemahkan** — ini konsekuensi langsung
dari pipeline di atas: model yang sama membaca satu system prompt (bahasa
apa pun ia ditulis, biasanya bahasa tim) dan tetap bisa mengklasifikasi
intent dari input berbahasa apa pun serta merender output di locale yang
diminta, karena instruksi routing/kebijakan sudah dipindah ke kode netral,
bukan hidup sebagai prosa yang harus "dipahami" model dalam bahasa yang sama
dengan user. Yang **wajib** dilokalkan adalah permukaan yang langsung
membaca atau ditampilkan ke user: leksikon guardrail, few-shot, template
output, pesan error.

### Tabel titik yang terkunci bahasa

Tiap baris adalah satu titik penegakan/keputusan yang berperilaku beda per
bahasa kalau tidak ditangani eksplisit. Kolom "Pemilik" menunjuk file yang
memegang detail teknis titik itu — file ini tidak mengulanginya, cuma
menegaskan sudut pandang multibahasa-nya.

| # | Titik | Kenapa terkunci bahasa | Pemilik detail |
|---|---|---|---|
| 1 | Trigger skill | Deskripsi skill yang jadi dasar judgment model (`SkillsMiddleware`) atau frasa `intents` yang ditulis satu bahasa gagal cocok untuk ekspresi setara di bahasa lain — lihat `## Di deepagents` untuk kenapa mekanisme bawaan `deepagents` sendiri murni judgment model atas teks, bukan kode | [`skill-composition.md`](skill-composition.md) §`intents` memakai kode netral |
| 2 | Regex guardrail | Format identitas nasional berbeda struktur, bukan cuma beda panjang — NIK (16 digit: kode provinsi+kab/kota+kecamatan+tanggal lahir+nomor urut) dan NPWP (format `XX.XXX.XXX.X-XXX.XXX`, 15 digit lama / 16 digit NIK-terpadu baru) **bukan** SSN AS (`XXX-XX-XXXX`, 9 digit). `[inferred]` — format NIK/NPWP di sini pengetahuan umum, tidak diverifikasi terhadap dokumen resmi Ditjen Dukcapil/Ditjen Pajak di task ini; poin strukturalnya (beda format, bukan cuma beda panjang, jadi regex SSN tidak otomatis menutupnya) yang wajib dipegang, bukan digit persisnya. Regex yang divalidasi cuma terhadap pola SSN akan false-negative total terhadap NIK/NPWP (tidak pernah cocok, jadi tidak pernah meredaksi data yang sebenarnya PII) dan berpotensi false-positive kebetulan (9 digit acak di tengah NIK 16 digit bisa kebetulan cocok pola lain yang tidak relevan). Daftar/lexicon moderasi konten juga overwhelmingly berbahasa Inggris — kata kunci abuse/kekerasan yang di-curate untuk Inggris tidak otomatis menutup padanan di bahasa lain | [`guardrails.md`](guardrails.md) titik 1 & 4 (PII, moderasi) — file itu memiliki mekanisme enforcement (`PIIMiddleware`, dsb.); file ini menambahkan syarat: leksikon/regex per bahasa/negara wajib eksplisit, bukan satu set generik yang kebetulan ditulis untuk satu negara |
| 3 | Deteksi injection & jailbreak | Classifier keamanan (Llama Guard dkk., lihat `guardrails.md` §Bertingkat) dilatih dominan korpus Inggris; payload injection yang ditulis dalam bahasa lain, atau di-*code-switch* di tengah kalimat, punya recall lebih rendah pada model yang sama — bukan karena model "tidak paham" bahasa itu, tapi karena distribusi data latih untuk *tugas keamanan spesifik* ini condong ke Inggris `[inferred]` (pola umum kinerja model keamanan lintas-bahasa; klaim spesifik "Llama Guard mendukung 8 bahasa" ada di `guardrails.md`, akurasi per-bahasa untuk kelas serangan ini tidak diklaim di sana) | [`security.md`](security.md) §Prompt injection, [`guardrails.md`](guardrails.md) titik 1 |
| 4 | Golden-test eval | Golden set satu bahasa buta total (bukan cuma kurang sensitif) terhadap regresi di bahasa lain — perubahan yang merusak bahasa Indonesia sambil bahasa Inggris tetap baik menghasilkan nol sinyal di suite berbahasa Inggris saja | [`evaluation.md`](evaluation.md) §Kewajiban eval multibahasa — dimiliki penuh di sana, dikutip di sini sebagai satu baris tabel karena ia instrumen **pengukuran** untuk seluruh baris lain di tabel ini (butir 1-3, 5 semuanya butuh golden set berlabel bahasa untuk tahu apakah mereka sungguh berfungsi lintas bahasa) |
| 5 | Kalibrasi budget token | Bahasa non-Latin/non-spasi (aksara Jawa, Han, Thai, dst.) dan bahasa aglutinatif memakan token jauh lebih banyak per kata/karakter dibanding bahasa Latin berspasi — tokenizer BPE yang di-fit dominan korpus Inggris memecah kata non-Inggris jadi lebih banyak subword token. Threshold yang dikalibrasi dari contoh berbahasa Inggris (batas kompaksi `SummarizationMiddleware`, `ToolCallLimitMiddleware`/`ModelCallLimitMiddleware` yang dihitung dari estimasi token per giliran, lihat `cost-control.md` dan `context-engineering.md`) memicu kompaksi/pemotongan lebih cepat untuk percakapan bahasa lain pada jumlah *kata* yang setara — pengalaman user jadi berbeda kualitasnya semata karena bahasa yang mereka pakai, bukan isi percakapannya | Tidak dimiliki file lain di KB ini — ground baru; `context-engineering.md`/`cost-control.md` memiliki mekanisme kompaksi/limitnya, file ini menambahkan syarat: threshold itu wajib dikalibrasi (atau diukur) per bahasa yang benar-benar dipakai produksi, bukan diwarisi dari default yang dihitung dari korpus contoh berbahasa Inggris |

## Trade-off

- **Klasifikasi intent + deteksi bahasa dalam satu panggilan model vs dua
  langkah terpisah** — satu panggilan gabungan lebih murah (satu round-trip)
  tapi mencampur dua mode kegagalan berbeda jadi satu sinyal: kalau hasilnya
  salah, tidak langsung jelas apakah kode intent-nya salah atau bahasa yang
  terdeteksi salah, menyulitkan debug per-bahasa dari eval golden set (butir
  4 di atas). Dua langkah terpisah bisa didiagnosis independen (ukur akurasi
  deteksi bahasa dan akurasi klasifikasi intent secara terpisah) dengan
  biaya latensi/token dua kali lipat di setiap turn.
- **Locale dipersist sekali di session vs disimpulkan ulang tiap turn** —
  dipersist stabil dan murah (satu lookup, bukan satu klasifikasi per turn)
  tapi butuh mekanisme eksplisit untuk user mengubahnya (tidak otomatis
  mengikuti kalau user pindah bahasa secara sengaja untuk seluruh sesi
  berikutnya); disimpulkan ulang otomatis adaptif terhadap perubahan itu tapi
  rentan flip-flop dari satu kalimat campuran bahasa seperti dijelaskan di
  atas — proyek ini memilih dipersist karena flip-flop locale render dinilai
  lebih mengganggu daripada friksi kecil "ubah locale lewat pengaturan".
- **Lokalkan seluruh system prompt per locale vs lokalkan cuma leksikon/
  template/error (keputusan spec §8.6)** `[ours]` — vanilla di banyak
  produk multibahasa: system prompt diterjemahkan penuh ke tiap locale yang
  didukung, satu file per bahasa. Itu gampang dinalar (satu prompt = satu
  bahasa, konsisten) tapi biayanya kali jumlah locale untuk setiap perubahan
  prompt (skill baru, kebijakan baru → tulis ulang N terjemahan, jaga tetap
  sinkron — persis penyakit duplikasi yang dinamai `skill-composition.md`
  §Masalah, cuma di lapis prompt bukan lapis skill), dan kualitas
  instruction-following model untuk prompt yang diterjemahkan tidak
  terjamin setara dengan prompt aslinya. Kita menyimpang: system prompt
  tetap satu (pipeline sudah memisahkan bahasa dari keputusan, lihat
  `## Pola`), yang dilokalkan cuma permukaan yang memang ditulis untuk
  dibaca/dilihat user — biayanya jadi kali jumlah locale hanya untuk
  permukaan itu, bukan seluruh prompt.

## Di deepagents

`deepagents` tidak punya mekanisme bahasa/locale bawaan apa pun — tidak ada
parameter `locale`, tidak ada klasifier intent, tidak ada terjemahan
otomatis. Yang relevan dari primitif yang sudah ada:

- **`SkillsMiddleware` murni judgment model atas teks deskripsi** (lihat
  [`../systems/deepagents.md`](../systems/deepagents.md) §7) — tidak ada
  classifier kode bawaan yang memetakan intent ke skill. Ini persis titik 1
  tabel di atas: kalau tim mengandalkan mekanisme bawaan `deepagents` apa
  adanya (deskripsi skill ditulis satu bahasa, model menilai kecocokan
  langsung dari teks user), cakupan bahasanya terikat seberapa lengkap
  deskripsi itu menyebut variasi lintas bahasa. Pipeline nol-bahasa di
  `## Pola` (klasifikasi intent → kode → lookup `intents` manifest,
  `skill-composition.md`) harus dibangun **di depan** `SkillsMiddleware`
  sebagai lapisan tambahan aplikasi — `deepagents` tidak menyediakannya.
  `[code]` — dikutip `../systems/deepagents.md` §7 (`deepagents/middleware/skills.py`).
- **`context_schema` + `Runtime[ContextT]`** adalah primitif konkret paling
  pas untuk "locale sebagai konteks kelas satu di session, bukan tebakan
  per turn": `create_deep_agent(..., context_schema=Context)` mendefinisikan
  *"immutable run-scoped context"* — sebuah dataclass/`TypedDict` yang
  ditetapkan sekali saat run dimulai (mis. `Context(user_id=..., locale=...)`)
  dan dibaca lewat `runtime.context.locale` dari middleware/tool mana pun
  sepanjang run, tanpa perlu dihitung ulang. Ini bukan mekanisme locale
  bawaan — `deepagents`/`langgraph` tidak tahu apa itu "locale", field-nya
  murni yang aplikasi definisikan sendiri — tapi bentuknya (immutable,
  run-scoped, dibaca lewat `Runtime`) persis kontrak yang dibutuhkan §Locale
  di atas. `[code]` — `deepagents/graph.py` baris 282, 543 (docstring
  parameter `context_schema`: *"Schema class that defines immutable
  run-scoped context"*), `langgraph/runtime.py` kelas `Runtime` (*"This
  class is injected into graph nodes and middleware... `context`, `store`,
  `stream_writer`..."*). Pola pemakaian `Runtime` untuk field per-user
  serupa sudah dipakai di `StoreBackend(namespace=lambda rt: (rt.server_info.
  user.identity,))` yang dikutip `../systems/deepagents.md` §Backend
  filesystem — bukti bahwa jalur `Runtime.context`/`Runtime.server_info`
  memang jalur yang dipakai untuk data per-sesi seperti ini, bukan usulan
  baru yang tidak konsisten dengan pola `deepagents` yang sudah ada.
- Tidak ada middleware bawaan yang mengalibrasi threshold token
  (`compute_summarization_defaults` di `SummarizationMiddleware`, lihat
  `../systems/deepagents.md` §2) per bahasa — perhitungannya murni berbasis
  `max_input_tokens` profil model, tidak sadar bahasa konten yang dihitung.
  `[inferred]` — disimpulkan dari tidak ditemukannya parameter bahasa di
  signature `create_summarization_middleware`/`compute_summarization_defaults`
  yang dikutip `../systems/deepagents.md` §2; kalibrasi per-bahasa (titik 5
  tabel di atas) harus dilakukan aplikasi lewat pengukuran token riil per
  locale, bukan disediakan otomatis oleh middleware.

## Sumber

- `[ours]` Spec proyek §8.6 — pipeline intent/ekspresi, tabel titik terkunci
  bahasa, dan aturan "locale kelas satu, bukan tebakan per turn" adalah
  keputusan desain proyek ini, dikutip dan diperluas di file ini.
- `[code]` [`skill-composition.md`](skill-composition.md) §`intents` memakai
  kode netral, §Dasar → turunan lewat manifest deklaratif — dikutip untuk
  simpul [3] pipeline, tidak diulang detailnya.
- `[code]` [`evaluation.md`](evaluation.md) §Kewajiban eval multibahasa —
  dikutip untuk titik 4 tabel, tidak diulang detailnya.
- `[code]` [`guardrails.md`](guardrails.md) titik 1 & 4 (PII, moderasi),
  §Bertingkat (Llama Guard dukungan 8 bahasa) — dikutip untuk titik 2 & 3
  tabel.
- `[code]` [`security.md`](security.md) §Prompt injection — dikutip untuk
  titik 3 tabel.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — dikutip untuk
  usulan kolom locale di lapis session; skema DDL itu sendiri tidak diubah
  di file ini.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §2, §7,
  §Backend filesystem — tier-1 reference terverifikasi, dikutip langsung
  tanpa membaca ulang source `deepagents` di task ini.
- `[code]` `deepagents/graph.py` baris 282, 543 — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/deepagents/graph.py`
  untuk memverifikasi docstring parameter `context_schema`.
- `[code]` `langgraph/runtime.py` — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langgraph/runtime.py`
  untuk memverifikasi kontrak kelas `Runtime` (run-scoped, immutable
  `context`).
