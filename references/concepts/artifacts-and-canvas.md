# Artifacts & canvas

## Masalah

Artefak (dokumen, kode, canvas) yang dihasilkan agent cenderung besar dan
sering diedit ulang. Kalau byte-nya ditaruh langsung di kolom pesan
transcript, dua hal rusak sekaligus: transcript membengkak tiap kali artefak
diedit (tiap edit = pesan baru berisi salinan penuh), dan model context ikut
membengkak tiap kali riwayat dimuat ulang ke model — padahal model jarang
butuh isi artefak penuh, cukup tahu bahwa artefak itu ada dan versi mana yang
sedang dibicarakan. Masalah kedua: tanpa versi eksplisit, "edit artefak" jadi
`UPDATE` yang menimpa — riwayat perubahan dan kemampuan undo hilang.

## Pola

### Aturan by-reference

- **Transcript** menyimpan `artifact_id + version` — pointer, bukan byte.
- **Model context** menyimpan handle (`artifact_id`, judul, kind) + ringkasan
  singkat — cukup untuk model tahu artefak itu ada dan bisa merujuknya lewat
  tool, tanpa isi penuh ikut termakan token tiap call.
- **Byte sungguhan** hidup di object store (S3/GCS); Postgres cuma menyimpan
  metadata + kunci object.

### Skema versioning

Meluaskan tabel di [`persistence-schema.md`](persistence-schema.md) — jalankan
setelah skema itu (butuh tabel `users` dan `messages`).

```sql
CREATE TABLE artifacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    kind        TEXT NOT NULL CHECK (kind IN ('text', 'code', 'image', 'sheet')),
    title       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX artifacts_user_idx ON artifacts (user_id, created_at DESC);

CREATE TABLE artifact_versions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id      UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id),
    version          INT NOT NULL,
    edit_mode        TEXT NOT NULL CHECK (edit_mode IN ('initial', 'rewrite', 'patch')),
    storage_backend  TEXT NOT NULL DEFAULT 's3',
    content_ref      TEXT NOT NULL,  -- kunci object store, mis. s3://bucket/artifacts/<id>/<version>
    byte_size        BIGINT,
    checksum         TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, version)
);
CREATE INDEX artifact_versions_artifact_idx ON artifact_versions (artifact_id, version DESC);

-- By-reference dengan integritas nyata: transcript pegang artifact_id +
-- version lewat baris yang bisa di-FK, bukan cuma field di messages.content
-- JSONB (Postgres tidak bisa FK ke dalam JSONB).
CREATE TABLE message_artifact_refs (
    message_id   UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    artifact_id  UUID NOT NULL,
    version      INT NOT NULL,
    user_id      UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (message_id, artifact_id, version),
    FOREIGN KEY (artifact_id, version) REFERENCES artifact_versions (artifact_id, version)
);

ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY artifacts_scope ON artifacts
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE artifact_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY artifact_versions_scope ON artifact_versions
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE message_artifact_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_artifact_refs FORCE ROW LEVEL SECURITY;
CREATE POLICY message_artifact_refs_scope ON message_artifact_refs
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
```

`version` adalah integer monotonik per `artifact_id` (`UNIQUE (artifact_id,
version)`), bukan timestamp. `[ours]` — vanilla-nya, dicontohkan Vercel
`ai-chatbot` `lib/db/schema.ts`: tabel `document` pakai **composite primary
key `(id, createdAt)`**, versi didapat dari `createdAt`, tanpa kolom versi
terpisah. `[code]` — dibaca langsung dari
`raw.githubusercontent.com/vercel/chatbot/main/lib/db/schema.ts`. Kita pilih
integer eksplisit karena timestamp tidak dijamin monoton di bawah concurrent
write/clock skew, dan versi manusiawi ("v3") lebih jelas daripada timestamp
mentah di UI — konsekuensinya app harus menghitung `MAX(version) + 1` dalam
transaksi yang sama saat insert (atau `SELECT ... FOR UPDATE` di baris
`artifacts` untuk mencegah race).

Setiap edit — rewrite maupun patch — adalah `INSERT` baris baru ke
`artifact_versions`, tidak pernah `UPDATE` konten yang sudah ada. Ini
dikonfirmasi jadi pola nyata di `ai-chatbot`: `saveDocument()` di
`lib/db/queries.ts` baris 323-325 memanggil `db.insert(document)` untuk
setiap penyimpanan dokumen, dipanggil balik dari kedua tool edit di bawah.
`[code]`.

### Rewrite penuh vs patch

`ai-chatbot` mengekspos **dua tool terpisah** untuk mengedit satu artefak,
`[code]` dibaca dari `lib/ai/tools/update-document.ts` dan
`lib/ai/tools/edit-document.ts`:

| Aspek | Rewrite penuh (`updateDocument`) | Patch (`editDocument`) |
|---|---|---|
| Deskripsi tool asli | *"Full rewrite of an existing artifact. Only use for major changes where most content needs replacing. Prefer editDocument for targeted changes."* | *"Make a targeted edit to an existing artifact by finding and replacing an exact string. Preferred over updateDocument for small changes. The old_string must match exactly."* |
| Mekanisme | Model men-generate ulang **seluruh** konten lewat `streamText` (LLM call baru, `smoothStream`), hasilnya menimpa draft penuh | App melakukan `content.replace(old_string, new_string)` string biasa (atau `replaceAll` kalau `replace_all: true`) — tidak ada LLM call kedua |
| Biaya token/latency | Tinggi — sebanding panjang seluruh dokumen, LLM harus keluarkan ulang bagian yang sama sekali tidak berubah | Rendah — model hanya keluarkan `old_string`/`new_string`, independen dari panjang dokumen |
| Mode kegagalan | Diam-diam bisa drift — bagian yang tidak dimaksud berubah ikut ter-generate ulang beda | Eksplisit & aman — gagal keras kalau `old_string` tidak ditemukan persis di `document.content` (`"old_string not found in document"`), tidak pernah menimpa hal yang salah |
| Kapan dipakai | Restrukturisasi besar, >separuh isi berubah, atau draft awal (`onCreateDocument`) | Perubahan bertarget — typo, satu fungsi, satu paragraf; ini yang **disukai secara default** menurut deskripsi tool-nya sendiri |

Keduanya berujung ke `INSERT` baris versi baru yang sama (lihat "Skema
versioning" di atas) — perbedaannya cuma *bagaimana* konten baru itu
dihasilkan, bukan *bagaimana* ia disimpan. `edit_mode` di `artifact_versions`
mencatat mana yang dipakai (`'rewrite'` / `'patch'` / `'initial'` untuk
draft pertama) supaya riwayat versi bisa menjawab "apakah ini regenerasi
penuh atau tambalan kecil" tanpa membuka diff.

## Trade-off

- **By-reference vs inline** — inline (byte artefak langsung di
  `messages.content`) lebih sederhana untuk dibaca ulang (tidak perlu join
  ke object store), tapi melanggar batas transcript vs model context: setiap
  reload riwayat ikut menyeret byte artefak penuh ke context. By-reference
  butuh satu round-trip tambahan (fetch content_ref) tapi menjaga context
  tetap murah.
- **Rewrite vs patch** — rewrite murah secara implementasi (satu jalur kode:
  "minta model tulis ulang") tapi mahal token dan berisiko drift diam-diam;
  patch murah token dan aman-secara-gagal tapi butuh `old_string` yang cukup
  unik (model harus menyertakan konteks sekitar supaya match tidak ambigu) —
  `ai-chatbot` menanganinya dengan instruksi eksplisit di deskripsi tool
  ("Include 3-5 surrounding lines for uniqueness"), bukan validasi terpisah.
- **`version INT` vs `createdAt` sebagai versi** — dibahas di atas; trade-off
  intinya sederhana-tapi-berisiko-race (timestamp) vs eksplisit-tapi-butuh-
  koordinasi-insert (integer monotonik).
- **Satu `artifact_versions` row per edit selamanya** — history lengkap +
  undo gratis, tapi storage tumbuh linear dengan jumlah edit. Kalau volume
  edit sangat tinggi (mis. canvas realtime keystroke-per-keystroke), pola ini
  butuh diubah jadi checkpoint periodik + diff, bukan satu row per keystroke
  — belum relevan untuk artefak level dokumen/kode yang diedit lewat tool
  call diskrit seperti di atas.

## Di deepagents

`deepagents` tidak punya primitive "artifact"/dokumen versi bawaan — tidak
ada tool `update_document`/`edit_document` di base stack manapun
(`create_deep_agent`). Yang tersedia adalah backend filesystem yang bisa
dipakai sebagai lapisan durable di baliknya, `[code]` — lihat
[`../systems/deepagents.md`](../systems/deepagents.md) §Backend filesystem:

| Backend | Cocok untuk lapis apa di sini |
|---|---|
| `StateBackend` (default) | Draft ephemeral selama satu run — bukan tempat artefak *permanen* hidup |
| `FilesystemBackend` / `LocalShellBackend` | Working file di disk host — isolasi antar user jadi tanggung jawab pemanggil, tidak cocok untuk artefak multi-user tanpa proses/container terpisah |
| `StoreBackend(namespace=...)` | Paling dekat dengan "durable lintas-thread" — tapi tetap tidak punya konsep versi/`edit_mode`; app yang menaruh versioning di atasnya |
| `CompositeBackend` | Pola hybrid: rute `/artifacts/` ke `StoreBackend`, sisanya ke `StateBackend` — masih butuh app menulis skema `artifact_versions` sendiri (tabel di atas) untuk metadata terstruktur |

Konsekuensinya: skema `artifacts`/`artifact_versions`/`message_artifact_refs`
di atas, dan keputusan rewrite-vs-patch sebagai dua tool terpisah, adalah
sesuatu yang harus ditulis eksplisit sebagai tool aplikasi (mirip
`update-document.ts`/`edit-document.ts` di `ai-chatbot`) yang dipasang lewat
parameter `tools=[...]` ke `create_deep_agent` — bukan sesuatu yang datang
dari `deepagents` itu sendiri.

## Sumber

- `[code]` Vercel `ai-chatbot` (`vercel/chatbot`, repo di-rename dari
  `ai-chatbot`) `lib/db/schema.ts` — tabel `document`, `suggestion`,
  composite primary key `(id, createdAt)`; dibaca utuh via
  `raw.githubusercontent.com/vercel/chatbot/main/lib/db/schema.ts`.
- `[code]` `lib/ai/tools/update-document.ts` — tool rewrite penuh, deskripsi
  tool verbatim, pemanggilan `documentHandler.onUpdateDocument`.
- `[code]` `lib/ai/tools/edit-document.ts` — tool patch, deskripsi tool
  verbatim, mekanisme `content.replace`/`replaceAll` + error eksplisit kalau
  `old_string` tidak ditemukan.
- `[code]` `lib/db/queries.ts` baris 310-325 (`saveDocument`) — konfirmasi
  bahwa kedua tool berujung `db.insert(document)`, bukan `update`.
- `[code]` `artifacts/text/server.ts` — konfirmasi `onUpdateDocument`
  memanggil `streamText` baru (LLM call penuh) untuk kasus rewrite.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §Backend
  filesystem — tier-1 reference yang sudah diverifikasi di Task 3, dikutip
  di sini tanpa membaca ulang source.
