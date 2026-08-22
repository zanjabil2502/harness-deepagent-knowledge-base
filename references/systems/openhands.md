# OpenHands

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. Catatan penting soal identitas repo: nama `OpenHands` hari ini
menunjuk ke **dua** repo berbeda. `All-Hands-AI/OpenHands` (di-redirect ke
`OpenHands/OpenHands`) sudah berganti isi total menjadi **Agent Canvas** —
"self-hosted developer control center for coding agents and automations" yang
menjalankan OpenHands, Claude Code, Codex, atau agent ACP lain sebagai backend
terpilih; ini bukan lagi agent coding itu sendiri. `[code]` — `README.md` repo
`OpenHands/OpenHands` (dibaca via `git clone --depth 1`, 2026-08-23). Agent
coding aslinya (loop, tool, condenser, subagent, sandbox) sekarang hidup di
repo terpisah **`OpenHands/software-agent-sdk`** ("A clean, modular SDK for
building AI agents with OpenHands V1"), paket `openhands-sdk`,
`openhands-tools`, `openhands-workspace`, `openhands-agent-server`. File ini
mendokumentasikan **`software-agent-sdk`** karena itulah yang benar-benar
menjalankan tujuh sumbu di bawah — bukan Agent Canvas, yang hanya UI/orkestrasi
multi-backend di atasnya. `[code]` — struktur direktori `software-agent-sdk`
(`git clone --depth 1`, commit HEAD saat kloning 2026-08-23).

## Arketipe

**Workspace Agent (01)**, hibrida dengan elemen **Generative Builder (02)**
lewat `RemoteWorkspace`/Docker (state = 1 kontainer sandbox terisolasi, bisa
di-pause/resume). Blast radius menyentuh workspace/repo target (lokal atau
kontainer), artefak = edit kode + jawaban, kendali manusia diatur lewat
`ConfirmationPolicy` per-risk (lihat sumbu 6), antarmuka: SDK Python + CLI +
agent-server (headless, dipakai Agent Canvas sebagai salah satu backend).
`[code]` — `openhands-sdk/openhands/sdk/workspace/{local,base}.py`,
`openhands-workspace/openhands/workspace/docker/workspace.py`.

## 1. Loop shape

ReAct: `Agent.step()` (subclass `AgentBase`, wajib diimplementasi tiap agent)
mendokumentasikan sendiri urutan **"1. LLM call → 2. execute tool → 3. update
state → 4. kalau selesai set `execution_status = FINISHED`"**. `[code]` —
`openhands-sdk/openhands/sdk/agent/base.py` baris 630-648 (docstring `step`).

Loop luar ada di `LocalConversation.run()`: `while True: step(); if
execution_status in (FINISHED, PAUSED, ...): break`. Model yang memutuskan
berhenti secara normal — lewat `FinishTool` (tool built-in eksplisit, bukan
sekadar "tidak ada tool_calls lagi") — tapi harness memasang jaring pengaman
`max_iteration_per_run` (default **500**, jauh lebih ketat dari
`recursion_limit=9999` default `deepagents`): begitu iterasi mencapai batas
tanpa `FINISHED`, `run()` menghentikan loop dan set `execution_status =
ConversationExecutionStatus.ERROR`. `[code]` —
`openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py` baris
186, 218, 1902-2044; `openhands-sdk/openhands/sdk/tool/builtins/finish.py`
kelas `FinishTool`.

Ada juga jalur `StuckDetector` terpisah (`conversation/stuck_detector.py`,
14K) yang bisa memaksa `execution_status = STUCK` — deteksi oscillation/no-
progress independen dari batas iterasi. `[code]` (nama file & konstanta
dikonfirmasi, isi detail tidak dibaca penuh).

## 2. Context

`LLMSummarizingCondenser` (subclass `RollingCondenser`) — kompaksi berbasis
LLM terpisah dari LLM agen (`llm` attribute condenser bisa beda model dari
LLM utama, eksplisit untuk pemisahan biaya/kecepatan). Parameter kunci:
`max_size` (default 240 event), `keep_first` (default 2, event awal tidak
pernah dikondensasi), `minimum_progress` (default 0.1 — kondensasi ditolak
sebagai error kalau memaksa forget <10% event, mencegah kondensasi yang tidak
menghasilkan penghematan berarti). Dipicu oleh tiga `Reason`: `REQUEST`
(manual), `TOKENS` (ambang token), `EVENTS` (ambang jumlah event). `[code]` —
`openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py`
baris 1-60. Ada juga `NoOpCondenser` dan `PipelineCondenser` (mengompos
beberapa condenser) — `[code]` (nama file, isi tak dibaca penuh).

Tidak ditemukan pola filesystem-as-memory setara `deepagents` (tidak ada
backend yang meng-evict tool-result besar ke file secara otomatis) di modul
`context/` yang dibaca; memori antar-sesi ditangani lewat `skills/` (lihat
sumbu 7) dan bukan lapisan condenser. `[inferred]` — dari tidak ditemukannya
mekanisme setara di direktori `context/` dan `skills/` yang dibaca.

## 3. Tool surface

Sedikit tool luas dengan built-in eksplisit: `finish`, `think`, plus tool
kerja utama dari paket `openhands-tools` (mis. terminal/bash, editor file) —
`AgentBase.include_default_tools` memetakan nama built-in ke kelas lewat
`BUILT_IN_TOOL_CLASSES`. `[code]` —
`openhands-sdk/openhands/sdk/agent/base.py` baris 160-165, 602-603, 714-722.
Tool tambahan didaftarkan lewat parameter `tools=[Tool(name=...)]` saat
membangun `Agent` (lihat contoh `register_agent` di sumbu 4) — pola deklaratif
mirip `deepagents`, bukan tool generik tunggal seperti `execute` shell bebas
bentuk. `[code]` — `openhands-sdk/openhands/sdk/subagent/registry.py`
docstring modul.

## 4. Delegation

Ada mekanisme subagent eksplisit, bukan flat: `register_agent(name,
factory_func, description=...)` mendaftarkan `AgentFactory` (fungsi pembuat
`Agent` + `AgentDefinition`) ke registry global (`RLock`-protected). Definisi
subagent juga bisa dimuat dari file proyek/user lewat `load_project_agents` /
`load_user_agents` (analog `.claude/agents/*.md` atau `AGENTS.md`). `[code]` —
`openhands-sdk/openhands/sdk/subagent/registry.py` baris 1-60,
`openhands-sdk/openhands/sdk/subagent/load.py`, `subagent/schema.py`
(`AgentDefinition`). Karena tiap subagent adalah `Agent` penuh dengan tool
subset dan `agent_context` sendiri (lihat contoh `security_expert` di
docstring registry), pola hasil-kembali mengikuti kontrak `Agent`/`step()`
yang sama seperti agent utama — bukan diverifikasi lebih dalam di task ini
apakah subagent mengembalikan ringkasan atau transkrip penuh ke pemanggil.
`[code]`/`[inferred]` — struktur pendaftaran dikonfirmasi dari source,
mekanisme persis "hasil kembali ke pemanggil" tidak dibaca sampai ke titik
pemanggilan tool subagent di `tool/impl/`.

## 5. State & resume

`ConversationState` (31K, `conversation/state.py`) menyimpan `execution_status`
(`RUNNING`/`FINISHED`/`ERROR`/`STUCK`/`PAUSED`/...), `active_branch()` untuk
percabangan transkrip, dan daftar aksi belum dieksekusi (`get_unmatched_actions`
— dipakai jalur *confirmation mode*, lihat sumbu 6). `[code]` —
`openhands-sdk/openhands/sdk/conversation/state.py`,
`openhands-sdk/openhands/sdk/agent/agent.py` baris 645-651 (pemakaian
`get_unmatched_actions` di `step()`). `run()` bisa dipanggil ulang untuk
resume dari `execution_status='idle'`, dan `max_iteration_per_run` diteruskan
lagi setiap resume — bukan akumulasi lintas sesi. `[code]` —
`local_conversation.py` baris 770-810, 833.

Sandbox Docker (`DockerWorkspace`, paket `openhands-workspace`) mendukung
`pause`/`resume` kontainer via `docker pause`/`docker unpause` — state proses
sandbox bisa dibekukan tanpa membunuhnya, terpisah dari checkpoint
percakapan. `[code]` —
`openhands-workspace/openhands/workspace/docker/workspace.py` baris 401-428.

## 6. Safety gate

`ConfirmationPolicyBase` (subclass `DiscriminatedUnionMixin`) dengan tiga
implementasi konkret: `AlwaysConfirm`, `NeverConfirm`, `ConfirmRisky`
(`threshold: SecurityRisk = HIGH` default, `confirm_unknown: bool = True`
default — risiko `UNKNOWN` **fail-closed**, minta konfirmasi kecuali
eksplisit dimatikan). `should_confirm(risk)` dipakai *sebelum* eksekusi aksi;
kalau ada aksi pending yang belum dikonfirmasi, `step()` mengeksekusinya di
awal giliran berikutnya (`_execute_actions`) alih-alih memanggil LLM lagi —
pola "jeda-lalu-lanjut" seperti `interrupt_on` di `deepagents`. `[code]` —
`openhands-sdk/openhands/sdk/security/confirmation_policy.py` (utuh),
`openhands-sdk/openhands/sdk/agent/agent.py` baris 645-651.

Level risiko datang dari `security/risk.py` (`SecurityRisk` enum) dan
dievaluasi lewat analyzer tersendiri — ada `LLMAnalyzer`, `ensemble.py`
(gabungan beberapa analyzer), dan modul `_shell_ast.py`/`shell_parser.py`/
`shell_semantics.py` yang mem-parse **AST shell command** untuk menilai risiko
command sebelum eksekusi (bukan sekadar regex string). `[code]` — daftar file
`openhands-sdk/openhands/sdk/security/*.py` (isi parser tidak dibaca detail).

Sandbox: `LocalWorkspace` (proses host langsung) vs `DockerWorkspace`/
`RemoteWorkspace` (kontainer `ghcr.io/openhands/agent-server:latest`,
dijalankan via `docker run` dari `execute_command`, di-track lewat
`_container_id`, bisa `docker stop`/`pause`/`unpause`). `[code]` —
`openhands-workspace/openhands/workspace/docker/workspace.py` baris 65,
263-264, 331-428.

**Ketidaksesuaian dengan `references/concepts/sandboxing.md` dan
`resource-profiling.md`**: kedua file itu mengutip OpenHands lewat path
`openhands/core/config/sandbox_config.py` dan
`openhands/runtime/impl/docker/docker_runtime.py` (soal `memory_limit` opsional
dipetakan ke `mem_limit` Docker), disumberkan dari PR
`All-Hands-AI/OpenHands#6616` dan commit `db37f350` — keduanya pinned ke
snapshot historis repo Python lama. Path itu **tidak ditemukan** di kedua
repo yang dibaca task ini (`OpenHands/OpenHands` maupun
`OpenHands/software-agent-sdk`, dicek lewat `find -iname
sandbox_config.py -o -iname docker_runtime.py`, 2026-08-23) — konsisten
dengan pivot arsitektur besar yang dibahas di `## Arketipe` di atas. Klaim
`memory_limit`/`mem_limit` di kedua concept file itu kemungkinan besar masih
akurat untuk commit yang mereka kutip, tapi tidak terverifikasi lagi di
repo saat ini; file ini tidak mengklaim ulang atau membantahnya, hanya
mencatat repo sudah berpindah struktur sejak commit itu disitir.
`[code]` (hasil pencarian file, negatif) + catatan silang, bukan koreksi.

## 7. Capability routing & policy

**Manifest deklaratif + match deterministik di kode — bukan classifier ML,
bukan murni prosa + judgment model.** Modul `skills/trigger.py` mendefinisikan
tiga tipe trigger sebagai `pydantic.BaseModel` berbeda:

- `KeywordTrigger(keywords: list[str])` — aktif kalau keyword muncul di pesan
  user.
- `TaskTrigger(triggers: list[str])` — aktif untuk tipe task tertentu, bisa
  memodifikasi prompt.
- `PathTrigger(paths: list[str])` — aktif ("rules") kalau agent menyentuh file
  yang cocok glob gitignore-style (`**`).

`[code]` — `openhands-sdk/openhands/sdk/skills/trigger.py` (utuh).

Pencocokan trigger dilakukan **di kode**, bukan diserahkan ke judgment model:
`skills/skill.py` punya fungsi `_keyword_matches(keyword, message_lower)` dan
`path_matches_glob(file_path, pattern)`, dipanggil dari method
`match_trigger(message)` dan `match_path_trigger(file_path)` pada objek skill.
`[code]` — `openhands-sdk/openhands/sdk/skills/skill.py` baris 87, 164,
732-758. Ini kontras eksplisit dengan pola `SkillsMiddleware` di `deepagents`
dan `claude-code.md` (lihat file itu) yang menyerahkan pemilihan skill 100%
ke judgment model atas deskripsi — OpenHands menaruh sebagian keputusan
routing di kode deterministik (keyword/path match), baru **isi** skill yang
match yang disuntik ke prompt/context untuk dipakai model. Ini pola yang
`references/concepts/policy-as-data.md` argumentasikan sebagai lebih dapat
diverifikasi dibanding "prosa sebagai aturan" murni — lihat file itu untuk
argumen lengkapnya.

Delegasi ke subagent (sumbu 4) tetap **judgment model**: pemanggil (agent
utama) memilih subagent mana yang dipanggil berdasar `description` di
`AgentDefinition`, tidak ada classifier terpisah yang terlihat di source yang
dibaca. `[inferred]` — dari tidak ditemukannya modul classifier di
`subagent/`.

## Sumber

Repo dikloning shallow (`git clone --depth 1`) 2026-08-23 ke lingkungan lokal
dan dibaca langsung sebagai file, bukan lewat ringkasan:

- `OpenHands/OpenHands` (`github.com/OpenHands/OpenHands`, redirect dari
  `All-Hands-AI/OpenHands`) — `README.md` saja, untuk mengonfirmasi pivot
  identitas ke Agent Canvas. `[code]`
- `OpenHands/software-agent-sdk` (`github.com/OpenHands/software-agent-sdk`)
  — file `[code]` yang dibaca:
  - `openhands-sdk/openhands/sdk/agent/base.py` (docstring `step`, method
    `verify`)
  - `openhands-sdk/openhands/sdk/agent/agent.py` baris 637-720 (`Agent.step`)
  - `openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py`
    baris 180-270, 700-780, 1900-2050 (`run()`, `max_iteration_per_run`,
    `execution_status`)
  - `openhands-sdk/openhands/sdk/conversation/state.py` (nama kelas, method
    `get_unmatched_actions`/`active_branch` via grep)
  - `openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py`
    baris 1-90
  - `openhands-sdk/openhands/sdk/tool/builtins/finish.py` (kelas `FinishTool`)
  - `openhands-sdk/openhands/sdk/subagent/registry.py` (utuh, ~60 baris awal
    + docstring), `subagent/load.py`, `subagent/schema.py` (nama & tipe via
    listing)
  - `openhands-sdk/openhands/sdk/security/confirmation_policy.py` (utuh)
  - `openhands-sdk/openhands/sdk/skills/trigger.py` (utuh),
    `openhands-sdk/openhands/sdk/skills/skill.py` baris 87, 159-215,
    550-760
  - `openhands-workspace/openhands/workspace/docker/workspace.py` baris
    1-70, 260-430
  - `openhands-sdk/openhands/sdk/workspace/{base,local}.py` (nama kelas via
    grep)
- Verifikasi identitas org via GitHub API
  `api.github.com/orgs/OpenHands/repos` untuk menemukan `software-agent-sdk`
  sebagai lokasi baru core agent — dikutip untuk menjelaskan alasan file ini
  tidak memakai repo `OpenHands/OpenHands`.

Catatan kejujuran: modul `security/_shell_ast.py`, `shell_parser.py`,
`shell_semantics.py`, `ensemble.py`, `llm_analyzer.py`, `toolshield_*.py`,
dan `critic/`, `mcp/`, `marketplace/`, `hooks/` terdaftar lewat listing
direktori tapi **isinya tidak dibaca** — tidak diklaim apa pun tentang cara
kerja detailnya di file ini.
