# Isolation & scoping

## Masalah

"Multi-user" dan "multi-tenant" sering dipakai bertukar padahal beda model
isolasi, dan salah pilih di awal itu mahal ke dua arah: membangun
multi-tenant penuh (schema-per-tenant, tenant sebagai entitas first-class
di tiap query) padahal produknya baru punya satu jenis pelanggan (individu)
adalah over-engineering yang menambah kerumitan tanpa pembeli; sebaliknya
menghardcode `user_id` di query tanpa jalur migrasi eksplisit membuat
tambahan tenant nanti jadi migrasi skema besar, bukan penambahan kolom.

Masalah kedua, lebih berbahaya: cara paling umum menegakkan scope adalah
`WHERE user_id = :current_user` di tiap query — dan itu **pasti** akan ada
satu query yang lupa menambahkannya begitu codebase hidup cukup lama
(query baru ditulis tergesa, join yang lupa scope di salah satu sisi,
admin script yang "cuma sekali pakai"). Satu query yang lupa filter itu
kebocoran data user lain, seketika, tanpa error yang terlihat — request-nya
tetap sukses 200, cuma isinya salah pemilik.

## Pola

### Multi-user vs multi-tenant

| Sumbu | Multi-user | Multi-tenant |
|---|---|---|
| Unit isolasi | Satu baris `user_id` | Satu organisasi (`tenant_id`), berisi banyak `user_id` |
| Scope object | `(user_id)` | `(tenant_id, user_id)` |
| Model data | Semua tabel `user_id`-scoped, flat | Tabel `user_id`-scoped **plus** kolom/context `tenant_id` yang membatasi lebih dulu sebelum `user_id` |
| Siapa lihat siapa | User A tidak pernah lihat data user B, titik | User dalam tenant yang sama bisa berbagi resource (workspace, billing, admin lintas-user); user tenant lain tidak pernah lihat apa pun |
| Contoh nyata | ChatGPT personal, Claude.ai personal | Slack workspace, Notion workspace, produk B2B SaaS |
| Kompleksitas | Rendah — satu kolom scope, satu policy | Lebih tinggi — dua level scope, kebijakan admin-lintas-user dalam tenant, kemungkinan kolokasi vs isolasi fisik per tenant |

Asumsi proyek ini (§8.2, sesuai konstrain global): **multi-user hari ini,
multi-tenant sebagai jalur migrasi** — bukan dibangun penuh sejak awal.

### Scope object, bukan `user_id` hardcode

Semua akses data lewat satu **scope object** yang bentuknya berubah seiring
produk tumbuh, tapi titik pemakaiannya di kode tidak berubah:

```
Hari ini:        scope = (user_id,)
Setelah migrasi:  scope = (tenant_id, user_id)
```

Kode yang memanggil query/RLS-context selalu lewat scope object ini, bukan
menyisipkan `user_id` mentah di tiap tempat terpisah. Konsekuensinya:
menambah `tenant_id` nanti berarti mengubah **bentuk scope object di satu
tempat** dan menambah kolom + policy DB baru, bukan menelusuri ulang tiap
query aplikasi yang pernah ditulis. Ini konsisten dengan keputusan
`persistence-schema.md`: skema DDL Task 4 **sengaja tidak** menambah
kolom `tenant_id` sekarang meski precedent industri (LibreChat) sudah
menaruhnya — argumen YAGN-nya: kolom yang belum dipakai di mana pun cuma
menambah permukaan tanpa manfaat, dan migrasinya nanti (`ALTER TABLE ...
ADD COLUMN tenant_id`) tidak menuntut redesain tabel karena scope object
sudah jadi titik tunggal yang berubah.

### Kenapa RLS, bukan `WHERE` manual

Penegakan di **Postgres Row-Level Security**, bukan `WHERE` manual per
query. Alasannya persis seperti di `## Masalah`: satu query lupa filter =
kebocoran antar user, dan itu pasti terjadi di codebase yang hidup cukup
lama — argumen ini bukan spekulasi, ini pernyataan tentang tingkat error
manusia yang tidak berkurang seiring waktu, cuma berkurang **titik di mana
error itu bisa terjadi**. `WHERE` manual punya satu titik penegakan per
query (N titik gagal, N = jumlah query yang pernah dan akan ditulis). RLS
punya satu titik penegakan per tabel, dievaluasi Postgres sendiri di level
row **terlepas dari bentuk query** — `SELECT *` tanpa `WHERE` sama sekali
pun tetap cuma mengembalikan baris milik scope aktif, karena Postgres
menyisipkan predikat policy ke rencana eksekusi sebelum query dieksekusi,
bukan bergantung pada aplikasi menulisnya dengan benar.

Implementasi konkret persis seperti yang sudah dipatok `persistence-schema.md`
— file ini **tidak mengubahnya**, cuma menjelaskan alasannya:

```sql
-- App wajib set variabel sesi ini per koneksi/transaksi SEBELUM query apa pun:
SET LOCAL app.current_user_id = '<uuid user yang sedang login>';

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;  -- berlaku juga untuk owner tabel
CREATE POLICY conversations_scope ON conversations
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
```

Tiga detail yang bikin pola ini benar-benar fail-closed, bukan cuma
fail-safe-di-kasus-umum:

- **`FORCE ROW LEVEL SECURITY`** — tanpa ini, role pemilik tabel (yang
  biasanya dipakai koneksi aplikasi) **melewati** RLS sepenuhnya. RLS aktif
  tapi tidak dipaksakan adalah RLS yang tidak melakukan apa-apa untuk
  koneksi aplikasi normal.
- **`current_setting(..., true)`** — argumen kedua `true` bikin
  `current_setting` mengembalikan `NULL` (bukan error keras) kalau
  variabel sesi lupa di-set. `NULL = user_id` selalu `false` di SQL, jadi
  policy jatuh ke "tidak ada baris terlihat" — fail-closed ke kosong, bukan
  fail-open ke semua baris atau crash request.
- **Connection pooling adalah vektor kebocoran baru yang harus dijaga
  eksplisit** — kalau koneksi dari pool dipakai ulang lintas user tanpa
  `SET LOCAL` di-reset tiap request/transaksi, `current_setting` yang
  "kelupaan direset" bukan `NULL` tapi nilai user sebelumnya. `SET LOCAL`
  (bukan `SET`) sengaja dipakai karena otomatis berakhir di batas
  transaksi — tapi aplikasi tetap wajib memanggilnya di **setiap**
  transaksi baru, tidak sekali per koneksi.

## Trade-off

- **RLS vs `WHERE` manual** — `WHERE` manual lebih mudah ditelusuri secara
  lokal (baca satu fungsi, lihat semua filternya di situ, tidak perlu tahu
  ada state sesi DB di luar teks query) tapi correctness-nya bergantung
  100% pada disiplin tiap penulis query, termasuk migrasi/admin
  script/ORM raw query yang mudah lupa. RLS memindahkan invariant itu ke
  database, ditegakkan bahkan untuk query yang ditulis manusia lain di
  masa depan yang tidak tahu ada aturan ini — dengan biaya: setiap koneksi
  DB (termasuk yang dibuat pool/worker background) harus disiplin
  men-set `app.current_user_id` per transaksi, dan predikat RLS lewat
  subquery/JOIN tidak selalu sargable (sudah dibahas di
  `persistence-schema.md` untuk `compaction_event_messages` — kolom scope
  langsung dipilih di atas JOIN demi query planner yang murah, pola yang
  sama berlaku di tabel manapun yang discope tidak langsung).
- **`(user_id)` sekarang vs `(tenant_id, user_id)` sejak awal** — menambah
  `tenant_id` sejak hari pertama menghindari migrasi skema nanti, tapi
  menambah kerumitan (kolom, index, policy, keputusan "siapa admin tenant
  boleh lihat siapa") untuk kebutuhan yang belum ada pembelinya — YAGNI
  sampai multi-tenant sungguh dibangun. Ini keputusan yang sama seperti
  yang sudah diambil `persistence-schema.md`, bukan keputusan baru di
  file ini.
- **Shared-schema + RLS vs schema-per-tenant vs database-per-tenant** —
  relevan begitu migrasi ke multi-tenant sungguh terjadi. Shared-schema
  (satu skema, kolom `tenant_id`/`user_id`, RLS) murah untuk banyak tenant
  kecil (satu migrasi berlaku semua), tapi isolasi "cuma" sekuat policy
  RLS. Schema-per-tenant memberi isolasi lebih kuat (bug query lintas
  tenant lebih sulit terjadi — namespace beda) dengan ongkos operasional
  yang naik linear terhadap jumlah tenant (migrasi harus jalan N kali).
  Database-per-tenant memberi isolasi terkuat (blast radius tenant lain
  = nol, cocok untuk on-prem satu pelanggan enterprise — untuk kasus itu
  seluruh database **memang** milik satu tenant, isolasi datang gratis)
  tapi paling mahal untuk banyak tenant kecil. Asumsi proyek ini (multi-
  user dulu) berarti pilihan default shared-schema + RLS; opsi lain jadi
  relevan cuma kalau segmen enterprise/on-prem-per-pelanggan muncul.

## Di deepagents

`deepagents` tidak punya konsep user/tenant sama sekali — scoping 100%
tanggung jawab aplikasi yang memanggilnya, konsisten dengan pola "BE punya
kebenaran" di `session-state.md`. Dua titik konkret tempat scope harus
disuntik aplikasi:

- **Checkpointer** — `thread_id` diteruskan aplikasi ke `checkpointer` yang
  disuntik ke `create_deep_agent`, dan **disamakan secara konvensi** dengan
  `conversations.id` (bukan FK — beda subsistem, beda migration; sudah
  ditetapkan di `persistence-schema.md`). Scoping-nya ditegakkan di level
  aplikasi (thread cuma diminta untuk `conversation_id` yang sudah lolos
  RLS Postgres di tabel `conversations`), **bukan** RLS Postgres native di
  tabel `checkpoints`/`writes` milik library checkpointer itu sendiri —
  gap yang sudah dilaporkan jujur di `persistence-schema.md`, diulang di
  sini karena file ini persis soal penegakan scope: kalau isolasi
  multi-tenant yang lebih ketat sampai ke lapis checkpoint dibutuhkan,
  itu butuh checkpointer kustom, bukan sesuatu yang datang gratis dari
  RLS tabel aplikasi.
- **`StoreBackend(namespace=...)`** — *hook* scoping resmi untuk state
  durable lintas-thread. Contoh dari dokumentasi:
  `namespace=lambda rt: (rt.server_info.user.identity,)` untuk isolasi
  per-user; pola yang sama tinggal diperluas jadi
  `(rt.server_info.tenant.id, rt.server_info.user.identity)` begitu
  migrasi ke multi-tenant terjadi — bentuknya persis mengikuti scope
  object `(user_id)` → `(tenant_id, user_id)` di atas. `[code]`+`[docs]` —
  [`../systems/deepagents.md`](../systems/deepagents.md) §Backend
  filesystem.

`FilesystemBackend`/`LocalShellBackend` (baca/tulis langsung ke disk host)
**tidak** punya *hook* scoping — isolasi antar user untuk keduanya harus
dibangun di luar backend (proses/container terpisah per user), fakta yang
sudah dicatat `deepagents.md` dan `retention-and-deletion.md`. `[code]` —
[`../systems/deepagents.md`](../systems/deepagents.md) §Backend
filesystem.

## Sumber

- `[code]` [`persistence-schema.md`](persistence-schema.md) — DDL RLS
  (`FORCE ROW LEVEL SECURITY`, `USING`/`WITH CHECK`,
  `current_setting(..., true)`) sudah dieksekusi terhadap Postgres 16
  hidup dan sepuluh tabel bermuatan `user_id` sudah punya forced RLS
  policy (Task 4) — file ini tidak mengubah DDL itu, cuma menjelaskan
  alasannya secara lebih dalam.
- `[code]` [`session-state.md`](session-state.md) — konvensi
  `thread_id = conversation.id` dan pemilik kebenaran BE vs proyeksi AI
  yang jadi dasar kenapa scoping ditegakkan di lapis aplikasi/DB, bukan
  di `deepagents`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md)
  §Backend filesystem — tier-1 reference terverifikasi Task 3, dikutip
  tanpa membaca ulang source.
- `[code]` LibreChat `packages/data-schemas/src/schema/message.ts` —
  kolom `tenantId` terindeks berdampingan dengan skema yang tetap
  berjalan single-tenant, precedent nyata yang sudah dikutip
  `persistence-schema.md` untuk argumen "scope object hari ini `user_id`,
  jalur migrasi `tenant_id`"; dikutip ulang di sini sebagai rujukan, bukan
  dibaca ulang.
