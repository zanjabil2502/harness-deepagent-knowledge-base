# Skill dasar: keluaran bertag (table, chart, diagram, formula)

Empat skill yang di-scaffold sebagai **himpunan dasar** ke project mana pun
yang jawabannya kadang perlu berbentuk selain prosa. Isinya kontrak
pemancaran, bukan komponen UI: skill memberi tahu model **kapan** dan
**dalam bentuk apa** memancarkan, aplikasi yang memutuskan cara
merendernya.

| Skill | Tag pagar | Muatan | Dirender oleh |
|---|---|---|---|
| [`tag-table/`](tag-table/SKILL.md) | ` ```table ` | JSON | komponen tabel aplikasi |
| [`tag-chart/`](tag-chart/SKILL.md) | ` ```chart ` | JSON | pustaka chart aplikasi |
| [`tag-diagram/`](tag-diagram/SKILL.md) | ` ```mermaid ` | sumber Mermaid | renderer Mermaid |
| [`tag-formula/`](tag-formula/SKILL.md) | ` ```math ` | LaTeX | KaTeX/MathJax |

## Kenapa blok berpagar, bukan tag XML

`[ours]` — Keputusan sintaksis ini milik kita; tidak ada konvensi bawaan di
`deepagents` untuk keluaran terstruktur inline. Alternatif vanilla-nya
adalah `response_format` pada `create_deep_agent`, yang memaksa **seluruh
balasan** jadi satu objek berskema (lihat
[`../../concepts/structured-output.md`](../../concepts/structured-output.md)).
Itu tepat untuk endpoint yang keluarannya memang satu objek, dan salah
untuk asisten percakapan: jawabannya prosa yang **kadang** menyisipkan
tabel, kadang dua diagram, kadang tidak sama sekali. Skema tunggal tidak
bisa menyatakan "prosa dengan nol sampai n sisipan heterogen" tanpa
menjadikan seluruh balasan sebagai array blok — yang mengorbankan
streaming teks dan membuat model menulis lebih buruk.

Tiga alasan memilih pagar (` ``` `) daripada tag bergaya XML:

- **Batasnya sudah punya arti di Markdown.** Renderer chat mana pun sudah
  memisahkan blok kode dari prosa. Tag XML dalam Markdown bertabrakan
  dengan HTML dan bisa tersaring sanitizer.
- **Bisa dideteksi saat streaming.** Baris pembuka menentukan jenis blok
  sebelum isinya lengkap, jadi UI bisa langsung menampilkan placeholder
  yang benar. Detail penanganannya di §Streaming.
- **Satu sudah standar de facto.** Mermaid sudah bertag `mermaid` di
  seluruh ekosistem. Menamainya ulang jadi `diagram` cuma memutus
  kompatibilitas dengan renderer yang sudah ada — jadi nama skill-nya
  `tag-diagram`, tapi tag pagarnya tetap `mermaid`.

## Kontrak pemancaran

Alurnya tiga langkah, dan langkah tengahnya tidak boleh dilewati:

```
model memancarkan blok  →  aplikasi mem-parse & memvalidasi  →  render / degradasi
```

**Validasi bukan opsional.** Keluaran model bukan input tepercaya, sekalipun
skill-nya jelas. JSON bisa cacat, kolom bisa tidak cocok dengan baris,
Mermaid bisa gagal parse, LaTeX bisa tak berujung. Aplikasi yang langsung
menyuap blok ke pustaka render menyerahkan penanganan errornya ke pustaka
itu, yang biasanya berarti komponen kosong tanpa penjelasan.

**Degradasi wajib terlihat, tidak pernah senyap.** Blok yang gagal
divalidasi dirender sebagai blok kode biasa disertai satu baris keterangan
kenapa. Membuangnya diam-diam adalah kegagalan yang paling mahal: user
melihat jawaban yang terbaca utuh padahal separuh isinya hilang, dan tidak
ada yang tahu — persis mode kegagalan yang dilarang
[`../../concepts/guardrails.md`](../../concepts/guardrails.md).

## Streaming

Blok tidak bisa dirender sebelum pagar penutupnya tiba. Ini konsekuensi
langsung, bukan detail implementasi:

- Saat baris pembuka terlihat, UI sudah tahu **jenis** blok. Tampilkan
  placeholder sesuai jenisnya (kerangka tabel, kotak chart) dan tahan
  isinya.
- Selama isi mengalir, jangan mencoba parse sebagian. JSON separuh selalu
  invalid; Mermaid separuh bisa **valid tapi salah** (subgraph yang belum
  ditutup) — merender lalu mengganti membuat diagram berkedip-kedip.
- Blok yang tidak pernah tertutup (turn dibatalkan, model kehabisan token)
  wajib ditutup oleh aplikasi sebagai blok gagal, bukan dibiarkan
  menggantung sebagai placeholder abadi.

Bentuk event dan reattach-nya di
[`../../concepts/streaming-protocol.md`](../../concepts/streaming-protocol.md).

## Keamanan

Dua dari empat tag ini dieksekusi oleh pustaka render di browser, dan
keduanya punya permukaan yang bukan sekadar tampilan:

- **Mermaid** mengenal direktif `click` yang bisa menautkan atau memanggil
  callback, dan sebagian konfigurasi mengizinkan HTML dalam label. Jalankan
  dengan `securityLevel: "strict"` dan tolak blok yang memuat `click`
  kecuali memang diinginkan.
- **LaTeX** lewat KaTeX/MathJax punya makro yang menjangkau di luar
  matematika (`\href` yang paling jelas). Pakai daftar makro yang
  di-allowlist, batasi kedalaman ekspansi, dan pasang batas waktu render.

JSON pada `table`/`chart` inert, tapi **isinya string yang tampil ke user**.
Label kolom dan caption bisa memuat markup; escape saat render, jangan
percaya karena "kan cuma data".

Ketiganya masuk kategori yang sama: konten yang ditulis model, dieksekusi
di browser user. Perlakukan seperti input tak tepercaya —
[`../../concepts/security.md`](../../concepts/security.md).

## Multilingual

Aturannya satu, dan ia memisahkan dua hal yang mudah tercampur:

- **Kunci mesin selalu netral bahasa dan stabil** — `columns[].key`,
  `series[].key`, `type`, `v`. Ini identifier, bukan teks.
- **Teks yang dilihat manusia mengikuti locale sesi** — `label`,
  `caption`, `note`, label node diagram.

Praktik yang salah dan sering terjadi: memakai label lokal sebagai kunci
(`{"Pendapatan": 120}`). Begitu locale berganti, data yang sama jadi tidak
bisa dicocokkan dengan dirinya sendiri. Penjelasan penuh pemisahan
intent/ekspresi di
[`../../concepts/multilingual.md`](../../concepts/multilingual.md).

Deskripsi frontmatter tiap skill ditulis dalam bahasa Inggris karena ia
dicocokkan model, bukan dibaca user — tapi memuat kata pemicu lintas
bahasa supaya permintaan berbahasa Indonesia tetap mengaktifkannya.

## Kapan sisipan seharusnya jadi artefak

Blok inline tepat untuk hasil yang **dibaca sekali di dalam percakapan**.
Begitu keluarannya perlu bertahan, diberi versi, diunduh, atau disunting
terpisah, ia bukan sisipan lagi melainkan artefak — disimpan by-reference
dengan transkrip cuma memuat `artifact_id` + versi
([`../../concepts/artifacts-and-canvas.md`](../../concepts/artifacts-and-canvas.md)).

Ambang praktis yang dipakai keempat skill: tabel di atas ~50 baris atau
data chart di atas ~200 titik dipancarkan sebagai artefak, bukan inline.
`[ours]` — angka ini pilihan kami, bukan batas dari `deepagents` (yang
ambang bawaannya beroperasi di lapisan lain: offload hasil tool di 20.000
token, lihat [`../../deepagents/best-practices.md`](../../deepagents/best-practices.md)
§3). Setel ulang sesuai lebar render dan biaya token project.

## Memasang: skill atau memori?

Keempatnya ditulis sebagai skill, dan pilihan itu perlu disadari
konsekuensinya. Dokumentasi upstream menganjurkan **memori untuk konvensi
yang selalu relevan, skill untuk kapabilitas per-tugas**
([`../../deepagents/best-practices.md`](../../deepagents/best-practices.md)
§3, §5). Memancarkan tabel memang per-tugas — hanya saat jawabannya
menuntut — jadi skill adalah bentuk yang benar.

Ongkosnya tetap ada: frontmatter tiap skill masuk system prompt **tiap
giliran**, jadi empat skill ini menambah empat deskripsi ke baseline
selamanya. Kalau sebuah project hanya pernah memakai satu di antaranya,
pasang yang satu itu saja. Kalau keempatnya nyaris selalu dipakai dan
deskripsinya jadi beban, gabungkan jadi satu skill `tag-output` dengan
empat bagian — dokumentasi upstream justru menganjurkan konsolidasi saat
deskripsi mulai beririsan.

Pemasangannya lewat `skills=` pada `create_deep_agent`; mekanisme discovery
dan aktivasinya di
[`../../concepts/skill-composition.md`](../../concepts/skill-composition.md).

## Menurunkan skill lain dari keempatnya

Skill turunan **tidak menyalin** format; ia merujuknya. Skill kuis
misalnya menyatakan kapan hasilnya berbentuk tabel dan menyebut
`tag-table`, bukan mengulang skemanya — begitu skema berubah, turunan yang
menyalin jadi basi tanpa ada yang tahu. Pola dasar→turunan lewat manifest
deklaratif ada di
[`../../concepts/skill-composition.md`](../../concepts/skill-composition.md)
§"Dasar → turunan lewat manifest deklaratif".

## Sumber

- `[ours]` Sintaksis tag, skema JSON `table`/`chart`, ambang inline→artefak,
  dan aturan degradasi — keputusan kami; alternatif vanilla (`response_format`
  untuk seluruh balasan) dinyatakan di §Kenapa blok berpagar. Terdaftar di
  bagian roster di
  [`../../deepagents/conformance.md`](../../deepagents/conformance.md).
- `[docs]` [`../../deepagents/best-practices.md`](../../deepagents/best-practices.md)
  §3 (memori vs skill untuk konvensi selalu-relevan; ambang offload 20.000
  token) dan §5 (anggaran frontmatter, konsolidasi skill yang beririsan) —
  dasar §Memasang dan §Kapan sisipan seharusnya jadi artefak.
- `[code]` [`../../concepts/structured-output.md`](../../concepts/structured-output.md)
  §Di deepagents — perilaku `response_format`, dasar penolakan skema
  tunggal untuk balasan percakapan; dirujuk tanpa ditulis ulang.
