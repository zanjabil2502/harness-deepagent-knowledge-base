# Skill composition

## Masalah

Skill baru yang mirip skill lama biasanya lahir lewat copy-paste: duplikasi
seluruh `SKILL.md`, ubah beberapa baris, deploy. Ini DRY violation yang
membusuk diam-diam — begitu skill dasarnya (`retrieval`, misalnya) diperbaiki
(tool baru ditambah, policy PII diperketat), semua turunannya yang
di-copy-paste **tidak** ikut menerima perbaikan itu kecuali seseorang ingat
mengulang perubahan yang sama di tiap salinan secara manual. Semakin banyak
skill vertikal (skill riset untuk domain legal, domain medis, domain
finansial — semuanya varian dari satu skill riset generik), semakin besar
selisih yang harus disinkronkan tangan, dan semakin sering selisih itu
dilupakan.

Masalah kedua, independen dari yang pertama: routing skill yang dipicu lewat
frasa bahasa alami ("kalau user bilang 'riset hukum', pakai skill ini") diam-
diam terkunci ke satu bahasa. Sistem yang benar-benar multibahasa (asumsi
proyek ini, lihat spec §8.6) punya user yang menulis permintaan yang sama
dalam puluhan cara berbeda lintas bahasa — "riset hukum", "legal research",
"nghubungke masalah hukum" — dan kalau kecocokan skill bergantung pada frasa
tertentu (atau bahkan terjemahan literal dari frasa tertentu), skill itu
diam-diam gagal dipicu untuk setiap bahasa yang tidak diuji, tanpa error yang
terlihat — user cuma dapat jawaban generik alih-alih skill khusus yang
seharusnya jalan. Ini bukan bug yang muncul di log; ia bug yang tidak
terlihat sampai seseorang di bahasa yang kalah cakupan melapor.

## Pola

### Dasar → turunan lewat manifest deklaratif, bukan copy-paste

Skill turunan ditulis sebagai **delta** dari skill dasar, dinyatakan lewat
manifest deklaratif — komposisi, bukan duplikasi teks. Manifest normatif
dari spec §8.5 proyek ini `[ours]`:

```yaml
id: legal-research
extends: retrieval
intents: [research.legal]        # kode netral, bukan frasa bahasa
locales: [id, en]
tools:    [+citation_check, -web_write]
policies: [+require_citation, +pii_redact]
precedence: derived_wins
```

`extends: retrieval` berarti manifest ini **tidak** mendefinisikan ulang
seluruh isi skill `retrieval` — ia mewarisi tool/policy/instruksi dasarnya,
lalu menyatakan selisihnya: `tools: [+citation_check, -web_write]` menambah
satu tool dan mencabut satu tool dari set dasar; `policies:
[+require_citation, +pii_redact]` menyalakan dua policy tambahan (bentuk
data policy-nya sendiri ada di [`policy-as-data.md`](policy-as-data.md), file
ini tidak mengulanginya). Ketika `retrieval` diperbaiki di masa depan (mis.
tool baru ditambah ke set dasarnya), `legal-research` dan semua turunan
`retrieval` lain otomatis mewarisi perbaikan itu tanpa disentuh — karena
mereka menyimpan selisih, bukan salinan penuh.

### Resolusi = komposisi eksplisit, bukan sambung paragraf

Perbedaan mendasar dengan skill yang dibangun sebagai satu blok prosa besar
(dasar + turunan digabung jadi satu system prompt panjang): resolusi
manifest adalah operasi himpunan yang bisa ditelusuri langkah demi langkah,
bukan model membaca paragraf dari atas ke bawah dan menyimpulkan sendiri
mana yang menang.

Urutan resolusi konkret:

1. Muat manifest dasar (`retrieval`) dan manifest turunan (`legal-research`).
2. Gabung `tools`: mulai dari set tool dasar, tambahkan tiap entri berawalan
   `+`, cabut tiap entri berawalan `-`. Hasilnya satu set eksplisit — bisa
   dicetak, bisa di-diff antar versi.
3. Gabung `policies` dengan operasi yang sama.
4. Untuk field yang **bentrok** (dasar dan turunan sama-sama mendeklarasikan
   nilai berbeda untuk field yang sama, bukan cuma menambah/mengurangi item
   dari set) — pemenang ditentukan oleh `precedence`, dibaca dari manifest
   itu sendiri, bukan dari urutan siapa "ditulis belakangan" dalam teks
   gabungan. `precedence: derived_wins` berarti nilai turunan menang atas
   nilai dasar untuk field yang bentrok; `base_wins` kebalikannya.

Field `precedence` boleh sengaja berbeda untuk kelas field yang berbeda —
tidak wajib satu nilai global untuk seluruh manifest. Contoh konkret:
`legal-research` boleh set `precedence: derived_wins` untuk `tools` (skill
turunan yang tahu domainnya lebih baik soal tool mana yang relevan), sambil
tetap menghormati `base_wins` khusus untuk policy kelas keamanan (`pii_redact`
tidak boleh dicabut skill turunan mana pun meski turunan itu men-deklarasikan
`policies: [-pii_redact]`) — keputusan ini sendiri harus eksplisit di level
definisi policy (`policy-as-data.md` menandai policy semacam ini
non-removable), bukan diam-diam diasumsikan dari `precedence` global manifest.
Titik pentingnya bukan nilai mana yang benar, tapi bahwa keputusan itu **ada
sebagai field yang bisa dibaca**, bukan tersirat dari urutan penulisan —
persis kebalikan dari penyakit "presedensi implisit" yang dinamai
[`policy-as-data.md`](policy-as-data.md) §Masalah.

### `intents` memakai kode netral, bukan frasa bahasa

`intents: [research.legal]` bukan gaya penamaan sembarang — ia titik di
mana pemisahan intent/ekspresi (spec §8.6) `[ours]` masuk ke skema manifest.
Alurnya: input user (bahasa apa pun) diklasifikasi lebih dulu jadi kode
intent netral, **baru** kode itu dipakai mencari skill yang cocok lewat
field `intents` manifest — pencarian skill dari titik itu ke depan nol
bahasa, murni pencocokan string kode (`research.legal` == `research.legal`,
sama persis untuk user berbahasa Indonesia, Inggris, atau apa pun yang
memicu klasifikasi intent yang sama).

Vanilla-nya, dan yang kita simpang: kalau `intents` diisi frasa bahasa
("intent yang cocok: 'riset hukum'/'legal research'") atau — lebih buruk —
kalau routing skill dibiarkan murni mengandalkan judgment model membaca
`description` (mekanisme native `SkillsMiddleware` `deepagents`, lihat
`## Di deepagents` di bawah), maka cakupan bahasa skill itu terikat pada
seberapa lengkap penulis manifest menuliskan variasi frasa di tiap bahasa
yang didukung — dan tim yang menulis manifest, seperti dicatat
`evaluation.md` §Kewajiban eval multibahasa, hampir selalu menulis dalam
satu bahasa (bahasa mereka sendiri) lebih dulu. Kode netral memutus
ketergantungan itu: menambah bahasa baru berarti memperluas classifier
intent (satu tempat, di luar skema manifest) supaya bisa memetakan frasa
bahasa baru itu ke kode yang **sudah ada** — manifest skill itu sendiri
tidak pernah disentuh, dan tidak pernah butuh ditulis ulang per bahasa.
Field `locales: [id, en]` di manifest bukan mekanisme routing — ia
metadata untuk lapis lain (mis. lokalisasi output/template pesan per spec
§8.6), terpisah dari `intents` yang menentukan *apakah* skill ini dipilih
sama sekali.

## Trade-off

- **Manifest deklaratif (delta + resolusi eksplisit) vs skill mandiri penuh
  (tanpa `extends`)** — manifest menghindari duplikasi dan mewariskan
  perbaikan otomatis, tapi menambah satu langkah tidak-langsung: memahami
  perilaku akhir `legal-research` butuh membaca dua file (dasar + turunan)
  dan menjalankan resolusi mental/nyata, bukan membaca satu `SKILL.md` yang
  lengkap. Skill mandiri lebih mudah dibaca sendirian tapi kembali ke
  masalah duplikasi begitu ada skill kedua yang mirip.
- **Kode intent netral vs deskripsi bahasa alami untuk routing** — kode
  netral memisahkan cakupan bahasa dari jumlah skill (classifier intent
  yang diperluas menutupi semua skill sekaligus), dengan biaya: butuh
  classifier intent yang dipelihara terpisah (§8.6) dan taksonomi kode yang
  disepakati (siapa yang berhak menambah `research.legal` baru, dan kapan
  itu seharusnya jadi sub-kode dari kode yang sudah ada alih-alih kode
  baru). Deskripsi bahasa alami (mekanisme native `SkillsMiddleware`) tidak
  butuh taksonomi terpisah — model membaca deskripsi dan memutuskan sendiri
  — tapi mewarisi celah cakupan bahasa yang sama seperti yang dinamai di
  atas, dan keputusan routing-nya tidak bisa diuji deterministik (dua
  panggilan model bisa memilih skill berbeda untuk deskripsi yang sama
  persis).
- **`precedence` seragam per manifest vs per-field** — seragam lebih
  sederhana untuk dinalar (satu aturan, satu tempat), tapi memaksa
  kompromi: kalau turunan butuh menang di sebagian besar field tapi kalah
  di satu field keamanan, `precedence` global tidak bisa menyatakan itu
  tanpa mekanisme tambahan (policy non-removable, dicatat di atas). Per-field
  lebih ekspresif tapi menambah permukaan yang harus diperiksa saat review
  manifest — precedence yang salah diset per-field lebih sulit terlihat
  sekilas dibanding satu baris `precedence: derived_wins` global.

## Di deepagents

`SkillsMiddleware` `deepagents` mengimplementasikan pola Agent Skills
Anthropic dengan *progressive disclosure*: metadata (`name`/`description`
dari frontmatter YAML `SKILL.md`) dimuat ke system prompt di awal, isi
lengkap dimuat saat model memilihnya. `[code]` dikutip
`../systems/deepagents.md` §7. Frontmatter yang benar-benar dibaca parser
`SkillsMiddleware` cuma `name`, `description`, `allowed-tools`,
`compatibility`, `metadata` (bebas `dict[str,str]`, tidak divalidasi
skemanya lebih jauh), dan `license` — **tidak ada** field `extends`,
`precedence`, `intents`, `locales`, atau `tools: [+/-]`/`policies: [+/-]`
yang dipahami middleware ini. `[code]` `deepagents/middleware/skills.py`
(fungsi parsing frontmatter, class `SkillMetadata`), venv riset yang sama
dengan `../systems/deepagents.md` (`deepagents==0.7.8`). Jadi seluruh skema
manifest §8.5 — `extends`, `precedence`, `intents`, delta `tools`/`policies`
— adalah `[ours]`, lapisan resolusi yang berjalan **sebelum** `deepagents`
dipanggil, bukan sesuatu yang dibaca `SkillsMiddleware` sendiri.

Pemetaannya konkret: hasil resolusi manifest (set `tools` final, set
`policies` final yang sudah dipetakan ke middleware lewat
[`policy-as-data.md`](policy-as-data.md)) menjadi **input** ke konstruksi
`create_deep_agent`/`SubAgent` — set tool final masuk parameter `tools=`
(atau `excluded_tools` di `HarnessProfile` untuk yang dicabut), set policy
final masuk `middleware=[...]` sesuai `enforcement.mechanism` tiap policy,
dan isi `SKILL.md` hasil resolusi (dasar + delta narasi turunan) yang
menjadi konten skill sesungguhnya yang dipasang lewat `skills=[...]` ke
`SkillsMiddleware`. `[code]` `deepagents/graph.py` (parameter `tools`,
`middleware`, `skills` pada `create_deep_agent`, dikutip
`../systems/deepagents.md` §API permukaan).

Untuk skill bernama sama dari sumber berbeda (mis. skill `user` menimpa
skill `base` bernama sama), `SkillsMiddleware` sudah punya aturan urutan
sendiri — sumber yang dimuat belakangan menang (layering
base→user→project→team, ditentukan urutan `skills=[...]` yang diberikan
aplikasi). `[code]` dikutip `../systems/deepagents.md` §7. Ini **bukan**
mekanisme `extends`/`precedence` manifest di atas — ini override total
berbasis urutan daftar (skill kedua menggantikan skill pertama sepenuhnya,
bukan komposisi delta), jadi kalau aplikasi ingin pola dasar→turunan yang
sesungguhnya (bukan override total), resolusi manifest `[ours]` harus
sudah selesai **sebelum** hasil akhirnya dimasukkan ke `skills=[...]` —
`SkillsMiddleware` sendiri tidak tahu apa pun soal `extends`.

Routing skill di `deepagents` sepenuhnya **prosa + judgment model** —
model memilih skill berdasar `description` yang terlihat di system prompt,
tidak ada classifier intent bawaan. `[inferred]` dikutip
`../systems/deepagents.md` §7 (disimpulkan dari tidak ditemukannya modul
classifier di source yang dibaca Task 3). Field `intents` di manifest
`[ours]` karenanya adalah kunci lookup untuk lapis routing **tambahan** di
luar `deepagents` — classifier intent (§8.6) yang harus dibangun aplikasi
sendiri, memetakan input mentah ke kode netral, baru kode itu dipakai
memilih manifest mana yang resolusinya diteruskan ke `skills=[...]`.
Tanpa lapis tambahan itu, `deepagents` tetap bisa jalan (model tetap
membaca `description`), tapi cakupan multibahasa kembali bergantung pada
seberapa lengkap `description` ditulis di tiap bahasa — persis masalah yang
`intents` kode netral dirancang menghindari.

## Sumber

- `[ours]` Spec desain internal proyek ini §8.5 — dokumen kerja yang
  **tidak ikut di-repo**, jadi ini catatan provenance, bukan tautan
  — manifest normatif (`id`/`extends`/`intents`/`locales`/`tools`/`policies`/
  `precedence`), dikutip verbatim di `## Pola`. Vanilla-nya: tidak ada
  standar industri untuk skema manifest skill dasar→turunan yang kami
  ketahui dibaca dari source — ini keputusan desain proyek, bukan pola yang
  disalin dari `deepagents`/Anthropic Agent Skills (lihat `## Di deepagents`
  untuk apa yang sungguh native).
- `[ours]` Spec §8.6 proyek ini — pemisahan intent/ekspresi (`input → kode
  intent netral → lookup policy/skill → eksekusi → render locale user`),
  dasar argumen `intents` kode netral di `## Pola`.
- `[code]` [`policy-as-data.md`](policy-as-data.md) — bentuk data satu
  policy (`id`/`applies_to`/`rule`/`enforcement`) yang dirujuk field
  `policies` manifest; ditulis dalam task yang sama, tidak diusulkan ulang
  di sini.
- `[code]` [`evaluation.md`](evaluation.md) §Kewajiban eval multibahasa —
  dasar klaim "tim menulis dalam satu bahasa lebih dulu" di `## Pola`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §7
  (`SkillsMiddleware`, layering sumber, ketiadaan classifier intent),
  §API permukaan (`create_deep_agent(tools=, middleware=, skills=)`) —
  tier-1 reference terverifikasi Task 3.
- `[code]` `deepagents/middleware/skills.py` (paket `deepagents==0.7.8`,
  dibaca dari `references/recipes/.venv/lib/python3.13/site-packages/`,
  venv yang sama dipakai `../systems/deepagents.md`) — daftar lengkap field
  frontmatter yang diparse (`name`, `description`, `allowed-tools`,
  `compatibility`, `metadata`, `license`), dasar klaim "tidak ada field
  `extends`/`precedence`/`intents`" di `## Di deepagents`.
