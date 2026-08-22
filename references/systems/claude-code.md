# Claude Code

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**, tapi **berbeda perlakuan dari delapan file lain di grid ini**:
Claude Code adalah produk closed-source — tidak ada repo publik untuk
dibaca. Setiap klaim di file ini berlabel `[docs]` (dikutip langsung dari
`docs.claude.com`, diambil lewat `curl` ke URL `.md` mentah, bukan lewat
ringkasan) atau `[inferred]` (disimpulkan dari perilaku produk/dokumentasi
tidak langsung). **Tidak ada klaim `[code]` di file ini** — kalau ada
kebutuhan membaca source sungguhan untuk pola serupa, lihat `deepagents.md`
(T1) atau `openhands.md`/`letta.md` di grid ini, yang mengimplementasikan
mekanisme setara secara terbuka.

File ini punya tugas spesifik di KB: jadi **contoh utama sumbu 7** untuk
pola "prosa + judgment model" pada *capability routing* — termasuk
kelemahan pola itu, yang sudah diargumentasikan penuh di
`references/concepts/policy-as-data.md` dan
`references/concepts/skill-composition.md`. File ini mengutip argumen itu,
tidak mengulanginya.

## Arketipe

**Workspace Agent (01)** — CLI lokal, tool bash/file luas, permission gate
granular, dan compaction agresif adalah konsekuensi archetype yang persis
cocok dengan deskripsi `archetypes/01-workspace-agent.md`. `[docs]` —
struktur command/tool yang didokumentasikan di `docs.claude.com/en/docs/
claude-code/*` (permissions, hooks, subagents, skills — semua dikutip di
`## Sumber`).

## 1. Loop shape

Tidak diverifikasi dari source (closed). Dari dokumentasi publik: loop
ReAct standar (baca/tulis file, jalankan shell, panggil tool, ulangi sampai
model berhenti memanggil tool) — perilaku ini **tidak** didokumentasikan
secara eksplisit sebagai diagram loop di halaman manapun yang dibaca, hanya
tersirat dari cara `hooks.md` mendeskripsikan siklus `PreToolUse`/
`PostToolUse` per tool call. `[inferred]`.

## 2. Context

**Auto-compaction** didokumentasikan eksplisit dengan interaksi konkret ke
skill (lihat sumbu 7): *"Auto-compaction carries invoked skills forward
within a token budget. When the conversation is summarized to free context,
Claude Code re-attaches the most recent invocation of each skill after the
summary, keeping the first 5,000 tokens of each. Re-attached skills share a
combined budget of 25,000 tokens... older skills can be dropped entirely
after compaction if you have invoked many in one session."* `[docs]` —
`docs.claude.com/en/docs/claude-code/skills.md` baris ~503 (dikutip persis).

Ini contoh konkret dari trade-off compaction-vs-fidelity yang dibahas
`references/concepts/context-engineering.md`: ringkasan bukan penyimpanan
lengkap — skill yang di-drop dari budget kompaksi butuh **di-invoke ulang**
secara eksplisit untuk konten penuhnya kembali, bukan otomatis pulih.
`[docs]` — kutipan sama.

## 3. Tool surface

Tidak diverifikasi daftar lengkap dari source. Dari dokumentasi: subagent
`general-purpose` bawaan mendapat "every tool available to subagents"
(permukaan luas), sementara subagent `Explore`/`Plan` bawaan sengaja dibatasi
read-only ("Write and Edit are denied") — pola tool surface yang **berbeda
per peran**, bukan satu tool set flat untuk semua konteks. `[docs]` —
`docs.claude.com/en/docs/claude-code/sub-agents.md` (tabel "Built-in
subagents").

## 4. Delegation

Subagent adalah mekanisme delegasi utama, didokumentasikan dengan tiga
built-in (`Explore`, `Plan`, `general-purpose`) plus beberapa helper
(`statusline-setup`, `claude-code-guide`, `claude` catch-all), dan subagent
custom lewat file Markdown+frontmatter di `.claude/agents/` (project) atau
`~/.claude/agents/` (user). Klaim eksplisit dari docs: *"Each subagent runs
in its own context window with a custom system prompt, specific tool
access, and independent permissions"* — isolasi context penuh, bukan
sekadar prompt tambahan di context yang sama. `[docs]` —
`docs.claude.com/en/docs/claude-code/sub-agents.md`.

**Hasil kembali ke pemanggil**: *"The subagent summarizes its results and
returns them to your main conversation when it finishes"* — ringkasan, bukan
transkrip kerja penuh, sama filosofinya dengan pola `ToolMessage` ringkas di
`deepagents`/OpenHands. `[docs]` — sama, baris ~717.

Pemilihan subagent mana yang dipanggil untuk task tertentu adalah **judgment
model murni** atas `description`: *"Claude uses each subagent's description
to decide when to delegate tasks. When you create a subagent, write a clear
description so Claude knows when to use it."* — sama pola dan sama
kelemahan yang dibahas di sumbu 7 di bawah, karena mekanismenya identik
dengan routing skill. `[docs]` — `docs.claude.com/en/docs/claude-code/
sub-agents.md`.

## 5. State & resume

Tidak diverifikasi mekanisme checkpoint/resume dari source. Halaman docs
yang dibaca menyebut kemampuan terkait tapi tidak dibaca detail di task ini
(`background agents`, `agent-view`, `cross-session messaging`, `agent
teams` — dirujuk sebagai fitur terpisah di `sub-agents.md`, bukan
diverifikasi isinya). `[inferred]` untuk detail mekanisme; `[docs]` hanya
untuk keberadaan fitur (nama & rujukan silang, dari
`docs.claude.com/en/docs/claude-code/sub-agents.md` baris ~13, Note box).

## 6. Safety gate

**Enam mode permission terdokumentasi**, spektrum dari paling ketat ke
paling longgar:

| Mode | Perilaku |
|---|---|
| `default` ("Manual") | Prompt izin di pemakaian pertama tiap tool |
| `acceptEdits` | Auto-accept edit file + command filesystem umum (`mkdir`, `touch`, `mv`, `cp`) dalam working directory |
| `plan` | Baca-saja untuk eksplorasi; command read-only-classifier boleh jalan kalau `auto` mode aktif |
| `auto` | Auto-approve tool call, **dengan background safety check berbasis model** yang memverifikasi kesesuaian aksi dengan permintaan |
| `dontAsk` | Auto-**deny** tool kecuali sudah di-allow lewat `/permissions`/`permissions.allow` — `AskUserQuestion` dan tool MCP bertanda `requiresUserInteraction` tetap ditolak meski sudah di-allow |
| `bypassPermissions` | Lewati semua prompt kecuali *"actions no mode auto-approves"* — dokumentasi eksplisit memperingatkan: hanya dipakai di lingkungan terisolasi (kontainer/VM) |

`[docs]` — `docs.claude.com/en/docs/claude-code/permissions.md` baris
74-91 (tabel mode, kutipan `bypassPermissions` warning persis).

Mode `auto` menarik untuk kontras arsitektur: gate-nya **bukan** aturan
deterministik seperti `ConfirmRisky` OpenHands atau `FsSandboxPolicy` Letta
— ia model-as-judge (*"background safety checks that verify actions align
with your request"*), yang menurut taksonomi §Bertingkat
`references/concepts/guardrails.md` adalah tingkat pemeriksaan **paling
mahal dan paling tidak deterministik**, dipakai di sini sebagai gate utama
mode paling longgar kedua — bukan lapisan pertama murah. `[docs]` + analisis
`[inferred]` dari perbandingan pola.

**Hooks** adalah mekanisme enforcement **deterministik** yang berbeda dari
permission mode: skrip eksternal (shell/PowerShell) menerima JSON di stdin
saat event `PreToolUse`/`PostToolUse`, mengembalikan
`{"hookSpecificOutput": {"permissionDecision": "deny"/...}}` untuk
memblokir tool call — kode di luar kendali model, persis definisi "policy
as data" yang diargumentasikan `references/concepts/policy-as-data.md`
(*"kalau sebuah aturan bisa diverifikasi kode, aturan itu tidak boleh hidup
di prompt"*). Dokumentasi resminya bahkan secara eksplisit merekomendasikan
hook sebagai fallback saat instruksi prosa gagal: *"If a skill seems to stop
influencing behavior after the first response... use hooks to enforce
behavior deterministically."* — pengakuan resmi Anthropic sendiri bahwa
routing berbasis deskripsi (sumbu 7) **tidak** deterministik dan hook adalah
jalan keluarnya untuk kasus yang butuh kepastian. `[docs]` —
`docs.claude.com/en/docs/claude-code/hooks.md` (contoh `block-rm.sh`/
`.ps1`, alur `PreToolUse` → matcher → `if` → handler → `permissionDecision`);
`docs.claude.com/en/docs/claude-code/skills.md` baris ~505 (kutipan
rekomendasi hook).

## 7. Capability routing & policy

**Prosa + judgment model murni — contoh kanonik KB ini untuk pola ini, dan
tempat kelemahannya paling terlihat konkret lewat angka nyata dari
dokumentasi resmi.**

Mekanisme: tiap skill (`SKILL.md`, format terbuka Agent Skills) punya field
`description` (dan opsional `when_to_use`) di frontmatter YAML. *"Claude
uses this to decide when to apply the skill... Put the key use case first:
the combined `description` and `when_to_use` text is truncated at **1,536
characters** in the skill listing to reduce context usage."* Ini
*progressive disclosure* yang sama polanya dengan `SkillsMiddleware`
`deepagents`: metadata (nama+deskripsi, dipangkas ke budget karakter tetap)
dimuat ke listing awal, isi lengkap `SKILL.md` baru dimuat penuh saat model
memilih memanggilnya. `[docs]` — `docs.claude.com/en/docs/claude-code/
skills.md` baris 323-324 (kutipan persis, termasuk angka 1.536).

**Kelemahan 1 — dilusi instruksi, dengan angka nyata**: budget listing
skill dibagi rata di antara semua skill yang termuat
(`skillListingBudgetFraction`, default sebagian kecil context; konfigurasi
alternatif: `SLASH_COMMAND_TOOL_CHAR_BUDGET`,
`skillListingMaxDescChars`). Makin banyak skill terpasang, makin sedikit
karakter deskripsi tersedia per skill sebelum terpotong — persis mekanisme
"aturan ke-47 melemahkan salience 1-46" yang diargumentasikan
`references/concepts/policy-as-data.md` §Masalah, hanya di sini bukan
metafora: ada angka karakter nyata yang dipotong (`skillListingMaxDescChars`,
default 1.536 gabungan `description`+`when_to_use`) dan mekanisme
konfigurasi eksplisit untuk *mengurangi* dilusi (menandai skill prioritas
rendah sebagai `"name-only"` di `skillOverrides` supaya skill lain dapat
lebih banyak budget). Bahwa fitur mitigasi ini **ada** membuktikan tim
Anthropic sendiri mengakui dilusi sebagai masalah nyata, bukan hipotetis.
`[docs]` — `docs.claude.com/en/docs/claude-code/skills.md` baris ~1041
(kutipan `skillListingBudgetFraction`, `skillOverrides`,
`skillListingMaxDescChars`).

**Kelemahan 2 — keterikatan bahasa**: tidak ada mekanisme kode netral
(`intents: [research.legal]`) yang ditemukan di dokumentasi Skills yang
dibaca — pencocokan `description` ke permintaan user berjalan murni lewat
model membaca teks deskripsi dalam bahasa apa pun deskripsi itu ditulis.
`references/concepts/skill-composition.md` §`intents` memakai kode netral
menjelaskan konsekuensinya: cakupan bahasa skill terikat pada seberapa
lengkap penulis `SKILL.md` menuliskan variasi frasa di tiap bahasa yang
didukung — menambah bahasa baru berarti menulis ulang/menambah frasa di
`description` tiap skill yang relevan, bukan memperluas satu classifier
terpusat. Claude Code tidak punya lapisan klasifikasi intent terpisah dari
pemilihan skill itu sendiri (routing = satu langkah: model baca deskripsi →
model putuskan) — persis mekanisme "native `SkillsMiddleware`" yang
dikontraskan `skill-composition.md` §Trade-off dengan pendekatan kode netral
KB ini. `[inferred]` — dari tidak ditemukannya mekanisme classifier/intent
terpisah di `skills.md`; `[docs]` untuk mekanisme dasarnya (description-only
routing).

**Kontras dengan sistem lain di grid**: OpenHands (`skills/trigger.py`,
lihat `openhands.md`) menaruh sebagian keputusan routing di kode
deterministik (`KeywordTrigger`/`PathTrigger`, dicocokkan lewat fungsi
`_keyword_matches`/`path_matches_glob`) — pemicu skill tidak 100% judgment
model. `deepagents` dan Letta (`letta.md`) sama-sama murni judgment model
seperti Claude Code. LiteLLM (`litellm.md`) tidak melakukan routing skill
sama sekali — routing-nya (model/deployment) sepenuhnya algoritmik lewat
`routing_strategy`. Claude Code, bersama `deepagents` dan Letta, adalah
titik ekstrem "serahkan semua ke judgment model" di spektrum sumbu 7 —
mudah diperluas (skill baru = tambah file, tidak ada taksonomi/registry
terpusat untuk dipelihara) tapi tidak bisa diuji deterministik dan rentan
dilusi begitu jumlah skill bertambah, persis trade-off yang dicatat
`skill-composition.md` §Trade-off. `[inferred]` — sintesis lintas file
grid ini, bukan klaim baru soal satu sistem.

## Sumber

Semua kutipan diambil `curl -sL` ke versi `.md` mentah dokumentasi resmi
(`docs.claude.com`), bukan lewat rendering HTML atau ringkasan pihak ketiga,
2026-08-23:

- `docs.claude.com/en/docs/claude-code/sub-agents.md` (1054+ baris terkait
  dibaca sebagian besar) — bagian "Built-in subagents" (tabel `Explore`/
  `Plan`/`general-purpose`/`Other`), "Quickstart: create your first
  subagent", kutipan *"Each subagent runs in its own context window..."*,
  *"The subagent summarizes its results..."*, *"Claude uses each
  subagent's description to decide..."*
- `docs.claude.com/en/docs/claude-code/skills.md` (1054 baris, dibaca
  sebagian besar) — baris 69-110 (quickstart, contoh frontmatter), baris
  133-165 (skill bertingkat direktori nested), baris 322-328 (tabel field
  frontmatter: `description`, `when_to_use`, `user-invocable`), baris
  458-511 (`disable-model-invocation`, `allowed-tools`, batas trust), baris
  501-505 (auto-compaction + skill, rekomendasi hook), baris 1041 (budget
  listing, `skillOverrides`, `skillListingMaxDescChars`)
- `docs.claude.com/en/docs/claude-code/permissions.md` (592 baris, dibaca
  sebagian besar) — baris 74-92 (tabel enam mode permission, warning
  `bypassPermissions`)
- `docs.claude.com/en/docs/claude-code/hooks.md` (3526 baris, dibaca
  sebagian: ~150 baris di sekitar contoh `PreToolUse`) — alur resolusi hook,
  contoh `block-rm.sh`/`.ps1`, format `hookSpecificOutput.permissionDecision`

Catatan kejujuran eksplisit (diulang dari pembuka file): **tidak ada file
source yang dibaca untuk sistem ini** — Claude Code closed-source. Semua
sembilan sumbu di atas berlabel `[docs]` (kutipan dokumentasi resmi
verbatim) atau `[inferred]` (simpulan eksplisit ditandai sebagai simpulan,
bukan dikutip seolah-olah fakta terverifikasi). Bagian dokumentasi yang
tidak dibaca (`agent-view`, `cross-session-messaging`, `agent-teams`,
`context-window` visualisasi, `permission-modes` halaman detail penuh,
`settings-reference` penuh) hanya dirujuk namanya lewat cross-link di
halaman yang dibaca, isinya **tidak** diverifikasi — tidak ada klaim dibuat
soal isi halaman-halaman itu.
