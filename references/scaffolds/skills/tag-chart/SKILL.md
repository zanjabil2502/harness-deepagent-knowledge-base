---
name: tag-chart
description: Emit quantitative data as a validated ```chart JSON block so the app renders a real chart instead of describing numbers in prose. Use when the answer shows a trend over time, compares magnitudes across categories, or breaks a total into parts — including requests phrased as chart, grafik, diagram batang, gráfico, or 図表.
---

# Emit quantitative data as a `chart` block

## Kapan dipakai

Pakai saat yang penting adalah **bentuk angkanya**, bukan angka persisnya:
tren sepanjang waktu, perbandingan besaran antar kategori, komposisi sebuah
total.

Jangan pakai kalau pembaca butuh membaca nilai persis — itu tabel
(`tag-table`). Jangan pakai untuk satu-dua angka; kalimat lebih jelas.
Kalau dua-duanya perlu (bentuk **dan** nilai), pancarkan chart lalu tabel,
bukan chart dengan label nilai di tiap titik.

## Bentuk

Blok berpagar dengan info string `chart`, isinya JSON tunggal.

````
```chart
{
  "v": 1,
  "type": "line",
  "caption": "Pengguna aktif bulanan",
  "x": {"key": "period", "label": "Bulan", "type": "date"},
  "series": [
    {"key": "active", "label": "Aktif",     "unit": "user"},
    {"key": "new",    "label": "Pendaftar", "unit": "user"}
  ],
  "data": [
    {"period": "2026-01", "active": 1240, "new": 180},
    {"period": "2026-02", "active": 1390, "new": 210},
    {"period": "2026-03", "active": 1610, "new": 265}
  ]
}
```
````

### Field

| Field | Wajib | Isi |
|---|---|---|
| `v` | ya | Versi skema. Selalu `1`. |
| `type` | ya | `line` \| `bar` \| `area` \| `pie` \| `scatter`. |
| `x.key` | ya | Identifier netral bahasa untuk sumbu kategori/waktu. |
| `x.label` | ya | Teks sumbu, dalam bahasa percakapan. |
| `x.type` | tidak | `date` \| `text` \| `number`. Default `text`. |
| `series[].key` | ya | Identifier netral bahasa; jadi kunci di tiap objek `data`. |
| `series[].label` | ya | Nama seri di legenda, dalam bahasa percakapan. |
| `series[].unit` | tidak | Satuan (`user`, `IDR`, `%`, `ms`). Renderer memakainya untuk sumbu dan tooltip. |
| `data[]` | ya | Objek berisi `x.key` plus tiap `series[].key`. |
| `caption` | tidak | Satu baris penjelas. |
| `note` | tidak | Sumber, asumsi, atau batasan data. |

Untuk `pie`, pakai tepat **satu** seri; tiap entri `data` jadi satu irisan.

## Aturan

**Kunci netral bahasa, label ikut bahasa percakapan** — sama persis dengan
`tag-table`. Ganti bahasa berarti mengganti `label`, tidak pernah `key`.

**Satuan campur butuh sumbu terpisah atau chart terpisah.** Menaruh rupiah
dan persen di satu sumbu menghasilkan grafik yang menyesatkan. Kalau
satuannya berbeda skala, pancarkan dua blok.

**Angka mentah, tanpa format.** `1240`, bukan `"1.240"`. Persen sebagai
angka apa adanya (`12.4` dengan `"unit": "%"`), bukan `0.124`.

**Titik data terurut** menurut `x`. Renderer tidak mengurutkan ulang.

**Nilai hilang ditulis `null`**, bukan `0`. Nol adalah pengukuran; `null`
adalah ketiadaan pengukuran, dan garis yang menukik ke nol karena data
belum masuk adalah kebohongan grafis.

**Di atas ~200 titik data, jangan inline** — agregasi dulu (per minggu, per
bulan), atau simpan sebagai artefak.

## Setelah blok

Satu-dua kalimat yang menyatakan apa yang ditunjukkan bentuknya — arah
tren, titik belok, kesenjangan antar seri. Bukan pembacaan ulang angka.
