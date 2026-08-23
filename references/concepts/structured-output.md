# Structured output

## Masalah

Output model adalah teks bebas secara default — kalau aplikasi butuh bentuk
tertentu (JSON dengan field wajib, enum nilai valid, tipe data yang bisa
langsung dipakai kode di belakangnya), penegakan bentuk itu harus terjadi
di suatu tempat. Tempat paling gampang untuk memasangnya — instruksi di
prompt ("balas dalam format JSON dengan field `x`, `y`, `z`") — cuma
**advisory**, sama persis dengan alasan
[`guardrails.md`](guardrails.md) §Kebijakan tidak boleh hanya di prompt
menolak prompt sebagai satu-satunya lapis penegakan: model bisa lupa satu
field, salah tipe, atau menambah teks pembuka sebelum JSON-nya ("Tentu,
ini hasilnya:") yang membuat parser JSON naif gagal total. Kegagalan ini
biasanya baru ketahuan di lapis kode yang mengasumsikan output sudah valid
— `json.loads()` yang meledak, atau lebih buruk, tidak meledak tapi
mengembalikan struktur yang secara diam-diam salah bentuk dan lolos ke
lapis berikutnya.

Masalah kedua: begitu skema ditegakkan **dan** ada mekanisme retry saat
gagal, retry itu sendiri butuh keputusan eksplisit — retry tanpa batas
untuk kegagalan yang sistematis (skema yang secara struktural tidak bisa
dipenuhi model, mis. field yang saling kontradiktif) membakar biaya tanpa
akhir; retry nol kali membuat satu kegagalan sesaat (model salah format
sekali karena noise sampling) langsung jadi error yang diteruskan ke user,
padahal percobaan kedua kemungkinan besar berhasil.

## Pola

### Dua jalur penegakan skema: native provider vs tool-call sintetis

- **Native/provider-side** — model provider punya mode structured output
  bawaan (constrained decoding/JSON mode) yang menjamin output sesuai
  skema JSON di level generasi token itu sendiri, bukan divalidasi
  belakangan. Paling ketat (secara struktural tidak mungkin menghasilkan
  JSON tidak valid), tapi tidak semua provider/model mendukungnya, dan
  provider yang beda punya mekanisme beda (tidak portable lintas
  provider tanpa lapisan abstraksi).
- **Tool-call sintetis** — skema didaftarkan sebagai "tool" buatan (bukan
  tool sungguhan yang punya efek samping); model "memanggil" tool itu
  dengan argumen yang berbentuk skema yang diminta, lalu argumen itu
  diparse dan divalidasi seperti argumen tool biasa (lihat
  `tool-design.md` §Skema ketat vs longgar). Portable lintas provider
  (memakai mekanisme tool-calling yang sudah ada, bukan fitur khusus
  provider), tapi validitas skema baru diketahui **setelah** model selesai
  generate, bukan dijamin saat generate — di sinilah retry (di bawah)
  jadi penting, karena kegagalan validasi di jalur ini adalah kegagalan
  yang wajar terjadi, bukan kasus langka.

Dua jalur ini bukan pilihan eksklusif proyek — sistem produksi biasanya
memilih otomatis: pakai native kalau model/provider yang sedang aktif
mendukungnya (lebih ketat, tidak butuh retry untuk kegagalan bentuk),
jatuh ke tool-call sintetis kalau tidak (portable, tapi butuh retry). Lihat
`## Di deepagents` untuk bentuk konkret pemilihan otomatis ini.

### Retry sebagai bagian dari kontrak skema, bukan wrapper terpisah

Kegagalan validasi skema harus punya jawaban eksplisit untuk tiga hal,
sama seperti guardrail (`guardrails.md` §Pola: "tiap guardrail wajib
menyatakan tiga hal") — **skema/validator apa**, **berapa kali retry**,
**apa yang terjadi kalau retry habis**:

- **Sinyal retry harus dikirim balik ke model sebagai feedback yang bisa
  ditindaklanjuti**, bukan sekadar "coba lagi" tanpa konteks — pesan error
  validasi (field mana yang hilang/salah tipe) dikirim balik sebagai bagian
  riwayat percakapan supaya percobaan kedua punya informasi yang tidak
  dimiliki percobaan pertama. Retry buta (ulangi prompt yang sama persis)
  cuma berharap noise sampling kebetulan menghasilkan bentuk yang benar
  kali ini — kadang berhasil, tidak bisa diandalkan sebagai strategi.
- **Retry punya batas atas eksplisit** — sama dengan alasan
  `guardrails.md` titik 5 (Loop) mewajibkan `max_iterations`/limit
  eksplisit untuk mencegah kegagalan sistematis membakar biaya tanpa
  akhir: kegagalan yang bertahan sampai batas retry berarti masalahnya
  bukan noise sesaat, tapi struktural (skema tidak bisa dipenuhi dari
  konteks yang tersedia) — retry lebih banyak lagi tidak menyelesaikan
  masalah struktural.
- **Kegagalan setelah retry habis wajib punya jalan keluar terdefinisi** —
  pola yang sama dengan `guardrails.md` titik 4 (Output, `RubricMiddleware`
  pada `max_iterations` tercapai: *"kirim jawaban terbaik yang ada dg flag
  'belum lolos rubric'... jangan diamkan turn selamanya"*). Untuk
  structured output: pilihan eksplisit antara (a) kembalikan error terstruktur
  ke pemanggil (aplikasi tahu turn ini gagal validasi, bisa tampilkan pesan
  ke user) atau (b) kembalikan output mentah tak-tervalidasi dengan flag
  eksplisit "belum lolos skema" untuk pemanggil yang lebih toleran —
  **bukan** default diam-diam meneruskan output tak-tervalidasi seolah
  valid, itu memindahkan kegagalan ke lapis kode berikutnya yang justru
  paling tidak siap menanganinya (karena mengasumsikan sudah tervalidasi).

### Hubungan dengan guardrail output — dua lapis berbeda, jangan digabung jadi satu

Tabel [`guardrails.md`](guardrails.md) titik 4 (Output) mencantumkan
**"Validasi schema, groundedness, wajib sitasi"** (plus kebocoran PII dan
scan secret di baris terpisah), semuanya ditegakkan `RubricMiddleware`.
Kata "Validasi schema" di baris itu **bukan** mekanisme yang dijelaskan
file ini — dua file punya "validasi schema" di judulnya masing-masing dan
batasnya wajib eksplisit, bukan dibiarkan pembaca menebak: `RubricMiddleware`
milik `guardrails.md` adalah **kriteria rubric self-eval** yang menilai
output yang **sudah well-formed** (bagian dari penilaian kualitas bersama
groundedness/sitasi — mis. "apakah field yang wajib ada semuanya relevan
dan terisi bermakna", bukan "apakah JSON-nya valid"); file ini memiliki
**apakah output well-formed sama sekali** — pertanyaan yang harus terjawab
YA lebih dulu, di lapis sebelum rubric apa pun sempat mengevaluasi apa-apa,
lewat `response_format`/`ToolStrategy`/`ProviderStrategy` (lihat `## Di
deepagents`). Urutannya karena itu bukan cuma disarankan tapi struktural:
output yang gagal validasi bentuk (mis. field `amount` bukan angka, atau
`ToolStrategy` belum berhasil mem-parsenya sama sekali) tidak punya struktur
untuk dinilai `RubricMiddleware` — validasi skema file ini jalan **duluan**
(retry sampai bentuknya valid atau menyerah dengan jalan keluar terdefinisi
di atas), rubric `guardrails.md` titik 4 jalan **sesudahnya**, atas output
yang sudah pasti berbentuk benar. Dua lapis ini **tidak boleh digabung**
jadi satu validator besar — kegagalan bentuk dan kegagalan kebijakan/kualitas
butuh strategi retry dan mode kegagalan yang berbeda (lihat `guardrails.md`
§Pola: "tiap guardrail wajib menyatakan tiga hal" berlaku terpisah untuk
tiap lapis, bukan sekali untuk gabungan keduanya).

## Trade-off

- **Native/provider-side vs tool-call sintetis** — sudah dibahas §Pola;
  ringkas: native lebih ketat (dijamin di level generasi) tapi tidak
  portable dan tidak semua model mendukungnya; tool-call sintetis portable
  dan bekerja di model manapun yang sudah mendukung tool-calling, tapi
  validitasnya diketahui belakangan (butuh retry) dan sedikit lebih mahal
  (satu putaran tool-call sintetis vs generasi langsung).
- **Validasi ketat (raise semua penyimpangan skema) vs validasi longgar
  (terima superset, abaikan field ekstra)** — ketat menjamin kontrak
  persis dengan skema (aman untuk kode di belakangnya yang mengasumsikan
  bentuk eksak) tapi rapuh terhadap penyimpangan minor yang sebenarnya
  tidak berbahaya (field tambahan yang tidak dipakai); longgar toleran
  terhadap noise minor tapi bisa meloloskan penyimpangan yang sebenarnya
  penting (typo nama field yang seharusnya dianggap "field wajib hilang",
  bukan "field ekstra yang diabaikan").
- **Retry otomatis (dalam satu turn, transparan ke user) vs retry
  eksplisit yang terlihat (user tahu ada percobaan ulang)** — otomatis
  memberi UX mulus (user tidak pernah lihat kegagalan sesaat) tapi
  menyembunyikan sinyal yang berguna untuk observability (berapa sering
  skema gagal di percobaan pertama adalah metrik kesehatan prompt/model —
  lihat `evaluation.md`/`observability.md`); retry yang terlihat (log/span
  terpisah per percobaan) menjaga sinyal itu tapi butuh instrumentasi
  eksplisit supaya "retry transparan" tidak berubah jadi "retry yang
  tidak pernah diukur".

## Di deepagents

`response_format` pada `create_deep_agent(...)`/`langchain.agents.
create_agent(...)` adalah jalur bawaan untuk seluruh §Pola di atas:

- **Tiga strategi**, persis dua jalur di §Pola plus satu mode otomatis:
  `ToolStrategy` (tool-call sintetis — skema didaftarkan sebagai tool
  buatan, argumennya diparse & divalidasi lewat `TypeAdapter` Pydantic),
  `ProviderStrategy` (native — memakai mode structured output bawaan
  provider), `AutoStrategy` (pilih otomatis berdasar dukungan model yang
  sedang dipakai — helper privat `_supports_provider_strategy` mengecek
  profil model, dengan pengecualian eksplisit untuk model yang tidak
  mendukung tool-calling bersamaan dengan structured output native
  sekaligus). `[code]` —
  `langchain/agents/structured_output.py` kelas `ToolStrategy`,
  `ProviderStrategy`, `AutoStrategy`; `langchain/agents/factory.py` fungsi
  pengecekan dukungan provider-native structured output.
- **Retry adalah parameter eksplisit `handle_errors` pada `ToolStrategy`**,
  persis kontrak §Pola: `True` (default) menangkap semua error validasi
  dengan template pesan default yang dikirim balik ke model; `str` custom
  message; `type[Exception]`/`tuple[type[Exception], ...]` cuma menangkap
  kelas error tertentu; `Callable[[Exception], str]` fungsi custom yang
  menghasilkan pesan error dari exception; `False` = **tidak** retry,
  exception dibiarkan naik. Ini **persis** "sinyal retry dikirim balik ke
  model sebagai feedback yang bisa ditindaklanjuti" di §Pola — pesan
  error yang dihasilkan `handle_errors` masuk sebagai konten
  `ToolMessage`, bukan retry buta. `[code]` — `langchain/agents/
  structured_output.py` kelas `ToolStrategy`, field/parameter
  `handle_errors`.
- **Peringatan konkret**: kalau `schema` yang didaftarkan adalah raw JSON
  Schema `dict` (bukan Pydantic model/`dataclass`/`TypedDict`), argumen
  tool call **dikembalikan apa adanya tanpa validasi** — `handle_errors`
  jadi *"effectively inert"* untuk kasus ini, karena tidak ada validasi
  yang bisa gagal untuk dipicu retry-nya. Ini kelas defect yang sama
  dinamai instruksi task ini secara umum: nama parameter yang benar
  (`response_format=`, `handle_errors=True`) tidak otomatis berarti
  kapabilitasnya (validasi + retry) sungguh aktif — bergantung pada
  bentuk skema yang didaftarkan. `[code]` — dikutip langsung docstring
  `ToolStrategy.handle_errors`: *"Raw JSON schema dicts are not
  validated... `handle_errors` is effectively inert for dict schemas. To
  get validation and automatic retries, express the schema as a Pydantic
  model, dataclass, or TypedDict instead."*
- **Batas atas retry tidak ada bawaan di `handle_errors` itu sendiri** —
  parameter itu mengatur *apakah* dan *bagaimana* error ditangani per
  percobaan, bukan berapa kali maksimal percobaan diulang; batas jumlah
  percobaan struktural harus datang dari mekanisme lain yang sudah
  dipetakan `guardrails.md` titik 5 (`ModelCallLimitMiddleware`) atau
  `RubricMiddleware` (`max_iterations`, kalau structured output
  dikombinasikan dengan iterasi self-eval) — bukan diusulkan ulang di
  sini. `[inferred]` — disimpulkan dari signature `ToolStrategy.__init__`
  yang dikutip di atas: tidak ada parameter jumlah retry di kelas itu
  sendiri.
- **Hasil tersimpan di `state["structured_response"]`**, terpisah dari
  `messages` — kalau `has_structured_output=True` tapi model gagal
  menghasilkan structured response yang valid (setelah retry habis atau
  `handle_errors=False` dan errornya tidak fatal ke seluruh run),
  `structured_response` di-set eksplisit ke `None`, bukan dibiarkan berisi
  nilai lama/tidak terdefinisi — ini jalan keluar terdefinisi yang
  diminta §Pola (pemanggil bisa cek `None` secara eksplisit alih-alih
  mengasumsikan field itu selalu terisi). `[code]` — `langchain/agents/
  factory.py`, komentar & logika di sekitar penanganan
  `has_structured_output`/`state["structured_response"]`.

## Sumber

- `[code]` `langchain/agents/structured_output.py` — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langchain/agents/structured_output.py`,
  kelas `ToolStrategy` (`handle_errors`, docstring peringatan JSON Schema
  dict), `ProviderStrategy`, `AutoStrategy`, `ResponseFormat` (union
  type), `StructuredOutputError`/`MultipleStructuredOutputsError`/
  `StructuredOutputValidationError`.
- `[code]` `langchain/agents/factory.py` — dibaca langsung dari
  `references/recipes/.venv/lib/python3.13/site-packages/langchain/agents/factory.py`,
  parameter `response_format` pada `create_agent(...)`, fungsi pengecekan
  dukungan provider-native structured output, penanganan
  `state["structured_response"]`.
- `[code]` [`guardrails.md`](guardrails.md) §Pola ("tiap guardrail wajib
  menyatakan tiga hal"), titik 4 (Output, `RubricMiddleware`), titik 5
  (Loop, batas retry/iterasi) — dasar kerangka retry & jalan-keluar
  terdefinisi yang diterapkan file ini ke structured output; tidak
  diulang detail mekanisme guardrail-nya.
- `[code]` [`tool-design.md`](tool-design.md) §Skema ketat vs longgar —
  dasar analogi validasi argumen tool untuk jalur tool-call sintetis.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) — API
  permukaan `response_format` pada `create_deep_agent`, dikutip untuk
  konsistensi parameter dengan `langchain.agents.create_agent`.
