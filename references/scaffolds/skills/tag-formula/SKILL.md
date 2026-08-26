---
name: tag-formula
description: Emit mathematical expressions as LaTeX in a ```math block so the app renders real notation instead of ASCII approximations. Use for equations, derivations, statistical formulas, and symbolic definitions — including requests phrased as rumus, formula, persamaan, matematika, fórmula, or 数式.
---

# Emit mathematics as a `math` block

## Kapan dipakai

Pakai saat notasinya **membawa arti** yang hilang kalau ditulis sebagai
teks biasa: pecahan, akar, sigma, integral, matriks, subskrip/superskrip,
huruf Yunani.

Jangan pakai untuk aritmetika sederhana yang terbaca jelas dalam kalimat
("naik 12% dari 1.240 jadi 1.390"). Notasi untuk hal yang tidak butuh
notasi memperlambat pembaca.

## Bentuk

Persamaan tersendiri memakai blok berpagar `math`, tanpa `$$` di dalamnya:

````
```math
\text{skor} = \frac{\sum_{i=1}^{n} w_i \cdot x_i}{\sum_{i=1}^{n} w_i}
```
````

Simbol yang menyatu dalam kalimat memakai `$…$` inline: "bobot $w_i$
menormalkan tiap komponen". Jangan memakai blok untuk satu simbol; jangan
memakai inline untuk persamaan bertingkat.

## Aturan

**Definisikan tiap simbol.** Setelah blok, sebutkan arti tiap variabel dan
satuannya. Rumus tanpa daftar simbol tidak bisa diverifikasi pembaca.

**Nama variabel netral bahasa, penjelasannya ikut bahasa percakapan.**
Simbol matematika sudah universal — jangan menerjemahkan $x$ jadi $k$
karena bahasanya berganti. Yang diterjemahkan cuma prosa penjelasnya dan
isi `\text{…}`.

**Bungkus kata dengan `\text{…}`.** Kata polos dalam mode matematika
dirender sebagai perkalian huruf demi huruf: `skor` jadi $s\cdot k\cdot
o\cdot r$.

**Jangan pakai `\href`, `\includegraphics`, `\input`, atau `\write`.**
Semuanya menjangkau di luar matematika dan ditolak renderer yang aman.

**Batasi pada makro standar** yang dikenal KaTeX/MathJax. Paket LaTeX
lengkap (`amsmath` di luar himpunan umum, `tikz`, environment kustom)
tidak tersedia di renderer web dan gagal diam-diam atau memunculkan blok
merah.

**Turunan bertahap memakai `aligned`**, satu langkah per baris,
disejajarkan pada tanda `=`:

````
```math
\begin{aligned}
  p &= \frac{1}{1 + e^{-z}} \\
  z &= \beta_0 + \beta_1 x
\end{aligned}
```
````

**Satu persamaan satu blok.** Dua rumus yang tidak berhubungan adalah dua
blok dengan prosa di antaranya, bukan satu blok berbaris ganda.

## Setelah blok

Nyatakan **apa yang dilakukan rumus itu** dalam satu kalimat, lalu daftar
simbolnya. Pembaca yang tidak bisa mengurai notasinya tetap harus paham
maksudnya.
