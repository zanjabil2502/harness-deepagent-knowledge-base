# Persistence schema

## Masalah

Skema state agent yang ditulis ad hoc gagal dengan pola yang berulang: riwayat
disimpan sebagai list rata sehingga "edit pesan lalu regenerate" menimpa
riwayat lama; tool call ditaruh sebagai field JSON di dalam pesan sehingga
tidak bisa di-query/di-redact per baris; kompaksi mengganti isi pesan asli
langsung (transcript ikut hilang, bukan cuma context yang dipangkas); retry
jaringan pada satu turn membuat turn kedua karena tidak ada kunci idempotensi;
dan satu tabel lupa kolom `user_id` sehingga bocor antar user — pasti terjadi
di codebase yang hidup cukup lama (§8.2).

DDL di bawah adalah jawaban langsung: bisa di-paste ke `psql` apa adanya.

## Pola

Urutan `CREATE TABLE` sudah mengikuti urutan dependency FK — jalankan dari
atas ke bawah.

```sql
-- ============================================================
-- Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
-- CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector, opsional — hanya kalau
--                                          -- embedding memory disimpan di
--                                          -- Postgres, lihat memory_entries.

-- ============================================================
-- Identitas & scope
-- ============================================================
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- [ours] Tabel users lokal ada di sini supaya skema ini runnable mandiri di
-- psql. Di deployment nyata baris identitas sering dimiliki IdP eksternal
-- (mis. Supabase auth.users, Clerk) dan tabel ini jadi foreign
-- table/view, bukan sumber kebenaran. Vanilla-nya: tidak ada tabel users
-- lokal sama sekali, user_id di tabel lain cukup UUID opak tanpa FK lokal.

-- ============================================================
-- Percakapan & turn (idempotency key per turn)
-- ============================================================
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);
CREATE INDEX conversations_user_id_idx ON conversations (user_id, created_at DESC);

-- Satu "turn" = satu unit permintaan pengguna -> respons agent (termasuk
-- semua tool call di dalamnya). idempotency_key dikirim client per turn
-- (mis. UUID dibuat client saat submit) supaya retry jaringan atau
-- duplicate-submit tidak membuat turn kedua: INSERT kedua dengan
-- (user_id, idempotency_key) yang sama akan gagal kena UNIQUE, app cukup
-- tangkap error itu dan kembalikan turn yang sudah ada.
CREATE TABLE turns (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id),
    idempotency_key  TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'completed', 'failed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX turns_conversation_id_idx ON turns (conversation_id, created_at);

-- ============================================================
-- Transcript sebagai TREE, bukan list
-- ============================================================
CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    parent_id        UUID REFERENCES messages(id) ON DELETE SET NULL,
    turn_id          UUID REFERENCES turns(id) ON DELETE SET NULL,
    user_id          UUID NOT NULL REFERENCES users(id),
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content          JSONB NOT NULL,  -- parts array; artifact ref hidup di sini,
                                       -- lihat artifacts-and-canvas.md
    status           TEXT NOT NULL DEFAULT 'complete'
                       CHECK (status IN ('complete', 'streaming', 'error')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation_parent_idx ON messages (conversation_id, parent_id);
CREATE INDEX messages_conversation_created_idx ON messages (conversation_id, created_at);
CREATE INDEX messages_turn_id_idx ON messages (turn_id);

COMMENT ON COLUMN messages.parent_id IS
  'NULL = root pesan di conversation. Edit pesan lama = INSERT baris baru '
  'dengan parent_id sama dengan versi lama (bukan UPDATE) -> bercabang. '
  '"Path aktif" = jalan dari root ke leaf terbaru yang dipilih user; '
  'dihitung app-side, lihat session-state.md.';

-- ============================================================
-- Tool call sebagai row transcript KELAS SATU
-- ============================================================
CREATE TABLE tool_calls (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id   UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id),
    sequence     INT NOT NULL DEFAULT 0,  -- urutan dalam satu message (bisa >1 tool call/turn)
    tool_name    TEXT NOT NULL,
    arguments    JSONB NOT NULL,
    result       JSONB,
    status       TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'success', 'error')),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (message_id, sequence)
);
CREATE INDEX tool_calls_message_id_idx ON tool_calls (message_id);
CREATE INDEX tool_calls_user_tool_idx ON tool_calls (user_id, tool_name, started_at DESC);

-- ============================================================
-- Compaction event -> menunjuk pesan yang DIGANTIKAN, tidak menghapusnya
-- ============================================================
CREATE TABLE compaction_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id    UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id            UUID NOT NULL REFERENCES users(id),
    summary_message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    reason             TEXT NOT NULL DEFAULT 'token_threshold'
                          CHECK (reason IN ('token_threshold', 'manual', 'tool_result_evict')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE compaction_event_messages (
    compaction_event_id UUID NOT NULL REFERENCES compaction_events(id) ON DELETE CASCADE,
    message_id           UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id               UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (compaction_event_id, message_id)
);
CREATE INDEX compaction_event_messages_message_idx ON compaction_event_messages (message_id);

COMMENT ON TABLE compaction_events IS
  'Pesan lama TIDAK dihapus saat kompaksi -- transcript tetap permanen. '
  'summary_message_id menunjuk pesan ringkasan baru; '
  'compaction_event_messages menunjuk pesan-pesan asli yang diringkas. '
  'Model context (lapis ephemeral) yang berhenti mengirim pesan asli ke '
  'model, bukan transcript yang kehilangan barisnya -- lihat session-state.md.';

-- ============================================================
-- Memory lintas sesi (Postgres + vector) -- baris minimal untuk lapis
-- "Memory" di tabel 5 lapis; desain lengkap ada di concepts/memory.md
-- (bidang Cognition, belum ditulis di task ini).
-- ============================================================
CREATE TABLE memory_entries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    key         TEXT,
    value       TEXT NOT NULL,
    -- embedding VECTOR(1536),  -- aktifkan setelah CREATE EXTENSION vector
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_entries_user_idx ON memory_entries (user_id, updated_at DESC);
```

### Row-Level Security — penegakan scope, bukan `WHERE` manual (§8.2)

```sql
-- App wajib set variabel sesi ini per koneksi/transaksi SEBELUM query apa pun:
--   SET LOCAL app.current_user_id = '<uuid user yang sedang login>';

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;  -- berlaku juga untuk owner tabel
CREATE POLICY conversations_scope ON conversations
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
CREATE POLICY messages_scope ON messages
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY tool_calls_scope ON tool_calls
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

ALTER TABLE memory_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY memory_entries_scope ON memory_entries
    USING (user_id = current_setting('app.current_user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

-- Pola yang sama berlaku ke turns, compaction_events,
-- compaction_event_messages, dan artifacts/artifact_versions/
-- message_artifact_refs (lihat artifacts-and-canvas.md) -- tiap tabel
-- discope lewat kolom user_id miliknya sendiri, bukan lewat JOIN ke
-- conversations. `current_setting(..., true)` (argumen kedua) supaya
-- policy fail-closed ke "tidak ada baris" kalau variabel sesi lupa
-- di-set, bukan error keras di tengah request.
```

### Yang sengaja TIDAK di-DDL-kan di sini: checkpointer

Tabel `checkpoints`/`writes` milik library checkpointer (mis.
`langgraph-checkpoint-postgres`) sengaja tidak didefinisikan ulang di sini.
Skemanya `[docs]`:

```sql
CREATE TABLE checkpoints (
    thread_id             TEXT NOT NULL,
    checkpoint_ns          TEXT NOT NULL DEFAULT '',
    checkpoint_id           TEXT NOT NULL,
    parent_checkpoint_id   TEXT,
    type                    TEXT,
    checkpoint              BYTEA,
    metadata                 JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

Alasan tidak dijadikan bagian skema aplikasi ini: tabel itu dimigrasi dan
dimiliki oleh library checkpointer sendiri, bukan oleh migration aplikasi —
mengubah bentuknya (mis. menambah kolom `user_id`) berisiko putus saat
library update. `thread_id` di tabel itu **disamakan secara konvensi**
dengan `conversations.id` (bukan FK — beda subsistem, beda migration), dan
scoping-nya ditegakkan di level aplikasi (thread hanya diminta untuk
`conversation_id` yang lolos RLS `conversations`), bukan RLS Postgres native
di tabel checkpoint itu sendiri. Ini gap yang jujur dilaporkan, bukan
disembunyikan — lihat `session-state.md` untuk kenapa checkpointer bukan
database produk.

## Trade-off

- **Junction table (`compaction_event_messages`) ikut punya `user_id`
  sendiri** meski bisa didapat lewat JOIN ke `messages`/`compaction_events`.
  `[ours]` — vanilla-nya: RLS lewat subquery (`message_id IN (SELECT id
  FROM messages WHERE user_id = ...)`), yang tidak sargable dan lebih
  lambat di tabel besar. Kita pilih kolom scope langsung + trade-off
  redundansi (harus ditulis konsisten dalam transaksi yang sama saat
  insert) demi policy RLS yang murah dan seragam di semua tabel.
- **`version INT` vs timestamp sebagai versi** — dibahas di
  `artifacts-and-canvas.md`, relevan juga di sini karena pola yang sama bisa
  dipakai untuk `memory_entries` kalau butuh riwayat perubahan fakta memory
  (skema di atas sengaja tidak menambah versioning ke memory — YAGNI sampai
  ada kebutuhan nyata "riwayat memory berubah").
- **Soft-delete vs hard-delete di lapis ini** — skema di atas pakai
  `ON DELETE CASCADE` (hard) dari `conversations` turun; kalau retensi legal
  butuh tombstone, ganti jadi `deleted_at TIMESTAMPTZ` + filter di RLS
  policy. Trade-off lengkap di `retention-and-deletion.md`.
- **`checkpoints`/`writes` tidak ikut RLS Postgres** (lihat di atas) adalah
  trade-off sadar: konsistensi skema checkpointer dengan upstream library vs
  penegakan scope seragam. Kalau isolasi multi-tenant yang lebih ketat
  dibutuhkan di lapis ini, alternatifnya adalah checkpointer kustom yang
  menambah kolom scope sendiri — belum dilakukan di sini karena deepagents
  meneruskan checkpointer apa adanya (lihat `Di deepagents` di bawah), jadi
  mengubahnya berarti keluar dari kontrak yang disuntikkan aplikasi.

## Di deepagents

`checkpointer` dan `store` yang dipakai untuk mengisi tabel di atas (secara
tidak langsung — lewat konvensi `thread_id = conversation_id`, bukan FK)
diteruskan **apa adanya** oleh `deepagents` ke
`langchain.agents.create_agent`; `deepagents` tidak pernah membangun
checkpointer/store sendiri. `[code]` — lihat
[`../systems/deepagents.md`](../systems/deepagents.md) §5 (`deepagents/graph.py`
baris 546-553, 922-931). Artinya skema `messages`/`tool_calls`/
`compaction_events` di atas murni tanggung jawab aplikasi yang memanggil
`create_deep_agent` — tidak ada bagian dari `deepagents` yang menulis ke
tabel-tabel ini.

## Sumber

- `[code]` LibreChat `packages/data-schemas/src/schema/toolCall.ts`
  (`danny-avila/LibreChat`, dibaca lewat
  `raw.githubusercontent.com/danny-avila/LibreChat/main/...`) — precedent
  nyata untuk "tool call sebagai koleksi/tabel terpisah" yang mereferensi
  `messageId`/`conversationId`, dengan `blockIndex`/`partIndex` untuk urutan
  dalam satu pesan (dipetakan ke kolom `sequence` di `tool_calls` di atas,
  `[ours]` penyederhanaan nama).
- `[code]` LibreChat `packages/data-schemas/src/schema/message.ts` — baris
  `parentMessageId` mengonfirmasi pola tree lewat pointer parent per baris
  (bukan list), dan kolom `tenantId` terindeks berdampingan dengan skema
  yang tetap berjalan single-tenant — precedent nyata untuk "scope column
  hari ini `user_id`, jalur migrasi `tenant_id`" di §8.2. `[ours]` — skema
  di atas sengaja tidak menyalin kolom `tenant_id` sekarang: §8.2 minta
  scope object di level aplikasi, bukan kolom DB, jadi menambah kolom
  yang belum dipakai di mana pun adalah YAGNI sampai multi-tenant
  sungguh dibangun (migrasinya nanti tinggal `ALTER TABLE ... ADD COLUMN
  tenant_id`, tidak menuntut redesain tabel).
- `[code]` Open WebUI `backend/open_webui/models/chats.py` — `Chat.chat =
  Column(JSON)`: seluruh tree pesan (`parentId`/`childrenIds`/`currentId`)
  hidup di **satu kolom JSON per chat**, bukan baris SQL ternormalisasi.
  Ini kontras langsung dengan pilihan `[ours]` di atas (baris `messages`
  ternormalisasi dengan `parent_id` FK) — vanilla Open WebUI: satu blob JSON
  per percakapan. Kita pilih baris ternormalisasi karena butuh tool call
  first-class per pesan dan RLS per baris, dua hal yang tidak bisa
  didapat dari isi JSON blob.
- `[docs]` LangGraph — skema `checkpoints`/`writes` dan kontrak
  `BaseCheckpointSaver`, dikutip via Context7 dari
  `docs.langchain.com/oss/python/langgraph/checkpointers`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §5 — untuk
  bagian "Di deepagents" (tier-1 reference, sudah diverifikasi di Task 3,
  dikutip di sini tanpa membaca ulang source).
