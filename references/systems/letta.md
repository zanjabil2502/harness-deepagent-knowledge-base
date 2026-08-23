# Letta

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. Catatan identitas penting, sama polanya dengan OpenHands: repo
`letta-ai/letta` (kandidat asli di spec §10 untuk "memory lintas sesi") sudah
**diarsipkan**. `README.md`-nya sendiri menyatakan: *"This repository now
serves as a landing page for the Letta project. The retired Letta V1 server
source is preserved on the `archive` branch... The current source code lives
in `letta-ai/letta-code`"*. `[code]` — `README.md` repo `letta-ai/letta`
(`git clone --depth 1`, 2026-08-23; commit terakhir sebelum arsip: `87fd37a
chore: archive the legacy server repository`). Letta modern (npm
`@letta-ai/letta-code`) adalah **harness coding-agent** (CLI interaktif +
App Server + channel Slack/Telegram/Discord/WhatsApp/Signal), bukan lagi
murni "platform memori API" — file ini mendokumentasikan `letta-code` karena
itulah software yang benar-benar berjalan hari ini, dan mencatat eksplisit
bahwa memori lintas-sesi (alasan Letta masuk kandidat T2) berpindah bentuk:
dari memory-block REST API murni menjadi **filesystem memori git-backed
per-agent** di atas server yang masih mengekspos primitif memory-block lama
lewat `@letta-ai/letta-client`.

## Arketipe

**Workspace Agent (01)** — CLI terminal interaktif dengan tool bash/file,
permission mode, dan sandbox OS-level (lihat sumbu 6), sangat paralel
strukturnya dengan `claude-code.md` (bedanya: Letta bisa dibaca sebagai
`[code]`, Claude Code tidak). Horizon bisa panjang (App Server + channel
async: Slack/Telegram/cron). `[code]` — `letta-ai/letta-code` `README.md`,
struktur direktori `src/channels/`, `src/cron/`.

## 1. Loop shape

Eksekusi giliran model (LLM call ⇄ tool call) berjalan **di sisi server**,
dipanggil lewat `@letta-ai/letta-client` (tipe `MessageCreate` dari
`resources/agents/agents`) — `letta-code` sendiri tidak mengimplementasi
loop ReAct-nya sendiri, ia klien dari agent server Letta (self-hosted lewat
`letta server` atau Letta Cloud). `[code]` — import
`@letta-ai/letta-client/resources/agents/agents` di
`src/queue/turn-queue-runtime.ts` baris 1; `README.md` ("Run the App Server
for local or self-hosted agents").

Yang **memang** diimplementasikan di `letta-code` adalah **penggabungan
input sebelum giliran dikirim**: `QueuedTurnInput` punya tiga jenis —
`"user"` (pesan user), `"task_notification"`, `"cron_prompt"` — digabung
lewat `mergeQueuedTurnInput` (helper `appendContentParts`,
`normalizeUserContent`) jadi satu `MessageCreate.content` sebelum dikirim ke
server. Ini pola coalescing input multi-sumber (chat interaktif + notifikasi
task async + cron), bukan loop tool-calling. `[code]` —
`src/queue/turn-queue-runtime.ts` baris 1-30.

## 2. Context

Dua lapis memori berbeda hidup berdampingan:

- **Memory block klasik** (warisan MemGPT/Letta V1) — label `persona`,
  `human` (`MEMORY_BLOCK_LABELS = ["persona", "human"]`), dimuat dari file
  `.mdx` di `src/agent/prompts/<label>.mdx`, dikirim ke server lewat tipe
  `CreateBlock` dari `@letta-ai/letta-client`. Catatan versi: field
  per-project (`skills`/`loaded_skills`) **dihapus** dari memory block
  (referensi tiket `LET-7353` di komentar kode) — skill sekarang disuntik
  lewat *system reminder*, bukan block memori. `[code]` —
  `src/agent/memory.ts` baris 1-21.
- **Memory filesystem git-backed ("MemFS")** — lapisan baru: tiap agent
  punya direktori `~/.letta/agents/<agentId>/memory/` di disk, dan
  `memory-git.ts` (2128 baris) mengelola direktori itu sebagai **repo git
  sungguhan**: commit, hook, worktree, config lock, dan signing commit
  sendiri (`memory-git-hooks.ts`, `memory-git-signing.ts`,
  `memory-git-config-lock.ts`, `memory-worktree.ts`). Komentar modul
  eksplisit menyebut migrasi: *"With git-backed memory, most sync/hash logic
  is removed"* — versi lama memakai hashing manual, versi sekarang memakai
  git sebagai mesin versi. `[code]` — `src/agent/memory-filesystem.ts` baris
  1-30 (docstring modul, konstanta `MEMORY_FS_ROOT = ".letta"`).

Ini adalah bentuk "memory lintas sesi" yang jauh lebih literal dibanding
kebanyakan sistem lain di grid ini — bukan vector store atau ringkasan,
tapi **riwayat git yang bisa di-diff, di-rollback, dan di-branch** persis
seperti kode.

## 3. Tool surface

Tidak diverifikasi detail daftar tool bawaan (modul `src/tools/` ada tapi
tidak dibaca isinya di task ini) — namun frontmatter skill builtin
menunjukkan pola tool minimal per-skill: skill `memory` (defragmentasi
memori, lihat sumbu 4) hanya diberi `tools: Bash, TaskOutput` — subset kecil
dan eksplisit, bukan seluruh tool surface agent utama. `[code]` —
`src/agent/subagents/builtin/memory.md` frontmatter (baris 1-7). `[inferred]`
untuk generalisasi ke tool surface agent utama (tidak dibaca).

## 4. Delegation

Ada mekanisme subagent eksplisit dan matang: `src/agent/subagents/manager.ts`
+ `subagent-launcher.ts` + `context-budget.ts` (**subagent punya anggaran
token/context sendiri, terpisah dari parent** — `buildMinimalParentMemorySection`/
`shrinkParentMemorySection`/`hardTruncateReflectionPrompt` menunjukkan parent
memory disuntik ke subagent dalam bentuk terpangkas, bukan penuh) +
`spawnSubagent` (async, dengan catatan komentar soal timing "runs after
several async yields"). `[code]` — `src/agent/subagents/manager.ts` baris
92-189, 340, 726-803 (nama fungsi & docstring, isi implementasi detail tidak
dibaca penuh).

Subagent didefinisikan sebagai **skill dengan frontmatter tambahan**:
`launchProfile: memory-subagent` di `subagents/builtin/memory.md` — pola
sama dengan skill biasa (Markdown + YAML frontmatter) tapi dengan
`launchProfile` yang menandainya bisa di-spawn sebagai proses subagent
terpisah, bukan disuntik sebagai instruksi ke agent utama. `[code]` —
`src/agent/subagents/builtin/memory.md` frontmatter.

**Hasil kembali ke pemanggil**: skill `memory` didefinisikan eksplisit
sebagai *"You run autonomously and return a **single final report** when
done. You **cannot ask questions** mid-execution."* — kontrak fire-and-report,
bukan interaktif, bukan transkrip penuh. `[code]` — `memory.md` baris 9-10.

## 5. State & resume

Tiga lapis state berbeda:

| Lapis | Mekanisme |
|---|---|
| Transkrip percakapan | Server Letta (via `@letta-ai/letta-client`) — tidak dibaca detail di task ini |
| Memori agent | Repo git per-agent di `~/.letta/agents/<id>/memory/` (sumbu 2) |
| Giliran tertunda | `QueuedTurnInput` (`user`/`task_notification`/`cron_prompt`) digabung sebelum dikirim |

`[code]` — `src/agent/memory-filesystem.ts` (konstanta path),
`src/queue/turn-queue-runtime.ts` (tipe `QueuedTurnInput`).

Resume: `resolve-startup-agent.ts` dan `reconcile-existing-agent-state.ts`
ada sebagai modul terpisah (nama file dikonfirmasi, isi tidak dibaca) —
menunjukkan ada jalur eksplisit "sambung ke agent yang sudah ada" saat CLI
start ulang, konsisten dengan model "agent sebagai entitas persisten di
server", bukan sesi sekali pakai. `[code]` (listing) /
`[inferred]` (isi mekanisme resume detail).

## 6. Safety gate

Sistem permission **empat mode**, mirip filosofi Claude Code tapi dengan
default berbeda:

```ts
export type PermissionMode = "standard" | "acceptEdits" | "unrestricted" | "strict";
export const DEFAULT_PERMISSION_MODE: PermissionMode = "unrestricted";
```

**Temuan kejujuran**: default mode adalah `"unrestricted"`, bukan mode
paling ketat — kontras dengan asumsi umum "harness coding-agent modern
default-nya minta approval". Kode juga mempertahankan migrasi nama mode
lama: `"default"` → `"standard"`, `"bypassPermissions"`/`"fullAccess"` →
`"unrestricted"` (backward-compat literal string dari versi sebelumnya).
`[code]` — `src/permissions/mode.ts` baris 3-32.

Sandbox OS-level nyata, dua backend: **Seatbelt** (macOS,
`sandbox/seatbelt.ts`) dan **bubblewrap/`bwrap`** (Linux, `sandbox/bwrap.ts`),
digerakkan oleh satu `FsSandboxPolicy` deklaratif yang sama di kedua backend
— `baseWritableRoots`, `deniedRoots`, `readonlyRoots`, `writableRoots`,
`restrictWrites`, dengan urutan penerapan eksplisit: *"global write-deny →
baseWritableRoots → deniedRoots → writableRoots → readonlyRoots"* (spesifik
menang lewat urutan, bukan kedalaman nesting). Kegunaan konkret yang dikutip
di komentar kode: memberi subagent memori akses tulis luas ke `~/.letta`
tapi tetap **menolak** akses ke `~/.letta/agents` milik agent lain
(cross-agent memory isolation) — kecuali carve-out sempit untuk memori
miliknya sendiri (`writableRoots` menang atas `deniedRoots`). `[code]` —
`src/sandbox/policy.ts` baris 1-40 (docstring modul, interface
`FsSandboxPolicy`); `src/permissions/cross-agent-guard.ts` (nama file,
dikonfirmasi lewat referensi di komentar `policy.ts`).

## 7. Capability routing & policy

**Prosa + judgment model murni, empat sumber berlapis prioritas** — pola
sama seperti Agent Skills (Anthropic) yang juga dipakai `deepagents`. Skill
ditemukan dari:

1. Project skills (`.agents/skills/`, fallback legacy `.skills/`) —
   prioritas tertinggi, override.
2. Agent skills (`~/.letta/agents/{agent-id}/memory/skills/`).
3. Global skills (`~/.letta/skills/`).
4. Bundled skills (dalam paket npm) — prioritas terendah, default.

`[code]` — `src/agent/skills.ts` baris 1-9 (docstring modul). Tiap skill
adalah file Markdown dengan frontmatter YAML (`name`, `description`,
`tools`, `model`, opsional `launchProfile` untuk subagent) — model memilih
skill berdasar `description` yang terlihat, tidak ada classifier kode yang
mencocokkan keyword/path seperti di OpenHands (`skills/trigger.py`,
lihat `openhands.md`). Ini kontras eksplisit yang sama dengan yang dibahas
`references/concepts/skill-composition.md` dan `references/concepts/
policy-as-data.md`: layering sumber (project > agent > global > bundled)
adalah **presedensi deklaratif** (siapa menang saat nama sama), tapi
**pemilihan skill mana yang relevan untuk giliran tertentu** tetap
sepenuhnya judgment model — tidak ada keputusan runtime yang ditegakkan
kode di luar urutan override sumber. `[code]` — `src/agent/skills.ts`,
`src/agent/skill-sources.ts` (nama tipe `SkillSource`/`ALL_SKILL_SOURCES`).

## Sumber

Dua repo dikloning shallow (`git clone --depth 1`) 2026-08-23 dan dibaca
langsung sebagai file:

- `letta-ai/letta` (`github.com/letta-ai/letta`) — `README.md` utuh, untuk
  mengonfirmasi status arsip dan lokasi source baru. `git log --oneline -1`
  dikonfirmasi: `87fd37a chore: archive the legacy server repository (#3430)`.
- `letta-ai/letta-code` (`github.com/letta-ai/letta-code`, npm
  `@letta-ai/letta-code`):
  - `README.md` utuh
  - `src/agent/memory.ts` baris 1-21 (`MEMORY_BLOCK_LABELS`, docstring
    migrasi `LET-7353`)
  - `src/agent/memory-filesystem.ts` baris 1-60 (docstring modul, konstanta
    path `MEMORY_FS_ROOT`, `MEMORY_FS_AGENTS_DIR`, `MEMORY_FS_MEMORY_DIR`)
  - `src/agent/subagents/manager.ts` baris 92-189, 340, 726-803 (nama fungsi
    via grep — isi tidak dibaca penuh)
  - `src/agent/subagents/builtin/memory.md` — utuh (frontmatter + badan
    deskripsi tugas)
  - `src/agent/skills.ts` baris 1-40 (docstring modul + fungsi
    `getBundledSkillsPath`)
  - `src/permissions/mode.ts` — utuh (32 baris awal, tipe `PermissionMode`,
    `DEFAULT_PERMISSION_MODE`, `migratePermissionMode`)
  - `src/sandbox/policy.ts` baris 1-40 (docstring modul, interface
    `FsSandboxPolicy`)
  - `src/queue/turn-queue-runtime.ts` baris 1-40 (tipe `QueuedTurnInput`,
    import `MessageCreate` dari `@letta-ai/letta-client`)
  - Listing direktori untuk konfirmasi struktur (isi tak dibaca detail):
    `src/permissions/*.ts` (>30 file — `sandbox-policy.ts`,
    `cross-agent-guard.ts`, `workspace-sandbox.ts`, `read-only-shell.ts`,
    dst), `src/sandbox/{bwrap,seatbelt,wrap,availability}.ts`,
    `src/channels/{slack,telegram,discord,whatsapp,signal}/`, `src/cron/`,
    `src/agent/memory-git*.ts` (2128 baris di `memory-git.ts`, tidak dibaca
    utuh)

Catatan kejujuran: loop tool-calling aktual (giliran LLM ⇄ tool) berjalan di
**server** Letta (paket/repo terpisah, kemungkinan closed atau di repo lain
yang tidak diverifikasi task ini) — klaim di sumbu 1 dibatasi pada apa yang
`letta-code` (klien) lakukan sebelum mengirim giliran, bukan bagaimana
server mengeksekusinya. `memory-git.ts` (2128 baris) dan
`SubagentExecutor`-setaranya di `manager.ts` **tidak** dibaca utuh — klaim
dibatasi pada docstring modul dan nama fungsi yang dikutip.
