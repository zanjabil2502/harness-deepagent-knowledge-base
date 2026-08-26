---
name: tag-table
description: Emit tabular data as a validated ```table JSON block so the app renders a real table instead of markdown pipes. Use when the answer compares items across attributes, lists records with repeated fields, or shows a matrix — including requests phrased as tabel, tabla, 表, or "show me a table".
---

# Emit tabular data as a `table` block

## Kapan dipakai

Pakai saat jawaban memuat **beberapa entitas yang berbagi atribut sama**:
perbandingan, daftar record, matriks, ringkasan berkolom.

Jangan pakai untuk: pasangan kunci-nilai tunggal (tulis sebagai prosa atau
daftar), teks berjenjang yang bukan data (pakai heading), atau angka
sepanjang deret waktu yang lebih terbaca sebagai chart — untuk itu pakai
`tag-chart`.

## Bentuk

Pancarkan blok berpagar dengan info string `table`. Isinya JSON tunggal.

````
```table
{
  "v": 1,
  "caption": "Perbandingan paket langganan",
  "columns": [
    {"key": "plan",    "label": "Paket",       "type": "text"},
    {"key": "price",   "label": "Harga/bulan", "type": "number", "align": "right"},
    {"key": "seats",   "label": "Kursi",       "type": "number", "align": "right"},
    {"key": "sso",     "label": "SSO",         "type": "bool"}
  ],
  "rows": [
    {"plan": "Starter",  "price": 0,      "seats": 3,   "sso": false},
    {"plan": "Team",     "price": 250000, "seats": 25,  "sso": false},
    {"plan": "Business", "price": 900000, "seats": 100, "sso": true}
  ]
}
```
````

### Field

| Field | Wajib | Isi |
|---|---|---|
| `v` | ya | Versi skema. Selalu `1`. |
| `columns[].key` | ya | Identifier netral bahasa, `snake_case`. Jadi kunci di tiap objek `rows`. |
| `columns[].label` | ya | Teks header, **dalam bahasa percakapan**. |
| `columns[].type` | ya | `text` \| `number` \| `date` \| `bool`. |
| `columns[].align` | tidak | `left` \| `right` \| `center`. Default: `right` untuk `number`, `left` selebihnya. |
| `rows[]` | ya | Objek dengan kunci persis dari `columns[].key`. |
| `caption` | tidak | Satu baris penjelas di atas tabel. |
| `note` | tidak | Satu baris catatan di bawah tabel (sumber, asumsi, satuan). |

## Aturan

**Kunci netral bahasa, label ikut bahasa percakapan.** `key` adalah
identifier mesin dan tidak pernah berubah meski jawabannya berbahasa
Indonesia, Inggris, atau apa pun. Yang berubah cuma `label` dan `caption`.
Jangan pernah memakai label sebagai kunci.

**Tiap baris memuat semua kunci.** Nilai yang tidak diketahui ditulis
`null`, bukan dihilangkan atau diisi `"-"`. Renderer yang membedakan
"kosong" dari "nol" bergantung pada ini.

**Angka adalah angka.** `250000`, bukan `"Rp250.000"`. Satuan dan format
mata uang urusan renderer; taruh satuannya di `label` atau `note`. Tanggal
memakai ISO-8601 (`2026-01-15`), bukan format lokal.

**Di atas ~50 baris, jangan inline.** Simpan sebagai artefak dan rujuk
dengan satu kalimat plus tautan. Tabel panjang membanjiri konteks dan tidak
terbaca di chat.

**Satu tabel satu blok.** Dua perbandingan yang tidak berbagi kolom adalah
dua blok, bukan satu tabel dengan kolom kosong di mana-mana.

## Setelah blok

Blok tidak menjelaskan dirinya sendiri. Sertakan satu-dua kalimat prosa
yang menyatakan **temuan**-nya — apa yang harus dilihat pembaca — bukan
membaca ulang isi selnya.
