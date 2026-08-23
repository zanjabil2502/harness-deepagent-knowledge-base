# Vercel `ai-chatbot`

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. `vercel/ai-chatbot`, Next.js App Router + Vercel AI SDK
(`ai@7.0.15`, `@ai-sdk/react@4.0.16`) + Postgres (Drizzle) + opsional Redis.
Dipilih sebagai eksemplar **artefak/canvas** sesuai kandidat T2 spec §10.
Catatan penamaan: GitHub API mengonfirmasi `vercel/ai-chatbot` sudah
di-rename jadi `vercel/chatbot` (`api.github.com/repos/vercel/ai-chatbot`
mengembalikan `"message": "Moved Permanently"`) — konsisten dengan yang
sudah dicatat `references/concepts/artifacts-and-canvas.md` §Sumber. Repo
tetap dikloning lewat URL lama (`git clone` mengikuti redirect otomatis),
jadi isi yang dibaca file ini adalah konten `vercel/chatbot` terkini; nama
file `vercel-ai-chatbot.md` dipertahankan sesuai daftar file di task brief.

## Arketipe

**In-App Copilot (05)** dengan elemen **Generative Builder (02)** lewat
sistem *artifact* (dokumen kode/teks/sheet yang dibuat & diedit sebagai
objek terpisah dari transkrip chat, mirip kanvas). Horizon pendek per giliran
HTTP (`maxDuration = 60`), tool surface sempit dan tetap (5 tool bernama),
tanpa delegasi subagent. `[code]` — `app/(chat)/api/chat/route.ts` baris 49,
271-278.

## 1. Loop shape

ReAct terbatas: `streamText({ ..., stopWhen: isStepCount(5), tools: {...} })`
dari Vercel AI SDK — harness memasang **batas keras 5 langkah** tool-call
per giliran (`isStepCount(5)`), bukan cuma jaring pengaman jauh di atas
(beda dari `recursion_limit=9999` `deepagents` atau
`max_iteration_per_run=500` OpenHands — di sini 5 adalah batas operasional
normal, bukan darurat). Dalam 5 langkah itu, model yang memutuskan berhenti
lebih awal dengan tidak memanggil tool lagi; SDK yang menegakkan batas atas.
`[code]` — `app/(chat)/api/chat/route.ts` baris 269, 305.

## 2. Context

Tidak ada compaction/summarization di jalur ini — `messages: modelMessages`
diteruskan langsung dari `convertToModelMessages(uiMessages)` tanpa
condenser. Tidak ditemukan modul ringkas riwayat di `lib/ai/` yang dibaca.
`[inferred]` — dari tidak ditemukannya import summarizer/condenser di
`app/(chat)/api/chat/route.ts` maupun `lib/ai/*`.

Sebaliknya, sistem **artifact** memindahkan konten besar (dokumen kode/
teks/sheet) **keluar** dari transkrip chat sejak awal, bukan lewat eviction
belakangan: `createDocument`/`updateDocument` tool menulis ke tabel
`document` (Postgres), transkrip hanya menyimpan hasil tool (biasanya
ringkasan/diff) — pola *artefak-by-reference* yang persis diargumentasikan
`references/concepts/artifacts-and-canvas.md` dan aturan turunan §8.1 spec
desain. `[code]` — `lib/artifacts/server.ts` baris 1-45 (`DocumentHandler`,
`saveDocument`), `lib/db/schema.ts` baris 73-90 (tabel `document`).

## 3. Tool surface

Sedikit tool bernama-eksplisit dan tetap, tidak berubah per giliran:
`getWeather`, `createDocument`, `editDocument`, `updateDocument`,
`requestSuggestions`. Kecuali satu pengecualian **deterministik**: kalau
model adalah *reasoning model* yang tidak mendukung tool-calling
(`isReasoningModel && !supportsTools`), `activeTools` diset ke array kosong
— tool surface dipangkas total berdasar kapabilitas model, dicek di kode,
bukan diputuskan model. `[code]` — `app/(chat)/api/chat/route.ts` baris
269-278, 306-316.

## 4. Delegation

**Flat, tidak ada subagent.** Tidak ditemukan mekanisme spawn-agent-lain,
task-tool, atau handoff di `app/(chat)/api/chat/route.ts` maupun `lib/ai/`
— satu `streamText` call, satu model, tool dijalankan inline dalam loop SDK
yang sama. `[inferred]` — dari tidak ditemukannya modul subagent/delegation
di direktori yang dibaca.

## 5. State & resume

- **Transkrip**: tabel `message` (`Message_v2`) di Postgres, dikonversi
  bolak-balik lewat `convertToModelMessages`/`convertToUIMessages`. `[code]`
  — `lib/db/schema.ts` baris 42, `lib/utils.ts` (fungsi `convertToUIMessages`
  dirujuk di import `route.ts` baris 43).
- **Artefak berversi**: tabel `document` pakai **composite primary key
  `(id, createdAt)`** — tiap edit dokumen adalah **row baru**, bukan
  `UPDATE` di tempat; `suggestion` mereferensikan versi dokumen spesifik
  lewat `(documentId, documentCreatedAt)`. Ini pola versioning
  append-only yang persis cocok dengan "S3/GCS + row metadata, permanen,
  berversi" di §8.1 spec desain (di sini row Postgres, bukan object
  store, tapi prinsip append-only-nya sama). `[code]` — `lib/db/schema.ts`
  baris 73-114.
- **Resume stream**: tabel `stream` + `createStreamId({chatId, streamId})`
  + `resumable-stream` (paket npm `resumable-stream`,
  `createResumableStreamContext`). **Bersyarat eksplisit ke `REDIS_URL`**:
  `if (!process.env.REDIS_URL) { return; }` sebelum
  `streamContext.createNewResumableStream(...)` dipanggil — tanpa Redis,
  resume stream **diam-diam tidak aktif** (bukan error, bukan fallback
  otomatis). `[code]` — `app/(chat)/api/chat/route.ts` baris 405-421.
  Endpoint reattach `GET /api/chat/[id]/stream` di source yang dibaca
  **hanya mengembalikan `Response(null, {status: 204})`** — badan endpoint
  yang biasanya membaca `streamContext.resumableStream(...)` untuk
  menyambung koneksi terputus tidak ada isinya di snapshot yang dikloning.
  `[code]` — `app/(chat)/api/chat/[id]/stream/route.ts` (utuh, 3 baris).
  **Temuan kejujuran**: ini kontras dengan ekspektasi umum "Vercel
  ai-chatbot = contoh resumable stream lengkap" — di commit yang dibaca,
  jalur reattach GET tampak sebagai stub/placeholder, bukan implementasi
  aktif. Tidak diverifikasi apakah ini regresi sementara, refactor
  sedang berjalan, atau reattach sudah dipindah ke mekanisme lain
  (mis. client polling `getMessagesByChatId`) — disebut sebagai
  ketidakpastian, bukan diklaim sebagai bug. `[code]` (isi file apa
  adanya) + `[inferred]` (interpretasi penyebab).

## 6. Safety gate

Tidak ada gerbang approval per-tool (tool yang tersedia adalah pembuatan
konten, bukan aksi destruktif/shell). Gerbang yang ada beroperasi di level
**request**, bukan level tool-call: `checkBotId` (deteksi bot sebelum proses
jalan) dan `checkIpRateLimit` dipanggil di awal `POST` handler, plus
`entitlementsByUserType` yang membatasi kuota model per tipe user. `[code]`
— import `botid/server`, `checkIpRateLimit`,
`entitlementsByUserType` di `app/(chat)/api/chat/route.ts` baris 15, 40-41.
Tidak ada sandbox eksekusi kode — artifact "code" hanya *menyimpan* teks
kode, tidak ada bukti eksekusi kode di server dalam file yang dibaca.
`[inferred]`.

## 7. Capability routing & policy

**Deterministik di kode, berbasis metadata model — bukan judgment model,
bukan classifier terlatih, bukan manifest per-request.** Satu-satunya
percabangan kapabilitas yang ditemukan: `activeTools: isReasoningModel &&
!supportsTools ? [] : [...5 tool tetap]` — properti model
(`isReasoningModel`, `supportsTools`, keduanya field statis dari katalog
model di `lib/ai/models.ts`) menentukan tool surface, dievaluasi tiap
request tapi hasilnya deterministik untuk model yang sama. `[code]` —
`app/(chat)/api/chat/route.ts` baris 269-278; `getCapabilities`,
`getModelAvailability` diimpor dari `lib/ai/models.ts` (baris 18-19).

Tidak ada mekanisme skill/mode routing tambahan (tidak ada registry skill,
tidak ada handoff antar-agent) — cakupan capability routing di sistem ini
jauh lebih sempit dibanding `deepagents`/OpenHands/LibreChat karena memang
hanya satu agent, satu tool set tetap. `[inferred]` — dari cakupan
`lib/ai/` yang dibaca (`tools/`, `models.ts`, `prompts.ts`, `providers.ts`).

## Sumber

Repo `vercel/ai-chatbot` dikloning shallow (`git clone --depth 1`)
2026-08-23 dan dibaca langsung sebagai file:

- `app/(chat)/api/chat/route.ts` — utuh (470 baris): import (1-45),
  `getStreamContext`/`createResumableStreamContext` (13, 60-68),
  `POST` handler, `streamText` call (260-330), `consumeSseStream` +
  gate `REDIS_URL` (405-425)
- `app/(chat)/api/chat/[id]/stream/route.ts` — utuh (3 baris)
- `app/(chat)/api/chat/schema.ts` — nama file dikonfirmasi, isi tak dibaca
  detail
- `lib/artifacts/server.ts` — baris 1-50 (`DocumentHandler`,
  `createDocumentHandler`, tipe `CreateDocumentCallbackProps`)
- `lib/db/schema.ts` — baris 28-134 (`chat`, `message`, `vote`,
  `document`, `suggestion`, `stream` — nama tabel & primary key)
- `lib/ai/tools/*.ts` — listing (`create-document.ts`, `edit-document.ts`,
  `get-weather.ts`, `request-suggestions.ts`, `update-document.ts`)
- `package.json` baris 22-40 (`ai@7.0.15`, `@ai-sdk/react@4.0.16`,
  `@ai-sdk/provider@4.0.2`, `@ai-sdk/otel@1.0.15`)

Catatan kejujuran: `lib/ai/models.ts`, `lib/ai/prompts.ts`,
`lib/ai/providers.ts`, dan isi tiga `artifacts/*/server.ts`
(`code/server.ts`, `sheet/server.ts`, `text/server.ts`) hanya dikutip lewat
import/listing, **tidak** dibaca isinya penuh — klaim `isReasoningModel`/
`supportsTools` sebagai field statis di `models.ts` disimpulkan dari nama
fungsi `getCapabilities`/`getModelAvailability`, bukan dari membaca definisi
tipe langsung.
