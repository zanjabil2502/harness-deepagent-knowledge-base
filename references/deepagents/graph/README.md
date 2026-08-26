# Graf AST source `deepagents` — indeks simbol → `file:line`

Indeks struktural source `deepagents==0.7.8`: apa memanggil apa, dan di
baris berapa tiap simbol didefinisikan. Ini yang mengubah "parameter apa
saja yang dipunya X" dari pertanyaan ingatan jadi pertanyaan lokasi —
graf memberi alamatnya, source memberi signature-nya.

## Apa yang ada di sini, dan apa yang tidak

Node menyimpan **identitas simbol dan alamatnya**, bukan isinya: `label`,
penanda callable/class, `source_file`, `source_location`. **Tidak ada**
nama parameter, nilai default, atau anotasi tipe — semua itu dibaca dari
source, dan dirangkum di [`../api-reference.md`](../api-reference.md).

Yang kaya justru sisi relasinya — 3.619 edge dalam sepuluh jenis, tiap
edge membawa `source_file` dan `source_location` sendiri:

| Relasi | Jumlah | Relasi | Jumlah |
|---|---:|---|---:|
| `calls` | 1.065 | `uses` | 167 |
| `references` | 766 | `inherits` | 73 |
| `rationale_for` | 723 | `indirect_call` | 13 |
| `contains` | 426 | `imports_from` | 2 |
| `method` | 383 | `imports` | 1 |

## Berkas

| Berkas | Isi |
|---|---|
| [`GRAPH_REPORT.md`](GRAPH_REPORT.md) | Laporan terbaca: hub per komunitas, node paling terhubung, siklus import, koneksi tak terduga |
| `graph.json` | Graf penuh (1.788 node, 3.619 edge). Dibaca `tools/build_glossary.py` untuk bagian simbol di [`../../GLOSSARY.md`](../../GLOSSARY.md) |
| `manifest.json` | md5 tiap berkas source saat graf dibangun. Dibaca `tools/check_kb.py` untuk membuktikan graf masih sinkron |
| `.graphify_labels.json` | Label komunitas |

Turunan yang tidak di-commit (git-ignored): `graph.html`, `cache/`,
`cost.json`, `.graphify_python`, `.graphify_root` — besar, mesin-spesifik,
atau memuat path absolut.

## Kesinkronan dijaga, bukan diasumsikan

Seluruh nilai indeks ini bergantung pada kecocokan dengan source yang
terpasang. Begitu paketnya berubah, sitasi `file.py:NNN` di seluruh KB
bisa meleset **tanpa satu pun cek gagal** — kelas kegagalan yang sudah dua
kali terjadi di proyek ini (32 sitasi dokumentasi meleset satu baris, dan
sitasi `graph.py` meleset +49).

Karena itu `manifest.json` menyimpan md5 mentah tiap berkas, dan
`tools/check_kb.py` membandingkannya dua arah tiap kali dijalankan: berkas
yang ada di graf tapi hilang atau berubah di source, dan berkas yang ada di
source tapi belum masuk graf. Status terakhir: **53/53 cocok**. Tanpa venv
`../../recipes/.venv`, cek itu dilewati dengan pesan `LEWAT` dan sisanya
tetap jalan.

## Membangun ulang

Dibangkitkan graphify — ekstraksi murni AST, nol token LLM, nol API key.
Langkahnya ada di [`../../../README.md`](../../../README.md) §Graph source
deepagents. Graphify melewati apa pun di dalam `.venv`, jadi source-nya
disalin dulu ke path biasa. Keluarannya mendarat di `graphify-out/`;
pindahkan isinya ke direktori ini.

Satu batas yang perlu diketahui: `graph.json` mencatat `built_at_commit`
berisi commit **repo ini**, bukan versi `deepagents` yang digambarkan.
Versinya dipastikan lewat cek md5 di atas, bukan lewat metadata graf.
