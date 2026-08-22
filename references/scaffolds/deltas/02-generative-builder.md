# Delta 02 — Generative Builder

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya. Rasional
lengkap: [`../../archetypes/02-generative-builder.md`](../../archetypes/02-generative-builder.md)
§Bangun ini pakai deepagents.

## Ganti

- **Backend**: `StoreBackend(namespace=...)` (`_base`) → backend keluarga
  sandbox microVM, mis. `DaytonaSandbox` dari `langchain_daytona`
  (`backend = DaytonaSandbox(sandbox=..., timeout=300)`), atau lewat
  `agent.json` CLI deepagents dengan `{"backend": {"type": "sandbox", ...}}`.
  `[code]` sumber `libs/partners/daytona/README.md`, `libs/cli/README.md`,
  archetype 02. Semua operasi `FilesystemMiddleware` (termasuk `execute`)
  otomatis terkurung ke sandbox tersebut, bukan disk lokal — beda dari
  delta 01 yang backend-nya menyentuh host asli.
- **Checkpointer**: `_base` selalu menyuntikkan checkpointer eksternal
  (Postgres) untuk semua turn. Untuk sesi build/iterate yang sengaja
  ephemeral, checkpointer **tetap dipasang** (dibutuhkan untuk resume kalau
  graceful drain memotong sesi di tengah jalan, `../_base.md` §Graceful
  drain) — yang berubah adalah `StoreBackend`/artefak lintas-sesi: `_base`
  memasangnya sebagai backend utama, di sini ia **tidak ada** kecuali
  ditambah eksplisit (lihat Tambah). `[code]`+`[ours]` archetype 02: vanilla
  contoh dokumentasi kadang tanpa checkpointer/store sama sekali untuk sesi
  pendek; kita tetap pertahankan checkpointer `_base` (beda dari archetype
  yang membuang totalnya) karena `_base.md` sudah membuat graceful drain +
  resumability jadi kontrak baku lintas arketipe — membuang checkpointer di
  sini berarti sesi yang terpotong drain window hilang total, bukan cuma
  "sesi pendek yang sengaja dibuang".

## Tambah

- **Safety gate minimal**: `interrupt_on={"publish": True, "deploy": True}`
  — hanya di tool publish/deploy, bukan tiap `write_file`/`execute` seperti
  delta 01. `[ours]` archetype 02: vanilla deepagents `interrupt_on=None`
  (tidak memaksa HITL sama sekali); kita menambah gate sesempit mungkin
  karena kendali manusia arketipe ini adalah "review di akhir lewat
  preview", bukan approve tiap langkah.
- **Persistence lintas-sesi (opsional)**: kalau produk butuh user kembali
  besok untuk lanjut project yang sama, tambah `StoreBackend` lewat
  `CompositeBackend(default=<sandbox backend>, routes={"/exports/":
  StoreBackend(namespace=...)})` — pilihan eksplisit per-produk, bukan
  default arketipe ini.

## Buang

- **`interrupt_on` seluas delta 01** — tidak relevan; approve per-`write_file`/
  `execute` akan mematikan loop rewrite-cepat yang jadi inti arketipe ini
  (`## Konsekuensi harness` archetype 02, poin loop shape rewrite-penuh vs
  patch granular).
- **Isolasi lewat "proses/container terpisah per user"** (pola delta 01) —
  tidak dibutuhkan di sini karena backend sandbox microVM sudah menyediakan
  isolasi per sesi secara bawaan (`sandboxing.md` — baris microVM, bukan
  baris "tanpa isolasi").
