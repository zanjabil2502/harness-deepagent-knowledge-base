# Retention & deletion

## Masalah

"Hapus user X" terdengar seperti satu `DELETE`, tapi state agent tersebar di
lima lapis lintas beberapa sistem (§8.1): Postgres transcript, checkpointer
Postgres, object store artefak, dan — dua yang paling sering luput —
**vector index** untuk memory/RAG dan **trace store** observability. FK
`ON DELETE CASCADE` cuma menjangkau apa yang ada di dalam satu database
Postgres; tiga sistem lain (object store, vector DB eksternal, trace store)
tidak tahu apa-apa soal `user_id` sampai dipanggil eksplisit. Kalau daftar
cascade tidak lengkap, "penghapusan" berhasil di UI (baris hilang dari
riwayat chat) sementara PII tetap hidup di trace observability atau index
vektor selamanya.

## Pola

### Daftar cascade lengkap

| Lapis | Store | Aksi hapus | Mekanisme |
|---|---|---|---|
| Transcript | Postgres — `conversations`, `messages`, `tool_calls`, `turns`, `compaction_events` | `DELETE FROM conversations WHERE user_id = ...` — sisanya ikut lewat `ON DELETE CASCADE` (lihat `persistence-schema.md`) | SQL, satu transaksi |
| Checkpoint (Run state) | Tabel `checkpoints`/`writes` milik library checkpointer, bukan skema aplikasi | Panggil `checkpointer.adelete_thread(thread_id)` per `conversation_id` yang dihapus — **bukan** `DELETE` manual ke tabel checkpointer, skemanya bukan milik migration aplikasi | `[docs]` API checkpointer, dipanggil dari app |
| Artefak (object store) | S3/GCS + `artifacts`/`artifact_versions` (lihat `artifacts-and-canvas.md`) | Hapus tiap object di `content_ref` untuk semua versi milik user, baru `DELETE FROM artifacts` (cascade ke `artifact_versions`/`message_artifact_refs`) | API storage (idempoten, di-retry) + SQL |
| Memory row | Postgres `memory_entries`, atau `StoreBackend` durable file kalau dipakai | `DELETE FROM memory_entries WHERE user_id = ...`; untuk yang lewat `StoreBackend`: `store.adelete(namespace, key)` per key hasil `store.asearch((user_id,))` | SQL + `[docs]` LangGraph `store.adelete`/`asearch` |
| **Vector index** | Kolom `embedding` di `memory_entries` (pgvector) **atau** vector DB eksternal (Pinecone/Weaviate/Qdrant) terpisah dari Postgres | Kalau pgvector kolokasi: ikut terhapus otomatis lewat `DELETE FROM memory_entries` di atas. Kalau eksternal: **wajib panggilan API delete-by-metadata terpisah** — tidak ada FK yang memaksa ini, paling gampang terlewat | `[ours]` — tidak ada mekanisme otomatis lintas sistem |
| **Trace store** | Observability/tracing eksternal (LangSmith, Langfuse, backend OpenTelemetry) | **Wajib** panggilan API/retention-policy terpisah untuk purge trace bertag `user_id` — trace store nyaris selalu sistem pihak ketiga yang tidak otomatis sinkron dengan penghapusan di produk | `[ours]` — idem, tidak ada mekanisme otomatis |

Dua baris terakhir ditandai tebal karena **paling sering terlewat**: baik
vector index maupun trace store biasanya hidup di sistem yang tidak
menganggap dirinya "milik" siklus hidup user — vector DB dianggap
infrastruktur pencarian, trace store dianggap tooling internal — sampai ada
audit atau permintaan penghapusan data yang menemukan sisa-sisa PII di
keduanya.

### Urutan operasi (saga, bukan satu transaksi)

Penghapusan lintas lima lapis ini tidak bisa jadi satu transaksi ACID —
object store, checkpointer, vector DB eksternal, dan trace store adalah
sistem terpisah. Urutan yang aman untuk kegagalan-parsial:

1. Tandai user untuk dihapus (transaksional: set `deleted_at` atau enqueue
   job penghapusan) — titik commit yang tidak bisa gagal setengah jalan.
2. Cascade Postgres (transcript, tool calls, turns, compaction events, memory
   rows, artifact metadata) dalam satu transaksi — cepat dan atomik karena
   semuanya di database yang sama.
3. Object store: hapus tiap `content_ref` artefak — idempoten, aman
   di-retry kalau job terputus.
4. Checkpointer: `adelete_thread` per `conversation_id`.
5. Vector index eksternal (kalau bukan pgvector kolokasi): delete-by-metadata
   `user_id`.
6. Trace store: purge/redact via API atau retention policy provider.
7. Tandai job selesai + catat di audit log **tanpa** menyertakan konten yang
   baru dihapus (audit log yang menyimpan ulang PII yang katanya sudah
   dihapus meniadakan tujuan penghapusan itu sendiri).

Langkah 3-6 idealnya job background dengan retry per langkah (bukan bagian
dari request HTTP yang menghapus baris di langkah 2) — kalau langkah 5 gagal
karena vector DB eksternal sedang down, langkah 2 tetap sudah selesai dan job
bisa retry cuma dari langkah 5 tanpa mengulang cascade Postgres.

## Trade-off

- **Hard delete vs soft-delete (tombstone)** — hard delete (skema
  `ON DELETE CASCADE` di `persistence-schema.md`) sederhana dan langsung
  patuh terhadap permintaan hapus, tapi menghancurkan bukti yang mungkin
  dibutuhkan investigasi abuse/audit trail. Tombstone (`deleted_at` +
  filter di RLS policy) memberi jendela recovery/investigasi, tapi PII tetap
  hidup sampai job hard-purge terjadwal jalan — artinya tombstone **menunda**
  retensi, bukan menyelesaikannya; masih butuh job hard-purge di langkah 2-6
  di atas setelah jendela retensi lewat. Pola produksi yang realistis:
  tombstone dulu, hard-purge terjadwal setelah grace period (mis. 30 hari).
- **Job sinkron vs asinkron untuk langkah 3-6** — sinkron (semua langkah
  dalam satu request) memberi kepastian instan ("sudah terhapus semua" saat
  response 200), tapi request bisa timeout kalau salah satu API eksternal
  lambat, dan kegagalan-parsial jadi sulit di-retry granular. Asinkron (job
  queue per langkah) tahan kegagalan-parsial tapi butuh status tracking
  ("penghapusan sedang diproses") dan user tidak dapat konfirmasi instan.
- **Vector index kolokasi (pgvector) vs eksternal** — kolokasi menghapus gap
  ini sepenuhnya (ikut `DELETE FROM memory_entries` biasa, tidak ada langkah
  saga tambahan), tapi vector DB terkelola eksternal biasanya lebih murah
  di skala besar dan search-nya lebih matang. Trade-off ini sama dengan yang
  disebut di `persistence-schema.md` soal `embedding VECTOR(...)` opsional.

## Di deepagents

`deepagents` tidak menjalankan retention/deletion job apa pun — konsisten
dengan `checkpointer`/`store` yang **diteruskan apa adanya** ke
`langchain.agents.create_agent` (`deepagents` tidak membangun keduanya
sendiri), `[code]` — lihat
[`../systems/deepagents.md`](../systems/deepagents.md) §5. Konsekuensinya,
memanggil `checkpointer.adelete_thread(...)`/`store.adelete(...)` di langkah
4-5 di atas adalah kode aplikasi yang memakai checkpointer/store yang sama
persis dengan yang disuntikkan ke `create_deep_agent` — bukan API dari
`deepagents` itu sendiri.

Satu cascade tambahan yang relevan kalau `FilesystemBackend`/
`LocalShellBackend` dipakai: keduanya baca/tulis langsung ke disk host
(`root_dir`), dan isolasi antar user **bukan** tanggung jawab backend
melainkan proses/container terpisah per user, `[code]` — lihat
[`../systems/deepagents.md`](../systems/deepagents.md) §Backend filesystem
(dikutip dari `THREAT_MODEL.md`). Kalau backend ini dipakai untuk state yang
bertahan lintas sesi per user (bukan cuma sandbox sekali-pakai yang dibuang),
penghapusan harus menyapu direktori itu juga — di luar cakupan skema
Postgres di atas sepenuhnya.

## Sumber

- `[docs]` LangGraph — `checkpointer.delete_thread`/`adelete_thread`
  ("removes all checkpoints and associated write records for a specified
  thread"), dikutip via Context7 dari
  `docs.langchain.com/oss/python/langgraph/checkpointers`.
- `[docs]` LangGraph — `store.adelete(namespace, key)` dan
  `store.asearch(namespace)` untuk enumerasi key sebelum dihapus, dikutip
  via Context7 dari `docs.langchain.com/oss/python/langgraph/stores`.
- `[code]` LibreChat `packages/data-schemas/src/schema/message.ts` baris 233
  (`messageSchema.index({ expiredAt: 1 }, { expireAfterSeconds: 0 })`) dan
  `packages/data-schemas/src/schema/toolCall.ts` baris 61 — precedent nyata
  untuk penghapusan otomatis berbasis TTL index (chat/tool-call sementara
  yang auto-expire). Postgres tidak punya TTL index native seperti MongoDB;
  pola yang setara adalah job terjadwal (`pg_cron` atau worker eksternal)
  yang men-scan kolom `expired_at`/`deleted_at` — dicatat di sini sebagai
  `[inferred]` translasi pola, bukan diklaim sebagai fitur Postgres bawaan.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5, §Backend
  filesystem — tier-1 reference yang sudah diverifikasi di Task 3, dikutip
  di sini tanpa membaca ulang source.
